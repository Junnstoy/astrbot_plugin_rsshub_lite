"""Versioned display switches and separate manual-feed display profiles."""

# ruff: noqa: N999 -- migration discovery requires V<number>_<name>.py.

from __future__ import annotations

from ....shared.profile_options import DISPLAY_FIELDS, NEW_PROFILE_FIELDS


async def upgrade(conn) -> None:
    """Add inheritable columns and convert legacy values exactly once."""
    for table in ("rsshub_user", "rsshub_sub"):
        result = await conn.exec_driver_sql(f"PRAGMA table_info({table})")
        columns = {str(row[1]) for row in result.fetchall()}
        if not columns:
            continue
        for key in NEW_PROFILE_FIELDS:
            if key not in columns:
                await conn.exec_driver_sql(
                    f"ALTER TABLE {table} ADD COLUMN {key} INTEGER NOT NULL DEFAULT -100"
                )
        for key in DISPLAY_FIELDS:
            if key not in columns:
                continue
            disabled = -2 if key == "display_via" else -1
            await conn.exec_driver_sql(
                f"UPDATE {table} SET {key} = CASE "
                f"WHEN {key} = -100 THEN -100 WHEN {key} = {disabled} THEN 0 ELSE 1 END"
            )
        if "send_mode" in columns:
            await conn.exec_driver_sql(
                f"UPDATE {table} SET send_mode = 1 WHERE send_mode IN (-1, 0)"
            )
        if "style" in columns:
            await conn.exec_driver_sql(f"UPDATE {table} SET style = 0 WHERE style = 1")
