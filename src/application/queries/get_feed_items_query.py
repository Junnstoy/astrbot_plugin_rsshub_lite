"""
获取 Feed 条目查询

处理获取 Feed 条目的查询。
"""

from pydantic import BaseModel, Field

from ...domain.repositories.feed_repository import FeedRepository
from ...infrastructure.fetcher.rss import RSSFeedFetcher
from ...infrastructure.fetcher.rss.parser import RSSParser
from ...infrastructure.utils import get_logger
from ..dto.item_dto import ItemDTO

logger = get_logger()


class FeedItemsResult(BaseModel):
    """
    Feed 条目查询结果
    """

    items: list[ItemDTO] = Field(default_factory=list, description="条目列表")
    total: int = Field(default=0, description="总数")
    page: int = Field(default=1, description="当前页码")
    page_size: int = Field(default=20, description="每页数量")
    error: str = Field(default="", description="错误信息")

    class Config:
        frozen = True


class GetFeedItemsQuery:
    """
    获取 Feed 条目查询

    处理获取 Feed 条目的查询。
    """

    def __init__(
        self,
        feed_repo: FeedRepository,
    ):
        self._feed_repo = feed_repo

    async def execute(
        self,
        feed_id: int,
        page: int = 1,
        page_size: int = 20,
    ) -> FeedItemsResult:
        """
        执行查询

        Args:
            feed_id: Feed ID
            page: 页码（从 1 开始）
            page_size: 每页数量

        Returns:
            FeedItemsResult: 查询结果
        """
        feed = await self._feed_repo.get_by_id(feed_id)
        if not feed:
            return FeedItemsResult(
                items=[],
                total=0,
                page=page,
                page_size=page_size,
                error=f"Feed 不存在 (ID: {feed_id})",
            )

        fetcher = RSSFeedFetcher()
        try:
            web_feed = await fetcher.fetch(feed.link)
            if web_feed.error or not web_feed.content:
                return FeedItemsResult(
                    items=[],
                    total=0,
                    page=page,
                    page_size=page_size,
                    error=web_feed.error.error_name if web_feed.error else "抓取失败",
                )

            parser = RSSParser()
            entries, parse_err = parser.parse(web_feed.content)
            if parse_err:
                logger.warning(
                    "解析 Feed 内容失败: feed=%s, err=%s", feed.link, parse_err
                )

            item_dtos: list[ItemDTO] = []
            for entry in entries:
                published = None
                if hasattr(entry, "published_at") and entry.published_at:
                    published = entry.published_at
                item_dto = ItemDTO(
                    title=entry.title or "",
                    link=entry.link or "",
                    guid=entry.guid or "",
                    summary=entry.summary or "",
                    published_at=published,
                    author=entry.author or None,
                    media_urls=[],
                    tags=entry.tags or [],
                )
                item_dtos.append(item_dto)

            total = len(item_dtos)
            start = (page - 1) * page_size
            end = start + page_size
            paged = item_dtos[start:end] if start < total else []

            return FeedItemsResult(
                items=paged,
                total=total,
                page=page,
                page_size=page_size,
            )

        finally:
            await fetcher.close()
