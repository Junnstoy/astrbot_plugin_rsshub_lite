"""Feed push simulation tests for deduplication behavior."""

from __future__ import annotations

from pathlib import Path

import pytest
from astrbot_plugin_rsshub_lite.src.domain.entities.feed import Feed
from astrbot_plugin_rsshub_lite.src.infrastructure.fetcher.rss.parser import (
    EntryParsed,
    RSSParser,
)


@pytest.fixture
def twitter_entries(fixtures_dir: Path) -> list[EntryParsed]:
    """Parse captured Twitter RSS entries in chronological order."""
    xml = (fixtures_dir / "feeds" / "twitter_rss.xml").read_text(encoding="utf-8")
    entries, error = RSSParser().parse(xml)
    assert error is None
    return sorted(entries, key=lambda entry: entry.published)


@pytest.fixture
def rounds(twitter_entries: list[EntryParsed]) -> list[list[EntryParsed]]:
    """Split parsed entries into three non-empty sync rounds."""
    chunk_size = len(twitter_entries) // 3
    return [
        twitter_entries[:chunk_size],
        twitter_entries[chunk_size : chunk_size * 2],
        twitter_entries[chunk_size * 2 :],
    ]


class TestFeedDedupSimulation:
    """Simulate three rounds of feed synchronization without persistence."""

    def test_round1_seed_and_new(self, rounds: list[list[EntryParsed]]) -> None:
        feed = Feed(
            link="https://rsshub.example/twitter/home",
            entry_hashes=[[entry.guid] for entry in rounds[0]],
        )

        later_entries = rounds[1] + rounds[2]
        new_guids = [
            entry.guid for entry in later_entries if not feed.has_entry(entry.guid)
        ]

        assert new_guids == [entry.guid for entry in later_entries]
        for guid in new_guids:
            feed.add_entry_hash(guid)

        assert all(feed.has_entry(guid) for guid in new_guids)

    def test_round2_modified_content(self, rounds: list[list[EntryParsed]]) -> None:
        seed_entries = rounds[0] + rounds[1]
        feed = Feed(
            link="https://rsshub.example/twitter/home",
            entry_hashes=[[entry.guid] for entry in seed_entries],
        )

        modified_guids = [
            f"{entry.guid}:modified-2026-05-15T12:00:00Z" for entry in rounds[1]
        ]

        assert all(not feed.has_entry(guid) for guid in modified_guids)
        for guid in modified_guids:
            feed.add_entry_hash(guid)

        assert all(feed.has_entry(guid) for guid in modified_guids)

    def test_round3_no_changes(self, rounds: list[list[EntryParsed]]) -> None:
        all_entries = rounds[0] + rounds[1] + rounds[2]
        feed = Feed(
            link="https://rsshub.example/twitter/home",
            entry_hashes=[[entry.guid] for entry in all_entries],
        )

        new_entries = [entry for entry in all_entries if not feed.has_entry(entry.guid)]

        assert new_entries == []

    def test_entry_hashes_storage_format(self, rounds: list[list[EntryParsed]]) -> None:
        feed = Feed(
            link="https://rsshub.example/twitter/home",
            entry_hashes=[[entry.guid] for entry in rounds[0]],
        )

        assert isinstance(feed.entry_hashes, list)
        assert feed.entry_hashes
        assert all(isinstance(group, list) for group in feed.entry_hashes)
        assert all(
            isinstance(entry_hash, str)
            for group in feed.entry_hashes
            for entry_hash in group
        )
