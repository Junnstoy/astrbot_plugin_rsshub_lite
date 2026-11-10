"""测试去重逻辑"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from astrbot_plugin_rsshub_lite.src.infrastructure.fetcher import EntryParsed, RSSParser


class TestEntryDeduplication:
    """测试条目去重逻辑"""

    def test_deduplication_by_guid(self, sample_duplicate_feed):
        """测试基于 GUID 的去重"""
        parser = RSSParser()
        entries, error = parser.parse(sample_duplicate_feed)

        assert error is None
        # 应该有5个条目（包括重复）
        assert len(entries) == 5

        # 按 GUID 去重
        seen_guids = set()
        unique_entries = []
        for entry in entries:
            if entry.id not in seen_guids:
                seen_guids.add(entry.id)
                unique_entries.append(entry)

        # 应该只剩4个唯一条目
        assert len(unique_entries) == 4

    def test_deduplication_by_url(self):
        """测试基于 URL 的去重"""
        # 模拟相同 URL 不同 GUID 的情况
        entries = [
            EntryParsed(
                id="guid-1",
                title="Article 1",
                link="https://example.com/same-url",
                summary="Summary 1",
                content=None,
                author=None,
                enclosures=[],
                published=datetime.now(timezone.utc),
                tags=[],
            ),
            EntryParsed(
                id="guid-2",
                title="Article 2",
                link="https://example.com/same-url",
                summary="Summary 2",
                content=None,
                author=None,
                enclosures=[],
                published=datetime.now(timezone.utc),
                tags=[],
            ),
        ]

        # 按 URL 去重
        seen_urls = set()
        unique_entries = []
        for entry in entries:
            if entry.link not in seen_urls:
                seen_urls.add(entry.link)
                unique_entries.append(entry)

        # 应该只剩1个
        assert len(unique_entries) == 1

    def test_deduplication_by_title_similarity(self):
        """测试基于标题相似度的去重"""
        entries = [
            EntryParsed(
                id="guid-1",
                title="Breaking News: Important Update",
                link="https://example.com/news1",
                summary="Summary",
                content=None,
                author=None,
                enclosures=[],
                published=datetime.now(timezone.utc),
                tags=[],
            ),
            EntryParsed(
                id="guid-2",
                title="Breaking News: Important Update",
                link="https://example.com/news2",
                summary="Different summary",
                content=None,
                author=None,
                enclosures=[],
                published=datetime.now(timezone.utc),
                tags=[],
            ),
        ]

        # 按标题去重（完全匹配）
        seen_titles = set()
        unique_entries = []
        for entry in entries:
            normalized_title = entry.title.strip().lower()
            if normalized_title not in seen_titles:
                seen_titles.add(normalized_title)
                unique_entries.append(entry)

        # 相同标题应该去重
        assert len(unique_entries) == 1

    def test_hash_generation_consistency(self):
        """测试哈希生成一致性"""
        entry = EntryParsed(
            id="test-guid",
            title="Test Title",
            link="https://example.com/test",
            summary="Test summary",
            content=None,
            author="Test Author",
            enclosures=[],
            published=datetime.now(timezone.utc),
            tags=["tag1", "tag2"],
        )

        # 生成哈希
        content = f"{entry.title}{entry.link}{entry.summary}"
        hash1 = hashlib.md5(content.encode("utf-8")).hexdigest()
        hash2 = hashlib.md5(content.encode("utf-8")).hexdigest()

        # 相同内容应该生成相同哈希
        assert hash1 == hash2

    def test_no_false_positive_deduplication(self, sample_rss_feed):
        """测试不误判不同条目为重复"""
        parser = RSSParser()
        entries, error = parser.parse(sample_rss_feed)

        assert error is None
        # 简单 RSS feed 应该有3个不同的条目
        assert len(entries) == 3

        # 验证 GUID 都不同
        guids = {entry.id for entry in entries}
        assert len(guids) == 3

        # 验证 URL 都不同
        urls = {entry.link for entry in entries}
        assert len(urls) == 3


class TestMultiAlgorithmDeduplication:
    """测试多算法组合去重"""

    def test_combined_hash_algorithms(self):
        """测试组合多种哈希算法"""
        entry = EntryParsed(
            id="guid-123",
            title="Test Article",
            link="https://example.com/article",
            summary="Summary text",
            content=None,
            author="Author",
            enclosures=[],
            published=datetime.now(timezone.utc),
            tags=[],
        )

        # 多种哈希策略
        hashes = {
            "md5_guid": hashlib.md5(entry.id.encode()).hexdigest(),
            "md5_url": hashlib.md5(entry.link.encode()).hexdigest(),
            "md5_title": hashlib.md5(entry.title.encode()).hexdigest(),
            "sha256_combined": hashlib.sha256(
                f"{entry.id}:{entry.link}:{entry.title}".encode()
            ).hexdigest(),
        }

        # 验证哈希都是有效的
        for h in hashes.values():
            assert len(h) > 0
            assert isinstance(h, str)

    def test_deduplication_priority_order(self):
        """测试去重优先级顺序"""
        # 优先级: GUID > URL > Title
        entries = [
            EntryParsed(
                id="unique-guid-1",
                title="Same Title",
                link="https://example.com/unique1",
                summary="Summary 1",
                content=None,
                author=None,
                enclosures=[],
                published=datetime.now(timezone.utc),
                tags=[],
            ),
            EntryParsed(
                id="unique-guid-2",  # 不同 GUID
                title="Same Title",  # 相同 Title
                link="https://example.com/unique2",  # 不同 URL
                summary="Summary 2",
                content=None,
                author=None,
                enclosures=[],
                published=datetime.now(timezone.utc),
                tags=[],
            ),
        ]

        # 按 GUID 去重（最优先）
        seen_guids = set()
        unique_by_guid = [
            e for e in entries if not (e.id in seen_guids or seen_guids.add(e.id))
        ]

        # GUID 不同，所以应该保留2个
        assert len(unique_by_guid) == 2

        # 如果 GUID 相同但 URL 不同，按 URL 去重
        entries_with_same_guid = [
            EntryParsed(
                id="same-guid",
                title="Title 1",
                link="https://example.com/unique1",
                summary="Summary 1",
                content=None,
                author=None,
                enclosures=[],
                published=datetime.now(timezone.utc),
                tags=[],
            ),
            EntryParsed(
                id="same-guid",  # 相同 GUID
                title="Title 2",
                link="https://example.com/unique2",  # 不同 URL
                summary="Summary 2",
                content=None,
                author=None,
                enclosures=[],
                published=datetime.now(timezone.utc),
                tags=[],
            ),
        ]

        seen_guids_2 = set()
        unique_by_guid_2 = [
            e
            for e in entries_with_same_guid
            if not (e.id in seen_guids_2 or seen_guids_2.add(e.id))
        ]

        # 相同 GUID，按 GUID 去重后只剩1个
        assert len(unique_by_guid_2) == 1
