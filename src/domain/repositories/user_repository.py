"""
用户仓库接口

定义用户实体的持久化操作规范。具体实现由基础设施层提供。
"""

from typing import Protocol

from ..entities.user import User


class UserRepository(Protocol):
    """
    用户仓库接口

    定义用户实体的持久化操作规范。具体实现由基础设施层提供。
    """

    async def get_by_id(self, user_id: str) -> User | None:
        """根据ID获取用户

        Args:
            user_id: 用户唯一标识

        Returns:
            User对象，不存在时返回None
        """
        ...

    async def get_all(self, limit: int = 100, offset: int = 0) -> list[User]:
        """获取所有用户

        Args:
            limit: 限制数量
            offset: 偏移量

        Returns:
            用户列表
        """
        ...

    async def get_or_create(self, user_id: str) -> User:
        """获取或创建用户

        Args:
            user_id: 用户唯一标识

        Returns:
            User对象（已存在或新创建）
        """
        ...

    async def save(self, user: User) -> User:
        """保存用户

        Args:
            user: 用户实体

        Returns:
            保存后的用户实体
        """
        ...

    async def update_defaults(self, user_id: str, **kwargs) -> User | None:
        """更新用户默认配置

        Args:
            user_id: 用户唯一标识
            **kwargs: 要更新的字段

        Returns:
            更新后的用户实体，不存在时返回None
        """
        ...

    async def delete(self, user_id: str) -> bool:
        """删除用户

        Args:
            user_id: 用户唯一标识

        Returns:
            是否删除成功
        """
        ...
