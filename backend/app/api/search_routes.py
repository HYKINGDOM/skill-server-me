"""
搜索路由
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user_optional
from app.db.database import get_db_session
from app.db.models import User
from app.services.search_service import SearchService


router = APIRouter(prefix="/search", tags=["搜索"])


class SearchResultItem(BaseModel):
    """搜索结果项"""
    skill_id: str
    name: str
    title: str
    summary: str
    tags: list[str]
    score: float


class SearchResponse(BaseModel):
    """搜索响应"""
    items: list[SearchResultItem]
    total: int
    page: int
    page_size: int
    query: str
    mode: str


class RebuildIndexResponse(BaseModel):
    """重建索引响应"""
    fulltext_indexed: int
    vector_indexed: int


@router.get("", response_model=SearchResponse)
async def search(
    q: str = Query(..., min_length=1, description="搜索关键词"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    mode: str = Query("hybrid", description="搜索模式: fulltext/vector/hybrid"),
    current_user: Optional[User] = Depends(get_current_user_optional),
    session: AsyncSession = Depends(get_db_session),
):
    """
    搜索 Skills
    
    - **q**: 搜索关键词
    - **mode**: 搜索模式
        - fulltext: 全文检索
        - vector: 向量检索
        - hybrid: 混合检索（默认）
    """
    service = SearchService(session)
    items, total = await service.search(
        query=q,
        page=page,
        page_size=page_size,
        mode=mode,
    )
    
    return SearchResponse(
        items=[SearchResultItem(**item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        query=q,
        mode=mode,
    )


@router.post("/rebuild-index", response_model=RebuildIndexResponse)
async def rebuild_index(
    session: AsyncSession = Depends(get_db_session),
):
    """重建索引"""
    service = SearchService(session)
    result = await service.rebuild_index()
    return RebuildIndexResponse(**result)
