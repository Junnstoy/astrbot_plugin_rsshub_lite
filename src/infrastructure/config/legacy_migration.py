"""Legacy AstrBot config shape migration helpers."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from ...shared.profile_options import DISPLAY_FIELDS, migrate_legacy_profile_value

CONFIG_VERSION = 3


def normalize_config_choice(key: str, value: Any) -> Any:
    """Accept historical strings while keeping current integer zero unambiguous."""
    if not isinstance(value, str):
        return value
    value = value.strip()
    lowered = value.lower()
    if key == "send_mode":
        return {
            "直接发送": 1,
            "direct": 1,
            "合并发送": 2,
            "合并": 2,
            "merged": 2,
            "merge": 2,
            "自动": 1,
            "auto": 1,
            "仅链接": 1,
            "link_only": 1,
        }.get(lowered, int(value) if value.lstrip("-").isdigit() else value)
    if key == "style":
        return {
            "自定义": 0,
            "custom": 0,
            "auto": 0,
            "自动": 0,
            "rssrt": 0,
            "rsstt": 0,
            "classic": 0,
            "flowerss": 0,
            "原始": 2,
            "原始顺序": 2,
            "original": 2,
        }.get(lowered, int(value) if value.lstrip("-").isdigit() else value)
    if key in {*DISPLAY_FIELDS, "merge_media", "notify"}:
        if lowered in {"禁用", "完全禁用", "false", "off", "否", "0"}:
            return False
        if lowered in {"启用", "强制", "自动", "仅链接", "true", "on", "是", "1"}:
            return True
    return value


def migrate_display_config(raw: dict[str, Any]) -> dict[str, Any]:
    """Migrate before schema projection; persist version to prevent a second pass."""
    result = deepcopy(raw)
    try:
        legacy = int(result.get("config_version", 0)) < CONFIG_VERSION
    except (TypeError, ValueError):
        legacy = True
    for section in ("global_config", "feed_defaults"):
        values = result.get(section)
        if not isinstance(values, dict):
            continue
        for key, raw_value in list(values.items()):
            value = raw_value
            # Only the old global profile had tri-state numeric switches.
            if legacy and section == "global_config" and not isinstance(value, bool):
                try:
                    numeric = int(value)
                except (TypeError, ValueError):
                    pass
                else:
                    value = migrate_legacy_profile_value(key, numeric)
            value = normalize_config_choice(key, value)
            if key in {*DISPLAY_FIELDS, "merge_media", "notify"} and value in (0, 1):
                value = bool(value)
            values[key] = value
    result["config_version"] = CONFIG_VERSION
    return result


def record_config_heal(changes: list[str], path: str, reason: str) -> None:
    changes.append(f"{path}: {reason}")
