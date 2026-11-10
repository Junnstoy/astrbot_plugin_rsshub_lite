"""Feed parsing port."""

from __future__ import annotations

from typing import Any, Protocol


class FeedParser(Protocol):
    """Parse RSS/Atom content into entry-like objects."""

    def parse(self, xml_content: str | bytes | None) -> tuple[list[Any], str | None]:
        """Parse XML content into entries and an optional error message."""
        ...
