"""
认证依赖模块

FastAPI 依赖注入：获取当前用户、验证权限
"""
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import RunMode, get_settings
from app.core.exceptions import AuthenticationError, AuthorizationError
from app.auth.jwt_service import token_service
from app.db.database import get_db_session
from app.db.models import User


security = HTTPBearer(auto_error=False)


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    session: AsyncSession = Depends(get_db_session),
) -> Optional[User]:
    """获取当前用户（可选）"""
    if not credentials:
        return None
    
    try:
        token_data = token_service.verify_access_token(credentials.credentials)
        
        result = await session.execute(
            select(User).where(User.id == token_data.user_id)
        )
        user = result.scalar_one_or_none()
        
        if user and user.is_active:
            return user
        
        return None
        
    except Exception:
        return None


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    session: AsyncSession = Depends(get_db_session),
) -> User:
    """获取当前用户（必须登录）"""
    settings = get_settings()
    
    # 只读匿名模式：返回匿名用户
    if settings.run_mode == RunMode.READONLY_ANONYMOUS:
        raise AuthenticationError("只读模式不需要登录")
    
    # 初始化管理模式：返回引导管理员
    if settings.run_mode == RunMode.BOOTSTRAP_ADMIN:
        # 验证引导令牌
        if settings.bootstrap_token:
            if not credentials or credentials.credentials != settings.bootstrap_token:
                raise AuthenticationError("无效的引导令牌")
        
        # 返回虚拟管理员用户
        return User(
            id="bootstrap_admin",
            username=settings.bootstrap_admin_username,
            email="bootstrap@skillshub.local",
            system_role="admin",
            is_active=True,
        )
    
    # 正常登录模式
    if not credentials:
        raise AuthenticationError("未提供认证令牌")
    
    token_data = token_service.verify_access_token(credentials.credentials)
    
    result = await session.execute(
        select(User).where(User.id == token_data.user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise AuthenticationError("用户不存在")
    
    if not user.is_active:
        raise AuthenticationError("用户已被禁用")
    
    return user


async def get_current_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """获取当前管理员用户"""
    if current_user.system_role != "admin":
        raise AuthorizationError("需要管理员权限")
    return current_user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """获取当前活跃用户"""
    if not current_user.is_active:
        raise AuthenticationError("用户已被禁用")
    return current_user
