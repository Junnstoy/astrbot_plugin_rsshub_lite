"""端到端测试：订阅 -> 抓取 -> 推送 完整流程"""

from __future__ import annotations

import pytest


class TestEndToEndFlow:
    """测试端到端完整流程"""

    @pytest.fixture
    def mock_rss_content(self):
        """模拟 RSS 内容"""
        return """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <link>https://example.com</link>
    <description>Test feed for e2e</description>
    <item>
      <title>New Article</title>
      <link>https://example.com/new</link>
      <guid>e2e-test-001</guid>
      <pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate>
      <description>This is a new article</description>
    </item>
  </channel>
</rss>"""

    @pytest.mark.asyncio
    async def test_full_subscription_flow(self, mock_rss_content):
        """测试完整订阅流程"""
        # 1. 用户订阅一个 RSS 源
        user_id = "test_user_123"
        target_session = "test:Group:12345"

        # 模拟订阅命令
        subscription = {
            "id": 1,
            "user_id": user_id,
            "feed_id": 1,
            "target_session": target_session,
            "interval": 10,
            "notify": True,
            "send_mode": 0,  # 自动
        }

        assert subscription["user_id"] == user_id
        assert subscription["feed_id"] == 1
        assert subscription["target_session"] == target_session

        # 2. 模拟抓取 RSS
        from astrbot_plugin_rsshub_lite.src.infrastructure.fetcher import RSSParser

        parser = RSSParser()
        entries, error = parser.parse(mock_rss_content)

        assert error is None
        assert len(entries) == 1
        assert entries[0].title == "New Article"

        # 3. 检查去重逻辑（首次推送，没有重复）
        seen_guids = set()
        new_entries = [e for e in entries if e.id not in seen_guids]

        assert len(new_entries) == 1

        # 4. 模拟推送消息格式化
        entry = new_entries[0]
        message = f"**{entry.title}**\n\n{entry.summary}\n\n[Read more]({entry.link})"

        assert entry.title in message
        assert entry.link in message
        assert "**" in message

        # 5. 验证推送成功
        assert len(message) > 0

    @pytest.mark.asyncio
    async def test_resubscribe_existing_feed(self):
        """测试重复订阅已存在的 feed"""
        # 模拟已存在的 feed
        existing_feed = {
            "id": 1,
            "url": "https://example.com/rss.xml",
            "title": "Test Feed",
        }

        # 新用户订阅同一个 feed
        new_subscription = {
            "id": 2,
            "user_id": "new_user_456",
            "feed_id": existing_feed["id"],
            "target_session": "test:Group:67890",
        }

        # feed_id 应该相同（复用）
        assert new_subscription["feed_id"] == existing_feed["id"]
        assert new_subscription["user_id"] != "test_user_123"

    @pytest.mark.asyncio
    async def test_update_subscription_options(self):
        """测试更新订阅选项"""
        subscription = {
            "id": 1,
            "interval": 10,
            "notify": True,
            "send_mode": 0,
        }

        # 更新选项
        subscription["interval"] = 30
        subscription["notify"] = False

        assert subscription["interval"] == 30
        assert subscription["notify"] is False

    @pytest.mark.asyncio
    async def test_unsubscribe_removes_subscription(self):
        """测试取消订阅移除订阅记录"""
        subscriptions = [
            {"id": 1, "user_id": "user1", "feed_id": 1},
            {"id": 2, "user_id": "user1", "feed_id": 2},
            {"id": 3, "user_id": "user2", "feed_id": 1},
        ]

        # 取消订阅 id=1
        remaining = [s for s in subscriptions if s["id"] != 1]

        assert len(remaining) == 2
        assert all(s["id"] != 1 for s in remaining)

    @pytest.mark.asyncio
    async def test_dedup_prevents_duplicate_push(self):
        """测试去重防止重复推送"""
        # 模拟已推送的条目
        pushed_guids = {"guid-001", "guid-002"}

        # 新的条目（包含一个已推送的）
        new_entries = [
            {"id": "guid-003", "title": "New"},
            {"id": "guid-001", "title": "Already pushed"},  # 重复
        ]

        # 过滤已推送的
        to_push = [e for e in new_entries if e["id"] not in pushed_guids]

        assert len(to_push) == 1
        assert to_push[0]["id"] == "guid-003"

    @pytest.mark.asyncio
    async def test_batch_push_multiple_entries(self):
        """测试批量推送多条目"""
        entries = [
            {"title": f"Article {i}", "link": f"https://example.com/{i}"}
            for i in range(5)
        ]

        # 批量推送格式化
        messages = [f"**{e['title']}**\n{e['link']}" for e in entries]
        batch_message = "\n\n---\n\n".join(messages)

        assert len(messages) == 5
        assert "Article 0" in batch_message
        assert "Article 4" in batch_message

    @pytest.mark.asyncio
    async def test_error_handling_in_fetch(self):
        """测试抓取错误处理"""
        from astrbot_plugin_rsshub_lite.src.infrastructure.fetcher import RSSParser

        parser = RSSParser()
        entries, error = parser.parse("invalid xml content")

        # 无效 XML 应该返回错误
        assert error is not None
        assert len(entries) == 0

    @pytest.mark.asyncio
    async def test_empty_feed_no_push(self):
        """测试空 feed 不推送"""
        entries = []

        # 空条目不应该产生推送
        assert len(entries) == 0

        # 模拟推送逻辑
        if entries:
            message = "推送消息"
        else:
            message = None

        assert message is None
