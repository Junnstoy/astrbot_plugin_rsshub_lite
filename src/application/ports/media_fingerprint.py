"""Media fingerprinting port."""

from __future__ import annotations

from typing import Protocol


class MediaFingerprintService(Protocol):
    """Calculate stable fingerprints for media URLs."""

    async def fingerprint_urls(self, urls: list[str]) -> list[str]:
        """Return media fingerprints for the given URLs."""
        ...
