"""
更新间隔值对象

封装 RSS Feed 监控的更新间隔，提供验证和转换功能。
值对象无身份标识，相等性由内容决定。
"""

from pydantic import BaseModel, Field

MIN_INTERVAL_MINUTES = 1
MAX_INTERVAL_MINUTES = 1440  # 24小时


class UpdateInterval(BaseModel):
    """
    更新间隔值对象

    封装 RSS Feed 监控的更新间隔（分钟），确保值在合理范围内。
    """

    minutes: int = Field(
        default=10,
        ge=MIN_INTERVAL_MINUTES,
        le=MAX_INTERVAL_MINUTES,
        description="监控间隔（分钟）",
    )

    def __init__(self, minutes: int = 10) -> None:
        super().__init__(minutes=minutes)

    def to_seconds(self) -> int:
        """转换为秒"""
        return self.minutes * 60

    def __str__(self) -> str:
        return f"{self.minutes}分钟"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, UpdateInterval):
            return NotImplemented
        return self.minutes == other.minutes

    def __hash__(self) -> int:
        return hash(self.minutes)
