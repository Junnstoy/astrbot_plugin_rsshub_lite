from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from astrbot_plugin_rsshub_lite.src.application.commands.push_feed_cmd import (
    PushFeedCommand,
)
from astrbot_plugin_rsshub_lite.src.application.ports import SendResult
from astrbot_plugin_rsshub_lite.src.application.services.feed_polling_service import (
    FeedReadResult,
)
from astrbot_plugin_rsshub_lite.src.application.services.notification_dispatcher import (
    NotificationDispatcher,
)
from astrbot_plugin_rsshub_lite.src.domain.entities.feed import Feed
from astrbot_plugin_rsshub_lite.src.domain.entities.subscription import Subscription
from astrbot_plugin_rsshub_lite.src.domain.entities.user import User
from astrbot_plugin_rsshub_lite.src.infrastructure.messaging.senders import base_sender
from astrbot_plugin_rsshub_lite.src.infrastructure.messaging.senders.onebot_sender import (
    OneBotMessageSender,
)
from astrbot_plugin_rsshub_lite.src.infrastructure.messaging.senders.provider import (
    InfrastructureMessageSenderAdapter,
)

SESSION = "telegram:Group:current"


def entry(title, published=None, content=None):
    return SimpleNamespace(
        title=title,
        published=published,
        link=f"https://example.com/{title}",
        content=content or f"<p>Body of {title}</p>",
        summary="",
        author="Author",
        tags=["news"],
        enclosures=[],
    )


class Sender:
    def __init__(self):
        self.requests = []
        self.results = []

    async def send_to_user(self, request, context=None):
        self.requests.append((request, context))
        return self.results.pop(0) if self.results else SendResult(ok=True)


def setup_command(entries, **sub_options):
    subscription = Subscription(
        id=7,
        user_id="owner",
        feed_id=42,
        target_session=SESSION,
        platform_name="telegram",
        **sub_options,
    )
    feed = Feed(id=42, link="https://example.com/feed", title="Feed", etag="unchanged")
    sub_repo, feed_repo, user_repo, history_repo = (AsyncMock() for _ in range(4))
    sub_repo.get_by_id.return_value = subscription
    feed_repo.get_by_id.return_value = feed
    user_repo.get_by_id.return_value = User(id="owner")
    polling = AsyncMock()
    polling.fetch_feed_entries.return_value = FeedReadResult(
        success=True,
        status="fetched",
        message="OK",
        entries=entries,
    )
    sender = Sender()
    provider = SimpleNamespace(get=lambda platform_name: sender)
    dispatcher = NotificationDispatcher(
        subscription_repo=sub_repo,
        push_history_repo=history_repo,
        sender_provider=provider,
        user_repo=user_repo,
    )
    command = PushFeedCommand(sub_repo, feed_repo, polling, dispatcher, user_repo)
    return SimpleNamespace(
        command=command,
        sub=subscription,
        feed=feed,
        sub_repo=sub_repo,
        feed_repo=feed_repo,
        user_repo=user_repo,
        history_repo=history_repo,
        polling=polling,
        sender=sender,
        dispatcher=dispatcher,
    )


async def run(command, count=3, sub_id=7, session=SESSION):
    return await command.execute(
        sub_id=sub_id,
        count=count,
        user_id="admin",
        target_session=session,
        platform_name="telegram",
    )


@pytest.mark.asyncio
async def test_pushes_latest_n_using_current_session_and_preserves_auto_state():
    rows = [
        entry("old", datetime(2026, 11, 9, tzinfo=UTC)),
        entry("new", datetime(2026, 11, 11, tzinfo=UTC)),
        entry("middle", datetime(2026, 11, 10, tzinfo=UTC)),
    ]
    state = setup_command(rows, state=0, notify=0)
    before_sub, before_feed = state.sub.model_dump(), state.feed.model_dump()
    result = await run(state.command, count=2)
    assert result.success
    assert result.data["sent"] == 2
    assert [
        item.message.split("\n\n")[1]
        for item in state.sender.requests[0][0].entries[:-1]
    ] == [
        "new",
        "middle",
    ]
    assert all(request.session_id == SESSION for request, _ in state.sender.requests)
    assert state.sub.model_dump() == before_sub
    assert state.feed.model_dump() == before_feed
    assert [row.title for row in rows] == ["old", "new", "middle"]
    state.polling.fetch_feed_entries.assert_awaited_once_with(
        state.feed.link, verbose=True
    )
    state.polling.poll_feed.assert_not_awaited()
    state.sub_repo.save.assert_not_awaited()
    state.sub_repo.update_options.assert_not_awaited()
    state.feed_repo.save.assert_not_awaited()
    assert state.history_repo.mock_calls == []


