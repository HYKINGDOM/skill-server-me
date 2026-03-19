"""
Skill 管理服务

处理 Skill 的上传、创建、编辑、删除等操作
"""
import hashlib
import json
import os
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiofiles
import frontmatter
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import (
    ResourceNotFoundError,
    SkillLockError,
    SkillNotFoundError,
    SkillValidationError,
    UploadError,
    ZipExtractionError,
)
from app.db.models import (
    Skill,
    SkillFile,
    SkillSourceType,
    SkillVersion,
    TimelineEvent,
    TimelineEventType,
    User,
)
from app.auth.permissions import PermissionService, PermissionAction


# 允许的文件扩展名
ALLOWED_TEXT_EXTENSIONS = {
    ".md", ".txt", ".json", ".yaml", ".yml", ".xml", ".html", ".css",
    ".js", ".ts", ".py", ".java", ".go", ".rs", ".c", ".cpp", ".h",
    ".sh", ".sql", ".conf", ".ini", ".env.example",
}

ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico"}

ALLOWED_DOC_EXTENSIONS = {".pdf", ".doc", ".docx"}

FORBIDDEN_EXTENSIONS = {
    ".exe", ".bat", ".cmd", ".ps1", ".vbs", ".jar", ".war",
    ".dll", ".so", ".dylib", ".app", ".dmg", ".pkg",
}


class SkillService:
    """Skill 管理服务"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.settings = get_settings()
        self.permission_service = PermissionService(session)

    async def create_skill(
        self,
        name: str,
        user: User,
        skill_md_content: Optional[str] = None,
    ) -> Skill:
        """创建新的私有 Skill"""
        # 验证名称
        if not self._validate_skill_name(name):
            raise SkillValidationError(f"无效的 Skill 名称: {name}")
        
        # 检查是否已存在
        existing = await self._get_skill_by_name(name)
        if existing:
            raise SkillValidationError(f"Skill 名称已存在: {name}")
        
        # 创建存储目录
        storage_path = self.settings.private_skills_path / name
        storage_path.mkdir(parents=True, exist_ok=True)
        
        # 创建 SKILL.md
        skill_md_path = storage_path / "SKILL.md"
        if skill_md_content:
            async with aiofiles.open(skill_md_path, "w", encoding="utf-8") as f:
                await f.write(skill_md_content)
        else:
            default_content = f"""---
name: {name}
tags: []
summary: 请填写 Skill 摘要
---

# {name}

## 用途

请描述 Skill 的用途。

## 参数

请列出 Skill 的参数。

## 使用方式

请说明如何使用此 Skill。

## 示例

