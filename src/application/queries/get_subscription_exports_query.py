"""Subscription export read-model query."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..dto.subscription_export_record import (
    SubscriptionExportRecord,
    build_subscription_export_record,
)

if TYPE_CHECKING:
    from ...domain.repositories.feed_repository import FeedRepository
    from ...domain.repositories.subscription_repository import SubscriptionRepository


class GetSubscriptionExportsQuery:
    """Build export read models for a user's subscriptions."""

    def __init__(
        self,
        subscription_repo: SubscriptionRepository,
        feed_repo: FeedRepository | None = None,
    ) -> None:
        self._subscription_repo = subscription_repo
        self._feed_repo = feed_repo

    async def execute(
        self,
        user_id: str,
        *,
        scope: str = "",
        current_session: str = "",
        is_admin: bool = False,
    ) -> list[SubscriptionExportRecord]:
        """Load subscriptions and hydrate export-ready records."""
        if self._feed_repo is None:
            raise RuntimeError("Subscription export requires a feed repository")

        if scope == "all" and is_admin:
            subscriptions = await self._subscription_repo.get_all_active()
        else:
            subscriptions = await self._subscription_repo.get_by_user(user_id)
            if current_session:
                subscriptions = [
                    sub
                    for sub in subscriptions
                    if (sub.target_session or current_session) == current_session
                ]
        if not subscriptions:
            return []

        feed_ids = list(
            dict.fromkeys(subscription.feed_id for subscription in subscriptions)
        )
        feeds = {
            feed.id: feed
            for feed in await self._feed_repo.get_by_ids(feed_ids)
            if feed.id is not None
        }

        records: list[SubscriptionExportRecord] = []
        for subscription in subscriptions:
            feed = feeds.get(subscription.feed_id)
            if feed is None:
                continue
            records.append(
                build_subscription_export_record(
                    subscription,
                    link=feed.link,
                    feed_title=feed.title or None,
                )
            )
        return records
