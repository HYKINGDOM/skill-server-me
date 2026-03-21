"""
通知服务
"""
import json
from datetime import datetime, UTC
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Notification, User


class NotificationService:
    """通知服务"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_notification(
        self,
        user_id: str,
        notification_type: str,
        title: str,
        content: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
    ) -> Notification:
        """创建通知"""
        notification = Notification(
            user_id=user_id,
            notification_type=notification_type,
            title=title,
            content=content,
            resource_type=resource_type,
            resource_id=resource_id,
        )
        
        self.session.add(notification)
        await self.session.commit()
        await self.session.refresh(notification)
        
        return notification

    async def list_user_notifications(
        self,
        user: User,
        page: int = 1,
        page_size: int = 20,
        unread_only: bool = False,
    ) -> tuple[list[dict], int]:
        """列出用户通知"""
        query = select(Notification).where(Notification.user_id == user.id)
        
        if unread_only:
            query = query.where(Notification.is_read == False)
        
        # 计算总数
        count_query = select(Notification).where(Notification.user_id == user.id)
        if unread_only:
            count_query = count_query.where(Notification.is_read == False)
        
        count_result = await self.session.execute(count_query)
        total = len(count_result.scalars().all())
        
        # 分页
        query = query.offset((page - 1) * page_size).limit(page_size)
        query = query.order_by(Notification.created_at.desc())
        
        result = await self.session.execute(query)
        notifications = result.scalars().all()
        
        items = []
        for notification in notifications:
            items.append({
                "id": notification.id,
                "type": notification.notification_type,
                "title": notification.title,
                "content": notification.content,
                "is_read": notification.is_read,
                "resource_type": notification.resource_type,
                "resource_id": notification.resource_id,
                "created_at": notification.created_at.isoformat(),
                "read_at": notification.read_at.isoformat() if notification.read_at else None,
            })
        
        return items, total

    async def mark_as_read(
        self,
        notification_id: str,
        user: User,
    ) -> bool:
        """标记通知为已读"""
        result = await self.session.execute(
            select(Notification).where(
                and_(
                    Notification.id == notification_id,
                    Notification.user_id == user.id,
                )
            )
        )
        notification = result.scalar_one_or_none()
        
        if notification:
            notification.is_read = True
            notification.read_at = datetime.now(UTC)
            await self.session.commit()
            return True
        
        return False

    async def mark_all_as_read(self, user: User) -> int:
        """标记所有通知为已读"""
        result = await self.session.execute(
            select(Notification).where(
                and_(
                    Notification.user_id == user.id,
                    Notification.is_read == False,
                )
            )
        )
        notifications = result.scalars().all()
        
        count = 0
        for notification in notifications:
            notification.is_read = True
            notification.read_at = datetime.now(UTC)
            count += 1
        
        await self.session.commit()
        
        return count

    async def get_unread_count(self, user: User) -> int:
        """获取未读通知数量"""
        result = await self.session.execute(
            select(Notification).where(
                and_(
                    Notification.user_id == user.id,
                    Notification.is_read == False,
                )
            )
        )
        return len(result.scalars().all())

    async def delete_notification(
        self,
        notification_id: str,
        user: User,
    ) -> bool:
        """删除通知"""
        result = await self.session.execute(
            select(Notification).where(
                and_(
                    Notification.id == notification_id,
                    Notification.user_id == user.id,
                )
            )
        )
        notification = result.scalar_one_or_none()
        
        if notification:
            await self.session.delete(notification)
            await self.session.commit()
            return True
        
        return False
