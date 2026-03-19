"""
搜索服务

实现混合检索：
- 全文检索（Whoosh + jieba）
- 向量检索（sentence-transformers）
- 混合检索（RRF 融合）
"""
import json
import os
from pathlib import Path
from typing import Optional

import jieba
import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from whoosh import index
from whoosh.analysis import StemmingAnalyzer, Tokenizer
from whoosh.fields import ID, TEXT, KEYWORD, Schema
from whoosh.qparser import MultifieldParser, OrGroup

from app.core.config import get_settings
from app.core.exceptions import SearchError
from app.db.models import Skill


class ChineseTokenizer(Tokenizer):
    """中文分词器"""

    def __init__(self):
        pass

    def __call__(self, value, positions=False, chars=False, keeporiginal=False,
                 removestops=True, start_pos=0, start_char=0, mode='', **kwargs):
        tokens = jieba.cut(value, cut_all=False)
        for i, token in enumerate(tokens):
            yield token


def chinese_analyzer():
    """中文分析器"""
    return ChineseTokenizer()


class SearchService:
    """搜索服务"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.settings = get_settings()
        self._fulltext_index = None
        self._embedding_model = None
        self._vector_index = None

    @property
    def fulltext_index(self):
        """获取全文索引"""
        if self._fulltext_index is None:
            self._init_fulltext_index()
        return self._fulltext_index

    @property
    def embedding_model(self):
        """获取嵌入模型"""
        if self._embedding_model is None:
            self._init_embedding_model()
        return self._embedding_model

    def _init_fulltext_index(self):
        """初始化全文索引"""
        index_path = self.settings.fulltext_index_path_full
        index_path.mkdir(parents=True, exist_ok=True)
        
        # 定义索引模式
        schema = Schema(
            skill_id=ID(stored=True, unique=True),
            name=TEXT(stored=True, analyzer=chinese_analyzer()),
            title=TEXT(stored=True, analyzer=chinese_analyzer()),
            summary=TEXT(stored=True, analyzer=chinese_analyzer()),
            content=TEXT(stored=True, analyzer=chinese_analyzer()),
            tags=KEYWORD(stored=True, commas=True),
        )
        
        # 创建或打开索引
        if index.exists_in(str(index_path)):
            self._fulltext_index = index.open_dir(str(index_path))
        else:
            self._fulltext_index = index.create_in(str(index_path), schema)

    def _init_embedding_model(self):
        """初始化嵌入模型"""
        try:
            from sentence_transformers import SentenceTransformer
            self._embedding_model = SentenceTransformer(self.settings.embedding_model)
        except ImportError:
            self._embedding_model = None

    async def index_skill(self, skill: Skill, content: str) -> None:
        """索引 Skill"""
        writer = self.fulltext_index.writer()
        
        try:
            # 解析 tags
            tags = []
            if skill.tags:
                try:
                    tags = json.loads(skill.tags)
                except json.JSONDecodeError:
                    tags = []
            
            # 更新或添加文档
            writer.update_document(
                skill_id=skill.id,
                name=skill.name,
                title=skill.title or skill.name,
                summary=skill.summary or "",
                content=content,
                tags=",".join(tags) if tags else "",
            )
            
            writer.commit()
            
        except Exception as e:
            writer.cancel()
            raise SearchError(f"索引失败: {str(e)}")

    async def remove_skill_from_index(self, skill_id: str) -> None:
        """从索引中删除 Skill"""
        writer = self.fulltext_index.writer()
        
        try:
            writer.delete_by_term("skill_id", skill_id)
            writer.commit()
        except Exception as e:
            writer.cancel()
            raise SearchError(f"删除索引失败: {str(e)}")

    async def search(
        self,
        query: str,
        page: int = 1,
        page_size: int = 20,
        mode: str = "hybrid",  # fulltext, vector, hybrid
    ) -> tuple[list[dict], int]:
        """
        搜索 Skills
        
        Args:
            query: 搜索关键词
            page: 页码
            page_size: 每页数量
            mode: 搜索模式（fulltext/vector/hybrid）
        
        Returns:
            (结果列表, 总数)
        """
        if mode == "fulltext":
            return await self._fulltext_search(query, page, page_size)
        elif mode == "vector":
            return await self._vector_search(query, page, page_size)
        else:
            return await self._hybrid_search(query, page, page_size)

    async def _fulltext_search(
        self,
        query: str,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict], int]:
        """全文检索"""
        searcher = self.fulltext_index.searcher()
        
        try:
            # 创建多字段查询解析器
            parser = MultifieldParser(
                ["name", "title", "summary", "content", "tags"],
                self.fulltext_index.schema,
                group=OrGroup,
            )
            
            # 解析查询
            q = parser.parse(query)
            
            # 执行搜索
            results = searcher.search_page(q, page, pagelen=page_size)
            
            items = []
            for hit in results:
                items.append({
                    "skill_id": hit["skill_id"],
                    "name": hit["name"],
                    "title": hit["title"],
                    "summary": hit["summary"],
                    "tags": hit.get("tags", "").split(",") if hit.get("tags") else [],
                    "score": hit.score,
                })
            
            return items, results.total
            
        finally:
            searcher.close()

    async def _vector_search(
        self,
        query: str,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict], int]:
        """向量检索"""
        if not self.embedding_model:
            return await self._fulltext_search(query, page, page_size)
        
        # 生成查询向量
        query_embedding = self.embedding_model.encode(query)
        
        # 加载向量索引
        vector_index_path = self.settings.vector_index_path_full
        embeddings_file = vector_index_path / "embeddings.npy"
        metadata_file = vector_index_path / "metadata.json"
        
        if not embeddings_file.exists() or not metadata_file.exists():
            return [], 0
        
        # 加载嵌入向量
        embeddings = np.load(str(embeddings_file))
        with open(metadata_file, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        
        # 计算相似度
        similarities = np.dot(embeddings, query_embedding) / (
            np.linalg.norm(embeddings, axis=1) * np.linalg.norm(query_embedding)
        )
        
        # 排序
        indices = np.argsort(similarities)[::-1]
        
        # 分页
        start = (page - 1) * page_size
        end = start + page_size
        
        items = []
        for idx in indices[start:end]:
            skill_meta = metadata[idx]
            items.append({
                "skill_id": skill_meta["skill_id"],
                "name": skill_meta["name"],
                "title": skill_meta["title"],
                "summary": skill_meta["summary"],
                "tags": skill_meta.get("tags", []),
                "score": float(similarities[idx]),
            })
        
        return items, len(metadata)

    async def _hybrid_search(
        self,
        query: str,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict], int]:
        """混合检索（RRF 融合）"""
        # 获取全文检索结果
        fulltext_results, _ = await self._fulltext_search(query, 1, 100)
        
        # 获取向量检索结果
        vector_results, _ = await self._vector_search(query, 1, 100)
        
        # RRF 融合
        k = 60  # RRF 参数
        scores = {}
        
        for rank, result in enumerate(fulltext_results):
            skill_id = result["skill_id"]
            scores[skill_id] = scores.get(skill_id, 0) + 1 / (k + rank + 1)
            scores[skill_id] = {
                "score": scores.get(skill_id, 0),
                "data": result,
            }
        
        for rank, result in enumerate(vector_results):
            skill_id = result["skill_id"]
            if skill_id in scores:
                scores[skill_id]["score"] += 1 / (k + rank + 1)
            else:
                scores[skill_id] = {
                    "score": 1 / (k + rank + 1),
                    "data": result,
                }
        
        # 排序
        sorted_results = sorted(
            scores.items(),
            key=lambda x: x[1]["score"],
            reverse=True,
        )
        
        # 分页
        start = (page - 1) * page_size
        end = start + page_size
        
        items = []
        for skill_id, data in sorted_results[start:end]:
            items.append({
                **data["data"],
                "score": data["score"],
            })
        
        return items, len(sorted_results)

    async def rebuild_index(self) -> dict:
        """重建索引"""
        # 获取所有活跃的 Skills
        result = await self.session.execute(
            select(Skill).where(Skill.is_active == True)
        )
        skills = result.scalars().all()
        
        fulltext_count = 0
        vector_count = 0
        
        # 重建全文索引
        for skill in skills:
            skill_md_path = Path(skill.storage_path) / "SKILL.md"
            if skill_md_path.exists():
                with open(skill_md_path, "r", encoding="utf-8") as f:
                    content = f.read()
                await self.index_skill(skill, content)
                fulltext_count += 1
        
        # 重建向量索引
        if self.embedding_model:
            embeddings = []
            metadata = []
            
            for skill in skills:
                skill_md_path = Path(skill.storage_path) / "SKILL.md"
                if skill_md_path.exists():
                    with open(skill_md_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    
                    # 生成嵌入向量
                    embedding = self.embedding_model.encode(content)
                    embeddings.append(embedding)
                    
                    # 解析 tags
                    tags = []
                    if skill.tags:
                        try:
                            tags = json.loads(skill.tags)
                        except json.JSONDecodeError:
                            tags = []
                    
                    metadata.append({
                        "skill_id": skill.id,
                        "name": skill.name,
                        "title": skill.title or skill.name,
                        "summary": skill.summary or "",
                        "tags": tags,
                    })
                    vector_count += 1
            
            # 保存向量索引
            vector_index_path = self.settings.vector_index_path_full
            vector_index_path.mkdir(parents=True, exist_ok=True)
            
            np.save(str(vector_index_path / "embeddings.npy"), np.array(embeddings))
            with open(vector_index_path / "metadata.json", "w", encoding="utf-8") as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        return {
            "fulltext_indexed": fulltext_count,
            "vector_indexed": vector_count,
        }
