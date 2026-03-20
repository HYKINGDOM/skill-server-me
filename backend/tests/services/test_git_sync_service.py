"""Git同步服务单元测试"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.git_sync_service import GitSyncService
from app.db.models import GitRepo, Skill, User, SkillSourceType
from app.core.exceptions import GitOperationError, GitRepoNotFoundError


class TestGitSyncService:
    """Git同步服务测试"""
    
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
    def git_sync_service(self, mock_session):
        """Git同步服务实例"""
        return GitSyncService(mock_session)
    
    async def test_validate_git_url(self, git_sync_service):
        """测试验证Git URL"""
        # 模拟配置
        git_sync_service.settings.git_allowed_domains = ["github.com"]
        git_sync_service.settings.git_blocked_ip_ranges = ["192.168.0.0/16"]
        
        # 模拟DNS解析
        with patch('socket.gethostbyname', return_value='140.82.114.4'):
            # 有效URL
            assert await git_sync_service._validate_git_url("https://github.com/user/repo.git")
    
    async def test_import_repo(self, git_sync_service, mock_session, mock_user):
        """测试导入Git仓库"""
        # 模拟查询结果
        mock_session.execute.return_value.scalar_one_or_none.return_value = None
        
        # 模拟验证URL
        git_sync_service._validate_git_url = AsyncMock(return_value=True)
        
        # 模拟同步
        git_sync_service.sync_repo = AsyncMock(return_value={"status": "success"})
        
        # 模拟权限分配
        git_sync_service.permission_service.assign_resource_role = AsyncMock()
        
        # 模拟文件操作
        import os
        original_mkdir = os.makedirs
        os.makedirs = Mock()
        
        try:
            repo = await git_sync_service.import_repo(
                name="test-repo",
                url="https://github.com/user/repo.git",
                user=mock_user
            )
            
            assert isinstance(repo, GitRepo)
            assert repo.name == "test-repo"
            assert repo.url == "https://github.com/user/repo.git"
            assert repo.created_by == mock_user.id
            
        finally:
            os.makedirs = original_mkdir
    
    async def test_import_repo_existing(self, git_sync_service, mock_session, mock_user):
        """测试导入已存在的Git仓库"""
        # 模拟查询结果，返回已存在的仓库
        existing_repo = Mock(spec=GitRepo)
        mock_session.execute.return_value.scalar_one_or_none.return_value = existing_repo
        
        with pytest.raises(GitOperationError):
            await git_sync_service.import_repo(
                name="test-repo",
                url="https://github.com/user/repo.git",
                user=mock_user
            )
    
    async def test_sync_repo(self, git_sync_service, mock_session, mock_user):
        """测试同步Git仓库"""
        # 模拟仓库
        repo = Mock(spec=GitRepo)
        repo.id = "1"
        repo.url = "https://github.com/user/repo.git"
        repo.branch = "main"
        repo.mirror_path = "/tmp/test-repo"
        repo.last_sync_commit = "old_commit"
        repo.sync_status = "pending"
        
        # 模拟查询结果
        mock_session.execute.return_value.scalar_one_or_none.return_value = repo
        
        # 模拟Git操作
        mock_git_repo = Mock()
        mock_origin = Mock()
        mock_origin.fetch = Mock()
        mock_git_repo.remotes = {"origin": mock_origin}
        mock_git_repo.git = Mock()
        mock_git_repo.head = Mock()
        mock_git_repo.head.commit = Mock()
        mock_git_repo.head.commit.hexsha = "new_commit"
        
        with patch('app.services.git_sync_service.git.Repo') as mock_repo_class:
            mock_repo_class.clone_from.return_value = mock_git_repo
            mock_repo_class.return_value = mock_git_repo
            
            # 模拟扫描Skills
            git_sync_service._scan_skills = AsyncMock(return_value=(1, 0))
            
            result = await git_sync_service.sync_repo("1", mock_user)
            
            assert result["status"] == "success"
            assert result["commit"] == "new_commit"
            assert result["skills_created"] == 1
            assert result["skills_updated"] == 0
    
    async def test_sync_repo_no_changes(self, git_sync_service, mock_session):
        """测试同步无变化的Git仓库"""
        # 模拟仓库
        repo = Mock(spec=GitRepo)
        repo.id = "1"
        repo.url = "https://github.com/user/repo.git"
        repo.branch = "main"
        repo.mirror_path = "/tmp/test-repo"
        repo.last_sync_commit = "current_commit"
        repo.sync_status = "pending"
        
        # 模拟查询结果
        mock_session.execute.return_value.scalar_one_or_none.return_value = repo
        
        # 模拟Git操作
        mock_git_repo = Mock()
        mock_origin = Mock()
        mock_origin.fetch = Mock()
        mock_git_repo.remotes = {"origin": mock_origin}
        mock_git_repo.git = Mock()
        mock_git_repo.head = Mock()
        mock_git_repo.head.commit = Mock()
        mock_git_repo.head.commit.hexsha = "current_commit"
        
        with patch('app.services.git_sync_service.git.Repo') as mock_repo_class:
            mock_repo_class.return_value = mock_git_repo
            
            result = await git_sync_service.sync_repo("1")
            
            assert result["status"] == "no_changes"
            assert result["commit"] == "current_commit"
    
    async def test_delete_repo(self, git_sync_service, mock_session, mock_user):
        """测试删除Git仓库"""
        # 模拟仓库
        repo = Mock(spec=GitRepo)
        repo.id = "1"
        repo.mirror_path = "/tmp/test-repo"
        repo.is_active = True
        
        # 模拟查询结果
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = repo
        
        # 模拟scalars()返回值，包含all()方法
        mock_scalars = Mock()
        mock_scalars.all.return_value = []  # 无关联的Skills
        mock_result.scalars.return_value = mock_scalars
        
        mock_session.execute.return_value = mock_result
        
        # 模拟权限检查
        git_sync_service.permission_service.check_repo_permission = AsyncMock()
        
        # 模拟文件操作
        import shutil
        original_rmtree = shutil.rmtree
        shutil.rmtree = Mock()
        
        try:
            result = await git_sync_service.delete_repo("1", mock_user)
            assert result is True
            assert repo.is_active is False
            
        finally:
            shutil.rmtree = original_rmtree
    
    async def test_delete_repo_not_found(self, git_sync_service, mock_session, mock_user):
        """测试删除不存在的Git仓库"""
        # 模拟查询结果，返回None
        mock_session.execute.return_value.scalar_one_or_none.return_value = None
        
        with pytest.raises(GitRepoNotFoundError):
            await git_sync_service.delete_repo("1", mock_user)
