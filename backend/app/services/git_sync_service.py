"""
Git 同步服务

处理 Git 仓库的导入、镜像、同步等操作
"""
import asyncio
import hashlib
import json
import os
import shutil
import socket
import ipaddress
from datetime import datetime, UTC
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import git
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.encryption import get_encryption_service
from app.core.exceptions import (
    GitOperationError,
    GitRepoNotFoundError,
    GitSyncError,
    SSRFError,
    EncryptionError,
)
from app.db.models import (
    GitRepo,
    Skill,
    SkillFile,
    SkillSourceType,
    SkillVersion,
    TimelineEvent,
    TimelineEventType,
    User,
)
from app.auth.permissions import PermissionService, PermissionAction
from app.services.skill_service import SkillService


class GitSyncService:
    """
    Git 同步服务
    
    事务边界管理说明：
    ====================
    本服务采用统一的事务管理策略，确保数据一致性：
    
    1. 主事务边界（sync_repo 方法）：
       - 所有同步相关的数据库操作都在单个事务中执行
       - 包括：状态更新、Skill 创建/更新、文件扫描、版本创建
       - 任何步骤失败都会回滚所有更改
       - 失败状态更新在独立的补救事务中执行
    
    2. 辅助方法事务策略：
       - _create_git_skill: 不提交事务，使用 flush() 获取 ID
       - _update_git_skill: 不提交事务，使用 flush() 刷新更改
       - _scan_skill_files: 不提交事务，由调用方统一管理
       - _create_version: 不提交事务，使用 flush() 获取 ID
    
    3. 事务一致性保证：
       - 使用 session.flush() 在不提交的情况下获取自增 ID
       - 使用 session.rollback() 在异常时回滚所有更改
       - 失败状态更新使用独立事务，避免影响主事务回滚
    
    4. 注意事项：
       - 不要在辅助方法中调用 commit()
       - 需要获取 ID 时使用 flush() 而非 commit()
       - 异常处理中先 rollback() 再更新失败状态
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.settings = get_settings()
        self.permission_service = PermissionService(session)
        self.skill_service = SkillService(session)
        self.encryption_service = get_encryption_service()

    async def import_repo(
        self,
        name: str,
        url: str,
        user: User,
        branch: str = "main",
        auth_type: Optional[str] = None,
        auth_secret_ref: Optional[str] = None,
    ) -> GitRepo:
        """
        导入 Git 仓库
        
        Args:
            name: 仓库名称
            url: Git 仓库 URL
            user: 当前用户
            branch: 分支名称
            auth_type: 认证类型（如 'token', 'ssh_key'）
            auth_secret_ref: 认证密钥引用（将被加密存储）
            
        Returns:
            GitRepo: 创建的仓库对象
            
        Raises:
            GitOperationError: 仓库已存在或操作失败
            EncryptionError: 加密失败
        """
        # 验证 URL 安全性
        await self._validate_git_url(url)
        
        # 检查名称是否已存在
        result = await self.session.execute(
            select(GitRepo).where(GitRepo.name == name)
        )
        if result.scalar_one_or_none():
            raise GitOperationError("import", f"仓库名称已存在: {name}")
        
        # 加密认证信息（如果提供）
        encrypted_auth_secret = None
        if auth_secret_ref:
            try:
                encrypted_auth_secret = self.encryption_service.encrypt(auth_secret_ref)
            except EncryptionError as e:
                raise GitOperationError(
                    "import",
                    f"认证信息加密失败: {str(e)}"
                )
        
        # 创建镜像目录
        mirror_path = self.settings.mirrors_path / name
        mirror_path.mkdir(parents=True, exist_ok=True)
        
        # 创建仓库记录
        repo = GitRepo(
            name=name,
            url=url,
            branch=branch,
            auth_type=auth_type,
            auth_secret_ref=encrypted_auth_secret,  # 存储加密后的认证信息
            mirror_path=str(mirror_path),
            sync_status="pending",
            created_by=user.id,
        )
        
        self.session.add(repo)
        await self.session.commit()
        await self.session.refresh(repo)
        
        # 分配所有者角色
        await self.permission_service.assign_resource_role(
            user.id, "repo", repo.id, "owner"
        )
        
        # 执行初始同步
        try:
            await self.sync_repo(repo.id, user)
        except Exception as e:
            # 同步失败不阻止导入
            repo.sync_status = "failed"
            repo.sync_error = str(e)
            await self.session.commit()
        
        return repo

    async def sync_repo(
        self,
        repo_id: str,
        user: Optional[User] = None,
    ) -> dict:
        """
        同步 Git 仓库
        
        事务边界说明：
        - 整个同步过程在一个事务中执行
        - 包括：状态更新、Skill 扫描、文件更新、版本创建
        - 任何步骤失败都会回滚所有数据库更改
        - 失败状态更新在独立事务中执行
        """
        result = await self.session.execute(
            select(GitRepo).where(GitRepo.id == repo_id)
        )
        repo = result.scalar_one_or_none()
        
        if not repo:
            raise GitRepoNotFoundError(repo_id)
        
        # 更新同步状态为 syncing（在事务内，不立即提交）
        repo.sync_status = "syncing"
        repo.sync_error = None
        
        try:
            mirror_path = Path(repo.mirror_path)
            
            # 解密认证信息（如果存在）
            auth_secret = None
            if repo.auth_secret_ref:
                try:
                    auth_secret = self.encryption_service.decrypt(repo.auth_secret_ref)
                except EncryptionError as e:
                    raise GitSyncError(
                        repo.url,
                        f"认证信息解密失败: {str(e)}"
                    )
            
            # 克隆或拉取（使用认证信息）
            if not (mirror_path / ".git").exists():
                # 首次克隆
                clone_url = self._build_authenticated_url(repo.url, auth_secret, repo.auth_type)
                git.Repo.clone_from(
                    clone_url,
                    str(mirror_path),
                    branch=repo.branch,
                    depth=1,
                )
            else:
                # 拉取更新
                git_repo = git.Repo(str(mirror_path))
                origin = git_repo.remotes.origin
                
                # 如果有认证信息，更新远程 URL
                if auth_secret:
                    authenticated_url = self._build_authenticated_url(repo.url, auth_secret, repo.auth_type)
                    origin.set_url(authenticated_url)
                
                origin.fetch()
                git_repo.git.reset("--hard", f"origin/{repo.branch}")
            
            # 获取最新 commit
            git_repo = git.Repo(str(mirror_path))
            latest_commit = git_repo.head.commit.hexsha
            
            # 检查是否有更新
            if repo.last_sync_commit == latest_commit:
                # 无更新，设置成功状态并提交
                repo.sync_status = "success"
                repo.last_sync_at = datetime.now(UTC)
                await self.session.commit()
                return {"status": "no_changes", "commit": latest_commit}
            
            # 扫描 Skill 目录（所有数据库操作在同一事务中）
            skills_created, skills_updated = await self._scan_skills(repo, user)
            
            # 更新同步状态为成功
            repo.last_sync_commit = latest_commit
            repo.last_sync_at = datetime.now(UTC)
            repo.sync_status = "success"
            
            # 统一提交所有更改
            await self.session.commit()
            
            return {
                "status": "success",
                "commit": latest_commit,
                "skills_created": skills_created,
                "skills_updated": skills_updated,
            }
            
        except Exception as e:
            # 回滚当前事务中的所有更改
            await self.session.rollback()
            
            # 在新事务中更新失败状态
            repo.sync_status = "failed"
            repo.sync_error = str(e)
            await self.session.commit()
            
            raise GitSyncError(repo.url, str(e))

    async def delete_repo(
        self,
        repo_id: str,
        user: User,
    ) -> bool:
        """删除 Git 仓库"""
        result = await self.session.execute(
            select(GitRepo).where(GitRepo.id == repo_id)
        )
        repo = result.scalar_one_or_none()
        
        if not repo:
            raise GitRepoNotFoundError(repo_id)
        
        # 检查权限
        await self.permission_service.check_repo_permission(
            user, repo_id, PermissionAction.DELETE
        )
        
        # 删除关联的 Skills
        result = await self.session.execute(
            select(Skill).where(Skill.git_repo_id == repo_id)
        )
        for skill in result.scalars().all():
            skill.is_active = False
        
        # 删除镜像目录
        mirror_path = Path(repo.mirror_path)
        if mirror_path.exists():
            shutil.rmtree(mirror_path)
        
        # 标记为已删除
        repo.is_active = False
        await self.session.commit()
        
        return True

    async def list_repos(
        self,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[GitRepo], int]:
        """列出 Git 仓库"""
        query = select(GitRepo).where(GitRepo.is_active == True)
        
        # 计算总数
        count_result = await self.session.execute(
            select(GitRepo).where(GitRepo.is_active == True)
        )
        total = len(count_result.scalars().all())
        
        # 分页
        query = query.offset((page - 1) * page_size).limit(page_size)
        query = query.order_by(GitRepo.updated_at.desc())
        
        result = await self.session.execute(query)
        repos = list(result.scalars().all())
        
        return repos, total

    async def get_repo(self, repo_id: str) -> Optional[GitRepo]:
        """获取仓库详情"""
        result = await self.session.execute(
            select(GitRepo).where(GitRepo.id == repo_id)
        )
        return result.scalar_one_or_none()

    async def sync_all_repos(self) -> dict:
        """同步所有仓库"""
        result = await self.session.execute(
            select(GitRepo).where(
                and_(GitRepo.is_active == True, GitRepo.auto_sync == True)
            )
        )
        repos = result.scalars().all()
        
        results = {
            "success": [],
            "failed": [],
        }
        
        for repo in repos:
            try:
                await self.sync_repo(repo.id)
                results["success"].append(repo.name)
            except Exception as e:
                results["failed"].append({
                    "name": repo.name,
                    "error": str(e),
                })
        
        return results

    # ==================== 私有方法 ====================

    def _build_authenticated_url(
        self,
        url: str,
        auth_secret: Optional[str],
        auth_type: Optional[str],
    ) -> str:
        """
        构建带认证信息的 Git URL
        
        Args:
            url: 原始 Git URL
            auth_secret: 认证密钥（token 或密码）
            auth_type: 认证类型（'token', 'password', 'ssh_key'）
            
        Returns:
            str: 带认证信息的 URL
            
        Example:
            >>> url = _build_authenticated_url(
            ...     "https://github.com/user/repo.git",
            ...     "my-token",
            ...     "token"
            ... )
            >>> # 返回: "https://my-token@github.com/user/repo.git"
        """
        if not auth_secret or not auth_type:
            return url
        
        parsed = urlparse(url)
        
        # 根据认证类型构建 URL
        if auth_type == "token" or auth_type == "password":
            # HTTPS 认证：在 URL 中添加用户名和密码/token
            # 格式：https://token@github.com/user/repo.git
            # 或：https://username:password@github.com/user/repo.git
            if parsed.username:
                # 如果 URL 中已有用户名，替换密码部分
                auth_url = f"{parsed.scheme}://{parsed.username}:{auth_secret}@{parsed.hostname}"
            else:
                # 如果没有用户名，使用 token 作为用户名（GitHub 风格）
                auth_url = f"{parsed.scheme}://{auth_secret}@{parsed.hostname}"
            
            # 添加端口（如果有）
            if parsed.port:
                auth_url += f":{parsed.port}"
            
            # 添加路径
            auth_url += parsed.path
            
            return auth_url
        
        # SSH 密钥认证不需要修改 URL，通过 SSH 配置文件处理
        elif auth_type == "ssh_key":
            return url
        
        return url

    async def _validate_git_url(self, url: str) -> bool:
        """验证 Git URL 安全性"""
        parsed = urlparse(url)
        
        # 检查协议
        allowed_schemes = ["https", "git", "ssh"]
        if parsed.scheme not in allowed_schemes:
            raise SSRFError(url, f"不允许的协议: {parsed.scheme}")
        
        # 检查域名白名单
        if parsed.hostname not in self.settings.git_allowed_domains:
            raise SSRFError(url, f"域名不在白名单中: {parsed.hostname}")
        
        # 解析 IP 并检查
        try:
            ip = socket.gethostbyname(parsed.hostname)
            ip_obj = ipaddress.ip_address(ip)
            
            # 检查是否为私有 IP
            for blocked_range in self.settings.git_blocked_ip_ranges:
                if ip_obj in ipaddress.ip_network(blocked_range):
                    raise SSRFError(url, f"禁止访问私有 IP: {ip}")
                    
        except socket.gaierror:
            raise SSRFError(url, f"无法解析域名: {parsed.hostname}")
        
        return True

    async def _scan_skills(
        self,
        repo: GitRepo,
        user: Optional[User] = None,
    ) -> tuple[int, int]:
        """
        扫描仓库中的 Skill 目录
        
        事务边界说明：
        - 此方法不执行 commit，由调用方统一管理事务
        - 所有数据库操作在同一事务中执行
        """
        mirror_path = Path(repo.mirror_path)
        skills_created = 0
        skills_updated = 0
        
        # 查找所有包含 SKILL.md 的目录
        for skill_md in mirror_path.rglob("SKILL.md"):
            skill_dir = skill_md.parent
            skill_name = f"{repo.name}/{skill_dir.relative_to(mirror_path)}"
            
            # 检查是否已存在
            result = await self.session.execute(
                select(Skill).where(Skill.name == skill_name)
            )
            existing_skill = result.scalar_one_or_none()
            
            if existing_skill:
                # 更新
                await self._update_git_skill(existing_skill, skill_dir, user)
                skills_updated += 1
            else:
                # 创建
                await self._create_git_skill(repo, skill_dir, skill_name, user)
                skills_created += 1
        
        return skills_created, skills_updated

    async def _create_git_skill(
        self,
        repo: GitRepo,
        skill_dir: Path,
        skill_name: str,
        user: Optional[User] = None,
    ) -> Skill:
        """
        创建 Git 来源的 Skill
        
        事务边界说明：
        - 此方法不执行 commit，由调用方统一管理事务
        - 所有数据库操作在同一事务中执行
        """
        # 解析 SKILL.md
        metadata = await self._parse_skill_md(skill_dir / "SKILL.md")
        
        skill = Skill(
            name=skill_name,
            source_type=SkillSourceType.GIT,
            git_repo_id=repo.id,
            storage_path=str(skill_dir),
            title=metadata.get("title", skill_name),
            summary=metadata.get("summary"),
            tags=json.dumps(metadata.get("tags", []), ensure_ascii=False),
            created_by=user.id if user else None,
        )
        
        self.session.add(skill)
        # 刷新以获取 ID，但不提交事务
        await self.session.flush()
        await self.session.refresh(skill)
        
        # 扫描文件
        await self._scan_skill_files(skill, skill_dir)
        
        # 创建初始版本
        await self._create_version(skill, user, "Git 同步创建")
        
        return skill

    async def _update_git_skill(
        self,
        skill: Skill,
        skill_dir: Path,
        user: Optional[User] = None,
    ) -> Skill:
        """
        更新 Git 来源的 Skill
        
        事务边界说明：
        - 此方法不执行 commit，由调用方统一管理事务
        - 所有数据库操作在同一事务中执行
        """
        # 解析 SKILL.md
        metadata = await self._parse_skill_md(skill_dir / "SKILL.md")
        
        skill.title = metadata.get("title", skill.title)
        skill.summary = metadata.get("summary", skill.summary)
        skill.tags = json.dumps(metadata.get("tags", []), ensure_ascii=False)
        skill.updated_at = datetime.now(UTC)
        
        # 刷新更改，但不提交事务
        await self.session.flush()
        await self.session.refresh(skill)
        
        # 扫描文件
        await self._scan_skill_files(skill, skill_dir)
        
        # 创建新版本
        await self._create_version(skill, user, "Git 同步更新")
        
        return skill

    async def _parse_skill_md(self, skill_md_path: Path) -> dict:
        """解析 SKILL.md 文件"""
        import frontmatter
        
        with open(skill_md_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        try:
            post = frontmatter.loads(content)
            metadata = dict(post.metadata)
            
            if "name" in metadata:
                metadata["title"] = metadata["name"]
            
            return metadata
            
        except Exception:
            return {}

    async def _scan_skill_files(self, skill: Skill, skill_dir: Path) -> None:
        """
        扫描 Skill 文件
        
        事务边界说明：
        - 此方法不执行 commit，由调用方统一管理事务
        - 所有数据库操作在同一事务中执行
        """
        # 删除旧记录
        result = await self.session.execute(
            select(SkillFile).where(SkillFile.skill_id == skill.id)
        )
        for old_file in result.scalars().all():
            await self.session.delete(old_file)
        
        # 扫描新文件
        for file_path in skill_dir.rglob("*"):
            if file_path.is_file():
                rel_path = file_path.relative_to(skill_dir)
                
                # 计算文件哈希
                with open(file_path, "rb") as f:
                    content = f.read()
                    checksum = hashlib.sha256(content).hexdigest()
                
                # 确定文件类型
                ext = file_path.suffix.lower()
                mime_type = self._get_mime_type(ext)
                
                skill_file = SkillFile(
                    skill_id=skill.id,
                    file_path=str(rel_path),
                    file_name=file_path.name,
                    file_size=file_path.stat().st_size,
                    file_type=mime_type,
                    checksum=checksum,
                    is_skill_md=file_path.name.upper() == "SKILL.MD",
                )
                
                self.session.add(skill_file)
        
        # 不提交事务，由调用方统一管理

    def _get_mime_type(self, ext: str) -> str:
        """获取 MIME 类型"""
        mime_map = {
            ".md": "text/markdown",
            ".txt": "text/plain",
            ".json": "application/json",
            ".yaml": "application/x-yaml",
            ".yml": "application/x-yaml",
            ".html": "text/html",
            ".css": "text/css",
            ".js": "text/javascript",
            ".py": "text/x-python",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".gif": "image/gif",
            ".svg": "image/svg+xml",
        }
        return mime_map.get(ext, "application/octet-stream")

    async def _create_version(
        self,
        skill: Skill,
        user: Optional[User],
        change_summary: str,
    ) -> SkillVersion:
        """
        创建版本
        
        事务边界说明：
        - 此方法不执行 commit，由调用方统一管理事务
        - 所有数据库操作在同一事务中执行
        """
        result = await self.session.execute(
            select(SkillVersion)
            .where(SkillVersion.skill_id == skill.id)
            .order_by(SkillVersion.version_number.desc())
            .limit(1)
        )
        last_version = result.scalar_one_or_none()
        version_number = (last_version.version_number + 1) if last_version else 1
        
        # 计算内容哈希
        version_hash = await self._calculate_skill_hash(skill)
        
        version = SkillVersion(
            skill_id=skill.id,
            version_number=version_number,
            version_hash=version_hash,
            change_summary=change_summary,
            snapshot_path=skill.storage_path,
            created_by=user.id if user else None,
        )
        
        self.session.add(version)
        # 刷新以获取 ID，但不提交事务
        await self.session.flush()
        
        return version

    async def _calculate_skill_hash(self, skill: Skill) -> str:
        """计算 Skill 内容哈希"""
        storage_path = Path(skill.storage_path)
        hasher = hashlib.sha256()
        
        for file_path in sorted(storage_path.rglob("*")):
            if file_path.is_file():
                with open(file_path, "rb") as f:
                    content = f.read()
                    hasher.update(file_path.name.encode())
                    hasher.update(content)
        
        return hasher.hexdigest()
