"""
权限服务模块

实现 RBAC 权限控制：
- 系统角色：admin, member
- 资源角色：owner, maintainer, editor, viewer
"""
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import RunMode, get_settings
from app.core.exceptions import AuthorizationError
from app.db.models import (
    ResourceRole,
    Skill,
    SystemRole,
    User,
    UserResourceRole,
)


class PermissionAction:
    """权限操作常量"""
    VIEW = "view"
    DOWNLOAD = "download"
    EDIT = "edit"
    DELETE = "delete"
    SYNC = "sync"
    IMPORT = "import"
    TAKEOVER_LOCK = "takeover_lock"
    ASSIGN_ROLE = "assign_role"
    USER_MANAGE = "user_manage"
    SYSTEM_CONFIG = "system_config"
    LOG_VIEW = "log_view"
    INDEX_REBUILD = "index_rebuild"
    FULL_SYNC = "full_sync"
    BACKUP_RESTORE = "backup_restore"


# Skill 权限矩阵
SKILL_PERMISSION_MATRIX = {
    PermissionAction.VIEW: [SystemRole.ADMIN, SystemRole.MEMBER],
    PermissionAction.DOWNLOAD: [SystemRole.ADMIN, SystemRole.MEMBER],
    PermissionAction.EDIT: [SystemRole.ADMIN, ResourceRole.OWNER, ResourceRole.MAINTAINER, ResourceRole.EDITOR],
    PermissionAction.DELETE: [SystemRole.ADMIN, ResourceRole.OWNER],
    PermissionAction.TAKEOVER_LOCK: [SystemRole.ADMIN, ResourceRole.OWNER],
    PermissionAction.ASSIGN_ROLE: [SystemRole.ADMIN, ResourceRole.OWNER],
}

# Git 仓库权限矩阵
REPO_PERMISSION_MATRIX = {
    PermissionAction.VIEW: [SystemRole.ADMIN, SystemRole.MEMBER],
    PermissionAction.DOWNLOAD: [SystemRole.ADMIN, SystemRole.MEMBER],
    PermissionAction.IMPORT: [SystemRole.ADMIN],
    PermissionAction.SYNC: [SystemRole.ADMIN, ResourceRole.OWNER, ResourceRole.MAINTAINER],
    PermissionAction.DELETE: [SystemRole.ADMIN, ResourceRole.OWNER],
    PermissionAction.ASSIGN_ROLE: [SystemRole.ADMIN, ResourceRole.OWNER],
}

# 系统级权限矩阵
SYSTEM_PERMISSION_MATRIX = {
    PermissionAction.USER_MANAGE: [SystemRole.ADMIN],
    PermissionAction.SYSTEM_CONFIG: [SystemRole.ADMIN],
    PermissionAction.LOG_VIEW: [SystemRole.ADMIN],
    PermissionAction.INDEX_REBUILD: [SystemRole.ADMIN],
    PermissionAction.FULL_SYNC: [SystemRole.ADMIN],
    PermissionAction.BACKUP_RESTORE: [SystemRole.ADMIN],
}