@pytest.mark.asyncio
async def test_sorts_dates_across_timezones_and_keeps_unknown_source_order():
    stamp = datetime(2026, 11, 11)
    state = setup_command(
        [
            entry("unknown-first"),
            entry("offset", stamp.replace(tzinfo=timezone(timedelta(hours=8)))),
            entry("same-first", stamp),
            entry("unknown-second"),
            entry("same-second", stamp.replace(tzinfo=UTC)),
        ]
    )
    result = await run(state.command, count=5)
    assert result.success
    assert [
        item.message.split("\n\n")[1]
        for item in state.sender.requests[0][0].entries[:-1]
    ] == [
        "same-first",
        "same-second",
        "offset",
        "unknown-first",
        "unknown-second",
    ]


@pytest.mark.asyncio
async def test_short_feed_pushes_available_and_reports_shortage():
    state = setup_command([entry("one"), entry("two")])
    result = await run(state.command, count=5)
    assert result.success
    assert result.data["requested"] == 5
    assert result.data["available"] == result.data["sent"] == 2
    assert result.data["shortage"]
    assert "仅有 2 条" in result.message


@pytest.mark.asyncio
async def test_empty_feed_is_reported_without_sending():
    state = setup_command([])
    result = await run(state.command)
    assert not result.success
    assert "没有可推送" in result.message
    assert state.sender.requests == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "sub_id,count", [(0, 1), (-1, 1), (True, 1), (7, 0), (7, -2), (7, True)]
)
async def test_invalid_positive_integer_arguments_are_rejected(sub_id, count):
    state = setup_command([entry("one")])
    result = await run(state.command, sub_id=sub_id, count=count)
    assert not result.success
    state.sub_repo.get_by_id.assert_not_awaited()
    state.polling.fetch_feed_entries.assert_not_awaited()


@pytest.mark.asyncio
async def test_rejects_other_session_before_fetching_or_resolving_feed():
    state = setup_command([entry("one")])
    result = await run(state.command, session="telegram:Group:other")
    assert not result.success
    assert "不属于当前会话" in result.message
    state.feed_repo.get_by_id.assert_not_awaited()
    state.polling.fetch_feed_entries.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", ["subscription", "feed"])
async def test_reports_missing_subscription_or_feed(missing):
    state = setup_command([entry("one")])
    repo = state.sub_repo if missing == "subscription" else state.feed_repo
    repo.get_by_id.return_value = None
    result = await run(state.command)
    assert not result.success
    assert "不存在" in result.message
    state.polling.fetch_feed_entries.assert_not_awaited()


@pytest.mark.asyncio
async def test_uses_subscription_and_owner_display_options_without_notify_gate():
    state = setup_command(
        [
            entry(
                "Title",
                content="<p>Long body for truncation</p><img src='https://example.com/image.jpg'>",
            )
        ],
        feed_display_title=0,
        feed_display_media=0,
        notify=0,
    )
    state.user_repo.get_by_id.return_value = User(
        id="owner",
        feed_length_limit=6,
        feed_display_via=0,
        send_mode=1,
    )
    result = await run(state.command, count=1)
    assert result.success
    request, context = state.sender.requests[0]
    request = request.entries[0]
    assert "Title" not in request.message
    assert "truncation" not in request.message
    assert "example.com" not in request.message
    assert not request.media
    assert all(item.kind == "text" for item in request.layout)
    assert context.send_mode == 2
    state.user_repo.get_by_id.assert_awaited_once_with("owner")


@pytest.mark.asyncio
async def test_feed_profile_is_independent_of_normal_send_and_display_options():
    state = setup_command(
        [entry("one", content="<img src='https://example.com/image.jpg'>")],
        send_mode=1,
        display_media=0,
        display_title=0,
    )
    result = await run(state.command, count=1)
    assert result.success
    request, context = state.sender.requests[0]
    assert "one" in request.entries[0].message
    assert request.entries[0].media == [("image", "https://example.com/image.jpg")]
    assert context.send_mode == 2
    assert len(request.entries) == 2
    assert result.data["summary_included"]
    assert request.entries[-1].message == result.message


@pytest.mark.asyncio
async def test_preserves_media_and_original_layout_with_subscription_length_limit():
    row = entry(
        "one",
        content="<p>First paragraph text</p><img src='https://example.com/image.jpg'><p>Second paragraph text</p>",
    )
    row.enclosures = [SimpleNamespace(url="https://example.com/audio.mp3")]
    state = setup_command(
        [row],
        feed_style=2,
        feed_length_limit=8,
        feed_display_title=0,
        feed_display_author=0,
        feed_display_via=0,
    )
    result = await run(state.command, count=1)
    assert result.success
    request, context = state.sender.requests[0]
    assert context.style == 2
    request = request.entries[0]
    assert ("image", "https://example.com/image.jpg") in request.media
    assert ("audio", "https://example.com/audio.mp3") in request.media
    assert request.layout
    text_length = sum(
        len(fragment.text or "")
        for fragment in request.layout
        if fragment.kind == "text"
    )
    assert text_length <= 8


