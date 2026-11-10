from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from astrbot_plugin_rsshub_lite.src.interfaces.handlers.feed import handle_feed


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "args", ["", "1", "1 2 3", "abc 2", "1 all", "0 3", "1 0", "-1 2", "1 -2"]
)
async def test_feed_handler_validates_id_and_count(args):
    command = SimpleNamespace(execute=AsyncMock())
    result = await handle_feed(MagicMock(), args, {"push_feed_cmd": command})
    assert "/feed <订阅ID> <N>" in result["plain"]
    command.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_feed_handler_passes_current_session_and_requested_count():
    event = MagicMock()
    event.get_sender_id.return_value = "admin"
    event.get_platform_name.return_value = "telegram"
    event.unified_msg_origin = "telegram:Group:current"
    command = SimpleNamespace(
        execute=AsyncMock(
            return_value=SimpleNamespace(message="sent", success=True, data={})
        )
    )
    result = await handle_feed(event, " 12  5 ", {"push_feed_cmd": command})
    assert result == {"plain": "sent"}
    command.execute.assert_awaited_once_with(
        sub_id=12,
        count=5,
        user_id="admin",
        target_session="telegram:Group:current",
        platform_name="telegram",
    )


@pytest.mark.asyncio
async def test_feed_handler_does_not_duplicate_included_success_summary():
    command = SimpleNamespace(
        execute=AsyncMock(
            return_value=SimpleNamespace(
                success=True,
                message="already in last node",
                data={"summary_included": True},
            )
        )
    )
    assert await handle_feed(MagicMock(), "12 5", {"push_feed_cmd": command}) == {}
