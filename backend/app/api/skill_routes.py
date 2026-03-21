"""
Skill 路由

处理 Skill 的 CRUD 操作
"""
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime, UTC
from typing import Optional, Generator

import aiofiles
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.background import BackgroundTask

from app.auth.dependencies import get_current_user
from app.auth.permissions import PermissionService, PermissionAction
from app.core.config import get_settings
from app.core.exceptions import SkillNotFoundError
from app.db.database import get_db_session
from app.db.models import Skill, User
from app.services.skill_service import SkillService


router = APIRouter(prefix="/skills", tags=["Skill管理"])


# ==================== 临时文件管理 ====================

@contextmanager
def temp_file_manager(suffix: Optional[str] = None, auto_cleanup: bool = True) -> Generator[str, None, None]:
    """
    临时文件上下文管理器
    
    确保在任何情况下（包括异常）都能清理临时文件
    
    Args:
        suffix: 临时文件后缀，例如 ".zip"
        auto_cleanup: 是否自动清理文件，默认为 True
        
    Yields:
        str: 临时文件的绝对路径
        
    Example:
        with temp_file_manager(suffix=".zip") as tmp_path:
            # 使用临时文件
            process_file(tmp_path)
        # 离开上下文后自动清理文件
    """
    # 创建临时文件（不自动删除，由上下文管理器控制）
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp_path = tmp.name
    
    try:
        yield tmp_path
    finally:
        # 在任何情况下都尝试清理临时文件
        if auto_cleanup and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception as e:
                # 记录错误但不抛出异常，避免掩盖原始异常
                import logging
                logging.warning(f"清理临时文件失败: {tmp_path}, 错误: {e}")


def cleanup_temp_file(file_path: str) -> None:
    """
    清理临时文件的辅助函数
    
    用于 BackgroundTask 中异步清理文件
    
    Args:
        file_path: 要清理的文件路径
    """
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception as e:
            import logging
            logging.warning(f"清理临时文件失败: {file_path}, 错误: {e}")


# ==================== 请求/响应模型 ====================

class SkillCreate(BaseModel):
    """创建 Skill 请求"""
    name: str = Field(..., min_length=1, pattern=r"^[a-zA-Z0-9_-]+$")
    skill_md_content: Optional[str] = None
    
    @field_validator("name")
    @classmethod
    def validate_name_length(cls, v: str) -> str:
        """验证名称长度不超过配置的最大值"""
        settings = get_settings()
        if len(v) > settings.max_skill_name_length:
            raise ValueError(f"名称长度不能超过 {settings.max_skill_name_length} 个字符")
        return v


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
    """
    上传 ZIP 包创建 Skill
    
    使用临时文件上下文管理器确保文件在任何情况下都会被清理
    """
    settings = get_settings()
    
    # 验证文件类型
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只支持 ZIP 文件",
        )
    
    # 使用上下文管理器管理临时文件，确保异常时也能清理
    with temp_file_manager(suffix=".zip") as tmp_path:
        # 异步读取上传的文件内容
        content = await file.read()
        
        # 在线程池中执行同步的文件写入操作
        await run_in_threadpool(
            lambda: open(tmp_path, "wb").write(content)
        )
        
        # 调用服务层处理上传逻辑
        service = SkillService(session)
        skill = await service.upload_skill(
            name=name,
            user=current_user,
            zip_file_path=tmp_path,
        )
        
        return skill


@router.get("", response_model=SkillListResponse)
async def list_skills(
    source_type: Optional[str] = None,
    page: int = 1,
    page_size: Optional[int] = None,
    session: AsyncSession = Depends(get_db_session),
):
    """列出所有 Skills"""
    # 使用配置中的默认分页大小
    settings = get_settings()
    if page_size is None:
        page_size = settings.default_page_size
    
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
    """
    下载 Skill 包
    
    使用临时文件上下文管理器创建 ZIP 文件，
    并通过 BackgroundTask 在响应发送后清理临时文件
    """
    import shutil
    
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
    
    # 使用上下文管理器创建临时文件（不自动清理，由 BackgroundTask 处理）
    with temp_file_manager(suffix=".zip", auto_cleanup=False) as tmp_path:
        # 在线程池中执行同步的压缩操作
        await run_in_threadpool(
            shutil.make_archive,
            tmp_path[:-4],  # 去掉 .zip 后缀
            "zip",
            skill.storage_path,
        )
        
        # 返回文件响应，使用 BackgroundTask 在发送后清理临时文件
        return FileResponse(
            path=tmp_path,
            filename=f"{skill.name}.zip",
            media_type="application/zip",
            background=BackgroundTask(cleanup_temp_file, tmp_path),
        )


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
