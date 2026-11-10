"""
Feed 领域实体

代表一个 RSS/Atom 订阅源，包含源的基本信息、状态和内容指纹。
不包含任何 ORM 或持久化逻辑。
"""

from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator


def normalize_entry_hashes(value: Any) -> list[list[str]] | None:
    """Accept legacy flat hash lists and normalize to grouped storage."""
    if value is None:
        return None
    if not isinstance(value, list):
        return None
    if not value:
        return []
    if isinstance(value[0], list):
        return [
            [str(item) for item in group if item]
            for group in value
            if isinstance(group, list) and group
        ]

    groups: list[list[str]] = []
    current: list[str] = []
    for raw in value:
        item = str(raw or "")
        if not item:
            continue
        if item.startswith("sid:") and current:
            groups.append(current)
            current = []
        current.append(item)
    if current:
        groups.append(current)
    return groups


class Feed(BaseModel):
    """
    Feed 领域实体

    代表一个 RSS/Atom 订阅源，包含源的基本信息、状态和内容指纹。
    """

    id: int | None = Field(default=None, description="数据库ID")
    state: int = Field(default=1, description="Feed状态: 0=停用, 1=启用")
    link: str = Field(..., max_length=4096, description="Feed链接URL")
    title: str = Field(default="", max_length=1024, description="Feed标题")
    entry_hashes: list[list[str]] | None = Field(
        default=None, description="已处理条目的哈希分组列表，每组对应一个条目"
    )
    etag: str | None = Field(default=None, max_length=128, description="HTTP ETag")
    last_modified: datetime | None = Field(default=None, description="最后修改时间")

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="创建时间"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="更新时间"
    )

    def model_post_init(self, __context: object) -> None:
        """初始化后验证链接格式"""
        self._validate_link()
        if not self.title:
            self.title = self.link

    @field_validator("entry_hashes", mode="before")
    @classmethod
    def _normalize_entry_hashes(cls, value: Any) -> list[list[str]] | None:
        return normalize_entry_hashes(value)

    def _validate_link(self) -> None:
        """
        验证链接格式

        Raises:
            ValueError: 链接格式无效
        """
        if not self.link:
            raise ValueError("Feed链接不能为空")

        parsed = urlparse(self.link)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"Feed链接必须使用http或https协议: {self.link}")

    def is_active(self) -> bool:
        """检查Feed是否处于启用状态"""
        return self.state == 1

    def activate(self) -> "Feed":
        """启用Feed"""
        self.state = 1
        self.updated_at = datetime.now(timezone.utc)
        return self

    def deactivate(self) -> "Feed":
        """停用Feed"""
        self.state = 0
        self.updated_at = datetime.now(timezone.utc)
        return self

    def update_etag(self, etag: str | None) -> "Feed":
        """更新ETag"""
        self.etag = etag
        self.updated_at = datetime.now(timezone.utc)
        return self

    def has_entry(self, entry_hash: str) -> bool:
        """检查条目是否已处理过（在任意哈希分组中搜索）"""
        if self.entry_hashes is None:
            return False
        return any(entry_hash in group for group in self.entry_hashes)

    def add_entry_hash(self, entry_hash: str) -> "Feed":
        """添加条目哈希到去重列表"""
        if self.entry_hashes is None:
            self.entry_hashes = []
        self.entry_hashes.append([entry_hash])
        self.updated_at = datetime.now(timezone.utc)
        return self
