"""Feed fetching port."""

from __future__ import annotations

from typing import Protocol

from ..dto.web_feed_dto import WebFeed


class FeedFetcher(Protocol):
    """Fetch RSS/Atom content and return a WebFeed result."""

    async def fetch(
        self,
        url: str,
        *,
        timeout: float | None = None,
        headers: dict[str, str] | None = None,
        verbose: bool = True,
        proxy: str | None = None,
    ) -> WebFeed:
        """Fetch a feed URL."""
        ...

    async def close(self) -> None:
        """Release fetcher resources."""
        ...


class FeedFetcherFactory(Protocol):
    """Factory for short-lived feed fetchers."""

    def __call__(self, *, timeout: int = 30, proxy: str = "") -> FeedFetcher:
        """Create a feed fetcher."""
        ...
