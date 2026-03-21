"""
搜索路由

支持：
- 搜索模式：fulltext（全文检索）、vector（向量检索）、hybrid（混合检索）
- 过滤维度：source_type、repo_source_id、status
- 排序方式：relevance、favorite_count、download_count、updated_at、blend
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user_optional
from app.db.database import get_db_session
from app.db.models import User
from app.services.search_service import (
    SearchService,
    SearchMode,
    SortBy,
    SearchFilter,
    SearchResultItem,
)


router = APIRouter(prefix="/search", tags=["搜索"])


class SearchResponseItem(BaseModel):
    """搜索结果项"""
    skill_id: str
    name: str
    title: str
    summary: str
    tags: list[str]
    score: float
    relevance_score: float = Field(default=0.0, description="相关度分数")
    business_score: float = Field(default=0.0, description="业务分数")
    download_count: int = Field(default=0, description="下载数")
    favorite_count: int = Field(default=0, description="收藏数")
    usage_count: int = Field(default=0, description="使用数")
    is_official: bool = Field(default=False, description="是否官方认证")
    source_type: str = Field(default="private", description="来源类型")
    updated_at: Optional[datetime] = Field(default=None, description="更新时间")


class SearchResponse(BaseModel):
    """搜索响应"""
    items: list[SearchResponseItem]
    total: int
    page: int
    page_size: int
    query: str
    mode: str
    sort_by: str


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
    sort_by: str = Query("blend", description="排序方式: relevance/favorite_count/download_count/updated_at/blend"),
    source_type: Optional[str] = Query(None, description="来源类型过滤: private/git"),
    repo_source_id: Optional[str] = Query(None, description="仓库源 ID 过滤"),
    status: Optional[str] = Query(None, description="状态过滤: active/inactive"),
    current_user: Optional[User] = Depends(get_current_user_optional),
    session: AsyncSession = Depends(get_db_session),
):
    """
    搜索 Skills
    
    **搜索模式**：
    - `fulltext`: 全文检索（Whoosh-Reloaded + jieba 分词）
    - `vector`: 向量检索（Embedding + 精确余弦）
    - `hybrid`: 混合检索（RRF 融合）
    
    **过滤维度**：
    - `source_type`: 来源类型（private / git）
    - `repo_source_id`: 仓库源 ID
    - `status`: 状态（active / inactive）
    
    **排序方式**：
    - `relevance`: 相关度
    - `favorite_count`: 收藏数
    - `download_count`: 下载数
    - `updated_at`: 更新时间
    - `blend`: 混合排序（默认）
    
    **blend 公式**：
    ```
    final_score = 0.55 × relevance_score + 0.20 × favorite_score + 0.15 × download_score + 0.10 × freshness_score
    ```
    """
    try:
        search_mode = SearchMode(mode)
    except ValueError:
        search_mode = SearchMode.HYBRID
    
    try:
        sort_method = SortBy(sort_by)
    except ValueError:
        sort_method = SortBy.BLEND
    
    search_filter = SearchFilter(
        source_type=source_type,
        repo_source_id=repo_source_id,
        status=status,
    )
    
    service = SearchService(session)
    items, total = await service.search(
        query=q,
        page=page,
        page_size=page_size,
        mode=search_mode,
        sort_by=sort_method,
        search_filter=search_filter,
    )
    
    return SearchResponse(
        items=[
            SearchResponseItem(
                skill_id=item.skill_id,
                name=item.name,
                title=item.title,
                summary=item.summary,
                tags=item.tags,
                score=item.score,
                relevance_score=item.relevance_score,
                business_score=item.business_score,
                download_count=item.download_count,
                favorite_count=item.favorite_count,
                usage_count=item.usage_count,
                is_official=item.is_official,
                source_type=item.source_type,
                updated_at=item.updated_at,
            )
            for item in items
        ],
        total=total,
        page=page,
        page_size=page_size,
        query=q,
        mode=mode,
        sort_by=sort_by,
    )


@router.post("/rebuild-index", response_model=RebuildIndexResponse)
async def rebuild_index(
    session: AsyncSession = Depends(get_db_session),
):
    """
    重建索引
    
    重建全文索引和向量索引，用于：
    - 首次部署后初始化索引
    - 索引损坏后恢复
    - 批量更新统计信息
    """
    service = SearchService(session)
    result = await service.rebuild_index()
    return RebuildIndexResponse(**result)
