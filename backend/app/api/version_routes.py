"""
版本管理路由
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.db.database import get_db_session
from app.db.models import User
from app.services.version_service import VersionService


router = APIRouter(prefix="/versions", tags=["版本管理"])


class VersionResponse(BaseModel):
    """版本响应"""
    id: str
    skill_id: str
    version_number: int
    version_hash: str
    change_summary: Optional[str] = None
    created_at: datetime
    created_by: Optional[str] = None

    class Config:
        from_attributes = True


class VersionListResponse(BaseModel):
    """版本列表响应"""
    items: list[VersionResponse]
    total: int
    page: int
    page_size: int


class VersionCompareResponse(BaseModel):
    """版本比较响应"""
    version1: dict
    version2: dict
    diff: dict


@router.get("/skill/{skill_id}", response_model=VersionListResponse)
async def list_versions(
    skill_id: str,
    page: int = 1,
    page_size: int = 20,
    session: AsyncSession = Depends(get_db_session),
):
    """列出 Skill 的所有版本"""
    service = VersionService(session)
    versions, total = await service.list_versions(
        skill_id=skill_id,
        page=page,
        page_size=page_size,
    )
    
    return VersionListResponse(
        items=[VersionResponse.model_validate(v) for v in versions],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{version_id}", response_model=VersionResponse)
async def get_version(
    version_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """获取版本详情"""
    service = VersionService(session)
    version = await service.get_version(version_id)
    
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="版本不存在",
        )
    
    return version


@router.post("/skill/{skill_id}/restore/{version_number}")
async def restore_version(
    skill_id: str,
    version_number: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """恢复到指定版本"""
    service = VersionService(session)
    skill = await service.restore_version(
        skill_id=skill_id,
        version_number=version_number,
        user=current_user,
    )
    
    return {"message": f"已恢复到版本 v{version_number}", "skill_id": skill.id}


@router.get("/skill/{skill_id}/compare", response_model=VersionCompareResponse)
async def compare_versions(
    skill_id: str,
    version1: int,
    version2: int,
    session: AsyncSession = Depends(get_db_session),
):
    """比较两个版本"""
    service = VersionService(session)
    result = await service.compare_versions(
        skill_id=skill_id,
        version1=version1,
        version2=version2,
    )
    
    return VersionCompareResponse(**result)
