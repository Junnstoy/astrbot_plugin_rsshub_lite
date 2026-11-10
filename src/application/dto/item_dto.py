"""
Item DTO

RSS 条目数据传输对象，用于在应用层和接口层之间传递条目数据。
"""

from datetime import datetime

from pydantic import BaseModel, Field


class ItemDTO(BaseModel):
    """
    RSS 条目数据传输对象
    """

    title: str = Field(default="", description="条目标题")
    link: str = Field(default="", description="条目链接")
    guid: str | None = Field(default=None, description="条目 GUID")
    summary: str = Field(default="", description="摘要")
    published_at: datetime | None = Field(default=None, description="发布时间")
    author: str | None = Field(default=None, description="作者")
    media_urls: list[str] = Field(default_factory=list, description="媒体 URL 列表")
    tags: list[str] = Field(default_factory=list, description="标签列表")

    class Config:
        frozen = True
