"""Canonical display options shared by persistence and settings boundaries."""

from __future__ import annotations

from typing import Any

from .constants import INHERIT_VALUE, SEND_MODES, STYLE_VALUES

DISPLAY_FIELDS = (
    "display_author",
    "display_via",
    "display_title",
    "display_entry_tags",
    "display_media",
)
FEED_DEFAULT_FIELDS = ("length_limit", *DISPLAY_FIELDS, "style", "merge_media")
FEED_PROFILE_FIELDS = tuple(f"feed_{key}" for key in FEED_DEFAULT_FIELDS)
NEW_PROFILE_FIELDS = ("merge_media", *FEED_PROFILE_FIELDS)
PROFILE_OPTION_FIELDS = (
    "send_mode",
    "length_limit",
    *DISPLAY_FIELDS,
    "style",
    *NEW_PROFILE_FIELDS,
)
TOGGLE_FIELDS = {
    "notify",
    *DISPLAY_FIELDS,
    "merge_media",
    *(f"feed_{key}" for key in (*DISPLAY_FIELDS, "merge_media")),
}


def validate_profile_value(key: str, value: Any, *, allow_inherit: bool = True) -> int:
    """Reject removed choices; a current zero always means disabled/custom."""
    if isinstance(value, bool):
        if key not in TOGGLE_FIELDS:
            raise ValueError(f"{key} 需要整数值")
        normalized = int(value)
    elif isinstance(value, int):
        normalized = value
    elif isinstance(value, str):
        try:
            normalized = int(value.strip())
        except ValueError as exc:
            raise ValueError(f"{key} 需要整数值") from exc
    else:
        raise ValueError(f"{key} 需要整数值")  # noqa: TRY004 - config boundaries use ValueError.
    if allow_inherit and normalized == INHERIT_VALUE:
        return normalized
    choices = None
    if key in TOGGLE_FIELDS:
        choices = {0, 1}
    elif key == "send_mode":
        choices = SEND_MODES
    elif key in {"style", "feed_style"}:
        choices = STYLE_VALUES
    elif key in {"length_limit", "feed_length_limit"} and not 0 <= normalized <= 10000:
        raise ValueError(f"{key} 必须为 0–10000，或 -100 继承")
    if choices is not None and normalized not in choices:
        allowed = "/".join(str(item) for item in sorted(choices))
        raise ValueError(
            f"{key} 只支持 {allowed}" + (" 或 -100 继承" if allow_inherit else "")
        )
    return normalized


def migrate_legacy_profile_value(key: str, value: int) -> int:
    """Convert v2 database/export values once, before normal validation."""
    if value == INHERIT_VALUE:
        return value
    if key == "display_via":
        return 0 if value == -2 else 1
    if key in DISPLAY_FIELDS:
        return 0 if value == -1 else 1
    if key == "send_mode" and value in {-1, 0}:
        return 1
    if key == "style" and value == 1:
        return 0
    return value
