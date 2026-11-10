"""Real SQLite migration, persistence and import/export of display profiles."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from astrbot_plugin_rsshub_lite.src.application.commands.export_subscriptions_cmd import (
    ExportSubscriptionsCommand,
)
from astrbot_plugin_rsshub_lite.src.application.commands.import_subscriptions_cmd import (
    ImportSubscriptionsCommand,
)
from astrbot_plugin_rsshub_lite.src.application.commands.set_user_settings_cmd import (
    SetUserSettingsCommand,
)
from astrbot_plugin_rsshub_lite.src.application.commands.update_subscription_cmd import (
    UpdateSubscriptionCommand,
)
from astrbot_plugin_rsshub_lite.src.application.queries.get_subscriptions_query import (
    GetSubscriptionsQuery,
)
from astrbot_plugin_rsshub_lite.src.application.services.subscription_serializer import (
    parse_subscriptions_toml,
)
from astrbot_plugin_rsshub_lite.src.domain.entities.subscription import Subscription
from astrbot_plugin_rsshub_lite.src.infrastructure.config import (
    RsshubPluginConfig,
    build_application_settings,
    heal_astrbot_plugin_config,
)
from astrbot_plugin_rsshub_lite.src.infrastructure.persistence.database import (
    DatabaseManager,
)
from astrbot_plugin_rsshub_lite.src.infrastructure.persistence.feed_repository_impl import (
    FeedRepositoryImpl,
)
from astrbot_plugin_rsshub_lite.src.infrastructure.persistence.migrations import (
    MigrationRunner,
)
from astrbot_plugin_rsshub_lite.src.infrastructure.persistence.subscription_repository_impl import (
    SubscriptionRepositoryImpl,
)
from astrbot_plugin_rsshub_lite.src.infrastructure.persistence.user_repository_impl import (
    UserRepositoryImpl,
)
from astrbot_plugin_rsshub_lite.src.shared.profile_options import (
    DISPLAY_FIELDS,
    NEW_PROFILE_FIELDS,
)
from sqlalchemy.ext.asyncio import create_async_engine


def _schema():
    return json.loads(
        (Path(__file__).resolve().parents[2] / "_conf_schema.json").read_text(
            encoding="utf-8"
        )
    )


@pytest.mark.parametrize(
    "raw",
    [
        {
            "display_author": "禁用",
            "display_via": "仅链接",
            "display_title": "自动",
            "display_media": False,
            "display_entry_tags": True,
            "send_mode": "自动",
            "style": "RSSRT",
        },
        {
            "display_author": -1,
            "display_via": -1,
            "display_title": 0,
            "display_media": -1,
            "display_entry_tags": 0,
            "send_mode": 0,
            "style": 1,
        },
    ],
)
def test_legacy_config_migrates_before_heal_and_keeps_current_zero(raw):
    healed, _ = heal_astrbot_plugin_config({"global_config": raw}, _schema())
    config = RsshubPluginConfig.from_astrbot_config(healed)
    assert config.config_version == 3
    assert config.global_config.display_author is False
    assert config.global_config.display_via is True
    assert config.global_config.display_title is True
    assert config.global_config.display_media is False
    assert config.global_config.display_entry_tags is True
    assert config.global_config.send_mode == 1
    assert config.global_config.style == 0
    # Explicit /feed defaults are independent of the automatic profile.
    assert config.feed_defaults.display_author is True
    assert config.feed_defaults.display_media is True
    assert not hasattr(config.feed_defaults, "send_mode")
    healed["global_config"]["display_title"] = False
    healed["global_config"]["send_mode"] = 2
    second, changes = heal_astrbot_plugin_config(healed, _schema())
    assert second == healed
    assert changes == []
    settings = build_application_settings(
        RsshubPluginConfig.from_astrbot_config(second)
    )
    assert settings.subscription_defaults.display_title is False
    assert settings.subscription_defaults.send_mode == 2
    assert settings.feed_defaults.display_title is True
    assert settings.feed_defaults.merge_media is True


@pytest.mark.asyncio
async def test_v3_converts_old_database_once_without_touching_handlers(tmp_path):
    path = str(tmp_path / "legacy.db")
    engine = create_async_engine(f"sqlite+aiosqlite:///{path}")
    legacy_handlers = '[{"name":"legacy_ai","opaque":{"keep":true}}]'
    old_values = [
        (-100, -100, -100, -100),
        (-1, -2, -1, 1),
        (0, -1, 0, 0),
        (1, 0, 1, 2),
        (0, 1, 1, 1),
    ]
    async with engine.begin() as conn:
        assert await MigrationRunner().run_to(conn, 2) == [1, 2]
        await conn.exec_driver_sql(
            "INSERT INTO rsshub_feed (id,link,title) VALUES (1,'https://example.com/rss','Feed')"
        )
        for index, (toggle, via, send, style) in enumerate(old_values, start=1):
            await conn.exec_driver_sql(
                "INSERT INTO rsshub_user (id) VALUES (?)", (f"u{index}",)
            )
            await conn.exec_driver_sql(
                "INSERT INTO rsshub_sub (id,user_id,feed_id) VALUES (?,?,1)",
                (index, f"u{index}"),
            )
            for table in ("rsshub_user", "rsshub_sub"):
                assignments = ", ".join(f"{key}=?" for key in DISPLAY_FIELDS)
                values = tuple(
                    via if key == "display_via" else toggle for key in DISPLAY_FIELDS
                )
                await conn.exec_driver_sql(
                    f"UPDATE {table} SET {assignments},send_mode=?,style=?,handlers=? WHERE id=?",
                    (
                        *values,
                        send,
                        style,
                        legacy_handlers,
                        f"u{index}" if table == "rsshub_user" else index,
                    ),
                )
    await engine.dispose()
    db = DatabaseManager()
    try:
        await db.init(path)
        async with db.engine.begin() as conn:
            for table in ("rsshub_user", "rsshub_sub"):
                rows = (
                    await conn.exec_driver_sql(
                        f"SELECT display_author,display_via,send_mode,style,handlers,{','.join(NEW_PROFILE_FIELDS)} FROM {table} ORDER BY id"
                    )
                ).fetchall()
                assert [tuple(row[:4]) for row in rows] == [
                    (-100, -100, -100, -100),
                    (0, 0, 1, 0),
                    (1, 1, 1, 0),
                    (1, 1, 1, 2),
                    (1, 1, 1, 0),
                ]
                assert all(row[4] == legacy_handlers for row in rows)
                assert all(tuple(row[5:]) == (-100,) * 9 for row in rows)
                await conn.exec_driver_sql(
                    f"UPDATE {table} SET display_author=0,display_via=0,send_mode=2,style=2"
                )
        await db.close()
        await db.init(path)
        async with db.engine.begin() as conn:
            for table in ("rsshub_user", "rsshub_sub"):
                rows = (
                    await conn.exec_driver_sql(
                        f"SELECT display_author,display_via,send_mode,style FROM {table}"
                    )
                ).fetchall()
                assert all(tuple(row) == (0, 0, 2, 2) for row in rows)
            assert (
                await conn.exec_driver_sql(
                    "SELECT count(*) FROM rsshub_migration_record WHERE version='3'"
                )
            ).scalar() == 1
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_display_profiles_save_reopen_export_import_and_dto(
    tmp_path, monkeypatch
):
    db = DatabaseManager()
    path = str(tmp_path / "profiles.db")
    await db.init(path)
    for module in (
        "user_repository_impl",
        "subscription_repository_impl",
        "feed_repository_impl",
    ):
        monkeypatch.setattr(
            f"astrbot_plugin_rsshub_lite.src.infrastructure.persistence.{module}.get_database",
            lambda: db,
        )
    monkeypatch.setattr(
        "astrbot_plugin_rsshub_lite.src.infrastructure.persistence.database.get_database",
        lambda: db,
    )
    users, subscriptions, feeds = (
        UserRepositoryImpl(),
        SubscriptionRepositoryImpl(),
        FeedRepositoryImpl(),
    )
    values = dict(zip(NEW_PROFILE_FIELDS, (0, 42, 0, 1, 0, 1, 0, 2, 1), strict=True))
    values.update(
        send_mode=2,
        style=0,
        display_author=0,
        display_via=1,
        display_title=1,
        display_entry_tags=0,
        display_media=1,
    )
    try:
        await users.get_or_create("u1")
        feed = await feeds.get_or_create("https://example.com/rss", "Feed")
        sub = await subscriptions.save(
            Subscription(user_id="u1", feed_id=feed.id, target_session="session-a")
        )
        legacy_handlers = '[{"opaque":"keep original AI data"}]'
        async with db.engine.begin() as conn:
            await conn.exec_driver_sql(
                "UPDATE rsshub_user SET handlers=?", (legacy_handlers,)
            )
            await conn.exec_driver_sql(
                "UPDATE rsshub_sub SET handlers=?,handlers_mode='override'",
                (legacy_handlers,),
            )
        assert (
            await SetUserSettingsCommand(users).execute("u1", settings=values)
        ).success
        updated = await UpdateSubscriptionCommand(subscriptions).execute(
            sub.id, "u1", **values
        )
        assert updated.success
        assert all(getattr(updated.data, key) == value for key, value in values.items())
        await db.close()
        await db.init(path)
        for entity in (
            await users.get_by_id("u1"),
            await subscriptions.get_by_id(sub.id),
        ):
            assert all(getattr(entity, key) == value for key, value in values.items())
        dto = (await GetSubscriptionsQuery(subscriptions).execute("u1")).subscriptions[
            0
        ]
        assert dto.feed_length_limit == 42
        assert dto.merge_media == 0
        export = await ExportSubscriptionsCommand(subscriptions, feeds).execute("u1")
        assert export.success
        assert "version = 3" in export.data.content
        record = parse_subscriptions_toml(export.data.content).records[0]
        assert all(record.options[key] == value for key, value in values.items())
        importer = ImportSubscriptionsCommand(subscriptions, feeds, users)
        imported = await importer.execute(
            export.data.content, "u1", target_session="session-b"
        )
        assert imported.success
        overwritten = await importer.execute(
            export.data.content, "u1", target_session="session-a", skip_existing=False
        )
        assert overwritten.success
        copied = await subscriptions.get_by_id(imported.data.items[0].subscription_id)
        assert all(getattr(copied, key) == value for key, value in values.items())
        async with db.engine.begin() as conn:
            assert (
                await conn.exec_driver_sql(
                    "SELECT handlers FROM rsshub_user WHERE id='u1'"
                )
            ).scalar() == legacy_handlers
            assert (
                await conn.exec_driver_sql(
                    "SELECT handlers FROM rsshub_sub WHERE id=?", (sub.id,)
                )
            ).scalar() == legacy_handlers
    finally:
        await db.close()
