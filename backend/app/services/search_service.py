"""
搜索服务

实现三层搜索架构：
- 召回层：向量搜索 + 全文检索
- 精排层：名称精确匹配、标签精确匹配、部门/技术栈匹配
- 业务加权：下载量权重、使用量权重、收藏量权重、官方认证权重

检索范围：仅索引 SKILL.md
索引字段权重：
  - title: 权重 ×3
  - summary: 权重 ×2
  - tags: 权重 ×2
  - body_markdown: 权重 ×1
"""
import json
import math
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum
from pathlib import Path
from typing import Optional

import jieba
import numpy as np
from sqlalchemy import and_, select, func
from sqlalchemy.ext.asyncio import AsyncSession
from whoosh import index
from whoosh.analysis import Tokenizer, Token
from whoosh.fields import ID, TEXT, KEYWORD, NUMERIC, BOOLEAN, Schema
from whoosh.qparser import MultifieldParser, OrGroup, QueryParser
from whoosh.scoring import BM25F, Weighting

from app.core.config import get_settings
from app.core.exceptions import SearchError
from app.db.models import Skill, GitRepo


class SearchMode(str, Enum):
    """搜索模式"""
    FULLTEXT = "fulltext"
    VECTOR = "vector"
    HYBRID = "hybrid"


class SortBy(str, Enum):
    """排序方式"""
    RELEVANCE = "relevance"
    FAVORITE_COUNT = "favorite_count"
    DOWNLOAD_COUNT = "download_count"
    UPDATED_AT = "updated_at"
    BLEND = "blend"


@dataclass
class SearchFilter:
    """搜索过滤条件"""
    source_type: Optional[str] = None
    repo_source_id: Optional[str] = None
    status: Optional[str] = None


@dataclass
class SearchResultItem:
    """搜索结果项"""
    skill_id: str
    name: str
    title: str
    summary: str
    tags: list[str]
    score: float
    relevance_score: float = 0.0
    business_score: float = 0.0
    download_count: int = 0
    favorite_count: int = 0
    usage_count: int = 0
    is_official: bool = False
    source_type: str = "private"
    updated_at: Optional[datetime] = None


@dataclass
class RecallResult:
    """召回层结果"""
    items: list[dict] = field(default_factory=list)
    total: int = 0


class ChineseTokenizer(Tokenizer):
    """中文分词器"""

    def __init__(self):
        pass

    def __call__(self, value, positions=False, chars=False, keeporiginal=False,
                 removestops=True, start_pos=0, start_char=0, mode='', **kwargs):
        tokens = jieba.cut(value, cut_all=False)
        pos = start_pos
        char_pos = start_char
        for token in tokens:
            t = Token(positions, chars, removestops=removestops, mode=mode, **kwargs)
            t.text = token
            t.stopped = False
            if positions:
                t.pos = pos
                pos += 1
            if chars:
                t.startchar = char_pos
                char_pos += len(token)
                t.endchar = char_pos
            yield t


def chinese_analyzer():
    """中文分析器"""
    return ChineseTokenizer()


class CustomBM25F(Weighting):
    """自定义 BM25F 权重
    
    字段权重：
    - title: 权重 ×3
    - summary: 权重 ×2
    - tags: 权重 ×2
    - body_markdown: 权重 ×1
    """
    def __init__(self):
        super().__init__()
        self.title_b = 0.75
        self.title_k1 = 1.5
        self.summary_b = 0.75
        self.summary_k1 = 1.5
        self.tags_b = 0.75
        self.tags_k1 = 1.5
        self.body_b = 0.75
        self.body_k1 = 1.5

    def scorer(self, searcher, fieldname, text, qf=1):
        return self.CustomBM25FScorer(
            searcher, fieldname, text, qf,
            title_b=self.title_b, title_k1=self.title_k1,
            summary_b=self.summary_b, summary_k1=self.summary_k1,
            tags_b=self.tags_b, tags_k1=self.tags_k1,
            body_b=self.body_b, body_k1=self.body_k1,
        )

    class CustomBM25FScorer:
        """自定义 BM25F 评分器"""
        def __init__(self, searcher, fieldname, text, qf, **kwargs):
            self.searcher = searcher
            self.fieldname = fieldname
            self.text = text
            self.qf = qf
            self.kwargs = kwargs

        def score(self, matcher):
            # 获取字段权重
            field_weights = {
                "title": 3.0,
                "summary": 2.0,
                "tags": 2.0,
                "body_markdown": 1.0,
            }
            weight = field_weights.get(self.fieldname, 1.0)
            return matcher.weight() * weight


