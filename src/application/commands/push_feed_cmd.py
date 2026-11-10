"""Push the latest entries from one current-session subscription on demand."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ...domain.entities.content_types import AudioContent, VideoContent
from ...domain.repositories.feed_repository import FeedRepository
from ...domain.repositories.subscription_repository import SubscriptionRepository
from ...domain.repositories.user_repository import UserRepository
from ...infrastructure.pipeline import EntryFormatInput, EntryTextFormatter
from ...infrastructure.rendering import cleanup_ephemeral_generated_media_paths
from ...infrastructure.utils import get_logger
from ...shared.constants import SEND_MODE_LINK_ONLY
from ..dto.result_dto import CommandResult
from ..services.feed_polling_service import FeedPollingService
from ..services.html_parser import HTMLParser
from ..services.notification_dispatcher import NotificationDispatcher, SendTarget

logger = get_logger()


class PushFeedCommand:
    """Manual delivery without changing subscriptions, feed cursors or dedup history.

    The command entry point supplies the administrator permission check. Resource
    access here is scoped to the current session, including subscriptions created
    by another user in that session. Display defaults belong to the subscriber.
    """

    def __init__(
        self,
        subscription_repo: SubscriptionRepository,
        feed_repo: FeedRepository,
        polling_service: FeedPollingService,
        notification_dispatcher: NotificationDispatcher,
        user_repo: UserRepository | None = None,
    ) -> None:
        self._subscription_repo = subscription_repo
        self._feed_repo = feed_repo
        self._polling_service = polling_service
        self._dispatcher = notification_dispatcher
        self._user_repo = user_repo
        self._formatter = EntryTextFormatter()

    async def execute(
        self,
        sub_id: int,
        count: int,
        user_id: str,
        target_session: str,
        platform_name: str,
    ) -> CommandResult:
        if isinstance(sub_id, bool) or not isinstance(sub_id, int) or sub_id <= 0:
            return CommandResult(success=False, message="订阅 ID 必须是正整数。")
        if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
            return CommandResult(success=False, message="推送条数 N 必须是正整数。")
        if not target_session:
            return CommandResult(success=False, message="当前会话为空，无法推送。")

        subscription = await self._subscription_repo.get_by_id(sub_id)
        if subscription is None:
            return CommandResult(success=False, message=f"订阅不存在 (ID: {sub_id})。")
        if subscription.target_session != target_session:
            return CommandResult(success=False, message="该订阅不属于当前会话。")
        feed = await self._feed_repo.get_by_id(subscription.feed_id)
        if feed is None:
            return CommandResult(success=False, message="订阅对应的 Feed 不存在。")

        try:
            # This read port does not update entry hashes, etag or next_check_time.
            read_result = await self._polling_service.fetch_feed_entries(
                feed.link, verbose=True
            )
        except Exception as exc:
            logger.exception("手动订阅抓取失败: sub_id=%s", sub_id)
            return CommandResult(success=False, message=f"抓取失败: {exc}")
        if not read_result.success:
            return CommandResult(success=False, message=read_result.message)
        if not read_result.entries:
            return CommandResult(success=False, message="当前 Feed 没有可推送的条目。")

        entries = sorted(
            read_result.entries, key=self._published_sort_key, reverse=True
        )
        selected = entries[:count]
        owner = (
            await self._user_repo.get_by_id(subscription.user_id)
            if self._user_repo is not None
            else None
        )
        # Reuse the automatic push inheritance rules without applying notify/state
        # gates: this is an explicit one-time request, not a subscription update.
        options = self._dispatcher._resolve_effective_push_options(subscription, owner)
        send_mode = self._dispatcher._resolve_send_mode(subscription, owner)
        target = SendTarget(
            user_id=user_id,
            platform_name=platform_name,
            target_session=target_session,
            sub_id=subscription.id,
        )
        feed_meta = getattr(getattr(read_result.web_feed, "rss_d", None), "feed", {})
        feed_title = (
            str(subscription.title or feed.title or "").strip()
            or str(feed_meta.get("title", "") if hasattr(feed_meta, "get") else "")
            or feed.link
        )

        sent = failed = 0
        cancelled = False
        first_error = ""
        for entry in selected:
            try:
                result = await self._send_entry(
                    entry, feed, feed_title, target, options, send_mode
                )
            except Exception as exc:
                logger.exception("手动条目推送失败: sub_id=%s", sub_id)
                result = {"ok": False, "error": str(exc)}
            if result.get("cancelled"):
                cancelled = True
                break
            if result.get("ok"):
                sent += 1
            else:
                failed += 1
                first_error = first_error or str(result.get("error") or "发送失败")

        shortage = count > len(entries)
        lines = []
        if shortage:
            lines.append(f"请求 {count} 条，当前源仅有 {len(entries)} 条。")
        if cancelled:
            lines.append(f"推送已停止：成功 {sent}/{len(selected)} 条。")
        else:
            lines.append(
                f"订阅 {sub_id}：最新 {len(selected)} 条，成功 {sent} 条，失败 {failed} 条。"
            )
        if first_error:
            lines.append(f"失败原因：{first_error}")
        return CommandResult(
            success=sent > 0 and failed == 0 and not cancelled,
            message="\n".join(lines),
            data={
                "sub_id": sub_id,
                "feed_id": feed.id,
                "requested": count,
                "available": len(entries),
                "selected": len(selected),
                "sent": sent,
                "failed": failed,
                "cancelled": cancelled,
                "shortage": shortage,
            },
        )

    @staticmethod
    def _published_sort_key(entry: Any) -> tuple[bool, datetime]:
        published = getattr(entry, "published", None)
        if isinstance(published, datetime):
            try:
                if published.tzinfo is None:
                    published = published.replace(tzinfo=UTC)
                return True, published.astimezone(UTC)
            except (ValueError, OverflowError):
                pass
        # Python's stable sort preserves source order among unknown/equal dates.
        return False, datetime.min.replace(tzinfo=UTC)

    async def _send_entry(self, entry, feed, feed_title, target, options, send_mode):
        title = str(getattr(entry, "title", "") or "")
        link = str(getattr(entry, "link", "") or feed.link)
        layout = None
        media_urls = None
        media_items = None
        parsed = None
        try:
            if send_mode == SEND_MODE_LINK_ONLY:
                content = self._dispatcher._build_link_only_content(
                    entry_title=title, entry_link=link
                )
            else:
                raw_content = str(
                    getattr(entry, "content", "") or getattr(entry, "summary", "") or ""
                )
                parsed = await HTMLParser(raw_content, feed_link=feed.link).parse()
                body = await self._formatter.clean_text(raw_content)
                if any(
                    isinstance(m, (AudioContent, VideoContent)) for m in parsed.media
                ):
                    body = FeedPollingService._remove_media_placeholders(body)
                content = await self._formatter.format_entry(
                    EntryFormatInput(
                        title=title,
                        content=body,
                        summary=body,
                        link=link,
                        author=str(getattr(entry, "author", "") or ""),
                        feed_title=feed_title,
                        feed_link=feed.link,
                        tags=tuple(getattr(entry, "tags", None) or ()),
                    ),
                    options,
                )
                if options.display_media:
                    media_items = FeedPollingService._media_items_from_parsed(
                        parsed.media
                    )
                    media_urls = [url for _, url in media_items]
                    media_urls.extend(
                        str(enclosure.url)
                        for enclosure in (getattr(entry, "enclosures", None) or [])
                        if getattr(enclosure, "url", "")
                    )
                    media_urls = list(dict.fromkeys(media_urls))
                    layout = self._dispatcher._limit_original_layout_text(
                        list(parsed.layout),
                        style=options.style,
                        length_limit=options.length_limit,
                    )
            # The session sender uses the existing queue, without creating a feed
            # success history record that could suppress a later scheduled push.
            return await self._dispatcher.send_to_session(
                target=target,
                content=content,
                media_urls=media_urls,
                media_items=media_items,
                layout=layout,
                job_description=f"feed sub={target.sub_id}",
                channel_title=feed_title,
                channel_link=feed.link,
                entry_title=title,
                entry_link=link,
                feed_id=feed.id,
                sub_id=target.sub_id,
                send_mode=send_mode,
                style=options.style,
            )
        finally:
            if parsed is not None:
                cleanup_ephemeral_generated_media_paths(parsed.layout)
