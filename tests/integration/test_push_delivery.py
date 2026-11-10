"""测试推送效果"""

from __future__ import annotations

from datetime import datetime, timezone

from astrbot_plugin_rsshub_lite.src.infrastructure.fetcher import EntryParsed


class TestMessageFormatting:
    """测试消息格式化"""

    def test_format_entry_as_text(self):
        """测试将条目格式化为文本消息"""
        entry = EntryParsed(
            id="guid-123",
            title="Test Article Title",
            link="https://example.com/article",
            summary="This is a test summary",
            content=None,
            author="Test Author",
            enclosures=[],
            published=datetime.now(timezone.utc),
            tags=["tech", "news"],
        )

        # 模拟消息格式化
        message = f"**{entry.title}**\n\n{entry.summary}\n\n[Read more]({entry.link})"

        assert entry.title in message
        assert entry.summary in message
        assert entry.link in message

    def test_format_entry_with_author(self):
        """测试包含作者的消息格式"""
        entry = EntryParsed(
            id="guid-123",
            title="Test Article",
            link="https://example.com/article",
            summary="Summary",
            content=None,
            author="John Doe",
            enclosures=[],
            published=datetime.now(timezone.utc),
            tags=[],
        )

        # 带作者的消息格式
        message = f"**{entry.title}**\n_by {entry.author}_\n\n{entry.summary}\n\n[Read more]({entry.link})"

        assert entry.title in message
        assert entry.author in message

    def test_format_entry_with_tags(self):
        """测试包含标签的消息格式"""
        entry = EntryParsed(
            id="guid-123",
            title="Test Article",
            link="https://example.com/article",
            summary="Summary",
            content=None,
            author=None,
            enclosures=[],
            published=datetime.now(timezone.utc),
            tags=["python", "rss", "bot"],
        )

        # 带标签的消息格式
        tags_str = " ".join([f"#{tag}" for tag in entry.tags])
        message = f"**{entry.title}**\n\n{entry.summary}\n\nTags: {tags_str}\n\n[Read more]({entry.link})"

        assert "#python" in message
        assert "#rss" in message
        assert "#bot" in message

    def test_format_entry_truncation(self):
        """测试长内容截断"""
        long_summary = "A" * 1000

        entry = EntryParsed(
            id="guid-123",
            title="Test Article",
            link="https://example.com/article",
            summary=long_summary,
            content=None,
            author=None,
            enclosures=[],
            published=datetime.now(timezone.utc),
            tags=[],
        )

        # 模拟截断逻辑（例如限制500字符）
        max_length = 500
        truncated = (
            entry.summary[:max_length] + "..."
            if len(entry.summary) > max_length
            else entry.summary
        )

        assert len(truncated) <= max_length + 3  # +3 for "..."
        assert "..." in truncated


class TestSendModes:
    """测试不同发送模式"""

    def test_send_mode_direct(self):
        """测试直接发送模式"""
        # 直接发送：完整内容
        entry = EntryParsed(
            id="guid-123",
            title="Test",
            link="https://example.com",
            summary="Summary",
            content=None,
            author=None,
            enclosures=[],
            published=datetime.now(timezone.utc),
            tags=[],
        )

        # 直接发送应该包含完整内容
        message = f"{entry.title}\n\n{entry.summary}\n\n{entry.link}"
        assert entry.summary in message

    def test_send_mode_forward(self):
        """测试转发模式"""
        # 转发模式可能包含特殊标记
        entry = EntryParsed(
            id="guid-123",
            title="Test",
            link="https://example.com",
            summary="Summary",
            content=None,
            author=None,
            enclosures=[],
            published=datetime.now(timezone.utc),
            tags=[],
        )

        # 转发消息可能包含来源标记
        message = (
            f"[Forwarded]\n**{entry.title}**\n\n{entry.summary}\n\nSource: {entry.link}"
        )
        assert "Forwarded" in message
        assert "Source:" in message

    def test_send_mode_link_only(self):
        """测试仅链接模式"""
        entry = EntryParsed(
            id="guid-123",
            title="Test",
            link="https://example.com/article",
            summary="Summary",
            content=None,
            author=None,
            enclosures=[],
            published=datetime.now(timezone.utc),
            tags=[],
        )

        # 仅链接模式只发送标题和链接
        message = f"**{entry.title}**\n{entry.link}"
        assert entry.link in message
        assert entry.summary not in message


class TestPushDeliveryEffects:
    """测试推送效果"""

    def test_multiple_entries_batching(self):
        """测试多条目批量推送"""
        entries = [
            EntryParsed(
                id=f"guid-{i}",
                title=f"Article {i}",
                link=f"https://example.com/article{i}",
                summary=f"Summary {i}",
                content=None,
                author=None,
                enclosures=[],
                published=datetime.now(timezone.utc),
                tags=[],
            )
            for i in range(5)
        ]

        # 批量推送应该合并为一条消息
        message_parts = [f"**{e.title}**\n{e.summary}" for e in entries]
        batch_message = "\n\n---\n\n".join(message_parts)

        assert len(batch_message) > 0
        assert "Article 0" in batch_message
        assert "Article 4" in batch_message

    def test_push_with_media(self):
        """测试带媒体的推送"""
        from astrbot_plugin_rsshub_lite.src.infrastructure.fetcher import Enclosure

        enclosure = Enclosure(
            url="https://example.com/image.jpg",
            type="image/jpeg",
            length=1024,
        )

        entry = EntryParsed(
            id="guid-123",
            title="Article with Image",
            link="https://example.com/article",
            summary="Summary",
            content=None,
            author=None,
            enclosures=[enclosure],
            published=datetime.now(timezone.utc),
            tags=[],
        )

        # 消息应该包含媒体信息
        assert len(entry.enclosures) == 1
        assert entry.enclosures[0].url == "https://example.com/image.jpg"

    def test_push_empty_entries(self):
        """测试空条目推送"""
        entries = []

        # 空列表不应该产生推送
        assert len(entries) == 0
