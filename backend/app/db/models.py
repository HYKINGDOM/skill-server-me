"""
数据库模型模块

定义所有数据库表结构
"""
from datetime import datetime
from typing import Optional
import uuid

from sqlmodel import Field, Relationship, SQLModel


def generate_uuid() -> str:
    """生成 UUID 字符串"""
    return str(uuid.uuid4())


# ==================== 用户相关模型 ====================

class SystemRole:
    """系统角色常量"""
    ADMIN = "admin"
    MEMBER = "member"


class ResourceRole:
    """资源角色常量"""
    OWNER = "owner"
    MAINTAINER = "maintainer"
    EDITOR = "editor"
    VIEWER = "viewer"


class User(SQLModel, table=True):
    """用户表"""
    __tablename__ = "users"

    id: str = Field(default_factory=generate_uuid, primary_key=True)
    username: str = Field(unique=True, index=True, max_length=50)
    email: str = Field(unique=True, index=True, max_length=255)
    hashed_password: str = Field(max_length=255)
    system_role: str = Field(default=SystemRole.MEMBER, max_length=20)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_login_at: Optional[datetime] = Field(default=None)

    # 关系
    resource_roles: list["UserResourceRole"] = Relationship(back_populates="user")
    favorites: list["Favorite"] = Relationship(back_populates="user")
    notifications: list["Notification"] = Relationship(back_populates="user")
    audit_logs: list["AuditLog"] = Relationship(back_populates="user")


class UserResourceRole(SQLModel, table=True):
    """用户资源角色关联表"""
    __tablename__ = "user_resource_roles"

    id: str = Field(default_factory=generate_uuid, primary_key=True)
    user_id: str = Field(foreign_key="users.id", index=True)
    resource_type: str = Field(max_length=20)  # skill, repo
    resource_id: str = Field(index=True)
    role: str = Field(max_length=20)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # 关系
    user: Optional[User] = Relationship(back_populates="resource_roles")


# ==================== Skill 相关模型 ====================

class SkillSourceType:
    """Skill 来源类型"""
    PRIVATE = "private"
    GIT = "git"


class Skill(SQLModel, table=True):
    """Skill 表"""
    __tablename__ = "skills"

    id: str = Field(default_factory=generate_uuid, primary_key=True)
    name: str = Field(unique=True, index=True, max_length=100)
    source_type: str = Field(max_length=20, default=SkillSourceType.PRIVATE)
    
    # Git 来源信息
    git_repo_id: Optional[str] = Field(default=None, foreign_key="git_repos.id", index=True)
    
    # 元数据（从 SKILL.md 提取）
    title: Optional[str] = Field(default=None, max_length=200)
    summary: Optional[str] = Field(default=None)
    tags: Optional[str] = Field(default=None)  # JSON 数组字符串
    
    # 文件系统路径
    storage_path: str = Field(max_length=500)
    
    # 编辑锁
    is_locked: bool = Field(default=False)
    locked_by: Optional[str] = Field(default=None, foreign_key="users.id")
    locked_at: Optional[datetime] = Field(default=None)
    
    # 状态
    is_active: bool = Field(default=True)
    
    # 时间戳
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: Optional[str] = Field(default=None, foreign_key="users.id")
    
    # 关系
    versions: list["SkillVersion"] = Relationship(back_populates="skill")
    favorites: list["Favorite"] = Relationship(back_populates="skill")
    timeline_events: list["TimelineEvent"] = Relationship(back_populates="skill")
    files: list["SkillFile"] = Relationship(back_populates="skill")
    git_repo: Optional["GitRepo"] = Relationship(back_populates="skills")


class SkillFile(SQLModel, table=True):
    """Skill 文件表"""
    __tablename__ = "skill_files"

    id: str = Field(default_factory=generate_uuid, primary_key=True)
    skill_id: str = Field(foreign_key="skills.id", index=True)
    file_path: str = Field(max_length=500)  # 相对于 Skill 根目录的路径
    file_name: str = Field(max_length=255)
    file_size: int = Field(default=0)
    file_type: str = Field(max_length=50)  # mime type
    checksum: Optional[str] = Field(default=None, max_length=64)  # SHA256
    is_skill_md: bool = Field(default=False)  # 是否为 SKILL.md
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # 关系
    skill: Optional[Skill] = Relationship(back_populates="files")


class SkillVersion(SQLModel, table=True):
    """Skill 版本表"""
    __tablename__ = "skill_versions"

    id: str = Field(default_factory=generate_uuid, primary_key=True)
    skill_id: str = Field(foreign_key="skills.id", index=True)
    version_number: int = Field(default=1)
    version_hash: str = Field(max_length=64)  # Git commit hash 或内容哈希
    
    # 变更信息
    change_summary: Optional[str] = Field(default=None)
    changed_files: Optional[str] = Field(default=None)  # JSON 数组
    
    # 快照存储
    snapshot_path: str = Field(max_length=500)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: Optional[str] = Field(default=None, foreign_key="users.id")
    
    # 关系
    skill: Optional[Skill] = Relationship(back_populates="versions")


