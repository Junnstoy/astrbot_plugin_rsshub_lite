"""Mock data for testing astrbot_plugin_rsshub_lite."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock


@dataclass
class MockFeedData:
    """模拟 RSS Feed 数据."""

    id: int = 1
    url: str = "https://example.com/rss.xml"
    title: str = "Test Feed"
    description: str = "Test feed description"
    link: str = "https://example.com"
    last_fetch: datetime | None = None
    etag: str = ""
    last_modified: str = ""

    def to_dict(self) -> dict[str, Any]:
        """转换为字典."""
        return {
            "id": self.id,
            "url": self.url,
            "title": self.title,
            "description": self.description,
            "link": self.link,
            "last_fetch": self.last_fetch,
            "etag": self.etag,
            "last_modified": self.last_modified,
        }


@dataclass
class MockEntryData:
    """模拟 RSS Entry 数据."""

    id: str = "entry-001"
    title: str = "Test Entry"
    link: str = "https://example.com/entry1"
    summary: str = "Test summary"
    content: str | None = "Test content"
    author: str | None = "Test Author"
    published: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tags: list[str] = field(default_factory=list)
    enclosures: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典."""
        return {
            "id": self.id,
            "title": self.title,
            "link": self.link,
            "summary": self.summary,
            "content": self.content,
            "author": self.author,
            "published": self.published,
            "tags": self.tags,
            "enclosures": self.enclosures,
        }


class MockAstrMessageEvent:
    """模拟 AstrBot 消息事件."""

    def __init__(
        self,
        message_str: str = "/rss",
        session_id: str = "test:Group:12345",
        user_id: str = "test_user",
        is_admin: bool = False,
        platform: str = "telegram",
    ):
        self.message_str = message_str
        self.session_id = session_id
        self.user_id = user_id
        self.is_admin = is_admin
        self.platform = platform
        self._responses: list[str] = []

    async def send(self, message: str) -> None:
        """模拟发送消息."""
        self._responses.append(message)

    def get_responses(self) -> list[str]:
        """获取所有响应."""
        return self._responses

    def clear_responses(self) -> None:
        """清除响应."""
        self._responses.clear()


class MockContext:
    """模拟 AstrBot 上下文."""

    def __init__(self):
        self.config = MagicMock()
        self.config.get = MagicMock(return_value=None)
        self._stars: dict[str, Any] = {}
        self._handlers: list[Any] = []

    def add_star(self, star: Any) -> None:
        """添加模拟插件."""
        self._stars[star.name] = star

    def get_stars(self) -> dict[str, Any]:
        """获取所有插件."""
        return self._stars

    def add_handler(self, handler: Any) -> None:
        """添加处理器."""
        self._handlers.append(handler)

    def get_handlers(self) -> list[Any]:
        """获取所有处理器."""
        return self._handlers
