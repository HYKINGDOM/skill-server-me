"""
版本管理服务
"""
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiofiles
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import ResourceNotFoundError, SkillNotFoundError
from app.db.models import Skill, SkillVersion, TimelineEvent, TimelineEventType, User


class VersionService:
    """版本管理服务"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.settings = get_settings()

    async def list_versions(
        self,
        skill_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[SkillVersion], int]:
        """列出 Skill 的所有版本"""
        # 验证 Skill 存在
        result = await self.session.execute(
            select(Skill).where(Skill.id == skill_id)
        )
        skill = result.scalar_one_or_none()
        
        if not skill:
            raise SkillNotFoundError(skill_id)
        
        # 查询版本
        query = select(SkillVersion).where(SkillVersion.skill_id == skill_id)
        query = query.order_by(SkillVersion.version_number.desc())
        
        # 计算总数
        count_result = await self.session.execute(
            select(SkillVersion).where(SkillVersion.skill_id == skill_id)
        )
        total = len(count_result.scalars().all())
        
        # 分页
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await self.session.execute(query)
        versions = list(result.scalars().all())
        
        return versions, total

    async def get_version(self, version_id: str) -> Optional[SkillVersion]:
        """获取版本详情"""
        result = await self.session.execute(
            select(SkillVersion).where(SkillVersion.id == version_id)
        )
        return result.scalar_one_or_none()

    async def get_version_by_number(
        self,
        skill_id: str,
        version_number: int,
    ) -> Optional[SkillVersion]:
        """通过版本号获取版本"""
        result = await self.session.execute(
            select(SkillVersion).where(
                and_(
                    SkillVersion.skill_id == skill_id,
                    SkillVersion.version_number == version_number,
                )
            )
        )
        return result.scalar_one_or_none()

    async def restore_version(
        self,
        skill_id: str,
        version_number: int,
        user: User,
    ) -> Skill:
        """恢复到指定版本"""
        # 获取版本
        version = await self.get_version_by_number(skill_id, version_number)
        if not version:
            raise ResourceNotFoundError("SkillVersion", f"{skill_id}/v{version_number}")
        
        # 获取 Skill
        result = await self.session.execute(
            select(Skill).where(Skill.id == skill_id)
        )
        skill = result.scalar_one_or_none()
        
        if not skill:
            raise SkillNotFoundError(skill_id)
        
        # 恢复文件
        snapshot_path = Path(version.snapshot_path)
        storage_path = Path(skill.storage_path)
        
        # 清空当前目录
        for item in storage_path.iterdir():
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)
        
        # 复制快照文件
        for item in snapshot_path.rglob("*"):
            if item.is_file():
                rel_path = item.relative_to(snapshot_path)
                dest = storage_path / rel_path
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, dest)
        
        # 创建新版本
        new_version = await self._create_version(
            skill, user, f"恢复到版本 v{version_number}"
        )
        
        # 更新 Skill 更新时间
        skill.updated_at = datetime.utcnow()
        await self.session.commit()
        
        return skill

    async def compare_versions(
        self,
        skill_id: str,
        version1: int,
        version2: int,
    ) -> dict:
        """比较两个版本"""
        v1 = await self.get_version_by_number(skill_id, version1)
        v2 = await self.get_version_by_number(skill_id, version2)
        
        if not v1 or not v2:
            raise ResourceNotFoundError("SkillVersion", f"{skill_id}")
        
        # 获取变更文件
        changed_files_v1 = json.loads(v1.changed_files or "[]")
        changed_files_v2 = json.loads(v2.changed_files or "[]")
        
        return {
            "version1": {
                "number": v1.version_number,
                "hash": v1.version_hash,
                "summary": v1.change_summary,
                "created_at": v1.created_at.isoformat(),
            },
            "version2": {
                "number": v2.version_number,
                "hash": v2.version_hash,
                "summary": v2.change_summary,
                "created_at": v2.created_at.isoformat(),
            },
            "diff": {
                "version1_changes": changed_files_v1,
                "version2_changes": changed_files_v2,
            },
        }

    async def _create_version(
        self,
        skill: Skill,
        user: User,
        change_summary: str,
    ) -> SkillVersion:
        """创建新版本"""
        # 获取最新版本号
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
