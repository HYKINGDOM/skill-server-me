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
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import git
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import (
    GitOperationError,
    GitRepoNotFoundError,
    GitSyncError,
    SSRFError,
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
    """Git 同步服务"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.settings = get_settings()
        self.permission_service = PermissionService(session)
        self.skill_service = SkillService(session)

    async def import_repo(
        self,
        name: str,
        url: str,
        user: User,
        branch: str = "main",
        auth_type: Optional[str] = None,
        auth_secret_ref: Optional[str] = None,
    ) -> GitRepo:
        """导入 Git 仓库"""
        # 验证 URL 安全性
        await self._validate_git_url(url)
        
        # 检查名称是否已存在
        result = await self.session.execute(
            select(GitRepo).where(GitRepo.name == name)
        )
        if result.scalar_one_or_none():
            raise GitOperationError("import", f"仓库名称已存在: {name}")
        
        # 创建镜像目录
        mirror_path = self.settings.mirrors_path / name
        mirror_path.mkdir(parents=True, exist_ok=True)
        
        # 创建仓库记录
        repo = GitRepo(
            name=name,
            url=url,
            branch=branch,
            auth_type=auth_type,
            auth_secret_ref=auth_secret_ref,
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
        """同步 Git 仓库"""
        result = await self.session.execute(
            select(GitRepo).where(GitRepo.id == repo_id)
        )
        repo = result.scalar_one_or_none()
        
        if not repo:
            raise GitRepoNotFoundError(repo_id)
        
        # 更新同步状态
        repo.sync_status = "syncing"
        repo.sync_error = None
        await self.session.commit()
        
        try:
            mirror_path = Path(repo.mirror_path)
            
            # 克隆或拉取
            if not (mirror_path / ".git").exists():
                # 首次克隆
                git.Repo.clone_from(
                    repo.url,
                    str(mirror_path),
                    branch=repo.branch,
                    depth=1,
                )
            else:
                # 拉取更新
                git_repo = git.Repo(str(mirror_path))
                origin = git_repo.remotes.origin
                origin.fetch()
                git_repo.git.reset("--hard", f"origin/{repo.branch}")
            
            # 获取最新 commit
            git_repo = git.Repo(str(mirror_path))
            latest_commit = git_repo.head.commit.hexsha
            
            # 检查是否有更新
            if repo.last_sync_commit == latest_commit:
                repo.sync_status = "success"
                repo.last_sync_at = datetime.utcnow()
                await self.session.commit()
                return {"status": "no_changes", "commit": latest_commit}
            
            # 扫描 Skill 目录
            skills_created, skills_updated = await self._scan_skills(repo, user)
            
            # 更新同步状态
            repo.last_sync_commit = latest_commit
            repo.last_sync_at = datetime.utcnow()
            repo.sync_status = "success"
            await self.session.commit()
            
            return {
                "status": "success",
                "commit": latest_commit,
                "skills_created": skills_created,
                "skills_updated": skills_updated,
            }
            
        except Exception as e:
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
        """扫描仓库中的 Skill 目录"""
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
        """创建 Git 来源的 Skill"""
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
        await self.session.commit()
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
        """更新 Git 来源的 Skill"""
        # 解析 SKILL.md
        metadata = await self._parse_skill_md(skill_dir / "SKILL.md")
        
        skill.title = metadata.get("title", skill.title)
        skill.summary = metadata.get("summary", skill.summary)
        skill.tags = json.dumps(metadata.get("tags", []), ensure_ascii=False)
        skill.updated_at = datetime.utcnow()
        
        await self.session.commit()
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
        """扫描 Skill 文件"""
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
        
        await self.session.commit()

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
        """创建版本"""
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
        await self.session.commit()
        
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
