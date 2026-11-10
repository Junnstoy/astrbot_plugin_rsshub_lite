import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from astrbot_plugin_rsshub_lite.src.application.commands import test_subscription_cmd
from astrbot_plugin_rsshub_lite.src.application.commands.test_subscription_cmd import (
    TestSubscriptionCommand,
)
from astrbot_plugin_rsshub_lite.src.application.ports import SendResult
from astrbot_plugin_rsshub_lite.src.application.services.notification_dispatcher import (
    NotificationDispatcher,
)
from astrbot_plugin_rsshub_lite.src.domain.entities.content_types import (
    LayoutFragment,
    build_generated_media_url,
)
from astrbot_plugin_rsshub_lite.src.domain.entities.feed import Feed
from astrbot_plugin_rsshub_lite.src.domain.entities.subscription import Subscription
from astrbot_plugin_rsshub_lite.src.domain.entities.user import User
from astrbot_plugin_rsshub_lite.src.infrastructure.config import (
    FeedDefaults,
    SubscriptionDefaults,
)
from astrbot_plugin_rsshub_lite.src.infrastructure.fetcher import EntryParsed
from astrbot_plugin_rsshub_lite.src.infrastructure.rendering import table_image_renderer
from astrbot_plugin_rsshub_lite.src.interfaces.handlers.admin import handle_test_sub


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", [1, 2])
@pytest.mark.parametrize("show_title", [False, True])
@pytest.mark.parametrize("outcome", ["sent", "cancelled", "retry"])
async def test_sub_test_uses_normal_profile_and_places_summary_by_send_mode(
    mode, show_title, outcome
):
    sub = Subscription(
        id=3,
        user_id="owner",
        feed_id=7,
        target_session="bot:GroupMessage:1",
        platform_name="aiocqhttp",
        send_mode=mode,
    )
    sub_repo = AsyncMock()
    sub_repo.get_by_id.return_value = sub
    sub_repo.get_active_by_feed_id.return_value = [sub]
    feed_repo = AsyncMock()
    feed_repo.get_by_id.return_value = Feed(
        id=7, link="https://example.com/rss", title="Feed"
    )
    user_repo = AsyncMock()
    user_repo.get_by_id.return_value = User(id="owner")
    user_repo.get_or_create.return_value = User(id="owner")
    history = AsyncMock()
    history.save.side_effect = lambda value: value
    sender = AsyncMock()
    sender.send_to_user.return_value = SendResult(ok=True)
    if outcome == "cancelled":
        sender.send_to_user.side_effect = asyncio.CancelledError()
    elif outcome == "retry":
        sender.send_to_user.return_value = SendResult(
            ok=False, detail="delivery failed"
        )
    dispatcher = NotificationDispatcher(
        subscription_repo=sub_repo,
        user_repo=user_repo,
        push_history_repo=history,
        sender_provider=SimpleNamespace(get=lambda _: sender),
        subscription_defaults=SubscriptionDefaults(display_title=show_title),
        feed_defaults=FeedDefaults(display_title=False),
    )
    polling = AsyncMock()
    polling.fetch_feed_entries.return_value = SimpleNamespace(
        success=True,
        entries=[
            EntryParsed(title="标题", content="正文", link="https://example.com/post")
        ],
        web_feed=SimpleNamespace(rss_d=SimpleNamespace(feed={})),
    )
    command = TestSubscriptionCommand(
        sub_repo,
        feed_repo,
        polling_service=polling,
        notification_dispatcher=dispatcher,
        user_repo=user_repo,
    )
    event = MagicMock()
    event.get_sender_id.return_value = "owner"
    event.get_platform_name.return_value = "aiocqhttp"
    event.unified_msg_origin = sub.target_session
    response = await handle_test_sub(event, "3", {"test_sub_cmd": command})
    assert sender.send_to_user.await_count == 1
    if outcome == "cancelled":
        assert "已取消" in response["plain"]
        assert "成功" not in response["plain"]
        return
    if outcome == "retry":
        assert "发送失败" in response["plain"]
        assert "delivery failed" in response["plain"]
        assert "成功" not in response["plain"]
        assert history.save.await_args.args[0].can_retry()
        return
    request = sender.send_to_user.await_args.args[0]
    expected = "已触发测试推送: 1/1 条进入正式链路（成功 1 条，最新 1 条）"
    if mode == 2:
        assert response == {}
        assert request.entries[-1].message == expected
        assert ("标题" in request.entries[0].message) == show_title
    else:
        assert response == {"plain": expected}
        assert request.entries is None
        assert ("标题" in request.message) == show_title
    assert all(
        "已触发测试推送" not in call.args[0].content
        for call in history.save.await_args_list
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("target", ["3", "https://example.com/rss"])
@pytest.mark.parametrize("error_type", [RuntimeError, asyncio.CancelledError])
async def test_sub_test_cleans_temporary_media_if_preparation_does_not_finish(
    monkeypatch, tmp_path, target, error_type
):
    temporary = tmp_path / "rsshub_table_subtest.png"
    temporary.write_bytes(b"temporary")
    monkeypatch.setattr(
        table_image_renderer, "get_plugin_cache_dir", lambda *args: tmp_path / "cache"
    )
    parsed = SimpleNamespace(
        html_tree=SimpleNamespace(get_plain=lambda: "body"),
        media=[],
        layout=[
            LayoutFragment(
                kind="image",
                url=build_generated_media_url("table", "a" * 64),
                local_path=str(temporary),
            )
        ],
    )
    monkeypatch.setattr(
        test_subscription_cmd,
        "HTMLParser",
        lambda *args, **kwargs: SimpleNamespace(parse=AsyncMock(return_value=parsed)),
    )
    monkeypatch.setattr(
        test_subscription_cmd.FeedPollingService,
        "_format_dispatch_content_async",
        AsyncMock(side_effect=error_type("preparation interrupted")),
    )
    sub_repo, feed_repo, polling, dispatcher = (AsyncMock() for _ in range(4))
    sub_repo.get_by_id.return_value = Subscription(id=3, user_id="owner", feed_id=7)
    feed_repo.get_by_id.return_value = Feed(id=7, link="https://example.com/rss")
    polling.fetch_feed_entries.return_value = SimpleNamespace(
        success=True,
        entries=[EntryParsed(title="title", content="body")],
        web_feed=None,
    )
    command = TestSubscriptionCommand(
        sub_repo, feed_repo, polling_service=polling, notification_dispatcher=dispatcher
    )
    with pytest.raises(error_type, match="preparation interrupted"):
        await command.execute_target(target, "owner", "group", "aiocqhttp")
    assert not temporary.exists()
    dispatcher.dispatch_to_feed_subscribers.assert_not_awaited()
    dispatcher.send_to_session.assert_not_awaited()


@pytest.mark.asyncio
async def test_session_profile_version_keeps_new_disabled_values():
    from astrbot_plugin_rsshub_lite.src.interfaces.handlers.config import (
        _get_session_defaults,
        handle_sub_set_session,
    )

    values = {"display_title": 0, "display_media": -1, "style": 1}
    context = MagicMock()
    context.get_kv_data = AsyncMock(side_effect=lambda key, default: values.copy())

    async def save(key, data):
        values.clear()
        values.update(data)

    context.put_kv_data = save
    event = SimpleNamespace(unified_msg_origin="group")
    assert await _get_session_defaults(context, "group") == {
        "display_title": 1,
        "display_media": 0,
        "style": 0,
    }
    await handle_sub_set_session(event, "display_title", "0", {}, context)
    await handle_sub_set_session(event, "feed_display_title", "0", {}, context)
    current = await _get_session_defaults(context, "group")
    assert current["display_title"] == current["feed_display_title"] == 0
    assert values["__profile_version"] == 3
