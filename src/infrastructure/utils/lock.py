"""并发锁管理模块

提供通用锁装饰器和锁管理器支持。
"""

from __future__ import annotations

import asyncio
import functools
import inspect
from collections import defaultdict
from collections.abc import Callable
from typing import Any, TypeVar
from urllib.parse import urlparse

from .expression_parser import CompiledExpression

F = TypeVar("F", bound=Callable[..., Any])


# =============================================================================
# Lock Manager
# =============================================================================


class LockManager:
    """锁管理器 - 管理各种类型的锁，避免并发冲突"""

    def __init__(self):
        self._feed_locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._user_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._hostname_locks: dict[str, asyncio.Semaphore] = defaultdict(
            lambda: asyncio.Semaphore(3)
        )
        self._global_web_lock = asyncio.Semaphore(20)
        self._db_write_lock = asyncio.Lock()
        self._custom_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    def feed_lock(self, feed_id: int) -> asyncio.Lock:
        """获取 Feed 更新锁"""
        return self._feed_locks[feed_id]

    def user_lock(self, user_id: str) -> asyncio.Lock:
        """获取用户操作锁"""
        return self._user_locks[user_id]

    def hostname_semaphore(
        self, hostname: str, parse: bool = True
    ) -> asyncio.Semaphore:
        """获取主机名信号量

        Args:
            hostname: 主机名或完整URL
            parse: 是否需要解析URL
        """
        if parse and hostname.startswith("http"):
            hostname = urlparse(hostname).hostname or hostname
        return self._hostname_locks[hostname]

    @property
    def global_web_semaphore(self) -> asyncio.Semaphore:
        """获取全局网络信号量"""
        return self._global_web_lock

    @property
    def db_write_lock(self) -> asyncio.Lock:
        """获取数据库写锁"""
        return self._db_write_lock

    def custom_lock(self, name: str) -> asyncio.Lock:
        """获取自定义锁"""
        return self._custom_locks[name]


_lock_manager: LockManager | None = None


def get_lock_manager() -> LockManager:
    """获取全局锁管理器单例"""
    global _lock_manager
    if _lock_manager is None:
        _lock_manager = LockManager()
    return _lock_manager


def _infer_lock_type(expr: str) -> tuple[str, Callable[[Any], Any]]:
    """从表达式推断锁类型

    Returns:
        (lock_type, key_transform): 锁类型和键转换函数
    """
    expr = expr.strip()

    if expr.startswith("'") and expr.endswith("'"):
        lock_name = expr[1:-1]
        if lock_name == "global_web":
            return "global_web", lambda x: x
        elif lock_name == "db_write":
            return "db_write", lambda x: x
        else:
            return "custom", lambda x: lock_name

    if expr.startswith("#"):
        if ".id" in expr.lower() or "feed" in expr.lower():
            return "feed", lambda x: int(x) if isinstance(x, (int, str)) else x
        if "user" in expr.lower():
            return "user", lambda x: str(x)
        if any(kw in expr.lower() for kw in ["url", "hostname", "host"]):
            return "hostname", lambda x: x

    raise ValueError(
        f"Cannot infer lock type from expression: {expr}. "
        f"Supported patterns: "
        f"'#*.id' (feed lock), "
        f"'#*user*' (user lock), "
        f"'#*url*' / '#*hostname*' / '#*host*' (hostname semaphore), "
        f"'global_web' (global web semaphore), "
        f"'db_write' (db write lock), "
        f"'custom_name' (custom lock)"
    )


def locked(key: str) -> Callable[[F], F]:
    """通用锁装饰器

    根据 key 表达式自动推断锁类型并加锁。

    Args:
        key: SpEL 表达式，用于提取锁键值

    Returns:
        装饰器函数

    Examples:
        >>> @locked("#feed.id")
        ... async def process_feed(self, feed):
        ...     pass

        >>> @locked("#user_id")
        ... async def handle_user(self, event, user_id: str):
        ...     pass
    """
    lock_type, key_transform = _infer_lock_type(key)
    compiled_expr = CompiledExpression(key)
    manager = get_lock_manager()

    def decorator(func: F) -> F:
        sig = inspect.signature(func)
        param_names = list(sig.parameters.keys())

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            raw_value = compiled_expr.evaluate(args, kwargs, param_names)
            lock_key = key_transform(raw_value)

            if lock_type == "feed":
                lock_obj = manager.feed_lock(lock_key)
            elif lock_type == "user":
                lock_obj = manager.user_lock(lock_key)
            elif lock_type == "hostname":
                lock_obj = manager.hostname_semaphore(str(lock_key), parse=True)
            elif lock_type == "global_web":
                lock_obj = manager.global_web_semaphore
            elif lock_type == "db_write":
                lock_obj = manager.db_write_lock
            elif lock_type == "custom":
                lock_obj = manager.custom_lock(lock_key)
            else:
                raise ValueError(f"Unknown lock type: {lock_type}")

            async with lock_obj:
                return await func(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator
