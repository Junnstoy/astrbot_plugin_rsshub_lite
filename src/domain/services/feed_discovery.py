"""
Feed 自动发现服务

负责从网页 URL 中自动发现 RSS/Atom Feed 链接。
属于领域服务，因为涉及跨实体的业务逻辑。
"""

from __future__ import annotations

import re
from typing import Protocol

from ..value_objects.feed_url import FeedUrl


class HttpClient(Protocol):
    """HTTP客户端接口，由基础设施层实现"""

    async def fetch_html(self, url: str) -> str:
        """获取网页HTML内容"""
        ...


class FeedDiscoveryService:
    """
    Feed 自动发现服务

    负责从网页 URL 中自动发现 RSS/Atom Feed 链接。
    """

    # RSS/Atom Feed 的 MIME 类型
    _FEED_MIME_TYPES = {
        "application/rss+xml",
        "application/atom+xml",
        "application/rdf+xml",
        "application/xml",
        "text/xml",
        "application/feed+json",  # JSON Feed
    }

    # 常见的 Feed 路径
    _COMMON_FEED_PATHS = [
        "/feed",
        "/rss",
        "/atom",
        "/feeds",
        "/index.xml",
        "/rss.xml",
        "/atom.xml",
        "/feed.xml",
        "/?feed=rss2",
        "/?feed=atom",
    ]

    def __init__(self, http_client: HttpClient):
        self._http_client = http_client

    async def discover(self, page_url: str) -> list[FeedUrl]:
        """
        从网页中发现 Feed 链接

        Args:
            page_url: 网页URL

        Returns:
            发现的 FeedUrl 列表
        """
        discovered_feeds: list[FeedUrl] = []
        seen_urls: set[str] = set()

        try:
            html = await self._http_client.fetch_html(page_url)
        except Exception:
            # 获取失败时尝试常见路径
            return await self._try_common_paths(page_url)

        # 1. 解析 HTML 中的 <link> 标签
        link_feeds = self._parse_link_tags(html, page_url)
        for feed_url in link_feeds:
            normalized = feed_url.normalized()
            if normalized not in seen_urls:
                discovered_feeds.append(feed_url)
                seen_urls.add(normalized)

        # 2. 解析 HTML 中的 <a> 标签
        anchor_feeds = self._parse_anchor_tags(html, page_url)
        for feed_url in anchor_feeds:
            normalized = feed_url.normalized()
            if normalized not in seen_urls:
                discovered_feeds.append(feed_url)
                seen_urls.add(normalized)

        # 3. 如果没有发现任何 Feed，尝试常见路径
        if not discovered_feeds:
            return await self._try_common_paths(page_url)

        return discovered_feeds

    def _parse_link_tags(self, html: str, base_url: str) -> list[FeedUrl]:
        """
        解析 HTML 中的 <link rel="alternate"> 标签

        Args:
            html: HTML 内容
            base_url: 基础 URL

        Returns:
            FeedUrl 列表
        """
        feeds: list[FeedUrl] = []

        # 匹配 <link rel="alternate" type="application/rss+xml" href="...">
        pattern = re.compile(
            r'<link[^>]*?rel=["\']alternate["\'][^>]*?type=["\']([^"\']+)["\'][^>]*?href=["\']([^"\']+)["\'][^>]*?>',
            re.IGNORECASE | re.DOTALL,
        )

        for match in pattern.finditer(html):
            mime_type = match.group(1).lower()
            href = match.group(2)

            if mime_type in self._FEED_MIME_TYPES:
                feed_url = self._resolve_url(href, base_url)
                if feed_url:
                    try:
                        feeds.append(FeedUrl(url=feed_url))
                    except ValueError:
                        pass

        # 也匹配反向顺序（type 在 rel 之前）
        pattern2 = re.compile(
            r'<link[^>]*?type=["\']([^"\']+)["\'][^>]*?rel=["\']alternate["\'][^>]*?href=["\']([^"\']+)["\'][^>]*?>',
            re.IGNORECASE | re.DOTALL,
        )

        for match in pattern2.finditer(html):
            mime_type = match.group(1).lower()
            href = match.group(2)

            if mime_type in self._FEED_MIME_TYPES:
                feed_url = self._resolve_url(href, base_url)
                if feed_url:
                    try:
                        feeds.append(FeedUrl(url=feed_url))
                    except ValueError:
                        pass

        return feeds

    def _parse_anchor_tags(self, html: str, base_url: str) -> list[FeedUrl]:
        """
        解析 HTML 中的 <a> 标签，寻找指向 Feed 的链接

        Args:
            html: HTML 内容
            base_url: 基础 URL

        Returns:
            FeedUrl 列表
        """
        feeds: list[FeedUrl] = []

        # 匹配可能指向 Feed 的链接
        patterns = [
            # RSS/Atom/Feed 链接
            re.compile(
                r'<a[^>]*?href=["\']([^"\']*?(?:rss|atom|feed)[^"\']*)["\'][^>]*?>',
                re.IGNORECASE | re.DOTALL,
            ),
        ]

        for pattern in patterns:
            for match in pattern.finditer(html):
                href = match.group(1)
                feed_url = self._resolve_url(href, base_url)
                if feed_url:
                    try:
                        feeds.append(FeedUrl(url=feed_url))
                    except ValueError:
                        pass

        return feeds

    async def _try_common_paths(self, base_url: str) -> list[FeedUrl]:
        """
        尝试常见的 Feed 路径

        Args:
            base_url: 基础 URL

        Returns:
            FeedUrl 列表
        """
        feeds: list[FeedUrl] = []

        # 确保 base_url 以 / 结尾
        if not base_url.endswith("/"):
            base_url += "/"

        for path in self._COMMON_FEED_PATHS:
            feed_url = base_url.rstrip("/") + path
            try:
                feeds.append(FeedUrl(url=feed_url))
            except ValueError:
                pass

        return feeds

    def _resolve_url(self, url: str, base_url: str) -> str | None:
        """
        解析相对 URL 为绝对 URL

        Args:
            url: 可能是相对的 URL
            base_url: 基础 URL

        Returns:
            绝对 URL 或 None
        """
        from urllib.parse import urljoin

        if not url:
            return None

        # 处理协议相对 URL (//example.com/feed)
        if url.startswith("//"):
            parsed_base = urljoin(base_url, "/")
            if parsed_base.startswith("https://"):
                return "https:" + url
            else:
                return "http:" + url

        # 使用 urljoin 处理相对 URL
        absolute = urljoin(base_url, url)

        # 验证协议
        if not absolute.startswith(("http://", "https://")):
            return None

        return absolute
