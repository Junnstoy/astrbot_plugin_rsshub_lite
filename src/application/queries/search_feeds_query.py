"""
搜索 Feed 查询

处理搜索 Feed 的查询。
"""

from pydantic import BaseModel, Field

from ...domain.repositories.feed_repository import FeedRepository
from ...infrastructure.utils import get_logger
from ..dto.feed_dto import FeedDTO

logger = get_logger()


class SearchFeedsResult(BaseModel):
    """
    搜索 Feed 查询结果
    """

    feeds: list[FeedDTO] = Field(default_factory=list, description="Feed 列表")
    total: int = Field(default=0, description="总数")
    query: str = Field(default="", description="搜索关键词")

    class Config:
        frozen = True


class SearchFeedsQuery:
    """
    搜索 Feed 查询

    处理搜索 Feed 的查询。
    """

    def __init__(
        self,
        feed_repo: FeedRepository,
    ):
        self._feed_repo = feed_repo

    async def execute(
        self,
        query: str,
        page: int = 1,
        page_size: int = 20,
    ) -> SearchFeedsResult:
        """
        执行搜索

        Args:
            query: 搜索关键词
            page: 页码（从 1 开始）
            page_size: 每页数量

        Returns:
            SearchFeedsResult: 查询结果
        """
        query_lower = query.strip().lower()
        if not query_lower:
            return SearchFeedsResult(feeds=[], total=0, query=query)

        all_feeds = await self._feed_repo.get_all_active()

        matched: list[FeedDTO] = []
        for feed in all_feeds:
            if query_lower in feed.link.lower() or query_lower in feed.title.lower():
                matched.append(
                    FeedDTO(
                        id=feed.id,
                        link=feed.link,
                        title=feed.title,
                        state=feed.state,
                        etag=feed.etag,
                        last_modified=feed.last_modified,
                        created_at=feed.created_at,
                        updated_at=feed.updated_at,
                    )
                )

        total = len(matched)
        start = (page - 1) * page_size
        end = start + page_size
        paged = matched[start:end] if start < total else []

        return SearchFeedsResult(
            feeds=paged,
            total=total,
            query=query,
        )
