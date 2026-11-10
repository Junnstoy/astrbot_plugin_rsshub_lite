"""RSS Web Feed DTO

RSS 抓取相关的数据传输对象，供基础设施层和应用层共享。
"""

from __future__ import annotations

from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any

import feedparser
from pydantic import BaseModel, Field

from ...domain.exceptions import WebError


class WebFeed(BaseModel):
    """RSS Feed 抓取结果"""

    url: str = Field(..., description="最终请求URL（可能经过重定向）")
    ori_url: str = Field(default="", description="原始请求URL")
    content: bytes | None = Field(default=None, description="原始响应内容")
    headers: dict[str, str] = Field(default_factory=dict, description="HTTP响应头")
    status: int = Field(default=0, description="HTTP状态码")
    reason: str | None = Field(default=None, description="HTTP状态描述")
    now: datetime | None = Field(default=None, description="响应时间")
    rss_d: feedparser.FeedParserDict | None = Field(
        default=None, description="feedparser解析结果"
    )
    error: WebError | None = Field(default=None, description="错误信息")

    model_config = {"arbitrary_types_allowed": True}

    @property
    def etag(self) -> str | None:
        """从响应头中提取 ETag（大小写不敏感）"""
        for key, value in self.headers.items():
            if key.lower() == "etag":
                return value
        return None

    @property
    def last_modified(self) -> datetime | None:
        """从响应头中提取 Last-Modified 时间"""
        lm = self.headers.get("Last-Modified") or self.headers.get("last-modified")
        if lm:
            try:
                return parsedate_to_datetime(lm)
            except Exception:
                return None
        return None

    @property
    def raw_xml(self) -> str:
        """获取原始 XML 内容（字符串形式）"""
        if self.content is None:
            return ""
        if isinstance(self.content, bytes):
            return self.content.decode("utf-8", errors="replace")
        return str(self.content)

    @property
    def feed_title(self) -> str | None:
        """获取 Feed 标题"""
        if self.rss_d and self.rss_d.feed:
            return self.rss_d.feed.get("title")
        return None

    @property
    def entries(self) -> list[Any]:
        """获取 Feed 条目列表"""
        if self.rss_d:
            return self.rss_d.entries
        return []

    def calc_next_check_as_per_server_side_cache(self) -> datetime | None:
        """根据服务器端缓存计算下次检查时间"""
        return None
