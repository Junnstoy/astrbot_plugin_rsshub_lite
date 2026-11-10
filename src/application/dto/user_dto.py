"""用户 DTO

用于应用层和表示层之间传递用户数据。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class UserDTO:
    """用户数据传输对象"""

    id: str
    state: int
    interval: int
    notify: int
    send_mode: int
    length_limit: int
    display_author: int
    display_via: int
    display_title: int
    display_entry_tags: int
    style: int
    display_media: int
    created_at: datetime
    updated_at: datetime

    merge_media: int = -100
    feed_length_limit: int = -100
    feed_display_author: int = -100
    feed_display_via: int = -100
    feed_display_title: int = -100
    feed_display_entry_tags: int = -100
    feed_display_media: int = -100
    feed_style: int = -100
    feed_merge_media: int = -100
