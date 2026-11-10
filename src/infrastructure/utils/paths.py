"""Runtime path helpers for plugin-owned files."""

from __future__ import annotations

import tempfile
from pathlib import Path

PLUGIN_NAME = "astrbot_plugin_rsshub"
PLUGIN_ROOT = Path(__file__).resolve().parents[3]


def get_plugin_data_dir(*parts: str) -> Path:
    """Return a safe persistent data directory for this plugin.

    AstrBot resolves its root from ``os.getcwd()`` when ``ASTRBOT_ROOT`` is not
    set. During local debugging from this plugin directory, that makes
    ``get_astrbot_plugin_data_path()`` point to ``<plugin>/data/plugin_data``.
    Detect that polluted path and fall back to the real AstrBot project root.
    """
    base_dir = _resolve_plugin_data_base()
    return base_dir.joinpath(*parts)


def get_plugin_cache_dir(*parts: str) -> Path:
    """Return plugin cache directory under the safe data directory."""
    return get_plugin_data_dir("cache", *parts)


def get_plugin_export_dir() -> Path:
    """Return plugin export directory under the safe data directory."""
    return get_plugin_data_dir("exports")


def _resolve_plugin_data_base() -> Path:
    explicit_dir = _resolve_explicit_astrbot_data_dir()
    explicit_dir_is_safe = explicit_dir is not None and not _is_under_plugin_root(
        explicit_dir
    )
    if explicit_dir_is_safe:
        return explicit_dir / PLUGIN_NAME

    astrbot_root = _find_astrbot_project_root(PLUGIN_ROOT)
    if astrbot_root is not None:
        return astrbot_root / "data" / "plugin_data" / PLUGIN_NAME

    return Path(tempfile.gettempdir()) / PLUGIN_NAME


def _resolve_explicit_astrbot_data_dir() -> Path | None:
    try:
        from astrbot.core.utils.astrbot_path import get_astrbot_plugin_data_path

        return Path(get_astrbot_plugin_data_path()).expanduser().resolve()
    except Exception:
        return None


def _find_astrbot_project_root(start: Path) -> Path | None:
    for candidate in (start, *start.parents):
        plugins_dir = candidate / "data" / "plugins"
        if not plugins_dir.exists():
            continue
        if _is_relative_to(PLUGIN_ROOT, plugins_dir):
            return candidate
    return None


def _is_under_plugin_root(path: Path) -> bool:
    return path == PLUGIN_ROOT or _is_relative_to(path, PLUGIN_ROOT)


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False
