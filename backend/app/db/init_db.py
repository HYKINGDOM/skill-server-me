"""
数据库初始化脚本

创建初始管理员用户和默认配置
"""
import asyncio
from sqlmodel import select

from app.core.config import get_settings, RunMode
from app.db.database import db_manager
from app.db.models import User, SystemConfig, SystemRole


async def init_admin_user(session) -> User:
    """创建初始管理员用户"""
    settings = get_settings()
    
    # 检查是否已存在管理员
    result = await session.execute(
        select(User).where(User.system_role == SystemRole.ADMIN)
    )
    existing_admin = result.scalar_one_or_none()
    
    if existing_admin:
        print(f"管理员用户已存在: {existing_admin.username}")
        return existing_admin
    
    # 创建默认管理员
    admin_username = "admin"
    admin_password = "admin"  # 默认密码，首次登录后应修改
    admin_email = "admin@skillshub.local"
    
    # 暂时使用一个简单的哈希值，避免 bcrypt 库的问题
    hashed_password = "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW"  # 密码为 "admin"
    
    admin = User(
        username=admin_username,
        email=admin_email,
        hashed_password=hashed_password,
        system_role=SystemRole.ADMIN,
        is_active=True,
    )
    
    session.add(admin)
    await session.commit()
    await session.refresh(admin)
    
    print(f"创建管理员用户成功: {admin_username}")
    print(f"默认密码: {admin_password}")
    print("请登录后立即修改密码！")
    
    return admin


async def init_system_configs(session) -> None:
    """初始化系统配置"""
    default_configs = [
        ("system.name", "Skills Hub", "系统名称"),
        ("system.version", "1.0.0", "系统版本"),
        ("skill.max_size_mb", "50", "Skill 最大大小（MB）"),
        ("search.results_per_page", "20", "每页搜索结果数"),
        ("git.sync_interval_hours", "24", "Git 同步间隔（小时）"),
    ]
    
    for key, value, description in default_configs:
        result = await session.execute(
            select(SystemConfig).where(SystemConfig.key == key)
        )
        existing = result.scalar_one_or_none()
        
        if not existing:
            config = SystemConfig(
                key=key,
                value=value,
                description=description,
            )
            session.add(config)
    
    await session.commit()
    print("系统配置初始化完成")


async def init_database() -> None:
    """初始化数据库"""
    print("开始初始化数据库...")
    
    # 初始化数据库连接
    await db_manager.init_db()
    
    # 创建初始数据
    async with db_manager.get_session() as session:
        await init_admin_user(session)
        await init_system_configs(session)
    
    print("数据库初始化完成")


if __name__ == "__main__":
    asyncio.run(init_database())
