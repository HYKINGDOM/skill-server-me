"""
通知路由
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.db.database import get_db_session
from app.db.models import User
from app.services.notification_service import NotificationService


router = APIRouter(prefix="/notifications", tags=["通知"])


class NotificationResponse(BaseModel):
    """通知响应"""
    id: str
    type: str
    title: str
    content: Optional[str] = None
    is_read: bool
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    created_at: str
    read_at: Optional[str] = None


class NotificationListResponse(BaseModel):
    """通知列表响应"""
    items: list[NotificationResponse]
    total: int
    page: int
    page_size: int


class UnreadCountResponse(BaseModel):
    """未读数量响应"""
    unread_count: int


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    page: int = 1,
    page_size: int = 20,
    unread_only: bool = False,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """列出我的通知"""
    service = NotificationService(session)
    items, total = await service.list_user_notifications(
        user=current_user,
        page=page,
        page_size=page_size,
        unread_only=unread_only,
    )
    
    return NotificationListResponse(
        items=[NotificationResponse(**item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """获取未读通知数量"""
    service = NotificationService(session)
    count = await service.get_unread_count(current_user)
    return UnreadCountResponse(unread_count=count)


@router.post("/{notification_id}/read")
async def mark_as_read(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """标记通知为已读"""
    service = NotificationService(session)
    await service.mark_as_read(notification_id, current_user)
    return {"message": "已标记为已读"}


@router.post("/read-all")
async def mark_all_as_read(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """标记所有通知为已读"""
    service = NotificationService(session)
    count = await service.mark_all_as_read(current_user)
    return {"message": f"已标记 {count} 条通知为已读"}


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """删除通知"""
    service = NotificationService(session)
    await service.delete_notification(notification_id, current_user)
    return {"message": "删除成功"}
