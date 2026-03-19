"""
时间线路由
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.db.database import get_db_session
from app.db.models import User
from app.services.timeline_service import TimelineService


router = APIRouter(prefix="/timeline", tags=["时间线"])


class TimelineEventResponse(BaseModel):
    """时间线事件响应"""
    id: str
    event_type: str
    event_data: Optional[dict] = None
    created_at: str
    created_by: Optional[str] = None
    created_by_name: Optional[str] = None


class TimelineListResponse(BaseModel):
    """时间线列表响应"""
    items: list[TimelineEventResponse]
    total: int
    page: int
    page_size: int


class RecentEventResponse(BaseModel):
    """最近事件响应"""
    id: str
    skill_id: str
    skill_name: Optional[str] = None
    event_type: str
    event_data: Optional[dict] = None
    created_at: str


@router.get("/skill/{skill_id}", response_model=TimelineListResponse)
async def get_skill_timeline(
    skill_id: str,
    page: int = 1,
    page_size: int = 20,
    event_type: Optional[str] = None,
    session: AsyncSession = Depends(get_db_session),
):
    """获取 Skill 时间线"""
    service = TimelineService(session)
    items, total = await service.get_timeline(
        skill_id=skill_id,
        page=page,
        page_size=page_size,
        event_type=event_type,
    )
    
    return TimelineListResponse(
        items=[TimelineEventResponse(**item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/recent", response_model=list[RecentEventResponse])
async def get_recent_events(
    limit: int = 20,
    session: AsyncSession = Depends(get_db_session),
):
    """获取最近的事件"""
    service = TimelineService(session)
    items = await service.get_recent_events(limit=limit)
    
    return [RecentEventResponse(**item) for item in items]
