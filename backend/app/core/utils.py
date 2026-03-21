"""
工具函数模块

提供各种通用工具函数
"""
from typing import Optional


def mask_sensitive_info(value: Optional[str], show_first: int = 4, show_last: int = 4) -> str:
    """
    脱敏敏感信息
    
    对敏感信息进行部分隐藏，只显示前N位和后N位字符
    
    Args:
        value: 需要脱敏的字符串
        show_first: 显示前几位字符，默认4位
        show_last: 显示后几位字符，默认4位
    
    Returns:
        脱敏后的字符串
        
    Examples:
        >>> mask_sensitive_info("admin123456")
        'amin...3456'
        >>> mask_sensitive_info("abc")
        '***'
        >>> mask_sensitive_info(None)
        '***'
    """
    if not value:
        return "***"
    
    # 如果字符串长度小于等于显示的总长度，完全隐藏
    if len(value) <= show_first + show_last:
        return "***"
    
    # 显示前N位和后N位，中间用省略号代替
    masked = f"{value[:show_first]}...{value[-show_last:]}"
    return masked


def mask_password(password: Optional[str]) -> str:
    """
    脱敏密码
    
    密码完全隐藏，不显示任何字符
    
    Args:
        password: 密码字符串
    
    Returns:
        固定返回 '******'
    """
    return "******"


def mask_token(token: Optional[str]) -> str:
    """
    脱敏令牌（Token）
    
    显示前8位和后8位字符
    
    Args:
        token: 令牌字符串
    
    Returns:
        脱敏后的令牌
    """
    return mask_sensitive_info(token, show_first=8, show_last=8)


def mask_secret_key(key: Optional[str]) -> str:
    """
    脱敏密钥
    
    显示前4位和后4位字符
    
    Args:
        key: 密钥字符串
    
    Returns:
        脱敏后的密钥
    """
    return mask_sensitive_info(key, show_first=4, show_last=4)


def mask_auth_secret(auth_secret: Optional[str]) -> str:
    """
    脱敏认证密钥
    
    显示前4位和后4位字符
    
    Args:
        auth_secret: 认证密钥字符串
    
    Returns:
        脱敏后的认证密钥
    """
    return mask_sensitive_info(auth_secret, show_first=4, show_last=4)


def mask_dict(data: dict, sensitive_keys: Optional[list[str]] = None) -> dict:
    """
    脱敏字典中的敏感字段
    
    Args:
        data: 需要脱敏的字典
        sensitive_keys: 敏感字段列表，默认包含常见的敏感字段名
    
    Returns:
        脱敏后的字典副本
    """
    if sensitive_keys is None:
        # 默认敏感字段列表
        sensitive_keys = [
            "password",
            "passwd",
            "pwd",
            "secret",
            "secret_key",
            "api_key",
            "token",
            "access_token",
            "refresh_token",
            "auth_secret",
            "auth_secret_ref",
            "private_key",
            "api_secret",
        ]
    
    result = {}
    for key, value in data.items():
        # 检查键名是否包含敏感字段（不区分大小写）
        key_lower = key.lower()
        is_sensitive = any(sensitive_key in key_lower for sensitive_key in sensitive_keys)
        
        if is_sensitive and isinstance(value, str):
            # 根据字段类型选择脱敏方式
            if "password" in key_lower or "passwd" in key_lower or "pwd" in key_lower:
                result[key] = mask_password(value)
            elif "token" in key_lower:
                result[key] = mask_token(value)
            else:
                result[key] = mask_sensitive_info(value)
        else:
            result[key] = value
    
    return result