class PermissionService:
    """权限服务"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user_resource_role(
        self,
        user_id: str,
        resource_type: str,
        resource_id: str,
    ) -> Optional[str]:
        """获取用户在资源上的角色"""
        result = await self.session.execute(
            select(UserResourceRole).where(
                and_(
                    UserResourceRole.user_id == user_id,
                    UserResourceRole.resource_type == resource_type,
                    UserResourceRole.resource_id == resource_id,
                )
            )
        )
        role = result.scalar_one_or_none()
        return role.role if role else None

    async def check_skill_permission(
        self,
        user: User,
        skill: Skill,
        action: str,
    ) -> bool:
        """检查 Skill 权限"""
        settings = get_settings()
        
        # 只读匿名模式：只允许查看和下载
        if settings.run_mode == RunMode.READONLY_ANONYMOUS:
            if action not in [PermissionAction.VIEW, PermissionAction.DOWNLOAD]:
                raise AuthorizationError("只读模式下不允许此操作")
            return True
        
        # 初始化管理模式：允许所有操作
        if settings.run_mode == RunMode.BOOTSTRAP_ADMIN:
            return True
        
        # 系统管理员拥有所有权限
        if user.system_role == SystemRole.ADMIN:
            return True
        
        # 查看和下载权限：所有成员都有
        if action in [PermissionAction.VIEW, PermissionAction.DOWNLOAD]:
            return True
        
        # 获取用户在该资源上的角色
        resource_role = await self.get_user_resource_role(
            user.id, "skill", skill.id
        )
        
        # 检查权限矩阵
        allowed_roles = SKILL_PERMISSION_MATRIX.get(action, [])
        
        if SystemRole.ADMIN in allowed_roles and user.system_role == SystemRole.ADMIN:
            return True
        
        if resource_role and resource_role in allowed_roles:
            return True
        
        raise AuthorizationError(f"没有权限执行操作: {action}")

    async def check_repo_permission(
        self,
        user: User,
        repo_id: str,
        action: str,
    ) -> bool:
        """检查 Git 仓库权限"""
        settings = get_settings()
        
        # 只读匿名模式：只允许查看和下载
        if settings.run_mode == RunMode.READONLY_ANONYMOUS:
            if action not in [PermissionAction.VIEW, PermissionAction.DOWNLOAD]:
                raise AuthorizationError("只读模式下不允许此操作")
            return True
        
        # 初始化管理模式：允许所有操作
        if settings.run_mode == RunMode.BOOTSTRAP_ADMIN:
            return True
        
        # 系统管理员拥有所有权限
        if user.system_role == SystemRole.ADMIN:
            return True
        
        # 查看和下载权限：所有成员都有
        if action in [PermissionAction.VIEW, PermissionAction.DOWNLOAD]:
            return True
        
        # 导入权限：仅管理员
        if action == PermissionAction.IMPORT:
            raise AuthorizationError("只有管理员可以导入 Git 仓库")
        
        # 获取用户在该资源上的角色
        resource_role = await self.get_user_resource_role(
            user.id, "repo", repo_id
        )
        
        # 检查权限矩阵
        allowed_roles = REPO_PERMISSION_MATRIX.get(action, [])
        
        if SystemRole.ADMIN in allowed_roles and user.system_role == SystemRole.ADMIN:
            return True
        
        if resource_role and resource_role in allowed_roles:
            return True
        
        raise AuthorizationError(f"没有权限执行操作: {action}")

    async def check_system_permission(
        self,
        user: User,
        action: str,
    ) -> bool:
        """检查系统级权限"""
        settings = get_settings()
        
        # 只读匿名模式：不允许任何系统操作
        if settings.run_mode == RunMode.READONLY_ANONYMOUS:
            raise AuthorizationError("只读模式下不允许此操作")
        
        # 初始化管理模式：允许所有操作
        if settings.run_mode == RunMode.BOOTSTRAP_ADMIN:
            return True
        
        # 检查权限矩阵
        allowed_roles = SYSTEM_PERMISSION_MATRIX.get(action, [])
        
        if SystemRole.ADMIN in allowed_roles and user.system_role == SystemRole.ADMIN:
            return True
        
        raise AuthorizationError(f"没有权限执行操作: {action}")

    async def assign_resource_role(
        self,
        user_id: str,
        resource_type: str,
        resource_id: str,
        role: str,
    ) -> UserResourceRole:
        """分配资源角色"""
        # 检查是否已存在
        existing = await self.get_user_resource_role(
            user_id, resource_type, resource_id
        )
        
        if existing:
            # 更新角色
            result = await self.session.execute(
                select(UserResourceRole).where(
                    and_(
                        UserResourceRole.user_id == user_id,
                        UserResourceRole.resource_type == resource_type,
                        UserResourceRole.resource_id == resource_id,
                    )
                )
            )
            role_record = result.scalar_one()
            role_record.role = role
            await self.session.commit()
            return role_record
        
        # 创建新角色
        role_record = UserResourceRole(
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            role=role,
        )
        self.session.add(role_record)
        await self.session.commit()
        return role_record

    async def remove_resource_role(
        self,
        user_id: str,
        resource_type: str,
        resource_id: str,
    ) -> bool:
        """移除资源角色"""
        result = await self.session.execute(
            select(UserResourceRole).where(
                and_(
                    UserResourceRole.user_id == user_id,
                    UserResourceRole.resource_type == resource_type,
                    UserResourceRole.resource_id == resource_id,
                )
            )
        )
        role_record = result.scalar_one_or_none()
        
        if role_record:
            await self.session.delete(role_record)
            await self.session.commit()
            return True
        
        return False
