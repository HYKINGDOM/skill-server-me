"""
系统配置模块

支持三种运行模式：
1. 登录开启模式（推荐生产环境）
2. 只读匿名模式（推荐对外展示）
3. 初始化管理模式（仅限初始化阶段）
"""
import os
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class RunMode(str, Enum):
    """运行模式枚举"""
    LOGIN_REQUIRED = "login_required"      # 登录开启模式
    READONLY_ANONYMOUS = "readonly_anonymous"  # 只读匿名模式
    BOOTSTRAP_ADMIN = "bootstrap_admin"    # 初始化管理模式


class DatabaseType(str, Enum):
    """数据库类型枚举"""
    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"


class Settings(BaseSettings):
    """系统配置类"""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # 基础配置
    app_name: str = "Skills Hub"
    app_version: str = "1.0.0"
    debug: bool = False
    run_mode: RunMode = RunMode.LOGIN_REQUIRED

    # 服务器配置
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1

    # 数据库配置
    database_type: DatabaseType = DatabaseType.SQLITE
    database_url: Optional[str] = None
    sqlite_db_path: str = "data/db/skills_hub.db"

    # 安全配置
    secret_key: str = Field(default="change-me-in-production-with-a-secure-random-key")
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    algorithm: str = "HS256"
    
    # 加密配置
    encryption_key: Optional[str] = None  # Fernet 加密密钥，用于加密敏感数据

    # 初始化管理模式配置
    bootstrap_token: Optional[str] = None
    bootstrap_admin_username: str = "bootstrap_admin"

    # 文件上传配置
    max_file_size_mb: int = 50
    max_total_upload_size_mb: int = 500
    max_files_per_upload: int = 1000

    # 工作区路径配置
    workspace_root: str = "workspace"
    private_skills_dir: str = "private-skills"
    mirrors_dir: str = "mirrors"

    # 数据路径配置
    data_root: str = "data"
    index_dir: str = "index"
    packages_dir: str = "packages"
    cache_dir: str = "cache"
    logs_dir: str = "logs"

    # Git 配置
    git_allowed_domains: list[str] = Field(
        default_factory=lambda: ["github.com", "gitlab.com", "bitbucket.org"]
    )
    git_blocked_ip_ranges: list[str] = Field(
        default_factory=lambda: ["127.0.0.0/8", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"]
    )
    git_sync_interval_hours: int = 24

    # 搜索配置
    fulltext_index_path: str = "data/index/fulltext"
    vector_index_path: str = "data/index/vector"
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    search_results_per_page: int = 20

    # 分页配置
    default_page_size: int = 20  # 默认分页大小
    max_page_size: int = 100     # 最大分页大小

    # Skill 配置
    lock_timeout_minutes: int = 30   # 编辑锁超时时间（分钟）
    max_skill_name_length: int = 100  # Skill名称最大长度

    # OIDC 配置（可选）
    oidc_enabled: bool = False
    oidc_client_id: Optional[str] = None
    oidc_client_secret: Optional[str] = None
    oidc_discovery_url: Optional[str] = None

    # CORS 配置
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173", "http://localhost:3000"])
    cors_allow_credentials: bool = True
    cors_allow_methods: list[str] = Field(default_factory=lambda: ["*"])
    cors_allow_headers: list[str] = Field(default_factory=lambda: ["*"])

    @model_validator(mode='after')
    def validate_secret_key(self) -> 'Settings':
        """
        验证 SECRET_KEY 配置
        
        生产环境（debug=False）下强制验证：
        1. SECRET_KEY 必须从环境变量读取
        2. SECRET_KEY 长度必须至少为32字符
        
        Raises:
            ValueError: 当验证失败时抛出配置错误
        """
        # 生产环境验证
        if not self.debug:
            # 检查是否从环境变量读取
            env_secret_key = os.getenv('SECRET_KEY')
            if not env_secret_key:
                raise ValueError(
                    "生产环境必须通过 SECRET_KEY 环境变量设置密钥"
                )
            
            # 验证密钥长度
            if len(self.secret_key) < 32:
                raise ValueError(
                    "SECRET_KEY 长度必须至少为32字符"
                )
        else:
            # 开发环境警告
            if self.secret_key == "change-me-in-production-with-a-secure-random-key":
                import warnings
                warnings.warn(
                    "使用默认 SECRET_KEY，请在生产环境中设置安全的密钥！",
                    UserWarning,
                    stacklevel=2,
                )
        
        return self
    
    @model_validator(mode='after')
    def validate_encryption_key(self) -> 'Settings':
        """
        验证 ENCRYPTION_KEY 配置
        
        生产环境（debug=False）下强制验证：
        1. ENCRYPTION_KEY 必须从环境变量读取
        2. ENCRYPTION_KEY 必须是有效的 Fernet 密钥格式
        
        Raises:
            ValueError: 当验证失败时抛出配置错误
        """
        from cryptography.fernet import Fernet
        
        # 生产环境验证
        if not self.debug:
            # 检查是否从环境变量读取
            env_encryption_key = os.getenv('ENCRYPTION_KEY')
            if not env_encryption_key:
                raise ValueError(
                    "生产环境必须通过 ENCRYPTION_KEY 环境变量设置加密密钥"
                )
            
            # 验证密钥格式
            try:
                Fernet(env_encryption_key.encode())
            except Exception as e:
                raise ValueError(
                    f"ENCRYPTION_KEY 不是有效的 Fernet 密钥格式: {str(e)}"
                )
        else:
            # 开发环境警告
            if not self.encryption_key:
                import warnings
                warnings.warn(
                    "未配置 ENCRYPTION_KEY，Git 认证信息将无法加密存储！"
                    "请使用 EncryptionService.generate_key() 生成密钥并设置到环境变量。",
                    UserWarning,
                    stacklevel=2,
                )
        
        return self

    @property
    def database_url_computed(self) -> str:
        """计算数据库连接 URL"""
        if self.database_url:
            return self.database_url
        if self.database_type == DatabaseType.SQLITE:
            db_path = Path(self.sqlite_db_path)
            db_path.parent.mkdir(parents=True, exist_ok=True)
            return f"sqlite+aiosqlite:///{db_path}"
        raise ValueError("PostgreSQL 需要配置 database_url")

    @property
    def workspace_path(self) -> Path:
        """工作区根路径"""
        return Path(self.workspace_root)

    @property
    def private_skills_path(self) -> Path:
        """私有 Skill 工作区路径"""
        return self.workspace_path / self.private_skills_dir

    @property
    def mirrors_path(self) -> Path:
        """Git 镜像工作区路径"""
        return self.workspace_path / self.mirrors_dir

    @property
    def data_path(self) -> Path:
        """数据根路径"""
        return Path(self.data_root)

    @property
    def packages_path(self) -> Path:
        """Skill 包存储路径"""
        return self.data_path / self.packages_dir

    @property
    def fulltext_index_path_full(self) -> Path:
        """全文索引路径"""
        return Path(self.fulltext_index_path)

    @property
    def vector_index_path_full(self) -> Path:
        """向量索引路径"""
        return Path(self.vector_index_path)

    def ensure_directories(self) -> None:
        """确保所有必要目录存在"""
        directories = [
            self.workspace_path,
            self.private_skills_path,
            self.mirrors_path,
            self.data_path,
            self.packages_path,
            self.fulltext_index_path_full,
            self.vector_index_path_full,
            Path(self.logs_dir),
        ]
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()
