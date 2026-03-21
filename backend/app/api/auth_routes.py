"""
认证路由

处理用户登录、注册、令牌刷新等
"""
from datetime import datetime, UTC
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, get_current_admin
from app.auth.jwt_service import token_service, password_service
from app.core.config import RunMode, get_settings
from app.core.exceptions import AuthenticationError
from app.db.database import get_db_session
from app.db.models import User, SystemRole


router = APIRouter(prefix="/auth", tags=["认证"])


# ==================== 请求/响应模型 ====================

class UserCreate(BaseModel):
    """用户注册请求"""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=100)


class UserLogin(BaseModel):
    """用户登录请求"""
    username: str
    password: str


class UserResponse(BaseModel):
    """用户响应"""
    id: str
    username: str
    email: str
    system_role: str
    is_active: bool
    created_at: datetime
    last_login_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """令牌响应"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class PasswordChange(BaseModel):
    """修改密码请求"""
    old_password: str
    new_password: str = Field(..., min_length=6, max_length=100)


# ==================== 路由 ====================

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    session: AsyncSession = Depends(get_db_session),
):
    """用户注册"""
    settings = get_settings()
    
    # 检查运行模式
    if settings.run_mode == RunMode.READONLY_ANONYMOUS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只读模式不允许注册",
        )
    
    # 检查用户名是否已存在
    result = await session.execute(
        select(User).where(User.username == user_data.username)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已存在",
        )
    
    # 检查邮箱是否已存在
    result = await session.execute(
        select(User).where(User.email == user_data.email)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邮箱已被注册",
        )
    
    # 创建用户
    hashed_password = password_service.hash_password(user_data.password)
    
    user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_password,
        system_role=SystemRole.MEMBER,
        is_active=True,
    )
    
    session.add(user)
    await session.commit()
    await session.refresh(user)
    
    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: UserLogin,
    session: AsyncSession = Depends(get_db_session),
):
    """用户登录"""
    settings = get_settings()
    
    # 初始化管理模式
    if settings.run_mode == RunMode.BOOTSTRAP_ADMIN:
        if settings.bootstrap_token:
            return TokenResponse(
                access_token=settings.bootstrap_token,
                refresh_token=settings.bootstrap_token,
                expires_in=settings.access_token_expire_minutes * 60,
            )
    
    # 查找用户
    result = await session.execute(
        select(User).where(User.username == credentials.username)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户已被禁用",
        )
    
    # 验证密码
    if not password_service.verify_password(
        credentials.password, user.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )
    
    # 更新最后登录时间
    user.last_login_at = datetime.now(UTC)
    await session.commit()
    
    # 生成令牌
    access_token = token_service.create_access_token(
        user_id=user.id,
        username=user.username,
        system_role=user.system_role,
    )
    
    refresh_token = token_service.create_refresh_token(
        user_id=user.id,
        username=user.username,
        system_role=user.system_role,
    )
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_token: str,
    session: AsyncSession = Depends(get_db_session),
):
    """刷新令牌"""
    # 验证刷新令牌
    token_data = token_service.verify_refresh_token(refresh_token)
    
    # 查找用户
    result = await session.execute(
        select(User).where(User.id == token_data.user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在或已被禁用",
        )
    
    # 生成新令牌
    access_token = token_service.create_access_token(
        user_id=user.id,
        username=user.username,
        system_role=user.system_role,
    )
    
    new_refresh_token = token_service.create_refresh_token(
        user_id=user.id,
        username=user.username,
        system_role=user.system_role,
    )
    
    settings = get_settings()
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
):
    """获取当前用户信息"""
    return current_user


@router.post("/change-password")
async def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """修改密码"""
    # 验证旧密码
    if not password_service.verify_password(
        password_data.old_password, current_user.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="旧密码错误",
        )
    
    # 更新密码
    current_user.hashed_password = password_service.hash_password(
        password_data.new_password
    )
    current_user.updated_at = datetime.now(UTC)
    
    await session.commit()
    
    return {"message": "密码修改成功"}


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db_session),
):
    """列出所有用户（管理员）"""
    result = await session.execute(select(User))
    return list(result.scalars().all())


@router.put("/users/{user_id}/role")
async def update_user_role(
    user_id: str,
    role: str,
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db_session),
):
    """更新用户角色（管理员）"""
    if role not in [SystemRole.ADMIN, SystemRole.MEMBER]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的角色",
        )
    
    result = await session.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )
    
    user.system_role = role
    user.updated_at = datetime.now(UTC)
    
    await session.commit()
    
    return {"message": f"用户角色已更新为 {role}"}
