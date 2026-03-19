"""
Git 仓库路由
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, get_current_admin
from app.auth.permissions import PermissionService, PermissionAction
from app.db.database import get_db_session
from app.db.models import User
from app.services.git_sync_service import GitSyncService


router = APIRouter(prefix="/repos", tags=["Git仓库管理"])


# ==================== 请求/响应模型 ====================

class RepoCreate(BaseModel):
    """创建仓库请求"""
    name: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    url: str = Field(..., max_length=500)
    branch: str = Field(default="main", max_length=100)
    auth_type: Optional[str] = Field(default=None, max_length=20)
    auth_secret_ref: Optional[str] = Field(default=None, max_length=255)


class RepoResponse(BaseModel):
    """仓库响应"""
    id: str
    name: str
    url: str
    branch: str
    last_sync_at: Optional[datetime] = None
    last_sync_commit: Optional[str] = None
    sync_status: str
    sync_error: Optional[str] = None
    is_active: bool
    auto_sync: bool
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None

    class Config:
        from_attributes = True


class RepoListResponse(BaseModel):
    """仓库列表响应"""
    items: list[RepoResponse]
    total: int
    page: int
    page_size: int


class SyncResult(BaseModel):
    """同步结果"""
    status: str
    commit: Optional[str] = None
    skills_created: Optional[int] = None
    skills_updated: Optional[int] = None


# ==================== 路由 ====================

@router.post("", response_model=RepoResponse, status_code=status.HTTP_201_CREATED)
async def import_repo(
    repo_data: RepoCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """导入 Git 仓库"""
    service = GitSyncService(session)
    repo = await service.import_repo(
        name=repo_data.name,
        url=repo_data.url,
        user=current_user,
        branch=repo_data.branch,
        auth_type=repo_data.auth_type,
        auth_secret_ref=repo_data.auth_secret_ref,
    )
    return repo


@router.get("", response_model=RepoListResponse)
async def list_repos(
    page: int = 1,
    page_size: int = 20,
    session: AsyncSession = Depends(get_db_session),
):
    """列出所有 Git 仓库"""
    service = GitSyncService(session)
    repos, total = await service.list_repos(
        page=page,
        page_size=page_size,
    )
    
    return RepoListResponse(
        items=[RepoResponse.model_validate(r) for r in repos],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{repo_id}", response_model=RepoResponse)
async def get_repo(
    repo_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """获取仓库详情"""
    service = GitSyncService(session)
    repo = await service.get_repo(repo_id)
    
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="仓库不存在",
        )
    
    return repo


@router.post("/{repo_id}/sync", response_model=SyncResult)
async def sync_repo(
    repo_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """同步 Git 仓库"""
    service = GitSyncService(session)
    
    # 检查权限
    permission_service = PermissionService(session)
    await permission_service.check_repo_permission(
        current_user, repo_id, PermissionAction.SYNC
    )
    
    result = await service.sync_repo(repo_id, current_user)
    return SyncResult(**result)


@router.delete("/{repo_id}")
async def delete_repo(
    repo_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """删除 Git 仓库"""
    service = GitSyncService(session)
    await service.delete_repo(repo_id=repo_id, user=current_user)
    return {"message": "删除成功"}


@router.post("/sync-all")
async def sync_all_repos(
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db_session),
):
    """同步所有仓库（管理员）"""
    service = GitSyncService(session)
    result = await service.sync_all_repos()
    return result
