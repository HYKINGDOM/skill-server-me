"""
收藏服务
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import SkillNotFoundError
from app.db.models import Favorite, Skill, User


class FavoriteService:
    """收藏服务"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_favorite(
        self,
        skill_id: str,
        user: User,
    ) -> Favorite:
        """添加收藏"""
        # 验证 Skill 存在
        result = await self.session.execute(
            select(Skill).where(Skill.id == skill_id)
        )
        skill = result.scalar_one_or_none()
        
        if not skill:
            raise SkillNotFoundError(skill_id)
        
        # 检查是否已收藏
        existing = await self._get_favorite(skill_id, user.id)
        if existing:
            return existing
        
        # 创建收藏
        favorite = Favorite(
            user_id=user.id,
            skill_id=skill_id,
        )
        
        self.session.add(favorite)
        await self.session.commit()
        await self.session.refresh(favorite)
        
        return favorite

    async def remove_favorite(
        self,
        skill_id: str,
        user: User,
    ) -> bool:
        """取消收藏"""
        favorite = await self._get_favorite(skill_id, user.id)
        
        if favorite:
            await self.session.delete(favorite)
            await self.session.commit()
            return True
        
        return False

    async def is_favorited(
        self,
        skill_id: str,
        user_id: str,
    ) -> bool:
        """检查是否已收藏"""
        favorite = await self._get_favorite(skill_id, user_id)
        return favorite is not None

    async def list_user_favorites(
        self,
        user: User,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict], int]:
        """列出用户收藏"""
        # 查询收藏
        query = select(Favorite).where(Favorite.user_id == user.id)
        
        # 计算总数
        count_result = await self.session.execute(query)
        total = len(count_result.scalars().all())
        
        # 分页
        query = query.offset((page - 1) * page_size).limit(page_size)
        query = query.order_by(Favorite.created_at.desc())
        
        result = await self.session.execute(query)
        favorites = result.scalars().all()
        
        # 获取 Skill 详情
        items = []
        for favorite in favorites:
            skill_result = await self.session.execute(
                select(Skill).where(Skill.id == favorite.skill_id)
            )
            skill = skill_result.scalar_one_or_none()
            
            if skill:
                items.append({
                    "favorite_id": favorite.id,
                    "skill_id": skill.id,
                    "skill_name": skill.name,
                    "title": skill.title,
                    "summary": skill.summary,
                    "source_type": skill.source_type,
                    "favorited_at": favorite.created_at.isoformat(),
                })
        
        return items, total

    async def _get_favorite(
        self,
        skill_id: str,
        user_id: str,
    ) -> Optional[Favorite]:
        """获取收藏记录"""
        result = await self.session.execute(
            select(Favorite).where(
                and_(
                    Favorite.skill_id == skill_id,
                    Favorite.user_id == user_id,
                )
            )
        )
        return result.scalar_one_or_none()
