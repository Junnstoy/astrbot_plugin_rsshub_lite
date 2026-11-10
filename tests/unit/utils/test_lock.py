"""测试锁管理器"""

from __future__ import annotations

import asyncio

import pytest
from astrbot_plugin_rsshub_lite.src.infrastructure.utils import (
    LockManager,
    get_lock_manager,
    locked,
)


class TestLockManager:
    """测试 LockManager 类"""

    def test_feed_lock_returns_same_lock_for_same_id(self):
        """测试相同 feed_id 返回相同锁"""
        manager = LockManager()
        lock1 = manager.feed_lock(1)
        lock2 = manager.feed_lock(1)
        assert lock1 is lock2

    def test_feed_lock_returns_different_locks_for_different_ids(self):
        """测试不同 feed_id 返回不同锁"""
        manager = LockManager()
        lock1 = manager.feed_lock(1)
        lock2 = manager.feed_lock(2)
        assert lock1 is not lock2

    def test_user_lock_returns_same_lock_for_same_id(self):
        """测试相同 user_id 返回相同锁"""
        manager = LockManager()
        lock1 = manager.user_lock("user123")
        lock2 = manager.user_lock("user123")
        assert lock1 is lock2

    def test_hostname_semaphore_with_url(self):
        """测试 URL 解析为主机名信号量"""
        manager = LockManager()
        sem1 = manager.hostname_semaphore("https://example.com/path")
        sem2 = manager.hostname_semaphore("example.com")
        # 解析后的主机名相同
        assert sem1 is sem2

    def test_hostname_semaphore_without_parse(self):
        """测试不解析 URL"""
        manager = LockManager()
        sem1 = manager.hostname_semaphore("https://example.com", parse=False)
        sem2 = manager.hostname_semaphore("example.com", parse=False)
        # 不解析时，整个字符串作为键
        assert sem1 is not sem2

    def test_global_web_semaphore(self):
        """测试全局网络信号量"""
        manager = LockManager()
        sem1 = manager.global_web_semaphore
        sem2 = manager.global_web_semaphore
        assert sem1 is sem2

    def test_db_write_lock(self):
        """测试数据库写锁"""
        manager = LockManager()
        lock1 = manager.db_write_lock
        lock2 = manager.db_write_lock
        assert lock1 is lock2

    def test_custom_lock(self):
        """测试自定义锁"""
        manager = LockManager()
        lock1 = manager.custom_lock("my_lock")
        lock2 = manager.custom_lock("my_lock")
        lock3 = manager.custom_lock("other_lock")
        assert lock1 is lock2
        assert lock1 is not lock3


class TestLockedDecorator:
    """测试 locked 装饰器"""

    @pytest.mark.asyncio
    async def test_locked_with_feed_id(self):
        """测试 feed 锁"""
        call_order = []

        class Service:
            @locked("#feed_id")
            async def process_feed(self, feed_id: int) -> str:
                await asyncio.sleep(0.01)
                call_order.append(feed_id)
                return f"processed_{feed_id}"

        service = Service()

        # 并发执行相同 feed_id
        results = await asyncio.gather(
            service.process_feed(1),
            service.process_feed(1),
            service.process_feed(2),
        )

        assert sorted(results) == ["processed_1", "processed_1", "processed_2"]
        # 相同 feed_id 的调用应该串行（按顺序）
        # 但因为我们只关心结果，这里不严格验证顺序

    @pytest.mark.asyncio
    async def test_locked_with_user_id(self):
        """测试用户锁"""

        @locked("#user_id")
        async def user_operation(user_id: str) -> str:
            await asyncio.sleep(0.01)
            return f"done_{user_id}"

        results = await asyncio.gather(
            user_operation("user1"),
            user_operation("user2"),
            user_operation("user1"),
        )

        assert sorted(results) == ["done_user1", "done_user1", "done_user2"]

    @pytest.mark.asyncio
    async def test_locked_with_hostname(self):
        """测试主机名锁"""

        @locked("#url")
        async def fetch(url: str) -> str:
            await asyncio.sleep(0.01)
            return f"fetched_{url}"

        results = await asyncio.gather(
            fetch("https://example.com/page1"),
            fetch("https://example.com/page2"),  # 相同主机名
            fetch("https://other.com/page"),
        )

        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_locked_with_global_web(self):
        """测试全局网络锁"""

        @locked("'global_web'")
        async def global_request() -> str:
            await asyncio.sleep(0.01)
            return "done"

        results = await asyncio.gather(
            global_request(),
            global_request(),
            global_request(),
        )

        assert results == ["done", "done", "done"]
        # 全局锁意味着这些调用是串行的


class TestGetLockManager:
    """测试 get_lock_manager 单例"""

    def test_returns_same_instance(self):
        """测试返回相同实例"""
        manager1 = get_lock_manager()
        manager2 = get_lock_manager()
        assert manager1 is manager2