# ==================== Git 仓库相关模型 ====================

class GitRepo(SQLModel, table=True):
    """Git 仓库表"""
    __tablename__ = "git_repos"

    id: str = Field(default_factory=generate_uuid, primary_key=True)
    name: str = Field(unique=True, index=True, max_length=100)
    url: str = Field(max_length=500)
    branch: str = Field(default="main", max_length=100)
    
    # 认证信息（加密存储）
    auth_type: Optional[str] = Field(default=None, max_length=20)  # ssh_key, token, none
    auth_secret_ref: Optional[str] = Field(default=None, max_length=255)  # 密钥引用
    
    # 同步状态
    last_sync_at: Optional[datetime] = Field(default=None)
    last_sync_commit: Optional[str] = Field(default=None, max_length=64)
    sync_status: str = Field(default="pending", max_length=20)  # pending, syncing, success, failed
    sync_error: Optional[str] = Field(default=None)
    
    # 本地镜像路径
    mirror_path: str = Field(max_length=500)
    
    # 状态
    is_active: bool = Field(default=True)
    auto_sync: bool = Field(default=True)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: Optional[str] = Field(default=None, foreign_key="users.id")
    
    # 关系
    skills: list[Skill] = Relationship(back_populates="git_repo")


# ==================== 时间线模型 ====================

class TimelineEventType:
    """时间线事件类型"""
    SKILL_CREATED = "skill_created"
    SKILL_UPDATED = "skill_updated"
    SKILL_DELETED = "skill_deleted"
    VERSION_CREATED = "version_created"
    FILE_ADDED = "file_added"
    FILE_MODIFIED = "file_modified"
    FILE_DELETED = "file_deleted"
    GIT_SYNC = "git_sync"


class TimelineEvent(SQLModel, table=True):
    """时间线事件表"""
    __tablename__ = "timeline_events"

    id: str = Field(default_factory=generate_uuid, primary_key=True)
    skill_id: str = Field(foreign_key="skills.id", index=True)
    event_type: str = Field(max_length=30)
    event_data: Optional[str] = Field(default=None)  # JSON
    
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    created_by: Optional[str] = Field(default=None, foreign_key="users.id")
    
    # 关系
    skill: Optional[Skill] = Relationship(back_populates="timeline_events")


# ==================== 收藏模型 ====================

class Favorite(SQLModel, table=True):
    """收藏表"""
    __tablename__ = "favorites"

    id: str = Field(default_factory=generate_uuid, primary_key=True)
    user_id: str = Field(foreign_key="users.id", index=True)
    skill_id: str = Field(foreign_key="skills.id", index=True)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # 关系
    user: Optional[User] = Relationship(back_populates="favorites")
    skill: Optional[Skill] = Relationship(back_populates="favorites")


# ==================== 通知模型 ====================

class NotificationType:
    """通知类型"""
    SYSTEM = "system"
    SKILL_SHARED = "skill_shared"
    SKILL_UPDATED = "skill_updated"
    EDIT_LOCK_RELEASED = "edit_lock_released"
    GIT_SYNC_COMPLETED = "git_sync_completed"
    GIT_SYNC_FAILED = "git_sync_failed"


class Notification(SQLModel, table=True):
    """通知表"""
    __tablename__ = "notifications"

    id: str = Field(default_factory=generate_uuid, primary_key=True)
    user_id: str = Field(foreign_key="users.id", index=True)
    notification_type: str = Field(max_length=30)
    title: str = Field(max_length=200)
    content: Optional[str] = Field(default=None)
    is_read: bool = Field(default=False)
    
    # 关联资源
    resource_type: Optional[str] = Field(default=None, max_length=20)
    resource_id: Optional[str] = Field(default=None)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    read_at: Optional[datetime] = Field(default=None)
    
    # 关系
    user: Optional[User] = Relationship(back_populates="notifications")


# ==================== 审计日志模型 ====================

class AuditLog(SQLModel, table=True):
    """审计日志表"""
    __tablename__ = "audit_logs"

    id: str = Field(default_factory=generate_uuid, primary_key=True)
    user_id: Optional[str] = Field(default=None, foreign_key="users.id", index=True)
    action: str = Field(max_length=50, index=True)
    resource_type: str = Field(max_length=20)
    resource_id: Optional[str] = Field(default=None, index=True)
    
    # 变更详情
    old_value: Optional[str] = Field(default=None)  # JSON
    new_value: Optional[str] = Field(default=None)  # JSON
    
    # 请求信息
    ip_address: Optional[str] = Field(default=None, max_length=45)
    user_agent: Optional[str] = Field(default=None, max_length=500)
    
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    
    # 关系
    user: Optional[User] = Relationship(back_populates="audit_logs")


# ==================== 系统配置模型 ====================

class SystemConfig(SQLModel, table=True):
    """系统配置表"""
    __tablename__ = "system_configs"

    id: str = Field(default_factory=generate_uuid, primary_key=True)
    key: str = Field(unique=True, index=True, max_length=100)
    value: str = Field(max_length=2000)
    description: Optional[str] = Field(default=None, max_length=500)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
