"""
主应用入口

FastAPI 应用配置和启动
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.core.exceptions import SkillHubException
from app.db.database import db_manager
from app.db.init_db import init_admin_user, init_system_configs

# 导入路由
from app.api.auth_routes import router as auth_router
from app.api.skill_routes import router as skill_router
from app.api.repo_routes import router as repo_router
from app.api.search_routes import router as search_router
from app.api.version_routes import router as version_router
from app.api.timeline_routes import router as timeline_router
from app.api.favorite_routes import router as favorite_router
from app.api.notification_routes import router as notification_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """应用生命周期管理"""
    settings = get_settings()
    
    # 启动时初始化
    settings.ensure_directories()
    await db_manager.init_db()
    
    # 初始化管理员用户和系统配置
    async with db_manager.get_session() as session:
        await init_admin_user(session)
        await init_system_configs(session)
    
    print(f"🚀 {settings.app_name} v{settings.app_version} 启动中...")
    print(f"📝 运行模式: {settings.run_mode.value}")
    print(f"💾 数据库: {settings.database_type.value}")
    
    yield
    
    # 关闭时清理
    await db_manager.close_db()
    print(f"👋 {settings.app_name} 已关闭")


def create_app() -> FastAPI:
    """创建 FastAPI 应用"""
    settings = get_settings()
    
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="""
## Skills Hub Platform

私有化部署的技能管理平台，支持：

- 📦 Skill 包管理（上传、创建、编辑、删除）
- 🔄 Git 仓库同步
- 🔍 混合检索（全文检索 + 向量检索）
- 📚 版本管理
- ⏱️ 时间线追踪
- ⭐ 收藏功能
- 🔔 消息通知
- 🔐 权限控制

### 运行模式

1. **登录开启模式**（推荐生产环境）
2. **只读匿名模式**（推荐对外展示）
3. **初始化管理模式**（仅限初始化阶段）
        """,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    
    # CORS 中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
    )
    
    # 异常处理
    @app.exception_handler(SkillHubException)
    async def skill_hub_exception_handler(
        request: Request,
        exc: SkillHubException,
    ) -> JSONResponse:
        """处理业务异常"""
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            },
        )
    
    # 注册路由
    app.include_router(auth_router)
    app.include_router(skill_router)
    app.include_router(repo_router)
    app.include_router(search_router)
    app.include_router(version_router)
    app.include_router(timeline_router)
    app.include_router(favorite_router)
    app.include_router(notification_router)
    
    # 健康检查
    @app.get("/health")
    async def health_check():
        """健康检查"""
        return {
            "status": "healthy",
            "version": settings.app_version,
            "mode": settings.run_mode.value,
        }
    
    # 根路径
    @app.get("/")
    async def root():
        """根路径"""
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs",
            "health": "/health",
        }
    
    return app


# 创建应用实例
app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        workers=settings.workers,
    )
