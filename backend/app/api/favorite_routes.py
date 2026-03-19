"""
收藏路由
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.db.database import get_db_session
from app.db.models import User
from app.services.favorite_service import FavoriteService


router = APIRouter(prefix="/favorites", tags=["收藏"])


class FavoriteResponse(BaseModel):
    """收藏响应"""
    favorite_id: str
    skill_id: str
    skill_name: str
    title: Optional[str] = None
    summary: Optional[str] = None
    source_type: str
    favorited_at: str


class FavoriteListResponse(BaseModel):
    """收藏列表响应"""
    items: list[FavoriteResponse]
    total: int
    page: int
    page_size: int


@router.post("/{skill_id}")
async def add_favorite(
    skill_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """添加收藏"""
    service = FavoriteService(session)
    await service.add_favorite(skill_id=skill_id, user=current_user)
    return {"message": "收藏成功"}


@router.delete("/{skill_id}")
async def remove_favorite(
    skill_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """取消收藏"""
    service = FavoriteService(session)
    await service.remove_favorite(skill_id=skill_id, user=current_user)
    return {"message": "取消收藏成功"}


@router.get("", response_model=FavoriteListResponse)
async def list_favorites(
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """列出我的收藏"""
    service = FavoriteService(session)
    items, total = await service.list_user_favorites(
        user=current_user,
        page=page,
        page_size=page_size,
    )
    
    return FavoriteListResponse(
        items=[FavoriteResponse(**item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/check/{skill_id}")
async def check_favorite(
    skill_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """检查是否已收藏"""
    service = FavoriteService(session)
    is_favorited = await service.is_favorited(
        skill_id=skill_id,
        user_id=current_user.id,
    )
    return {"is_favorited": is_favorited}
