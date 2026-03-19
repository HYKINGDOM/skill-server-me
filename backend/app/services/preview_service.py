"""
文件预览服务
"""
import base64
import hashlib
from pathlib import Path
from typing import Optional

import aiofiles
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import SecurityError
from app.db.models import Skill


class PreviewService:
    """文件预览服务"""

    # 允许预览的 MIME 类型
    ALLOWED_TEXT_TYPES = {
        "text/plain",
        "text/markdown",
        "text/html",
        "text/css",
        "text/javascript",
        "application/json",
        "application/x-yaml",
        "text/x-python",
        "text/typescript",
    }

    ALLOWED_IMAGE_TYPES = {
        "image/png",
        "image/jpeg",
        "image/gif",
        "image/svg+xml",
    }

    # 最大预览大小
    MAX_PREVIEW_SIZE = 1024 * 1024  # 1MB
    MAX_PREVIEW_LINES = 1000

    def __init__(self, session: AsyncSession):
        self.session = session
        self.settings = get_settings()

    async def preview_file(
        self,
        skill: Skill,
        file_path: str,
        mode: str = "source",  # source, render
    ) -> dict:
        """
        预览文件
        
        Args:
            skill: Skill 对象
            file_path: 文件路径
            mode: 预览模式（source/render）
        
        Returns:
            预览结果
        """
        storage_path = Path(skill.storage_path)
        full_path = storage_path / file_path
        
        # 安全检查：防止路径穿越
        try:
            full_path.resolve().relative_to(storage_path.resolve())
        except ValueError:
            raise SecurityError(f"路径穿越攻击检测: {file_path}")
        
        if not full_path.exists():
            return {
                "success": False,
                "error": "文件不存在",
            }
        
        # 检查文件大小
        file_size = full_path.stat().st_size
        if file_size > self.MAX_PREVIEW_SIZE:
            return {
                "success": False,
                "error": f"文件过大，最大支持 {self.MAX_PREVIEW_SIZE // 1024 // 1024}MB",
                "file_size": file_size,
            }
        
        # 获取文件类型
        ext = full_path.suffix.lower()
        mime_type = self._get_mime_type(ext)
        
        # 文本文件预览
        if mime_type in self.ALLOWED_TEXT_TYPES:
            return await self._preview_text(full_path, mime_type, mode)
        
        # 图片文件预览
        if mime_type in self.ALLOWED_IMAGE_TYPES:
            return await self._preview_image(full_path, mime_type)
        
        # 其他文件
        return {
            "success": True,
            "type": "binary",
            "mime_type": mime_type,
            "file_size": file_size,
            "file_name": full_path.name,
        }

    async def _preview_text(
        self,
        file_path: Path,
        mime_type: str,
        mode: str,
    ) -> dict:
        """预览文本文件"""
        async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
            content = await f.read()
        
        lines = content.split("\n")
        truncated = len(lines) > self.MAX_PREVIEW_LINES
        
        if truncated:
            content = "\n".join(lines[:self.MAX_PREVIEW_LINES])
        
        result = {
            "success": True,
            "type": "text",
            "mime_type": mime_type,
            "content": content,
            "line_count": len(lines),
            "truncated": truncated,
            "file_name": file_path.name,
        }
        
        # Markdown 渲染
        if mime_type == "text/markdown" and mode == "render":
            result["rendered"] = await self._render_markdown(content)
        
        # 代码高亮
        if mime_type in ["text/x-python", "text/javascript", "text/typescript"]:
            result["language"] = self._get_language(mime_type)
        
        return result

    async def _preview_image(
        self,
        file_path: Path,
        mime_type: str,
    ) -> dict:
        """预览图片文件"""
        async with aiofiles.open(file_path, "rb") as f:
            content = await f.read()
        
        # SVG 特殊处理
        if mime_type == "image/svg+xml":
            # 检查 SVG 中是否有脚本
            content_str = content.decode("utf-8")
            if "<script" in content_str.lower():
                return {
                    "success": False,
                    "error": "SVG 包含脚本，不允许预览",
                }
            
            return {
                "success": True,
                "type": "image",
                "mime_type": mime_type,
                "data": base64.b64encode(content).decode("utf-8"),
                "file_name": file_path.name,
            }
        
        return {
            "success": True,
            "type": "image",
            "mime_type": mime_type,
            "data": base64.b64encode(content).decode("utf-8"),
            "file_name": file_path.name,
        }

    async def _render_markdown(self, content: str) -> str:
        """渲染 Markdown"""
        try:
            from markdown_it import MarkdownIt
            md = MarkdownIt()
            return md.render(content)
        except ImportError:
            return content

    def _get_mime_type(self, ext: str) -> str:
        """获取 MIME 类型"""
        mime_map = {
            ".md": "text/markdown",
            ".txt": "text/plain",
            ".json": "application/json",
            ".yaml": "application/x-yaml",
            ".yml": "application/x-yaml",
            ".html": "text/html",
            ".css": "text/css",
            ".js": "text/javascript",
            ".ts": "text/typescript",
            ".py": "text/x-python",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".svg": "image/svg+xml",
        }
        return mime_map.get(ext, "application/octet-stream")

    def _get_language(self, mime_type: str) -> str:
        """获取代码语言"""
        language_map = {
            "text/x-python": "python",
            "text/javascript": "javascript",
            "text/typescript": "typescript",
            "text/css": "css",
            "text/html": "html",
            "application/json": "json",
            "application/x-yaml": "yaml",
        }
        return language_map.get(mime_type, "text")
