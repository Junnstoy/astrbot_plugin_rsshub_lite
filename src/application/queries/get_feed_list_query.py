"""
获取 Feed 列表查询

处理获取用户 Feed 订阅列表的查询。
"""

from pydantic import BaseModel, Field

from ...domain.repositories.feed_repository import FeedRepository
from ...domain.repositories.subscription_repository import SubscriptionRepository
from ..dto.feed_dto import FeedDTO


class FeedListResult(BaseModel):
    """
    Feed 列表查询结果
    """

    feeds: list[FeedDTO] = Field(default_factory=list, description="Feed 列表")
    total: int = Field(default=0, description="总数")
    page: int = Field(default=1, description="当前页码")
    page_size: int = Field(default=20, description="每页数量")

    class Config:
        frozen = True


class GetFeedListQuery:
    """
    获取 Feed 列表查询

    处理获取用户 Feed 订阅列表的查询。
    """

    def __init__(
        self,
        subscription_repo: SubscriptionRepository,
        feed_repo: FeedRepository,
    ):
        self._subscription_repo = subscription_repo
        self._feed_repo = feed_repo

    async def execute(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> FeedListResult:
        """
        执行查询

        Args:
            user_id: 用户 ID
            page: 页码（从 1 开始）
            page_size: 每页数量

        Returns:
            FeedListResult: 查询结果
        """
        subscriptions = await self._subscription_repo.get_by_user(user_id)

        feed_dtos: list[FeedDTO] = []
        for sub in subscriptions:
            if sub.feed_id:
                feed = await self._feed_repo.get_by_id(sub.feed_id)
                if feed:
                    feed_dtos.append(
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

        return FeedListResult(
            feeds=feed_dtos,
            total=len(feed_dtos),
            page=page,
            page_size=page_size,
        )
