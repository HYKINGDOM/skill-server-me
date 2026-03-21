"""
数据库初始化脚本

创建初始管理员用户和默认配置
"""
import asyncio
import os
import secrets
import string
from sqlmodel import select

from app.core.config import get_settings, RunMode
from app.core.utils import mask_password
from app.db.database import db_manager
from app.db.models import User, SystemConfig, SystemRole
from app.auth.jwt_service import PasswordService


async def init_admin_user(session) -> User:
    """
    创建初始管理员用户
    
    密码来源优先级：
    1. 环境变量 INITIAL_ADMIN_PASSWORD
    2. 自动生成16位随机密码
    """
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
    admin_email = "admin@skillshub.local"
    
    # 从环境变量获取初始密码，如果未配置则生成随机密码
    admin_password = os.environ.get("INITIAL_ADMIN_PASSWORD")
    is_random_password = False
    
    if not admin_password:
        # 生成16位随机密码（包含大小写字母、数字和特殊字符）
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        admin_password = ''.join(secrets.choice(alphabet) for _ in range(16))
        is_random_password = True
    
    # 使用 PasswordService 对密码进行哈希处理
    hashed_password = PasswordService.hash_password(admin_password)
    
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
    
    # 打印管理员创建信息（密码已脱敏处理，不显示明文）
    print("=" * 50)
    print(f"创建管理员用户成功: {admin_username}")
    print(f"默认密码: {mask_password(admin_password)}")
    
    # 如果是随机生成的密码，提示用户需要保存
    if is_random_password:
        print("注意: 密码已随机生成，请通过其他安全方式获取初始密码")
    else:
        print("密码来源: 环境变量 INITIAL_ADMIN_PASSWORD")
    
    print("请登录后立即修改密码！")
    print("=" * 50)
    
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