@pytest.mark.asyncio
async def test_fetch_error_and_exception_are_reported():
    state = setup_command([entry("one")])
    state.polling.fetch_feed_entries.return_value = FeedReadResult(
        success=False,
        status="fetch_error",
        message="源不可访问",
    )
    result = await run(state.command)
    assert not result.success
    assert "源不可访问" in result.message
    state.polling.fetch_feed_entries.side_effect = RuntimeError("timeout")
    result = await run(state.command)
    assert not result.success
    assert "timeout" in result.message
    assert state.sender.requests == []


@pytest.mark.asyncio
async def test_failed_merged_packet_reports_failure_without_success_summary():
    state = setup_command([entry("one"), entry("two"), entry("three")])
    state.sender.results = [SendResult(ok=False, detail="send failed")]
    result = await run(state.command)
    assert not result.success
    assert result.data["sent"] == 0
    assert result.data["failed"] == 3
    assert not result.data["summary_included"]
    assert "send failed" in result.message
    assert len(state.sender.requests) == 1
    assert state.history_repo.mock_calls == []


@pytest.mark.asyncio
async def test_preparation_failure_keeps_other_entries_and_counts_failure_in_packet():
    state = setup_command([entry("one"), entry("broken"), entry("three")])
    prepare = state.command._prepare_entry

    async def prepare_or_fail(row, *args):
        if row.title == "broken":
            raise ValueError("bad entry markup")
        return await prepare(row, *args)

    state.command._prepare_entry = prepare_or_fail
    result = await run(state.command)
    assert not result.success
    assert result.data["sent"] == 2
    assert result.data["failed"] == 1
    assert result.data["summary_included"]
    assert "成功 2 条，失败 1 条" in result.message
    request, _ = state.sender.requests[0]
    assert len(request.entries) == 3
    assert request.entries[-1].message == result.message


@pytest.mark.asyncio
async def test_empty_display_payload_is_not_counted_as_sent():
    state = setup_command(
        [entry("hidden", content=" ")],
        feed_display_title=0,
        feed_display_author=0,
        feed_display_via=0,
        feed_display_media=0,
        feed_display_entry_tags=0,
    )
    result = await run(state.command, count=1)
    assert not result.success
    assert result.data["sent"] == 0
    assert state.sender.requests == []


@pytest.mark.asyncio
async def test_cancelled_batch_is_reported_without_followup_send():
    state = setup_command([entry("one"), entry("two"), entry("three")])
    state.dispatcher.send_entries_to_session = AsyncMock(
        return_value={"ok": False, "cancelled": True}
    )
    result = await run(state.command)
    assert not result.success
    assert result.data["sent"] == 0
    assert result.data["cancelled"]
    assert state.dispatcher.send_entries_to_session.await_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel_by_id", [False, True])
async def test_real_sender_cancellation_reaches_command_and_stops_later_entries(
    monkeypatch, cancel_by_id
):
    state = setup_command([entry("one"), entry("two"), entry("three")])
    entered = asyncio.Event()
    blocked = asyncio.Event()

    async def platform_send(session_id, chain):
        assert session_id == SESSION
        entered.set()
        await blocked.wait()
        return True

    platform_mock = AsyncMock(side_effect=platform_send)
    monkeypatch.setattr(
        base_sender, "StarTools", SimpleNamespace(send_message=platform_mock)
    )
    adapter = InfrastructureMessageSenderAdapter(OneBotMessageSender())
    state.dispatcher._sender_provider = SimpleNamespace(get=lambda platform: adapter)
    pending = asyncio.create_task(run(state.command))
    try:
        await asyncio.wait_for(entered.wait(), timeout=2)
        queue = state.dispatcher._push_job_queue
        if cancel_by_id:
            # /unpush cancels already known jobs for the affected subscription.
            job = queue.get_current_job(SESSION)
            assert job is not None and job.sub_id == state.sub.id
            stopped = queue.stop_by_job_id(SESSION, job.job_id)
        else:
            # /push_cancel without an ID cancels the current session job.
            stopped = queue.stop_current(SESSION)
        assert stopped.stopped
        result = await asyncio.wait_for(pending, timeout=2)
    finally:
        blocked.set()
        if not pending.done():
            pending.cancel()
        await asyncio.gather(pending, return_exceptions=True)

    assert not result.success
    assert result.data["cancelled"]
    assert result.data["sent"] == 0
    assert result.data["failed"] == 0
    assert "已停止" in result.message
    assert platform_mock.await_count == 1
    assert queue.get_jobs(SESSION) == []
    assert state.history_repo.mock_calls == []
