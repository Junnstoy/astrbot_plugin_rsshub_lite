from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from astrbot_plugin_rsshub_lite.src.application.ports import SendResult
from astrbot_plugin_rsshub_lite.src.application.services.notification_dispatcher import (
    NotificationDispatcher,
)
from astrbot_plugin_rsshub_lite.src.domain.entities.push_history import PushHistory
from astrbot_plugin_rsshub_lite.src.domain.entities.subscription import Subscription
from astrbot_plugin_rsshub_lite.src.domain.entities.user import User
from astrbot_plugin_rsshub_lite.src.infrastructure.config import (
    FeedDefaults,
    SubscriptionDefaults,
)


def build_dispatcher(**kwargs):
    sub = Subscription(
        id=1,
        user_id="owner",
        feed_id=3,
        platform_name="aiocqhttp",
        target_session="onebot:Group:1",
    )
    repo, history = AsyncMock(), AsyncMock()
    repo.get_by_id.return_value = sub
    repo.get_active_by_feed_id.return_value = [sub]
    history.exists_success_by_scope_and_guid.return_value = False
    history.save.side_effect = lambda row: row
    sender = SimpleNamespace(send_to_user=AsyncMock(return_value=SendResult(ok=True)))
    dispatcher = NotificationDispatcher(
        repo, history, SimpleNamespace(get=lambda platform: sender), **kwargs
    )
    return dispatcher, sub, sender, history


def test_independent_profiles_resolve_subscription_owner_global_and_booleans():
    dispatcher, sub, _, _ = build_dispatcher(
        subscription_defaults=SubscriptionDefaults(
            display_title=True, display_via=True, merge_media=True
        ),
        feed_defaults=FeedDefaults(
            display_title=False, display_via=False, merge_media=False
        ),
    )
    owner = User(
        id="owner", display_title=0, feed_display_title=1, feed_length_limit=123
    )
    sub.display_via = 0
    sub.feed_display_via = 1
    normal = dispatcher._resolve_effective_push_options(sub, owner)
    feed = dispatcher._resolve_effective_push_options(sub, owner, profile="feed")
    assert normal.display_title is False and normal.display_via is False
    assert normal.merge_media is True and normal.length_limit == 0
    assert feed.display_title is True and feed.display_via is True
    assert feed.merge_media is False and feed.length_limit == 123
    for options in (normal, feed):
        for key in (
            "display_title",
            "display_author",
            "display_via",
            "display_media",
            "display_entry_tags",
            "merge_media",
        ):
            assert type(getattr(options, key)) is bool


def test_apply_defaults_updates_live_profiles_without_overriding_subscription():
    dispatcher, sub, _, _ = build_dispatcher()
    sub.display_author = 1
    dispatcher.apply_defaults(
        SubscriptionDefaults(
            send_mode=2, display_title=False, display_author=False, merge_media=False
        ),
        FeedDefaults(display_title=False, style=2, length_limit=7),
    )
    assert dispatcher._resolve_send_mode(sub) == 2
    normal = dispatcher._resolve_effective_push_options(sub)
    feed = dispatcher._resolve_effective_push_options(sub, profile="feed")
    assert normal.display_title is False and normal.display_author is True
    assert normal.merge_media is False
    assert feed.display_title is False and feed.style == 2 and feed.length_limit == 7


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", [1, 2])
async def test_test_push_summary_is_inside_only_successful_merged_packet(mode):
    dispatcher, sub, sender, history = build_dispatcher()
    sub.send_mode = mode
    sub.merge_media = 0
    stats = await dispatcher.dispatch_to_feed_subscribers(
        feed_id=3,
        content="body",
        entry_title="title",
        entry_link="https://example.com/item",
        completion_summary="success 1 / failed 0",
    )
    assert stats["success"] == 1
    request = sender.send_to_user.await_args.args[0]
    context = sender.send_to_user.await_args.kwargs["context"]
    assert context.merge_media is False
    if mode == 2:
        assert [entry.message for entry in request.entries] == [
            "body",
            "success 1 / failed 0",
        ]
        assert stats["summary_included"]
    else:
        assert request.entries is None
        assert not stats.get("summary_included")
    assert history.save.await_args.args[0].status == "success"


@pytest.mark.asyncio
async def test_unsupported_merged_error_is_not_scheduled_for_retry():
    dispatcher, sub, sender, history = build_dispatcher()
    sub.send_mode = 2
    sender.send_to_user.return_value = SendResult(
        ok=False, detail="merged_forward_not_supported: telegram"
    )
    stats = await dispatcher.dispatch_to_feed_subscribers(
        feed_id=3,
        content="body",
        entry_title="title",
        entry_link="https://example.com/item",
        completion_summary="success 1 / failed 0",
    )
    assert stats["failed"] == 1
    assert not stats.get("summary_included")
    saved = history.save.await_args.args[0]
    assert saved.status == "failed" and saved.max_retries == 0


@pytest.mark.asyncio
async def test_cancelled_dispatch_has_separate_count_and_no_included_summary():
    dispatcher, sub, _, history = build_dispatcher()
    sub.send_mode = 2
    dispatcher.send_to_session = AsyncMock(
        return_value={"ok": False, "cancelled": True}
    )
    stats = await dispatcher.dispatch_to_feed_subscribers(
        feed_id=3,
        content="body",
        entry_title="title",
        entry_link="https://example.com/item",
        completion_summary="success 1 / failed 0",
    )
    assert stats["success"] == stats["cancelled"] == 1
    assert not stats.get("summary_included")
    assert history.save.await_args.args[0].status == "stopped"


@pytest.mark.asyncio
async def test_retry_keeps_content_snapshot_and_current_merged_send_policy():
    dispatcher, sub, sender, history_repo = build_dispatcher()
    sub.send_mode, sub.merge_media = 2, 0
    history = PushHistory(
        id=5,
        sub_id=1,
        user_id="owner",
        feed_id=3,
        content="saved body",
        platform_name="aiocqhttp",
        target_session="onebot:Group:1",
        status="retrying",
        retry_count=1,
        max_retries=3,
    )
    history_repo.get_and_mark_retrying.return_value = [history]
    result = await dispatcher.dispatch_pending_retries()
    assert result["success"] == 1
    request = sender.send_to_user.await_args.args[0]
    context = sender.send_to_user.await_args.kwargs["context"]
    assert request.message == "saved body"
    assert context.send_mode == 2 and context.merge_media is False
