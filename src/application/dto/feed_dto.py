"""
Feed DTO

Feed 数据传输对象，用于在应用层和接口层之间传递 Feed 数据。
"""

from datetime import datetime

from pydantic import BaseModel, Field


class FeedDTO(BaseModel):
    """
    Feed 数据传输对象
    """

    id: int | None = Field(default=None, description="Feed ID")
    link: str = Field(..., description="Feed 链接")
    title: str = Field(default="", description="Feed 标题")
    state: int = Field(default=1, description="状态: 0=停用, 1=启用")
    etag: str | None = Field(default=None, description="ETag")
    last_modified: datetime | None = Field(default=None, description="最后修改时间")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")

    class Config:
        frozen = True
