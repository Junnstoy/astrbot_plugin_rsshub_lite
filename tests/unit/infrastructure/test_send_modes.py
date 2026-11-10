"""Exercise configured send modes through the real infrastructure adapter."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from unittest.mock import AsyncMock

import pytest
from astrbot_plugin_rsshub_lite.src.application.ports import (
    MessageContext,
    SendEntry,
    SendRequest,
)
from astrbot_plugin_rsshub_lite.src.domain.entities.content_types import LayoutFragment
from astrbot_plugin_rsshub_lite.src.infrastructure.messaging.senders import (
    onebot_sender,
)
from astrbot_plugin_rsshub_lite.src.infrastructure.messaging.senders.base_sender import (
    DefaultMessageSender,
)
from astrbot_plugin_rsshub_lite.src.infrastructure.messaging.senders.onebot_sender import (
    OneBotMessageSender,
)
from astrbot_plugin_rsshub_lite.src.infrastructure.messaging.senders.provider import (
    InfrastructureMessageSenderAdapter,
)
from astrbot_plugin_rsshub_lite.src.infrastructure.messaging.senders.qq_official_sender import (
    QQOfficialMessageSender,
)
from astrbot_plugin_rsshub_lite.src.infrastructure.messaging.senders.telegram_sender import (
    TelegramMessageSender,
)
from astrbot_plugin_rsshub_lite.src.infrastructure.messaging.senders.types import (
    PreparedMedia,
    SendResult,
)
from astrbot_plugin_rsshub_lite.src.infrastructure.messaging.senders.weixin_oc_sender import (
    WeixinOCMessageSender,
)


@dataclass
class Plain:
    text: str


@dataclass
class Image:
    file: str


@dataclass
class Node:
    content: list
    name: str
    uin: str = ""


@dataclass
class Nodes:
    nodes: list


@pytest.fixture
def sender(monkeypatch, tmp_path):
    for name, component in {"Plain": Plain, "Image": Image}.items():
        monkeypatch.setattr(
            sys.modules["astrbot.api.message_components"],
            name,
            component,
            raising=False,
        )
    monkeypatch.setattr(onebot_sender, "Node", Node)
    monkeypatch.setattr(onebot_sender, "Nodes", Nodes)
    concrete = OneBotMessageSender()
    concrete._send_chain = AsyncMock(return_value=SendResult(ok=True))

    async def prepare(media, **kwargs):
        result = []
        for index, (kind, url) in enumerate(media):
            path = tmp_path / f"{index}.jpg"
            path.write_bytes(b"local media placeholder")
            result.append(
                PreparedMedia(media_type=kind, original_url=url, local_path=path)
            )
        return result

    concrete.prepare_media = AsyncMock(side_effect=prepare)
    concrete._resolve_bot_client = lambda context: None
    return concrete


def item(text="entry"):
    return SendEntry(
        message=text,
        media=[
            ("image", "https://example.com/one.jpg"),
            ("image", "https://example.com/two.jpg"),
        ],
        layout=[
            LayoutFragment(kind="text", text=text),
            LayoutFragment(kind="image", url="https://example.com/one.jpg"),
            LayoutFragment(kind="image", url="https://example.com/two.jpg"),
        ],
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("merge_media", [True, False])
async def test_direct_mode_sends_chains_not_forward_nodes(sender, merge_media):
    entry = item()
    result = await InfrastructureMessageSenderAdapter(sender).send_to_user(
        SendRequest(
            session_id="onebot:Group:1",
            message=entry.message,
            media=entry.media,
            layout=entry.layout,
        ),
        MessageContext(platform_name="aiocqhttp", send_mode=1, merge_media=merge_media),
    )
    assert result.ok
    chains = [call.args[1] for call in sender._send_chain.await_args_list]
    assert len(chains) == (1 if merge_media else 3)
    flattened = [component for chain in chains for component in chain]
    assert [type(component) for component in flattened] == [Plain, Image, Image]
    assert flattened[0].text == "entry"
    sender.prepare_media.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("merge_media", [True, False])
async def test_merged_batch_is_one_forward_with_final_summary(sender, merge_media):
    result = await InfrastructureMessageSenderAdapter(sender).send_to_user(
        SendRequest(
            session_id="onebot:Group:1",
            entries=[
                item("first"),
                item("second"),
                SendEntry(message="success 2 / failed 0"),
            ],
        ),
        MessageContext(platform_name="aiocqhttp", send_mode=2, merge_media=merge_media),
    )
    assert result.ok
    sender._send_chain.assert_awaited_once()
    chain = sender._send_chain.await_args.args[1]
    assert len(chain) == 1 and isinstance(chain[0], Nodes)
    nodes = chain[0].nodes
    assert len(nodes) == (3 if merge_media else 7)
    assert nodes[-1].content == [Plain("success 2 / failed 0")]
    assert nodes[0].content[0] == Plain("first")
    if merge_media:
        assert [type(component) for component in nodes[0].content] == [
            Plain,
            Image,
            Image,
        ]
        assert nodes[1].content[0] == Plain("second")
    else:
        assert all(len(node.content) == 1 for node in nodes)
        assert nodes[3].content == [Plain("second")]


@pytest.mark.asyncio
async def test_original_layout_and_enclosures_keep_source_order(sender):
    entry = item()
    entry.layout.insert(2, LayoutFragment(kind="text", text="between"))
    # This media exists only as an RSS enclosure, not in the original HTML.
    entry.layout.pop()
    result = await InfrastructureMessageSenderAdapter(sender).send_to_user(
        SendRequest(session_id="onebot:Group:1", entries=[entry]),
        MessageContext(platform_name="aiocqhttp", send_mode=2, style=2),
    )
    assert result.ok
    node = sender._send_chain.await_args.args[1][0].nodes[0]
    assert [type(component) for component in node.content] == [
        Plain,
        Image,
        Plain,
        Image,
    ]
    assert node.content[2].text == "between"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "concrete",
    [
        DefaultMessageSender,
        TelegramMessageSender,
        QQOfficialMessageSender,
        WeixinOCMessageSender,
    ],
)
async def test_unsupported_merged_platform_reports_failure_without_sending(concrete):
    sender = concrete()
    sender._send_chain = AsyncMock()
    result = await InfrastructureMessageSenderAdapter(sender).send_to_user(
        SendRequest(session_id="other:Group:1", entries=[SendEntry(message="entry")]),
        MessageContext(platform_name="other", send_mode=2),
    )
    assert not result.ok
    assert "merged_forward_not_supported" in result.detail
    assert not result.transient
    sender._send_chain.assert_not_awaited()


@pytest.mark.asyncio
async def test_failed_merged_forward_never_falls_back_to_direct(sender):
    sender._send_chain.return_value = SendResult(ok=False, detail="forward rejected")
    result = await InfrastructureMessageSenderAdapter(sender).send_to_user(
        SendRequest(
            session_id="onebot:Group:1",
            entries=[SendEntry(message="entry"), SendEntry(message="summary")],
        ),
        MessageContext(platform_name="aiocqhttp", send_mode=2),
    )
    assert not result.ok and result.detail == "forward rejected"
    sender._send_chain.assert_awaited_once()
    assert isinstance(sender._send_chain.await_args.args[1][0], Nodes)


@pytest.mark.asyncio
async def test_telegram_native_caption_keeps_text_source_order(sender):
    telegram = TelegramMessageSender()
    telegram.prepare_media, telegram._send_chain = (
        sender.prepare_media,
        sender._send_chain,
    )
    entry = item("first paragraph")
    entry.media.pop()
    entry.layout.pop()
    entry.layout.append(LayoutFragment(kind="text", text="second paragraph"))
    result = await InfrastructureMessageSenderAdapter(telegram).send_to_user(
        SendRequest(
            session_id="telegram:Group:1",
            message=entry.message,
            media=entry.media,
            layout=entry.layout,
        ),
        MessageContext(
            platform_name="telegram", send_mode=1, merge_media=True, style=2
        ),
    )
    assert result.ok
    chain = sender._send_chain.await_args.args[1]
    assert [type(component) for component in chain] == [Image, Plain]
    assert chain[-1].text == "first paragraph\n\nsecond paragraph"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "concrete,platform",
    [
        (TelegramMessageSender, "telegram"),
        (QQOfficialMessageSender, "qq_official"),
        (WeixinOCMessageSender, "weixin_oc"),
    ],
)
@pytest.mark.parametrize("merge_media", [True, False])
async def test_native_platform_rejects_unsupported_combination_or_sends_in_order(
    sender, concrete, platform, merge_media
):
    native = concrete()
    native.prepare_media, native._send_chain = sender.prepare_media, sender._send_chain
    entry = item()
    result = await InfrastructureMessageSenderAdapter(native).send_to_user(
        SendRequest(
            session_id=f"{platform}:Group:1",
            message=entry.message,
            media=entry.media,
            layout=entry.layout,
        ),
        MessageContext(platform_name=platform, send_mode=1, merge_media=merge_media),
    )
    if merge_media:
        assert not result.ok and "combined_media_not_supported" in result.detail
        assert "关闭合并媒体" in result.detail
        sender._send_chain.assert_not_awaited()
    else:
        assert result.ok
        chains = [call.args[1] for call in sender._send_chain.await_args_list]
        assert len(chains) == 3
        assert [type(chain[0]) for chain in chains] == [Plain, Image, Image]


@pytest.mark.asyncio
async def test_official_qq_single_image_text_keeps_native_markdown_policy(sender):
    native = QQOfficialMessageSender()
    native.prepare_media, native._send_chain = sender.prepare_media, sender._send_chain
    entry = item()
    entry.media.pop()
    entry.layout.pop()
    result = await InfrastructureMessageSenderAdapter(native).send_to_user(
        SendRequest(
            session_id="qq_official:Group:1",
            message=entry.message,
            media=entry.media,
            layout=entry.layout,
        ),
        MessageContext(platform_name="qq_official", send_mode=1, merge_media=True),
    )
    assert result.ok
    assert sender._send_chain.await_args.kwargs == {"use_markdown": False}
    assert [type(component) for component in sender._send_chain.await_args.args[1]] == [
        Plain,
        Image,
    ]