class SearchService:
    """搜索服务
    
    三层架构：
    1. 召回层：向量搜索 + 全文检索
    2. 精排层：名称精确匹配、标签精确匹配
    3. 业务加权：下载量、使用量、收藏量、官方认证
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.settings = get_settings()
        self._fulltext_index = None
        self._embedding_model = None
        self._vector_index = None
        self._vector_metadata = None

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
        """初始化全文索引
        
        索引字段：
        - skill_id: 唯一标识
        - name: Skill 名称
        - title: 标题（权重 ×3）
        - summary: 摘要（权重 ×2）
        - tags: 标签（权重 ×2）
        - body_markdown: 正文（权重 ×1）
        - download_count: 下载数
        - favorite_count: 收藏数
        - usage_count: 使用数
        - is_official: 是否官方
        - source_type: 来源类型
        - repo_source_id: 仓库源 ID
        - status: 状态
        - updated_at: 更新时间
        """
        index_path = self.settings.fulltext_index_path_full
        index_path.mkdir(parents=True, exist_ok=True)
        
        schema = Schema(
            skill_id=ID(stored=True, unique=True),
            name=TEXT(stored=True, analyzer=chinese_analyzer()),
            title=TEXT(stored=True, analyzer=chinese_analyzer()),
            summary=TEXT(stored=True, analyzer=chinese_analyzer()),
            tags=KEYWORD(stored=True, commas=True),
            body_markdown=TEXT(stored=True, analyzer=chinese_analyzer()),
            download_count=NUMERIC(stored=True, numtype=int),
            favorite_count=NUMERIC(stored=True, numtype=int),
            usage_count=NUMERIC(stored=True, numtype=int),
            is_official=BOOLEAN(stored=True),
            source_type=KEYWORD(stored=True),
            repo_source_id=ID(stored=True),
            status=KEYWORD(stored=True),
            updated_at=NUMERIC(stored=True, numtype=float),
        )
        
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

    def _load_vector_index(self):
        """加载向量索引"""
        vector_index_path = self.settings.vector_index_path_full
        embeddings_file = vector_index_path / "embeddings.npy"
        metadata_file = vector_index_path / "metadata.json"
        
        if not embeddings_file.exists() or not metadata_file.exists():
            return None, None
        
        embeddings = np.load(str(embeddings_file))
        with open(metadata_file, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        
        return embeddings, metadata

    async def index_skill(self, skill: Skill, content: str) -> None:
        """索引 Skill
        
        仅索引 SKILL.md 文件内容
        """
        writer = self.fulltext_index.writer()
        
        try:
            tags = []
            if skill.tags:
                try:
                    tags = json.loads(skill.tags)
                except json.JSONDecodeError:
                    tags = []
            
            repo_source_id = None
            if skill.git_repo_id:
                result = await self.session.execute(
                    select(GitRepo).where(GitRepo.id == skill.git_repo_id)
                )
                git_repo = result.scalar_one_or_none()
                if git_repo:
                    repo_source_id = git_repo.id
            
            updated_at_ts = skill.updated_at.timestamp() if skill.updated_at else 0
            
            writer.update_document(
                skill_id=skill.id,
                name=skill.name,
                title=skill.title or skill.name,
                summary=skill.summary or "",
                tags=",".join(tags) if tags else "",
                body_markdown=content,
                download_count=skill.download_count or 0,
                favorite_count=skill.favorite_count or 0,
                usage_count=skill.usage_count or 0,
                is_official=skill.is_official or False,
                source_type=skill.source_type,
                repo_source_id=repo_source_id or "",
                status="active" if skill.is_active else "inactive",
                updated_at=updated_at_ts,
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
        mode: SearchMode = SearchMode.HYBRID,
        sort_by: SortBy = SortBy.BLEND,
        search_filter: Optional[SearchFilter] = None,
    ) -> tuple[list[SearchResultItem], int]:
        """
        搜索 Skills
        
        Args:
            query: 搜索关键词
            page: 页码
            page_size: 每页数量
            mode: 搜索模式（fulltext/vector/hybrid）
            sort_by: 排序方式
            search_filter: 过滤条件
        
        Returns:
            (结果列表, 总数)
        """
        if search_filter is None:
            search_filter = SearchFilter()
        
        if mode == SearchMode.FULLTEXT:
            recall_result = await self._fulltext_recall(query, search_filter)
        elif mode == SearchMode.VECTOR:
            recall_result = await self._vector_recall(query, search_filter)
        else:
            recall_result = await self._hybrid_recall(query, search_filter)
        
        ranked_items = await self._rerank(query, recall_result.items)
        
        weighted_items = self._apply_business_weights(ranked_items)
        
        sorted_items = self._sort_results(weighted_items, sort_by)
        
        start = (page - 1) * page_size
        end = start + page_size
        
        return sorted_items[start:end], len(sorted_items)

    async def _fulltext_recall(
        self,
        query: str,
        search_filter: SearchFilter,
    ) -> RecallResult:
        """召回层：全文检索"""
        searcher = self.fulltext_index.searcher()
        
        try:
            parser = MultifieldParser(
                ["name", "title", "summary", "tags", "body_markdown"],
                self.fulltext_index.schema,
                group=OrGroup,
            )
            
            q = parser.parse(query)
            
            filter_queries = []
            if search_filter.source_type:
                filter_queries.append(QueryParser("source_type", None).parse(search_filter.source_type))
            if search_filter.repo_source_id:
                filter_queries.append(QueryParser("repo_source_id", None).parse(search_filter.repo_source_id))
            if search_filter.status:
                filter_queries.append(QueryParser("status", None).parse(search_filter.status))
            
            results = searcher.search(q, limit=200)
            
            items = []
            for hit in results:
                items.append({
                    "skill_id": hit["skill_id"],
                    "name": hit["name"],
                    "title": hit["title"],
                    "summary": hit["summary"],
                    "tags": hit.get("tags", "").split(",") if hit.get("tags") else [],
                    "score": hit.score,
                    "download_count": hit.get("download_count", 0),
                    "favorite_count": hit.get("favorite_count", 0),
                    "usage_count": hit.get("usage_count", 0),
                    "is_official": hit.get("is_official", False),
                    "source_type": hit.get("source_type", "private"),
                    "updated_at": datetime.fromtimestamp(hit.get("updated_at", 0), UTC) if hit.get("updated_at") else None,
                })
            
            return RecallResult(items=items, total=len(items))
            
        finally:
            searcher.close()

    async def _vector_recall(
        self,
        query: str,
        search_filter: SearchFilter,
    ) -> RecallResult:
        """召回层：向量检索"""
        if not self.embedding_model:
            return await self._fulltext_recall(query, search_filter)
        
        query_embedding = self.embedding_model.encode(query)
        
        embeddings, metadata = self._load_vector_index()
        if embeddings is None or metadata is None:
            return RecallResult(items=[], total=0)
        
        similarities = np.dot(embeddings, query_embedding) / (
            np.linalg.norm(embeddings, axis=1) * np.linalg.norm(query_embedding)
        )
        
        indices = np.argsort(similarities)[::-1]
        
        items = []
        for idx in indices:
            skill_meta = metadata[idx]
            
            if search_filter.source_type and skill_meta.get("source_type") != search_filter.source_type:
                continue
            if search_filter.repo_source_id and skill_meta.get("repo_source_id") != search_filter.repo_source_id:
                continue
            if search_filter.status and skill_meta.get("status") != search_filter.status:
                continue
            
            items.append({
                "skill_id": skill_meta["skill_id"],
                "name": skill_meta["name"],
                "title": skill_meta["title"],
                "summary": skill_meta["summary"],
                "tags": skill_meta.get("tags", []),
                "score": float(similarities[idx]),
                "download_count": skill_meta.get("download_count", 0),
                "favorite_count": skill_meta.get("favorite_count", 0),
                "usage_count": skill_meta.get("usage_count", 0),
                "is_official": skill_meta.get("is_official", False),
                "source_type": skill_meta.get("source_type", "private"),
                "updated_at": datetime.fromisoformat(skill_meta["updated_at"]) if skill_meta.get("updated_at") else None,
            })
        
        return RecallResult(items=items, total=len(items))

    async def _hybrid_recall(
        self,
        query: str,
        search_filter: SearchFilter,
    ) -> RecallResult:
        """召回层：混合检索（RRF 融合）"""
        fulltext_result = await self._fulltext_recall(query, search_filter)
        vector_result = await self._vector_recall(query, search_filter)
        
        fulltext_items = fulltext_result.items
        vector_items = vector_result.items
        
        k = 60
        scores = {}
        
        for rank, result in enumerate(fulltext_items):
            skill_id = result["skill_id"]
            scores[skill_id] = {
                "score": 1 / (k + rank + 1),
                "data": result,
            }
        
        for rank, result in enumerate(vector_items):
            skill_id = result["skill_id"]
            if skill_id in scores:
                scores[skill_id]["score"] += 1 / (k + rank + 1)
            else:
                scores[skill_id] = {
                    "score": 1 / (k + rank + 1),
                    "data": result,
                }
        
        sorted_results = sorted(
            scores.items(),
            key=lambda x: x[1]["score"],
            reverse=True,
        )
        
        items = []
        for skill_id, data in sorted_results:
            items.append({
                **data["data"],
                "score": data["score"],
            })
        
        return RecallResult(items=items, total=len(items))

    async def _rerank(self, query: str, items: list[dict]) -> list[dict]:
        """精排层
        
        精排因子：
        - 名称精确匹配
        - 标签精确匹配
        """
        query_lower = query.lower()
        query_tokens = set(jieba.cut(query))
        
        for item in items:
            rerank_score = item.get("score", 0)
            
            name = item.get("name", "").lower()
            if query_lower == name:
                rerank_score += 10.0
            elif query_lower in name:
                rerank_score += 5.0
            
            tags = item.get("tags", [])
            for tag in tags:
                tag_lower = tag.lower()
                if query_lower == tag_lower:
                    rerank_score += 8.0
                elif query_lower in tag_lower:
                    rerank_score += 4.0
            
            title = item.get("title", "").lower()
            if query_lower in title:
                rerank_score += 3.0
            
            item["relevance_score"] = rerank_score
        
        return items

    def _apply_business_weights(self, items: list[dict]) -> list[dict]:
        """业务加权层
        
        权重因子：
        - 下载量权重
        - 使用量权重
        - 收藏量权重
        - 官方认证权重
        """
        max_download = max((item.get("download_count", 0) for item in items), default=1)
        max_favorite = max((item.get("favorite_count", 0) for item in items), default=1)
        max_usage = max((item.get("usage_count", 0) for item in items), default=1)
        
        for item in items:
            business_score = 0.0
            
            if max_download > 0:
                business_score += (item.get("download_count", 0) / max_download) * 2.0
            
            if max_favorite > 0:
                business_score += (item.get("favorite_count", 0) / max_favorite) * 2.0
            
            if max_usage > 0:
                business_score += (item.get("usage_count", 0) / max_usage) * 1.0
            
            if item.get("is_official", False):
                business_score += 3.0
            
            item["business_score"] = business_score
        
        return items

    def _sort_results(self, items: list[dict], sort_by: SortBy) -> list[SearchResultItem]:
        """排序结果"""
        if sort_by == SortBy.RELEVANCE:
            sorted_items = sorted(items, key=lambda x: x.get("relevance_score", 0), reverse=True)
        elif sort_by == SortBy.FAVORITE_COUNT:
            sorted_items = sorted(items, key=lambda x: x.get("favorite_count", 0), reverse=True)
        elif sort_by == SortBy.DOWNLOAD_COUNT:
            sorted_items = sorted(items, key=lambda x: x.get("download_count", 0), reverse=True)
        elif sort_by == SortBy.UPDATED_AT:
            sorted_items = sorted(items, key=lambda x: x.get("updated_at") or datetime.min.replace(tzinfo=UTC), reverse=True)
        else:
            sorted_items = self._blend_sort(items)
        
        return [
            SearchResultItem(
                skill_id=item["skill_id"],
                name=item["name"],
                title=item["title"],
                summary=item["summary"],
                tags=item["tags"],
                score=item.get("score", 0),
                relevance_score=item.get("relevance_score", 0),
                business_score=item.get("business_score", 0),
                download_count=item.get("download_count", 0),
                favorite_count=item.get("favorite_count", 0),
                usage_count=item.get("usage_count", 0),
                is_official=item.get("is_official", False),
                source_type=item.get("source_type", "private"),
                updated_at=item.get("updated_at"),
            )
            for item in sorted_items
        ]

    def _blend_sort(self, items: list[dict]) -> list[dict]:
        """混合排序
        
        blend 公式：
        final_score = 0.55 × relevance_score + 0.20 × favorite_score + 0.15 × download_score + 0.10 × freshness_score
        """
        max_relevance = max((item.get("relevance_score", 0) for item in items), default=1)
        max_favorite = max((item.get("favorite_count", 0) for item in items), default=1)
        max_download = max((item.get("download_count", 0) for item in items), default=1)
        
        now = datetime.now(UTC)
        max_freshness = 0
        for item in items:
            updated_at = item.get("updated_at")
            if updated_at:
                days_old = (now - updated_at).days
                freshness = max(0, 365 - days_old) / 365
                max_freshness = max(max_freshness, freshness)
        if max_freshness == 0:
            max_freshness = 1
        
        for item in items:
            relevance_score = item.get("relevance_score", 0) / max_relevance if max_relevance > 0 else 0
            favorite_score = item.get("favorite_count", 0) / max_favorite if max_favorite > 0 else 0
            download_score = item.get("download_count", 0) / max_download if max_download > 0 else 0
            
            updated_at = item.get("updated_at")
            if updated_at:
                days_old = (now - updated_at).days
                freshness_score = max(0, 365 - days_old) / 365 / max_freshness
            else:
                freshness_score = 0
            
            final_score = (
                0.55 * relevance_score
                + 0.20 * favorite_score
                + 0.15 * download_score
                + 0.10 * freshness_score
            )
            
            item["final_score"] = final_score
        
        return sorted(items, key=lambda x: x.get("final_score", 0), reverse=True)

    async def rebuild_index(self) -> dict:
        """重建索引"""
        result = await self.session.execute(
            select(Skill).where(Skill.is_active == True)
        )
        skills = result.scalars().all()
        
        fulltext_count = 0
        vector_count = 0
        
        for skill in skills:
            skill_md_path = Path(skill.storage_path) / "SKILL.md"
            if skill_md_path.exists():
                with open(skill_md_path, "r", encoding="utf-8") as f:
                    content = f.read()
                await self.index_skill(skill, content)
                fulltext_count += 1
        
        if self.embedding_model:
            embeddings = []
            metadata = []
            
            for skill in skills:
                skill_md_path = Path(skill.storage_path) / "SKILL.md"
                if skill_md_path.exists():
                    with open(skill_md_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    
                    embedding = self.embedding_model.encode(content)
                    embeddings.append(embedding)
                    
                    tags = []
                    if skill.tags:
                        try:
                            tags = json.loads(skill.tags)
                        except json.JSONDecodeError:
                            tags = []
                    
                    repo_source_id = None
                    if skill.git_repo_id:
                        repo_result = await self.session.execute(
                            select(GitRepo).where(GitRepo.id == skill.git_repo_id)
                        )
                        git_repo = repo_result.scalar_one_or_none()
                        if git_repo:
                            repo_source_id = git_repo.id
                    
                    metadata.append({
                        "skill_id": skill.id,
                        "name": skill.name,
                        "title": skill.title or skill.name,
                        "summary": skill.summary or "",
                        "tags": tags,
                        "download_count": skill.download_count or 0,
                        "favorite_count": skill.favorite_count or 0,
                        "usage_count": skill.usage_count or 0,
                        "is_official": skill.is_official or False,
                        "source_type": skill.source_type,
                        "repo_source_id": repo_source_id,
                        "status": "active" if skill.is_active else "inactive",
                        "updated_at": skill.updated_at.isoformat() if skill.updated_at else None,
                    })
                    vector_count += 1
            
            vector_index_path = self.settings.vector_index_path_full
            vector_index_path.mkdir(parents=True, exist_ok=True)
            
            np.save(str(vector_index_path / "embeddings.npy"), np.array(embeddings))
            with open(vector_index_path / "metadata.json", "w", encoding="utf-8") as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        return {
            "fulltext_indexed": fulltext_count,
            "vector_indexed": vector_count,
        }

    async def update_skill_stats(self, skill_id: str) -> None:
        """更新 Skill 统计信息到索引"""
        result = await self.session.execute(
            select(Skill).where(Skill.id == skill_id)
        )
        skill = result.scalar_one_or_none()
        if not skill:
            return
        
        skill_md_path = Path(skill.storage_path) / "SKILL.md"
        if skill_md_path.exists():
            with open(skill_md_path, "r", encoding="utf-8") as f:
                content = f.read()
            await self.index_skill(skill, content)
