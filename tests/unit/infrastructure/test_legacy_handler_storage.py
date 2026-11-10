"""Legacy handler values survive storage, but are never executable settings."""

from __future__ import annotations

import json

import pytest
from astrbot_plugin_rsshub_lite.src.domain.entities.handlers import (
    HandlerSpec,
    dump_handlers,
    handlers_json,
    normalize_handlers,
)
from astrbot_plugin_rsshub_lite.src.domain.entities.subscription import Subscription
from astrbot_plugin_rsshub_lite.src.domain.entities.user import User
from astrbot_plugin_rsshub_lite.src.infrastructure.persistence.database import (
    DatabaseManager,
)
from astrbot_plugin_rsshub_lite.src.infrastructure.persistence.models import (
    FeedORM,
    SubORM,
    UserORM,
)
from astrbot_plugin_rsshub_lite.src.infrastructure.persistence.subscription_repository_impl import (
    SubscriptionRepositoryImpl,
)
from astrbot_plugin_rsshub_lite.src.infrastructure.persistence.user_repository_impl import (
    UserRepositoryImpl,
)

LEGACY_HANDLERS = [
    {
        "id": "builtin.ai_transform.default",
        "type": "builtin",
        "name": "ai_transform",
        "status": 1,
        # Deliberately no prompt/scope: old data is preserved without AI validation.
        "config": {"custom": {"message": "旧配置", "enabled": False}, "limit": 0},
    },
    {
        "id": "builtin.ai_filter.default",
        "type": "builtin",
        "name": "ai_filter",
        "status": -100,
        "config": {},
    },
]


def test_legacy_specs_normalize_idempotently_without_ai_defaults():
    specs = normalize_handlers(json.dumps(LEGACY_HANDLERS))
    assert all(isinstance(spec, HandlerSpec) for spec in specs)
    assert dump_handlers(specs) == LEGACY_HANDLERS
    assert dump_handlers(normalize_handlers(specs)) == LEGACY_HANDLERS
    assert json.loads(handlers_json(specs)) == LEGACY_HANDLERS
    assert specs[0].config == LEGACY_HANDLERS[0]["config"]
    assert specs[1].config == {}


@pytest.mark.parametrize("entity_type", [User, Subscription])
@pytest.mark.parametrize("as_json", [True, False])
def test_legacy_entity_handler_round_trip(entity_type, as_json):
    fields = (
        {"id": "user-1"}
        if entity_type is User
        else {"id": 1, "user_id": "user-1", "feed_id": 1, "handlers_mode": "override"}
    )
    value = (
        json.dumps(LEGACY_HANDLERS) if as_json else normalize_handlers(LEGACY_HANDLERS)
    )
    entity = entity_type(**fields, handler_specs=value)
    assert entity.get_handlers() == LEGACY_HANDLERS
    restored = entity_type.model_validate(entity.model_dump(by_alias=True))
    assert restored.get_handlers() == LEGACY_HANDLERS


@pytest.mark.asyncio
async def test_sqlite_legacy_handlers_survive_read_and_unrelated_save(
    tmp_path, monkeypatch
):
    db = DatabaseManager()
    await db.init(str(tmp_path / "legacy-handlers.db"))
    for module in ("user_repository_impl", "subscription_repository_impl"):
        monkeypatch.setattr(
            f"astrbot_plugin_rsshub_lite.src.infrastructure.persistence.{module}.get_database",
            lambda: db,
        )
    try:
        async with db.get_session() as session:
            session.add(UserORM(id="user-1", handlers=json.dumps(LEGACY_HANDLERS)))
            session.add(FeedORM(id=1, title="Feed", link="https://example.com/feed"))
            session.add(
                SubORM(
                    id=1,
                    user_id="user-1",
                    feed_id=1,
                    handlers_mode="override",
                    handlers=json.dumps(LEGACY_HANDLERS),
                )
            )
            await session.commit()

        user_repo = UserRepositoryImpl()
        sub_repo = SubscriptionRepositoryImpl()
        user = await user_repo.get_by_id("user-1")
        sub = await sub_repo.get_by_id(1)
        assert user.get_handlers() == LEGACY_HANDLERS
        assert sub.get_handlers() == LEGACY_HANDLERS

        user.notify = 1
        await user_repo.save(user)
        await sub_repo.update_options(1, "user-1", title="Updated title")
        # Exercise the subscription's entity -> ORM -> SQLite serialization path
        # through a new row, since repository.save is the insert operation.
        copied = await sub_repo.save(sub.model_copy(update={"id": None}))
        assert copied.get_handlers() == LEGACY_HANDLERS
        assert copied.handlers_mode == "override"

        async with db.get_session() as session:
            stored_user = await session.get(UserORM, "user-1")
            stored_sub = await session.get(SubORM, 1)
            stored_copy = await session.get(SubORM, copied.id)
            assert stored_user.notify == 1
            assert stored_sub.title == "Updated title"
            for row in (stored_user, stored_sub, stored_copy):
                assert json.loads(row.handlers) == LEGACY_HANDLERS
    finally:
        await db.close()
