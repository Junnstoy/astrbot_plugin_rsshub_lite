"""
命令结果 DTO

所有 Command 和 Query 的返回结果封装。
禁止返回裸 dict。
"""

from typing import Any

from pydantic import BaseModel


class CommandResult(BaseModel):
    """
    命令执行结果

    所有 Command 的 execute 方法必须返回此类型。
    """

    success: bool
    """是否成功"""

    message: str
    """结果消息"""

    data: Any | None = None
    """附加数据（可选）"""

    class Config:
        frozen = True
