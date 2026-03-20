"""Skill服务单元测试"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.skill_service import SkillService
from app.db.models import Skill, User, SkillSourceType
from app.core.exceptions import SkillValidationError, SkillNotFoundError


class TestSkillService:
    """Skill服务测试"""
    
    @pytest.fixture
    def mock_session(self):
        """模拟数据库会话"""
        session = Mock(spec=AsyncSession)
        session.add = AsyncMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        
        # 模拟execute方法返回一个同步的结果对象
        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock()
        mock_result.scalars = Mock(return_value=Mock(all=Mock(return_value=[])))
        session.execute = AsyncMock(return_value=mock_result)
        
        return session
    
    @pytest.fixture
    def mock_user(self):
        """模拟用户"""
        user = Mock(spec=User)
        user.id = "1"
        user.username = "testuser"
        return user
    
    @pytest.fixture
    def skill_service(self, mock_session):
        """Skill服务实例"""
        return SkillService(mock_session)
    
    def test_validate_skill_name(self, skill_service):
        """测试验证Skill名称"""
        # 有效名称
        assert skill_service._validate_skill_name("test-skill")
        assert skill_service._validate_skill_name("test_skill")
        assert skill_service._validate_skill_name("test123")
        
        # 无效名称
        assert not skill_service._validate_skill_name("")
        assert not skill_service._validate_skill_name("a" * 101)  # 过长
        assert not skill_service._validate_skill_name("test skill")  # 包含空格
        assert not skill_service._validate_skill_name("test@skill")  # 包含特殊字符
    
    async def test_create_skill(self, skill_service, mock_session, mock_user):
        """测试创建Skill"""
        # 模拟查询结果
        mock_session.execute.return_value.scalar_one_or_none.return_value = None
        
        # 模拟_parse_skill_md方法返回一个空字典
        skill_service._parse_skill_md = AsyncMock(return_value={})
        
        # 模拟Path.mkdir方法
        with patch('pathlib.Path.mkdir') as mock_mkdir:
            # 模拟文件操作相关的方法
            with patch('app.services.skill_service.aiofiles.open') as mock_open:
                # 模拟文件对象
                mock_file = Mock()
                mock_file.__aenter__ = AsyncMock(return_value=mock_file)
                mock_file.__aexit__ = AsyncMock()
                mock_file.write = AsyncMock()
                mock_open.return_value = mock_file
                
                # 模拟_scan_skill_files方法
                skill_service._scan_skill_files = AsyncMock()
                
                # 模拟_create_version方法
                skill_service._create_version = AsyncMock()
                
                # 模拟_add_timeline_event方法
                skill_service._add_timeline_event = AsyncMock()
                
                # 模拟权限服务
                skill_service.permission_service.assign_resource_role = AsyncMock()
                
                try:
                    skill = await skill_service.create_skill(
                        name="test-skill",
                        user=mock_user
                    )
                    
                    assert isinstance(skill, Skill)
                    assert skill.name == "test-skill"
                    assert skill.source_type == SkillSourceType.PRIVATE
                    assert skill.created_by == mock_user.id
                    
                finally:
                    pass
    
    async def test_create_skill_existing(self, skill_service, mock_session, mock_user):
        """测试创建已存在的Skill"""
        # 模拟查询结果，返回已存在的Skill
        existing_skill = Mock(spec=Skill)
        mock_session.execute.return_value.scalar_one_or_none.return_value = existing_skill
        
        with pytest.raises(SkillValidationError):
            await skill_service.create_skill(
                name="test-skill",
                user=mock_user
            )
    
    async def test_get_skill_by_id(self, skill_service, mock_session):
        """测试通过ID获取Skill"""
        # 模拟查询结果
        skill = Mock(spec=Skill)
        skill.id = "1"
        mock_session.execute.return_value.scalar_one_or_none.return_value = skill
        
        result = await skill_service._get_skill_by_id("1")
        assert result == skill
    
    async def test_get_skill_by_name(self, skill_service, mock_session):
        """测试通过名称获取Skill"""
        # 模拟查询结果
        skill = Mock(spec=Skill)
        skill.name = "test-skill"
        mock_session.execute.return_value.scalar_one_or_none.return_value = skill
        
        result = await skill_service._get_skill_by_name("test-skill")
        assert result == skill
    
    async def test_delete_skill(self, skill_service, mock_session, mock_user):
        """测试删除Skill"""
        # 模拟查询结果
        skill = Mock(spec=Skill)
        skill.id = "1"
        skill.storage_path = "/tmp/test-skill"
        skill.is_active = True
        mock_session.execute.return_value.scalar_one_or_none.return_value = skill
        
        # 模拟权限检查
        skill_service.permission_service.check_skill_permission = AsyncMock()
        
        # 模拟文件操作
        import shutil
        original_rmtree = shutil.rmtree
        shutil.rmtree = Mock()
        
        try:
            result = await skill_service.delete_skill("1", mock_user)
            assert result is True
            assert skill.is_active is False
            
        finally:
            shutil.rmtree = original_rmtree
    
    async def test_delete_skill_not_found(self, skill_service, mock_session, mock_user):
        """测试删除不存在的Skill"""
        # 模拟查询结果，返回None
        mock_session.execute.return_value.scalar_one_or_none.return_value = None
        
        with pytest.raises(SkillNotFoundError):
            await skill_service.delete_skill("1", mock_user)
