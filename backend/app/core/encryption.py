"""
加密服务模块

提供基于 Fernet 对称加密的数据加密和解密功能
用于保护敏感信息，如 Git 认证凭据
"""
import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings
from app.core.exceptions import EncryptionError


class EncryptionService:
    """
    加密服务类
    
    使用 Fernet 对称加密算法提供安全的加密和解密功能
    主要用于保护 Git 认证信息等敏感数据
    
    特性：
    - 使用 AES-128 算法进行加密
    - 支持 CBC 模式和 PKCS7 填充
    - 自动添加时间戳防止重放攻击
    - 使用 HMAC 确保数据完整性
    """
    
    def __init__(self):
        """初始化加密服务"""
        self.settings = get_settings()
        self._fernet: Optional[Fernet] = None
        
    @property
    def fernet(self) -> Fernet:
        """
        获取 Fernet 实例（延迟加载）
        
        Returns:
            Fernet: Fernet 加密实例
            
        Raises:
            EncryptionError: 当加密密钥未配置或无效时抛出
        """
        if self._fernet is None:
            encryption_key = self.settings.encryption_key
            
            if not encryption_key:
                raise EncryptionError(
                    "加密密钥未配置，请在环境变量中设置 ENCRYPTION_KEY"
                )
            
            try:
                self._fernet = Fernet(encryption_key.encode() if isinstance(encryption_key, str) else encryption_key)
            except Exception as e:
                raise EncryptionError(f"无效的加密密钥: {str(e)}")
                
        return self._fernet
    
    def encrypt(self, plaintext: str) -> str:
        """
        加密字符串数据
        
        Args:
            plaintext: 待加密的明文字符串
            
        Returns:
            str: Base64 编码的加密字符串
            
        Raises:
            EncryptionError: 加密失败时抛出
            
        Example:
            >>> encryption_service = EncryptionService()
            >>> encrypted = encryption_service.encrypt("my-secret-token")
            >>> print(encrypted)  # 输出加密后的字符串
        """
        if not plaintext:
            return plaintext
            
        try:
            # 将字符串转换为字节
            plaintext_bytes = plaintext.encode('utf-8')
            
            # 使用 Fernet 加密
            encrypted_bytes = self.fernet.encrypt(plaintext_bytes)
            
            # 返回 Base64 编码的字符串
            return encrypted_bytes.decode('utf-8')
            
        except Exception as e:
            raise EncryptionError(f"加密失败: {str(e)}")
    
    def decrypt(self, ciphertext: str) -> str:
        """
        解密字符串数据
        
        Args:
            ciphertext: 加密后的字符串（Base64 编码）
            
        Returns:
            str: 解密后的明文字符串
            
        Raises:
            EncryptionError: 解密失败或数据被篡改时抛出
            
        Example:
            >>> encryption_service = EncryptionService()
            >>> decrypted = encryption_service.decrypt(encrypted_string)
            >>> print(decrypted)  # 输出解密后的明文
        """
        if not ciphertext:
            return ciphertext
            
        try:
            # 将 Base64 字符串转换为字节
            ciphertext_bytes = ciphertext.encode('utf-8')
            
            # 使用 Fernet 解密
            decrypted_bytes = self.fernet.decrypt(ciphertext_bytes)
            
            # 返回解密后的字符串
            return decrypted_bytes.decode('utf-8')
            
        except InvalidToken:
            raise EncryptionError("解密失败: 无效的加密数据或密钥不匹配")
        except Exception as e:
            raise EncryptionError(f"解密失败: {str(e)}")
    
    @staticmethod
    def generate_key() -> str:
        """
        生成新的加密密钥
        
        用于生成新的 Fernet 密钥，可保存到环境变量中使用
        
        Returns:
            str: Base64 编码的 Fernet 密钥
            
        Example:
            >>> key = EncryptionService.generate_key()
            >>> print(key)  # 输出类似: "7zxK9_3mNpQrStUvWxYz..."
        """
        return Fernet.generate_key().decode('utf-8')


# 全局单例实例
_encryption_service: Optional[EncryptionService] = None


def get_encryption_service() -> EncryptionService:
    """
    获取加密服务单例实例
    
    Returns:
        EncryptionService: 加密服务实例
    """
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = EncryptionService()
    return _encryption_service
