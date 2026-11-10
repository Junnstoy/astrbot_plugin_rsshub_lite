"""Clock port."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol


class Clock(Protocol):
    """Current time provider."""

    def now(self) -> datetime:
        """Return the current time."""
        ...


class SystemClock:
    """System UTC clock adapter for application code."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)
