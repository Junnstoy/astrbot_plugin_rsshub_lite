"""
Feed URL 值对象

封装 RSS/Atom Feed 的 URL，提供格式验证和规范化功能。
值对象无身份标识，相等性由内容决定。
"""

from urllib.parse import urlparse

from pydantic import BaseModel, Field


class FeedUrl(BaseModel):
    """
    Feed URL 值对象

    封装 RSS/Atom Feed 的 URL，确保格式正确并提供规范化功能。
    """

    url: str = Field(..., max_length=4096, description="Feed URL")

    def __init__(self, url: str) -> None:
        super().__init__(url=url)
        self._validate()

    def _validate(self) -> None:
        """
        验证 URL 格式

        Raises:
            ValueError: URL 格式无效
        """
        if not self.url:
            raise ValueError("Feed URL 不能为空")

        parsed = urlparse(self.url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"Feed URL 必须使用 http 或 https 协议: {self.url}")

        if not parsed.netloc:
            raise ValueError(f"Feed URL 必须包含域名: {self.url}")

    def normalized(self) -> str:
        """返回规范化后的 URL"""
        return self.url.strip().rstrip("/")

    def __str__(self) -> str:
        return self.url

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, FeedUrl):
            return NotImplemented
        return self.normalized() == other.normalized()

    def __hash__(self) -> int:
        return hash(self.normalized())
