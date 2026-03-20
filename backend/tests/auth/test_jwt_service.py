"""JWT服务单元测试"""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.auth.jwt_service import TokenService, PasswordService, token_service, password_service
from app.core.exceptions import InvalidTokenError, TokenExpiredError


class TestTokenService:
    """Token服务测试"""
    
    def test_create_access_token(self):
        """测试创建访问令牌"""
        token = token_service.create_access_token(
            user_id="1",
            username="testuser",
            system_role="user"
        )
        assert isinstance(token, str)
        assert len(token) > 0
    
    def test_create_refresh_token(self):
        """测试创建刷新令牌"""
        token = token_service.create_refresh_token(
            user_id="1",
            username="testuser",
            system_role="user"
        )
        assert isinstance(token, str)
        assert len(token) > 0
    
    def test_decode_token(self):
        """测试解码令牌"""
        token = token_service.create_access_token(
            user_id="1",
            username="testuser",
            system_role="user"
        )
        token_data = token_service.decode_token(token)
        assert token_data.user_id == "1"
        assert token_data.username == "testuser"
        assert token_data.system_role == "user"
        assert token_data.token_type == "access"
    
    def test_verify_access_token(self):
        """测试验证访问令牌"""
        token = token_service.create_access_token(
            user_id="1",
            username="testuser",
            system_role="user"
        )
        token_data = token_service.verify_access_token(token)
        assert token_data.token_type == "access"
    
    def test_verify_refresh_token(self):
        """测试验证刷新令牌"""
        token = token_service.create_refresh_token(
            user_id="1",
            username="testuser",
            system_role="user"
        )
        token_data = token_service.verify_refresh_token(token)
        assert token_data.token_type == "refresh"
    
    def test_invalid_token(self):
        """测试无效令牌"""
        with pytest.raises(InvalidTokenError):
            token_service.decode_token("invalid_token")
    
    def test_expired_token(self):
        """测试过期令牌"""
        expires_delta = timedelta(seconds=-1)  # 过期1秒
        token = token_service.create_access_token(
            user_id="1",
            username="testuser",
            system_role="user",
            expires_delta=expires_delta
        )
        with pytest.raises(TokenExpiredError):
            token_service.decode_token(token)


class TestPasswordService:
    """密码服务测试"""
    
    @patch('app.auth.jwt_service.pwd_context')
    def test_hash_password(self, mock_pwd_context):
        """测试密码哈希"""
        mock_pwd_context.hash.return_value = "hashed_password"
        password = "test123"
        hashed = password_service.hash_password(password)
        assert isinstance(hashed, str)
        assert len(hashed) > 0
        assert hashed != password
        mock_pwd_context.hash.assert_called_once_with(password)
    
    @patch('app.auth.jwt_service.pwd_context')
    def test_verify_password(self, mock_pwd_context):
        """测试密码验证"""
        mock_pwd_context.verify.side_effect = lambda p, h: p == "test123"
        password = "test123"
        hashed = "hashed_password"
        assert password_service.verify_password(password, hashed)
        assert not password_service.verify_password("wrong", hashed)
        mock_pwd_context.verify.assert_any_call(password, hashed)
        mock_pwd_context.verify.assert_any_call("wrong", hashed)
