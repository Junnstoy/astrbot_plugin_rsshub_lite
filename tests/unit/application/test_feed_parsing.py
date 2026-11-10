"""RSS parsing behavior tests for real RSSHub Twitter output."""

from __future__ import annotations

from pathlib import Path

import pytest
from astrbot_plugin_rsshub_lite.src.infrastructure.fetcher.rss.parser import RSSParser


@pytest.fixture
def twitter_rss_xml(fixtures_dir: Path) -> str:
    """Return a captured RSSHub Twitter timeline feed."""
    return (fixtures_dir / "feeds" / "twitter_rss.xml").read_text(encoding="utf-8")


class TestTwitterRSSParsing:
    """Verify parsing behavior against realistic Twitter RSSHub XML."""

    def test_parse_twitter_rss(self, twitter_rss_xml: str) -> None:
        parser = RSSParser()
        entries, error = parser.parse(twitter_rss_xml)

        assert error is None
        assert len(entries) >= 20
        assert all(entry.guid for entry in entries)
        assert all(entry.link for entry in entries)
        assert all(entry.title is not None for entry in entries)
        assert all(entry.published is not None for entry in entries)

    def test_entries_have_required_fields(self, twitter_rss_xml: str) -> None:
        parser = RSSParser()
        entries, error = parser.parse(twitter_rss_xml)

        assert error is None
        for entry in entries:
            assert entry.guid.strip()
            assert entry.link.strip()
            assert entry.published is not None

    def test_split_into_rounds(self, twitter_rss_xml: str) -> None:
        parser = RSSParser()
        entries, error = parser.parse(twitter_rss_xml)
        assert error is None

        sorted_entries = sorted(entries, key=lambda entry: entry.published)
        chunk_size = len(sorted_entries) // 3
        rounds = [
            sorted_entries[:chunk_size],
            sorted_entries[chunk_size : chunk_size * 2],
            sorted_entries[chunk_size * 2 :],
        ]

        assert all(round_entries for round_entries in rounds)
        assert sum(len(round_entries) for round_entries in rounds) == len(entries)
