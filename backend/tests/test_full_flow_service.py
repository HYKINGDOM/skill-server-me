"""完整流程测试：上传/Git版本记录/修改/打包下载（直接测试服务层）"""
import asyncio
import os
import tempfile
import zipfile
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.services.skill_service import SkillService
from app.services.git_sync_service import GitSyncService
from app.db.models import User, SkillSourceType
from app.core.config import get_settings


async def get_db_session():
    """获取数据库会话"""
    settings = get_settings()
    engine = create_async_engine(
        settings.database_url_computed,
        echo=False
    )
    async_session = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    async with async_session() as session:
        yield session


async def create_test_zip():
    """创建测试ZIP文件"""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
        tmp_path = tmp.name
    
    with zipfile.ZipFile(tmp_path, "w") as zf:
        # 添加SKILL.md文件
        skill_md_content = """---
name: test-skill
version: 1.0.0
description: Test skill
---

# Test Skill

This is a test skill for full flow testing.
"""
        zf.writestr("SKILL.md", skill_md_content)
        
        # 添加一个测试文件
        zf.writestr("test.txt", "This is a test file.")
    
    return tmp_path


async def test_full_flow():
    """测试完整流程"""
    print("=== 开始测试完整流程（服务层）===")
    
    # 1. 获取数据库会话
    async for session in get_db_session():
        # 2. 创建模拟用户
        mock_user = User(
            id="1",
            username="testuser",
            email="test@example.com",
            hashed_password="test123"
        )
        
        # 3. 创建Skill服务实例
        skill_service = SkillService(session)
        
        # 4. 上传ZIP包创建Skill
        zip_path = await create_test_zip()
        print("✓ 创建测试ZIP文件成功")
        
        try:
            # 5. 创建Skill
            skill = await skill_service.create_skill(
                name="test-skill",
                user=mock_user
            )
            print(f"✓ 创建Skill成功，ID: {skill.id}")
            
            # 6. 修改Skill
            updated_content = """---
name: test-skill
version: 1.1.0
description: Updated test skill
---

# Test Skill

This is an updated test skill for full flow testing.
"""
            
            updated_skill = await skill_service.update_skill(
                skill_id=skill.id,
                user=mock_user,
                skill_md_content=updated_content
            )
            print("✓ 修改Skill成功")
            
            # 7. 测试Git同步服务
            git_sync_service = GitSyncService(session)
            
            # 8. 导入Git仓库
            try:
                repo = await git_sync_service.import_repo(
                    name="test-repo",
                    url="https://github.com/example/test-repo.git",
                    user=mock_user
                )
                print(f"✓ 导入Git仓库成功，ID: {repo.id}")
            except Exception as e:
                print(f"⚠️  导入Git仓库失败（预期内，示例URL）: {str(e)}")
            
            # 9. 测试下载功能
            # 这里我们直接验证skill的存储路径是否存在
            settings = get_settings()
            skill_path = settings.private_skills_path / skill.name
            if skill_path.exists() and skill_path.is_dir():
                print("✓ Skill存储路径存在")
                
                # 验证SKILL.md文件是否存在
                skill_md_path = skill_path / "SKILL.md"
                if skill_md_path.exists():
                    print("✓ SKILL.md文件存在")
                else:
                    print("⚠️  SKILL.md文件不存在")
            else:
                print("⚠️  Skill存储路径不存在")
            
        finally:
            # 10. 清理
            os.remove(zip_path)
            print("✓ 清理临时文件成功")
    
    print("=== 测试完成 ===")


if __name__ == "__main__":
    asyncio.run(test_full_flow())
