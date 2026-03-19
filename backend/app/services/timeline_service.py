"""
时间线服务
"""
import json
from datetime import datetime
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import SkillNotFoundError
from app.db.models import Skill, TimelineEvent, User


class TimelineService:
    """时间线服务"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_timeline(
        self,
        skill_id: str,
        page: int = 1,
        page_size: int = 20,
        event_type: Optional[str] = None,
    ) -> tuple[list[dict], int]:
        """获取 Skill 时间线"""
        # 验证 Skill 存在
        result = await self.session.execute(
            select(Skill).where(Skill.id == skill_id)
        )
        skill = result.scalar_one_or_none()
        
        if not skill:
            raise SkillNotFoundError(skill_id)
        
        # 构建查询
        query = select(TimelineEvent).where(TimelineEvent.skill_id == skill_id)
        
        if event_type:
            query = query.where(TimelineEvent.event_type == event_type)
        
        # 计算总数
        count_query = select(TimelineEvent).where(TimelineEvent.skill_id == skill_id)
        if event_type:
            count_query = count_query.where(TimelineEvent.event_type == event_type)
        
        count_result = await self.session.execute(count_query)
        total = len(count_result.scalars().all())
        
        # 分页和排序
        query = query.order_by(TimelineEvent.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await self.session.execute(query)
        events = result.scalars().all()
        
        # 格式化输出
        items = []
        for event in events:
            event_data = None
            if event.event_data:
                try:
                    event_data = json.loads(event.event_data)
                except json.JSONDecodeError:
                    event_data = event.event_data
            
            # 获取操作人信息
            created_by_name = None
            if event.created_by:
                user_result = await self.session.execute(
                    select(User).where(User.id == event.created_by)
                )
                user = user_result.scalar_one_or_none()
                if user:
                    created_by_name = user.username
            
            items.append({
                "id": event.id,
                "event_type": event.event_type,
                "event_data": event_data,
                "created_at": event.created_at.isoformat(),
                "created_by": event.created_by,
                "created_by_name": created_by_name,
            })
        
        return items, total

    async def add_event(
        self,
        skill_id: str,
        event_type: str,
        user: Optional[User] = None,
        event_data: Optional[dict] = None,
    ) -> TimelineEvent:
        """添加时间线事件"""
        event = TimelineEvent(
            skill_id=skill_id,
            event_type=event_type,
            event_data=json.dumps(event_data, ensure_ascii=False) if event_data else None,
            created_by=user.id if user else None,
        )
        
        self.session.add(event)
        await self.session.commit()
        
        return event

    async def get_recent_events(
        self,
        limit: int = 20,
    ) -> list[dict]:
        """获取最近的事件"""
        query = select(TimelineEvent).order_by(TimelineEvent.created_at.desc()).limit(limit)
        
        result = await self.session.execute(query)
        events = result.scalars().all()
        
        items = []
        for event in events:
            # 获取 Skill 信息
            skill_result = await self.session.execute(
                select(Skill).where(Skill.id == event.skill_id)
            )
            skill = skill_result.scalar_one_or_none()
            
            event_data = None
            if event.event_data:
                try:
                    event_data = json.loads(event.event_data)
                except json.JSONDecodeError:
                    event_data = event.event_data
            
            items.append({
                "id": event.id,
                "skill_id": event.skill_id,
                "skill_name": skill.name if skill else None,
                "event_type": event.event_type,
                "event_data": event_data,
                "created_at": event.created_at.isoformat(),
            })
        
        return items
