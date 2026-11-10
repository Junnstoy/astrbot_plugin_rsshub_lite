from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from astrbot_plugin_rsshub_lite.src.application.services import feed_polling_service
from astrbot_plugin_rsshub_lite.src.application.services.feed_polling_service import (
    FeedPollingService,
)
from astrbot_plugin_rsshub_lite.src.domain.entities.content_types import (
    ImageContent,
    LayoutFragment,
    build_generated_media_url,
)
from astrbot_plugin_rsshub_lite.src.domain.entities.feed import Feed
from astrbot_plugin_rsshub_lite.src.infrastructure.fetcher.rss.parser import EntryParsed
from astrbot_plugin_rsshub_lite.src.infrastructure.rendering import table_image_renderer


@pytest.fixture
def prepared_poll(monkeypatch, tmp_path):
    digest = "a" * 64
    source = build_generated_media_url("table", digest)
    temporary = tmp_path / "rsshub_table_polling.png"
    temporary.write_bytes(b"temporary table")
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    cached = cache_dir / f"table_{digest}.png"
    cached.write_bytes(b"cached table")
    monkeypatch.setattr(
        table_image_renderer, "get_plugin_cache_dir", lambda *args: cache_dir
    )
    layout = [
        LayoutFragment(kind="image", url=source, local_path=str(temporary)),
        LayoutFragment(kind="image", url=source, local_path=str(cached)),
    ]
    parsed = SimpleNamespace(layout=layout, media=[ImageContent(url=source)])
    monkeypatch.setattr(
        feed_polling_service,
        "HTMLParser",
        lambda *args, **kwargs: SimpleNamespace(parse=AsyncMock(return_value=parsed)),
    )
    clean = AsyncMock(return_value="body")
    monkeypatch.setattr(feed_polling_service._entry_text_formatter, "clean_text", clean)
    dispatcher, fingerprint = AsyncMock(), AsyncMock()
    dispatcher.dispatch_to_feed_subscribers.return_value = {"success": 1}
    service = FeedPollingService(
        feed_repo=MagicMock(),
        subscription_repo=MagicMock(),
        notification_dispatcher=dispatcher,
        media_fingerprint_service=fingerprint,
    )
    service._format_dispatch_content_async = AsyncMock(return_value="body")
    return SimpleNamespace(
        service=service,
        clean=clean,
        dispatcher=dispatcher,
        fingerprint=fingerprint,
        temporary=temporary,
        cached=cached,
        feed=Feed(id=1, link="https://example.com/rss"),
        entries=[
            EntryParsed(title="entry", content="body", link="https://example.com/item")
        ],
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["format", "dispatch"])
async def test_polling_cleans_generated_temporary_image_when_processing_raises(
    prepared_poll, stage
):
    state = prepared_poll
    failing = (
        state.clean
        if stage == "format"
        else state.dispatcher.dispatch_to_feed_subscribers
    )
    failing.side_effect = RuntimeError("processing failed")
    with pytest.raises(RuntimeError, match="processing failed"):
        await state.service._dispatch_entries(state.feed, state.entries)
    assert not state.temporary.exists()
    assert state.cached.exists()
    if stage == "format":
        state.dispatcher.dispatch_to_feed_subscribers.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["fingerprint", "dispatch"])
async def test_polling_cleans_temporary_image_when_cancelled_after_parse(
    prepared_poll, stage
):
    state = prepared_poll
    entered, blocked = asyncio.Event(), asyncio.Event()

    async def wait_for_cancellation(*args, **kwargs):
        assert state.temporary.exists()
        entered.set()
        await blocked.wait()

    target = (
        state.fingerprint.fingerprint_urls
        if stage == "fingerprint"
        else state.dispatcher.dispatch_to_feed_subscribers
    )
    target.side_effect = wait_for_cancellation
    pending = asyncio.create_task(
        state.service._dispatch_entries(state.feed, state.entries)
    )
    try:
        await asyncio.wait_for(entered.wait(), 2)
        pending.cancel()
        with pytest.raises(asyncio.CancelledError):
            await pending
    finally:
        blocked.set()
        if not pending.done():
            pending.cancel()
        await asyncio.gather(pending, return_exceptions=True)
    assert not state.temporary.exists()
    assert state.cached.exists()
    if stage == "fingerprint":
        state.dispatcher.dispatch_to_feed_subscribers.assert_not_awaited()


@pytest.mark.asyncio
async def test_polling_cleans_after_success_but_keeps_media_alive_until_dispatch(
    prepared_poll,
):
    state = prepared_poll

    async def dispatch(**kwargs):
        assert state.temporary.exists()
        assert kwargs["raw_entry"].layout[0].local_path == str(state.temporary)
        return {"success": 1}

    state.dispatcher.dispatch_to_feed_subscribers.side_effect = dispatch
    result = await state.service._dispatch_entries(state.feed, state.entries)
    assert result.dispatched == 1
    assert result.acknowledged_entries == state.entries
    assert not state.temporary.exists()
    assert state.cached.exists()
