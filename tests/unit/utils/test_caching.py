"""测试缓存装饰器"""

from __future__ import annotations

import asyncio
import time

import pytest
from astrbot_plugin_rsshub_lite.src.infrastructure.utils import (
    MemoryCache,
    cacheevict,
    cacheput,
    caching,
    get_memory_cache,
)


@pytest.fixture(autouse=True)
def clear_test_cache():
    get_memory_cache().clear("test_cache")


class TestMemoryCache:
    """测试 MemoryCache 类"""

    def test_get_nonexistent_returns_none(self):
        """测试获取不存在的键返回 None"""
        cache = MemoryCache()
        result = cache.get("test_cache", "nonexistent_key")
        assert result is None

    def test_set_and_get(self):
        """测试设置和获取缓存值"""
        cache = MemoryCache()
        cache.set("test_cache", "key1", "value1")
        result = cache.get("test_cache", "key1")
        assert result == "value1"

    def test_set_with_ttl_expires(self):
        """测试带 TTL 的缓存过期"""
        cache = MemoryCache()
        cache.set("test_cache", "key1", "value1", ttl=0.01)
        time.sleep(0.02)  # 等待过期
        result = cache.get("test_cache", "key1")
        assert result is None

    def test_delete_existing_key(self):
        """测试删除存在的键"""
        cache = MemoryCache()
        cache.set("test_cache", "key1", "value1")
        deleted = cache.delete("test_cache", "key1")
        assert deleted is True
        assert cache.get("test_cache", "key1") is None

    def test_delete_nonexistent_key(self):
        """测试删除不存在的键"""
        cache = MemoryCache()
        deleted = cache.delete("test_cache", "nonexistent")
        assert deleted is False

    def test_clear_cache(self):
        """测试清空缓存"""
        cache = MemoryCache()
        cache.set("test_cache", "key1", "value1")
        cache.set("test_cache", "key2", "value2")
        count = cache.clear("test_cache")
        assert count == 2
        assert cache.get("test_cache", "key1") is None
        assert cache.get("test_cache", "key2") is None

    def test_clear_empty_cache_returns_zero(self):
        """测试清空空缓存返回 0"""
        cache = MemoryCache()
        count = cache.clear("empty_cache")
        assert count == 0


class TestCachingDecorator:
    """测试 caching 装饰器"""

    def test_caching_basic(self):
        """测试基本缓存功能"""
        call_count = 0

        @caching("test_cache", key="#user_id")
        def get_user_data(user_id: int) -> dict:
            nonlocal call_count
            call_count += 1
            return {"id": user_id, "name": f"User{user_id}"}

        # 第一次调用
        result1 = get_user_data(1)
        assert result1 == {"id": 1, "name": "User1"}
        assert call_count == 1

        # 第二次调用（应该使用缓存）
        result2 = get_user_data(1)
        assert result2 == {"id": 1, "name": "User1"}
        assert call_count == 1  # 不应该增加

        # 不同参数的调用
        result3 = get_user_data(2)
        assert result3 == {"id": 2, "name": "User2"}
        assert call_count == 2

    def test_caching_with_ttl(self):
        """测试带 TTL 的缓存"""
        call_count = 0

        @caching("test_cache", key="#x", ttl=0.05)
        def compute(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        result1 = compute(5)
        assert result1 == 10
        assert call_count == 1

        # 立即再次调用，应该使用缓存
        result2 = compute(5)
        assert result2 == 10
        assert call_count == 1

        # 等待过期
        time.sleep(0.06)
        result3 = compute(5)
        assert result3 == 10
        assert call_count == 2  # 过期后重新计算

    def test_caching_with_condition(self):
        """测试带条件的缓存"""
        call_count = 0

        @caching("test_cache", key="#x", condition="#result > 0")
        def maybe_cache(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x

        # 正数应该缓存
        result1 = maybe_cache(5)
        assert result1 == 5
        assert call_count == 1

        result2 = maybe_cache(5)
        assert result2 == 5
        assert call_count == 1  # 使用缓存

        # 负数不应该缓存
        result3 = maybe_cache(-3)
        assert result3 == -3
        assert call_count == 2

        result4 = maybe_cache(-3)
        assert result4 == -3
        assert call_count == 3  # 没有缓存，再次计算

    @pytest.mark.asyncio
    async def test_caching_async(self):
        """测试异步缓存"""
        call_count = 0

        @caching("test_cache", key="#user_id")
        async def async_get_user(user_id: int) -> dict:
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)
            return {"id": user_id}

        result1 = await async_get_user(1)
        assert result1 == {"id": 1}
        assert call_count == 1

        result2 = await async_get_user(1)
        assert result2 == {"id": 1}
        assert call_count == 1  # 使用缓存


class TestCachePutDecorator:
    """测试 cacheput 装饰器"""

    def test_cacheput_always_executes(self):
        """测试 cacheput 始终执行函数"""
        call_count = 0

        @cacheput("test_cache", key="#x")
        def update_value(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * call_count

        result1 = update_value(5)
        assert result1 == 5  # 5 * 1
        assert call_count == 1

        result2 = update_value(5)
        assert result2 == 10  # 5 * 2（始终执行）
        assert call_count == 2

        # 验证缓存被更新
        cache = get_memory_cache()
        cached = cache.get("test_cache", "5")
        assert cached == 10


class TestCacheEvictDecorator:
    """测试 cacheevict 装饰器"""

    def test_cacheevict_single_key(self):
        """测试清除单个缓存键"""
        cache = get_memory_cache()
        cache.set("test_cache", "key1", "value1")
        cache.set("test_cache", "key2", "value2")

        @cacheevict("test_cache", key="#key")
        def delete_key(key: str) -> None:
            pass

        delete_key("key1")

        assert cache.get("test_cache", "key1") is None
        assert cache.get("test_cache", "key2") == "value2"

    def test_cacheevict_all_entries(self):
        """测试清除所有缓存条目"""
        cache = get_memory_cache()
        cache.set("test_cache", "key1", "value1")
        cache.set("test_cache", "key2", "value2")
        cache.set("test_cache", "key3", "value3")

        @cacheevict("test_cache", all_entries=True)
        def clear_all() -> None:
            pass

        clear_all()

        assert cache.get("test_cache", "key1") is None
        assert cache.get("test_cache", "key2") is None
        assert cache.get("test_cache", "key3") is None

    def test_cacheevict_before_invocation(self):
        """测试在调用前清除缓存"""
        cache = get_memory_cache()
        cache.set("test_cache", "key1", "old_value")

        @cacheevict("test_cache", key="#key", before_invocation=True)
        def update_and_return(key: str) -> str:
            # 此时缓存已被清除
            cached = cache.get("test_cache", key)
            assert cached is None
            return "new_value"

        result = update_and_return("key1")
        assert result == "new_value"
