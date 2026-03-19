"""
数据库连接和会话管理

支持 SQLite 和 PostgreSQL
"""
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Optional

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool, StaticPool
from sqlmodel import SQLModel

from app.core.config import DatabaseType, get_settings


# SQLite 外键支持
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """为 SQLite 启用外键约束"""
    if hasattr(dbapi_connection, "execute"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


class DatabaseManager:
    """数据库管理器"""

    def __init__(self):
        self._engine = None
        self._session_factory = None

    @property
    def engine(self):
        """获取数据库引擎"""
        if self._engine is None:
            raise RuntimeError("数据库未初始化，请先调用 init_db()")
        return self._engine

    @property
    def session_factory(self):
        """获取会话工厂"""
        if self._session_factory is None:
            raise RuntimeError("数据库未初始化，请先调用 init_db()")
        return self._session_factory

    async def init_db(self) -> None:
        """初始化数据库连接"""
        settings = get_settings()
        database_url = settings.database_url_computed

        # 根据数据库类型配置引擎
        if settings.database_type == DatabaseType.SQLITE:
            self._engine = create_async_engine(
                database_url,
                echo=settings.debug,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
            )
        else:
            # PostgreSQL
            self._engine = create_async_engine(
                database_url,
                echo=settings.debug,
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True,
            )

        self._session_factory = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

        # 创建所有表
        async with self._engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

    async def close_db(self) -> None:
        """关闭数据库连接"""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """获取数据库会话上下文管理器"""
        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise


# 全局数据库管理器实例
db_manager = DatabaseManager()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖注入：获取数据库会话"""
    async with db_manager.get_session() as session:
        yield session
