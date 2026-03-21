"""
自定义异常模块

定义系统中所有业务异常类型
"""
from typing import Any, Optional


class SkillHubException(Exception):
    """基础异常类"""

    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        self.message = message
        self.code = code or "UNKNOWN_ERROR"
        self.details = details or {}
        super().__init__(self.message)


# ==================== 认证授权异常 ====================

class AuthenticationError(SkillHubException):
    """认证失败异常"""

    def __init__(self, message: str = "认证失败", details: Optional[dict] = None):
        super().__init__(message, "AUTH_FAILED", details)


class AuthorizationError(SkillHubException):
    """授权失败异常"""

    def __init__(self, message: str = "权限不足", details: Optional[dict] = None):
        super().__init__(message, "FORBIDDEN", details)


class TokenExpiredError(SkillHubException):
    """令牌过期异常"""

    def __init__(self, message: str = "令牌已过期"):
        super().__init__(message, "TOKEN_EXPIRED")


class InvalidTokenError(SkillHubException):
    """无效令牌异常"""

    def __init__(self, message: str = "无效的令牌"):
        super().__init__(message, "INVALID_TOKEN")


# ==================== 资源异常 ====================

class ResourceNotFoundError(SkillHubException):
    """资源不存在异常"""

    def __init__(self, resource_type: str, resource_id: str):
        super().__init__(
            f"{resource_type} 不存在: {resource_id}",
            "RESOURCE_NOT_FOUND",
            {"resource_type": resource_type, "resource_id": resource_id},
        )


class ResourceAlreadyExistsError(SkillHubException):
    """资源已存在异常"""

    def __init__(self, resource_type: str, field: str, value: str):
        super().__init__(
            f"{resource_type} 已存在: {field}={value}",
            "RESOURCE_EXISTS",
            {"resource_type": resource_type, "field": field, "value": value},
        )


# ==================== Skill 相关异常 ====================

class SkillNotFoundError(ResourceNotFoundError):
    """Skill 不存在异常"""

    def __init__(self, skill_id: str):
        super().__init__("Skill", skill_id)


class SkillValidationError(SkillHubException):
    """Skill 验证异常"""

    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, "SKILL_VALIDATION_ERROR", details)


class SkillLockError(SkillHubException):
    """Skill 编辑锁异常"""

    def __init__(self, skill_id: str, locked_by: str, message: str = "Skill 正在被编辑"):
        super().__init__(
            message,
            "SKILL_LOCKED",
            {"skill_id": skill_id, "locked_by": locked_by},
        )


# ==================== Git 相关异常 ====================

class GitOperationError(SkillHubException):
    """Git 操作异常"""

    def __init__(self, operation: str, message: str, details: Optional[dict] = None):
        super().__init__(
            f"Git {operation} 失败: {message}",
            "GIT_OPERATION_ERROR",
            {"operation": operation, **(details or {})},
        )


class GitRepoNotFoundError(ResourceNotFoundError):
    """Git 仓库不存在异常"""

    def __init__(self, repo_id: str):
        super().__init__("GitRepo", repo_id)


class GitSyncError(SkillHubException):
    """Git 同步异常"""

    def __init__(self, repo_url: str, message: str):
        super().__init__(
            f"Git 同步失败 [{repo_url}]: {message}",
            "GIT_SYNC_ERROR",
            {"repo_url": repo_url},
        )


# ==================== 安全异常 ====================

class SecurityError(SkillHubException):
    """安全异常"""

    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, "SECURITY_ERROR", details)


class PathTraversalError(SecurityError):
    """路径穿越攻击异常"""

    def __init__(self, path: str):
        super().__init__(f"检测到路径穿越攻击: {path}", {"path": path})


class FileSizeExceededError(SecurityError):
    """文件大小超限异常"""

    def __init__(self, file_name: str, size: int, max_size: int):
        super().__init__(
            f"文件大小超限: {file_name}",
            {"file_name": file_name, "size": size, "max_size": max_size},
        )


class ForbiddenFileTypeError(SecurityError):
    """禁止的文件类型异常"""

    def __init__(self, file_name: str, file_type: str):
        super().__init__(
            f"禁止的文件类型: {file_name}",
            {"file_name": file_name, "file_type": file_type},
        )


class SensitiveContentError(SecurityError):
    """敏感内容异常"""

    def __init__(self, file_name: str, findings: list[dict]):
        super().__init__(
            f"检测到敏感内容: {file_name}",
            {"file_name": file_name, "findings": findings},
        )


class SSRFError(SecurityError):
    """SSRF 攻击异常"""

    def __init__(self, url: str, reason: str):
        super().__init__(
            f"SSRF 攻击检测: {url}",
            {"url": url, "reason": reason},
        )


# ==================== 搜索异常 ====================

class SearchError(SkillHubException):
    """搜索异常"""

    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, "SEARCH_ERROR", details)


class IndexError(SkillHubException):
    """索引异常"""

    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, "INDEX_ERROR", details)


# ==================== 上传异常 ====================

class UploadError(SkillHubException):
    """上传异常"""

    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, "UPLOAD_ERROR", details)


class ZipExtractionError(UploadError):
    """ZIP 解压异常"""

    def __init__(self, message: str):
        super().__init__(f"ZIP 解压失败: {message}")


# ==================== 配置异常 ====================

class ConfigurationError(SkillHubException):
    """配置异常"""

    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, "CONFIG_ERROR", details)


# ==================== 加密异常 ====================

class EncryptionError(SkillHubException):
    """加密异常"""

    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, "ENCRYPTION_ERROR", details)