请提供使用示例。
"""
            async with aiofiles.open(skill_md_path, "w", encoding="utf-8") as f:
                await f.write(default_content)
        
        # 解析 SKILL.md
        metadata = await self._parse_skill_md(skill_md_path)
        
        # 创建 Skill 记录
        skill = Skill(
            name=name,
            source_type=SkillSourceType.PRIVATE,
            storage_path=str(storage_path),
            title=metadata.get("title", name),
            summary=metadata.get("summary"),
            tags=json.dumps(metadata.get("tags", []), ensure_ascii=False),
            created_by=user.id,
        )
        
        self.session.add(skill)
        await self.session.commit()
        await self.session.refresh(skill)
        
        # 创建初始版本
        await self._create_version(skill, user, "初始创建")
        
        # 创建 SkillFile 记录
        await self._scan_skill_files(skill)
        
        # 分配所有者角色
        await self.permission_service.assign_resource_role(
            user.id, "skill", skill.id, "owner"
        )
        
        # 记录时间线
        await self._add_timeline_event(
            skill, TimelineEventType.SKILL_CREATED, user
        )
        
        return skill

    async def upload_skill(
        self,
        name: str,
        user: User,
        zip_file_path: Path,
    ) -> Skill:
        """上传 ZIP 包创建 Skill"""
        # 验证名称
        if not self._validate_skill_name(name):
            raise SkillValidationError(f"无效的 Skill 名称: {name}")
        
        # 检查是否已存在
        existing = await self._get_skill_by_name(name)
        if existing:
            raise SkillValidationError(f"Skill 名称已存在: {name}")
        
        # 创建存储目录
        storage_path = self.settings.private_skills_path / name
        
        # 安全解压
        await self._safe_extract_zip(zip_file_path, storage_path)
        
        # 检查 SKILL.md 是否存在
        skill_md_path = storage_path / "SKILL.md"
        if not skill_md_path.exists():
            shutil.rmtree(storage_path)
            raise SkillValidationError("ZIP 包中缺少 SKILL.md 文件")
        
        # 解析 SKILL.md
        metadata = await self._parse_skill_md(skill_md_path)
        
        # 创建 Skill 记录
        skill = Skill(
            name=name,
            source_type=SkillSourceType.PRIVATE,
            storage_path=str(storage_path),
            title=metadata.get("title", name),
            summary=metadata.get("summary"),
            tags=json.dumps(metadata.get("tags", []), ensure_ascii=False),
            created_by=user.id,
        )
        
        self.session.add(skill)
        await self.session.commit()
        await self.session.refresh(skill)
        
        # 创建初始版本
        await self._create_version(skill, user, "上传创建")
        
        # 创建 SkillFile 记录
        await self._scan_skill_files(skill)
        
        # 分配所有者角色
        await self.permission_service.assign_resource_role(
            user.id, "skill", skill.id, "owner"
        )
        
        # 记录时间线
        await self._add_timeline_event(
            skill, TimelineEventType.SKILL_CREATED, user
        )
        
        return skill

    async def update_skill(
        self,
        skill_id: str,
        user: User,
        skill_md_content: Optional[str] = None,
        files: Optional[dict[str, str]] = None,
    ) -> Skill:
        """更新 Skill"""
        skill = await self._get_skill_by_id(skill_id)
        if not skill:
            raise SkillNotFoundError(skill_id)
        
        # 检查权限
        await self.permission_service.check_skill_permission(
            user, skill, PermissionAction.EDIT
        )
        
        # 检查编辑锁
        if skill.is_locked and skill.locked_by != user.id:
            raise SkillLockError(skill.id, skill.locked_by or "")
        
        # 获取编辑锁
        await self._acquire_lock(skill, user)
        
        try:
            storage_path = Path(skill.storage_path)
            changed_files = []
            
            # 更新 SKILL.md
            if skill_md_content:
                skill_md_path = storage_path / "SKILL.md"
                async with aiofiles.open(skill_md_path, "w", encoding="utf-8") as f:
                    await f.write(skill_md_content)
                changed_files.append("SKILL.md")
                
                # 更新元数据
                metadata = await self._parse_skill_md(skill_md_path)
                skill.title = metadata.get("title", skill.title)
                skill.summary = metadata.get("summary", skill.summary)
                skill.tags = json.dumps(metadata.get("tags", []), ensure_ascii=False)
            
            # 更新其他文件
            if files:
                for file_path, content in files.items():
                    full_path = storage_path / file_path
                    full_path.parent.mkdir(parents=True, exist_ok=True)
                    async with aiofiles.open(full_path, "w", encoding="utf-8") as f:
                        await f.write(content)
                    changed_files.append(file_path)
            
            skill.updated_at = datetime.utcnow()
            await self.session.commit()
            await self.session.refresh(skill)
            
            # 创建新版本
            if changed_files:
                await self._create_version(
                    skill, user, f"更新文件: {', '.join(changed_files)}"
                )
            
            # 更新文件记录
            await self._scan_skill_files(skill)
            
            # 记录时间线
            await self._add_timeline_event(
                skill, TimelineEventType.SKILL_UPDATED, user,
                {"changed_files": changed_files}
            )
            
            return skill
            
        finally:
            # 释放编辑锁
            await self._release_lock(skill)

    async def delete_skill(
        self,
        skill_id: str,
        user: User,
    ) -> bool:
        """删除 Skill"""
        skill = await self._get_skill_by_id(skill_id)
        if not skill:
            raise SkillNotFoundError(skill_id)
        
        # 检查权限
        await self.permission_service.check_skill_permission(
            user, skill, PermissionAction.DELETE
        )
        
        # 删除存储目录
        storage_path = Path(skill.storage_path)
        if storage_path.exists():
            shutil.rmtree(storage_path)
        
        # 标记为已删除
        skill.is_active = False
        await self.session.commit()
        
        # 记录时间线
        await self._add_timeline_event(
            skill, TimelineEventType.SKILL_DELETED, user
        )
        
        return True

    async def get_skill(self, skill_id: str) -> Optional[Skill]:
        """获取 Skill 详情"""
        return await self._get_skill_by_id(skill_id)

    async def get_skill_by_name(self, name: str) -> Optional[Skill]:
        """通过名称获取 Skill"""
        return await self._get_skill_by_name(name)

    async def list_skills(
        self,
        source_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Skill], int]:
        """列出 Skills"""
        query = select(Skill).where(Skill.is_active == True)
        
        if source_type:
            query = query.where(Skill.source_type == source_type)
        
        # 计算总数
        count_query = select(Skill).where(Skill.is_active == True)
        if source_type:
            count_query = count_query.where(Skill.source_type == source_type)
        
        result = await self.session.execute(count_query)
        total = len(result.scalars().all())
        
        # 分页
        query = query.offset((page - 1) * page_size).limit(page_size)
        query = query.order_by(Skill.updated_at.desc())
        
        result = await self.session.execute(query)
        skills = list(result.scalars().all())
        
        return skills, total

    async def acquire_lock(self, skill_id: str, user: User) -> bool:
        """获取编辑锁"""
        skill = await self._get_skill_by_id(skill_id)
        if not skill:
            raise SkillNotFoundError(skill_id)
        
        # 检查权限
        await self.permission_service.check_skill_permission(
            user, skill, PermissionAction.EDIT
        )
        
        return await self._acquire_lock(skill, user)

    async def release_lock(self, skill_id: str, user: User) -> bool:
        """释放编辑锁"""
        skill = await self._get_skill_by_id(skill_id)
        if not skill:
            raise SkillNotFoundError(skill_id)
        
        return await self._release_lock(skill)

    async def takeover_lock(self, skill_id: str, user: User) -> bool:
        """接管编辑锁"""
        skill = await self._get_skill_by_id(skill_id)
        if not skill:
            raise SkillNotFoundError(skill_id)
        
        # 检查权限
        await self.permission_service.check_skill_permission(
            user, skill, PermissionAction.TAKEOVER_LOCK
        )
        
        skill.locked_by = user.id
        skill.locked_at = datetime.utcnow()
        await self.session.commit()
        
        return True

    # ==================== 私有方法 ====================

    async def _get_skill_by_id(self, skill_id: str) -> Optional[Skill]:
        """通过 ID 获取 Skill"""
        result = await self.session.execute(
            select(Skill).where(
                and_(Skill.id == skill_id, Skill.is_active == True)
            )
        )
        return result.scalar_one_or_none()

    async def _get_skill_by_name(self, name: str) -> Optional[Skill]:
        """通过名称获取 Skill"""
        result = await self.session.execute(
            select(Skill).where(
                and_(Skill.name == name, Skill.is_active == True)
            )
        )
        return result.scalar_one_or_none()

    def _validate_skill_name(self, name: str) -> bool:
        """验证 Skill 名称"""
        import re
        if not name:
            return False
        if len(name) > 100:
            return False
        # 只允许字母、数字、中划线、下划线
        return bool(re.match(r"^[a-zA-Z0-9_-]+$", name))

    async def _parse_skill_md(self, skill_md_path: Path) -> dict:
        """解析 SKILL.md 文件"""
        async with aiofiles.open(skill_md_path, "r", encoding="utf-8") as f:
            content = await f.read()
        
        try:
            post = frontmatter.loads(content)
            metadata = dict(post.metadata)
            
            # 提取标题
            if "name" in metadata:
                metadata["title"] = metadata["name"]
            elif "title" not in metadata:
                # 从第一个 H1 提取
                import re
                h1_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
                if h1_match:
                    metadata["title"] = h1_match.group(1).strip()
            
            # 提取摘要
            if "summary" not in metadata:
                # 从第一段提取
                lines = content.split("\n")
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        metadata["summary"] = line[:200]
                        break
            
            return metadata
            
        except Exception:
            return {}

    async def _safe_extract_zip(self, zip_path: Path, target_dir: Path) -> None:
        """安全解压 ZIP 文件"""
        try:
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                for member in zip_ref.namelist():
                    # 规范化路径
                    member_path = os.path.normpath(member)
                    
                    # 检查路径穿越
                    if member_path.startswith("..") or os.path.isabs(member_path):
                        raise ZipExtractionError(f"检测到路径穿越攻击: {member}")
                    
                    # 检查文件类型
                    ext = os.path.splitext(member_path)[1].lower()
                    if ext in FORBIDDEN_EXTENSIONS:
                        raise ZipExtractionError(f"禁止的文件类型: {member}")
                    
                    # 检查文件大小
                    info = zip_ref.getinfo(member)
                    if info.file_size > self.settings.max_file_size_mb * 1024 * 1024:
                        raise ZipExtractionError(f"文件大小超限: {member}")
                
                # 安全解压
                zip_ref.extractall(target_dir)
                
        except zipfile.BadZipFile as e:
            raise ZipExtractionError(f"无效的 ZIP 文件: {str(e)}")

    async def _create_version(
        self,
        skill: Skill,
        user: User,
        change_summary: str,
    ) -> SkillVersion:
        """创建新版本"""
        # 计算版本号
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
        
        # 创建快照
        snapshot_path = (
            self.settings.packages_path
            / skill.name
            / f"v{version_number}"
        )
        snapshot_path.mkdir(parents=True, exist_ok=True)
        
        storage_path = Path(skill.storage_path)
        for item in storage_path.rglob("*"):
            if item.is_file():
                rel_path = item.relative_to(storage_path)
                dest = snapshot_path / rel_path
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, dest)
        
        version = SkillVersion(
            skill_id=skill.id,
            version_number=version_number,
            version_hash=version_hash,
            change_summary=change_summary,
            snapshot_path=str(snapshot_path),
            created_by=user.id,
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
                async with aiofiles.open(file_path, "rb") as f:
                    content = await f.read()
                    hasher.update(file_path.name.encode())
                    hasher.update(content)
        
        return hasher.hexdigest()

    async def _scan_skill_files(self, skill: Skill) -> None:
        """扫描并记录 Skill 文件"""
        storage_path = Path(skill.storage_path)
        
        # 删除旧记录
        result = await self.session.execute(
            select(SkillFile).where(SkillFile.skill_id == skill.id)
        )
        for old_file in result.scalars().all():
            await self.session.delete(old_file)
        
        # 扫描新文件
        for file_path in storage_path.rglob("*"):
            if file_path.is_file():
                rel_path = file_path.relative_to(storage_path)
                
                # 计算文件哈希
                async with aiofiles.open(file_path, "rb") as f:
                    content = await f.read()
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
            ".ts": "text/typescript",
            ".py": "text/x-python",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".svg": "image/svg+xml",
            ".pdf": "application/pdf",
        }
        return mime_map.get(ext, "application/octet-stream")

    async def _acquire_lock(self, skill: Skill, user: User) -> bool:
        """获取编辑锁"""
        if skill.is_locked and skill.locked_by != user.id:
            raise SkillLockError(skill.id, skill.locked_by or "")
        
        skill.is_locked = True
        skill.locked_by = user.id
        skill.locked_at = datetime.utcnow()
        await self.session.commit()
        
        return True

    async def _release_lock(self, skill: Skill) -> bool:
        """释放编辑锁"""
        skill.is_locked = False
        skill.locked_by = None
        skill.locked_at = None
        await self.session.commit()
        
        return True

    async def _add_timeline_event(
        self,
        skill: Skill,
        event_type: str,
        user: User,
        event_data: Optional[dict] = None,
    ) -> TimelineEvent:
        """添加时间线事件"""
        event = TimelineEvent(
            skill_id=skill.id,
            event_type=event_type,
            event_data=json.dumps(event_data, ensure_ascii=False) if event_data else None,
            created_by=user.id,
        )
        
        self.session.add(event)
        await self.session.commit()
        
        return event
