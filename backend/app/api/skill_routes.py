"""
Skill 路由

处理 Skill 的 CRUD 操作
"""
import os
import tempfile
from datetime import datetime, UTC
from typing import Optional

import aiofiles
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.permissions import PermissionService, PermissionAction
from app.core.config import get_settings
from app.core.exceptions import SkillNotFoundError
from app.db.database import get_db_session
from app.db.models import Skill, User
from app.services.skill_service import SkillService


router = APIRouter(prefix="/skills", tags=["Skill管理"])


# ==================== 请求/响应模型 ====================

class SkillCreate(BaseModel):
    """创建 Skill 请求"""
    name: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    skill_md_content: Optional[str] = None


class SkillUpdate(BaseModel):
    """更新 Skill 请求"""
    skill_md_content: Optional[str] = None
    files: Optional[dict[str, str]] = None


class SkillResponse(BaseModel):
    """Skill 响应"""
    id: str
    name: str
    source_type: str
    title: Optional[str] = None
    summary: Optional[str] = None
    tags: Optional[str] = None
    is_locked: bool
    locked_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None

    class Config:
        from_attributes = True


class SkillListResponse(BaseModel):
    """Skill 列表响应"""
    items: list[SkillResponse]
    total: int
    page: int
    page_size: int


class SkillFileResponse(BaseModel):
    """Skill 文件响应"""
    file_path: str
    file_name: str
    file_size: int
    file_type: str
    is_skill_md: bool


class SkillDetailResponse(BaseModel):
    """Skill 详情响应"""
    skill: SkillResponse
    files: list[SkillFileResponse]
    skill_md_content: Optional[str] = None


class LockResponse(BaseModel):
    """锁响应"""
    skill_id: str
    is_locked: bool
    locked_by: Optional[str] = None
    locked_at: Optional[datetime] = None


# ==================== 路由 ====================

@router.post("", response_model=SkillResponse, status_code=status.HTTP_201_CREATED)
async def create_skill(
    skill_data: SkillCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """创建新的 Skill"""
    service = SkillService(session)
    skill = await service.create_skill(
        name=skill_data.name,
        user=current_user,
        skill_md_content=skill_data.skill_md_content,
    )
    return skill


@router.post("/upload", response_model=SkillResponse, status_code=status.HTTP_201_CREATED)
async def upload_skill(
    name: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """上传 ZIP 包创建 Skill"""
    settings = get_settings()
    
    # 验证文件类型
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只支持 ZIP 文件",
        )
    
    # 保存临时文件
    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name
    
    try:
        service = SkillService(session)
        skill = await service.upload_skill(
            name=name,
            user=current_user,
            zip_file_path=tmp_path,
        )
        return skill
    finally:
        # 清理临时文件
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@router.get("", response_model=SkillListResponse)
async def list_skills(
    source_type: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    session: AsyncSession = Depends(get_db_session),
):
    """列出所有 Skills"""
    service = SkillService(session)
    skills, total = await service.list_skills(
        source_type=source_type,
        page=page,
        page_size=page_size,
    )
    
    return SkillListResponse(
        items=[SkillResponse.model_validate(s) for s in skills],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{skill_id}", response_model=SkillDetailResponse)
async def get_skill(
    skill_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """获取 Skill 详情"""
    service = SkillService(session)
    skill = await service.get_skill(skill_id)
    
    if not skill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Skill 不存在",
        )
    
    # 获取文件列表
    from sqlalchemy import select
    from app.db.models import SkillFile
    
    result = await session.execute(
        select(SkillFile).where(SkillFile.skill_id == skill.id)
    )
    files = result.scalars().all()
    
    # 读取 SKILL.md 内容
    skill_md_content = None
    settings = get_settings()
    skill_md_path = settings.private_skills_path / skill.name / "SKILL.md"
    if skill_md_path.exists():
        async with aiofiles.open(skill_md_path, "r", encoding="utf-8") as f:
            skill_md_content = await f.read()
    
    return SkillDetailResponse(
        skill=SkillResponse.model_validate(skill),
        files=[SkillFileResponse(
            file_path=f.file_path,
            file_name=f.file_name,
            file_size=f.file_size,
            file_type=f.file_type,
            is_skill_md=f.is_skill_md,
        ) for f in files],
        skill_md_content=skill_md_content,
    )


@router.put("/{skill_id}", response_model=SkillResponse)
async def update_skill(
    skill_id: str,
    skill_data: SkillUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """更新 Skill"""
    service = SkillService(session)
    skill = await service.update_skill(
        skill_id=skill_id,
        user=current_user,
        skill_md_content=skill_data.skill_md_content,
        files=skill_data.files,
    )
    return skill


@router.delete("/{skill_id}")
async def delete_skill(
    skill_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """删除 Skill"""
    service = SkillService(session)
    await service.delete_skill(skill_id=skill_id, user=current_user)
    return {"message": "删除成功"}


@router.post("/{skill_id}/lock", response_model=LockResponse)
async def acquire_lock(
    skill_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """获取编辑锁"""
    service = SkillService(session)
    await service.acquire_lock(skill_id=skill_id, user=current_user)
    
    skill = await service.get_skill(skill_id)
    return LockResponse(
        skill_id=skill_id,
        is_locked=True,
        locked_by=current_user.id,
        locked_at=datetime.now(UTC),
    )


@router.delete("/{skill_id}/lock", response_model=LockResponse)
async def release_lock(
    skill_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """释放编辑锁"""
    service = SkillService(session)
    await service.release_lock(skill_id=skill_id, user=current_user)
    
    return LockResponse(
        skill_id=skill_id,
        is_locked=False,
        locked_by=None,
        locked_at=None,
    )


@router.post("/{skill_id}/takeover-lock", response_model=LockResponse)
async def takeover_lock(
    skill_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """接管编辑锁"""
    service = SkillService(session)
    await service.takeover_lock(skill_id=skill_id, user=current_user)
    
    return LockResponse(
        skill_id=skill_id,
        is_locked=True,
        locked_by=current_user.id,
        locked_at=datetime.now(UTC),
    )


@router.get("/{skill_id}/download")
async def download_skill(
    skill_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """下载 Skill 包"""
    service = SkillService(session)
    skill = await service.get_skill(skill_id)
    
    if not skill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Skill 不存在",
        )
    
    # 检查下载权限
    permission_service = PermissionService(session)
    await permission_service.check_skill_permission(
        current_user, skill, PermissionAction.DOWNLOAD
    )
    
    # 创建 ZIP 文件
    import shutil
    import tempfile
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
        tmp_path = tmp.name
    
    try:
        shutil.make_archive(
            tmp_path[:-4],  # 去掉 .zip 后缀
            "zip",
            skill.storage_path,
        )
        
        return FileResponse(
            path=tmp_path,
            filename=f"{skill.name}.zip",
            media_type="application/zip",
        )
    finally:
        # 注意：FileResponse 会在发送后自动清理文件
        pass


@router.get("/{skill_id}/files/{file_path:path}")
async def get_skill_file(
    skill_id: str,
    file_path: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """获取 Skill 文件内容"""
    service = SkillService(session)
    skill = await service.get_skill(skill_id)
    
    if not skill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Skill 不存在",
        )
    
    # 构建文件路径
    settings = get_settings()
    full_path = settings.private_skills_path / skill.name / file_path
    
    # 安全检查：防止路径穿越
    try:
        full_path.resolve().relative_to(settings.private_skills_path.resolve())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="禁止访问",
        )
    
    if not full_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件不存在",
        )
    
    return FileResponse(path=full_path)
