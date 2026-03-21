"""
JWT 令牌服务

处理访问令牌和刷新令牌的生成、验证、刷新
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from jose import JWTError, jwt

from app.core.config import get_settings
from app.core.exceptions import InvalidTokenError, TokenExpiredError


class TokenData:
    """令牌数据类"""
    
    def __init__(
        self,
        user_id: str,
        username: str,
        system_role: str,
        exp: datetime,
        iat: datetime,
        token_type: str = "access",
    ):
        self.user_id = user_id
        self.username = username
        self.system_role = system_role
        self.exp = exp
        self.iat = iat
        self.token_type = token_type


class TokenService:
    """令牌服务"""

    def __init__(self):
        self.settings = get_settings()
        self.secret_key = self.settings.secret_key
        self.algorithm = self.settings.algorithm
        self.access_token_expire_minutes = self.settings.access_token_expire_minutes
        self.refresh_token_expire_days = self.settings.refresh_token_expire_days

    def create_access_token(
        self,
        user_id: str,
        username: str,
        system_role: str,
        expires_delta: Optional[timedelta] = None,
    ) -> str:
        """创建访问令牌"""
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(
                minutes=self.access_token_expire_minutes
            )

        now = datetime.now(timezone.utc)
        
        to_encode = {
            "sub": user_id,
            "username": username,
            "system_role": system_role,
            "exp": expire,
            "iat": now,
            "token_type": "access",
        }
        
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)

    def create_refresh_token(
        self,
        user_id: str,
        username: str,
        system_role: str,
        expires_delta: Optional[timedelta] = None,
    ) -> str:
        """创建刷新令牌"""
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(
                days=self.refresh_token_expire_days
            )

        now = datetime.now(timezone.utc)
        
        to_encode = {
            "sub": user_id,
            "username": username,
            "system_role": system_role,
            "exp": expire,
            "iat": now,
            "token_type": "refresh",
        }
        
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)

    def decode_token(self, token: str) -> TokenData:
        """解码并验证令牌"""
        try:
            payload = jwt.decode(
                token, self.secret_key, algorithms=[self.algorithm]
            )
            
            user_id = payload.get("sub")
            username = payload.get("username")
            system_role = payload.get("system_role")
            exp = payload.get("exp")
            iat = payload.get("iat")
            token_type = payload.get("token_type", "access")
            
            if not all([user_id, username, system_role, exp, iat]):
                raise InvalidTokenError("令牌缺少必要字段")
            
            return TokenData(
                user_id=user_id,
                username=username,
                system_role=system_role,
                exp=datetime.fromtimestamp(exp, tz=timezone.utc),
                iat=datetime.fromtimestamp(iat, tz=timezone.utc),
                token_type=token_type,
            )
            
        except JWTError as e:
            if "expired" in str(e).lower():
                raise TokenExpiredError("令牌已过期")
            raise InvalidTokenError(f"无效的令牌: {str(e)}")

    def verify_access_token(self, token: str) -> TokenData:
        """验证访问令牌"""
        token_data = self.decode_token(token)
        if token_data.token_type != "access":
            raise InvalidTokenError("需要访问令牌")
        return token_data

    def verify_refresh_token(self, token: str) -> TokenData:
        """验证刷新令牌"""
        token_data = self.decode_token(token)
        if token_data.token_type != "refresh":
            raise InvalidTokenError("需要刷新令牌")
        return token_data


class PasswordService:
    """密码服务"""

    @staticmethod
    def hash_password(password: str) -> str:
        """哈希密码"""
        # bcrypt限制密码长度为72字节，超过的部分会被截断
        password_bytes = password[:72].encode('utf-8')
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password_bytes, salt)
        return hashed.decode('utf-8')

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """验证密码"""
        # bcrypt限制密码长度为72字节，超过的部分会被截断
        password_bytes = plain_password[:72].encode('utf-8')
        hashed_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hashed_bytes)


# 全局服务实例
token_service = TokenService()
password_service = PasswordService()
