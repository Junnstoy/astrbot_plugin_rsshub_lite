"""Subscription TOML import/export behavior tests."""

from __future__ import annotations

import pytest
from astrbot_plugin_rsshub_lite.src.application.commands.export_subscriptions_cmd import (
    ExportSubscriptionsCommand,
)
from astrbot_plugin_rsshub_lite.src.application.commands.import_subscriptions_cmd import (
    ImportSubscriptionsCommand,
)
from astrbot_plugin_rsshub_lite.src.application.dto.subscription_export_record import (
    SubscriptionExportRecord,
    build_subscription_export_record,
)
from astrbot_plugin_rsshub_lite.src.application.services.subscription_serializer import (
    parse_subscriptions_toml,
    serialize_subscriptions_to_toml,
)
from astrbot_plugin_rsshub_lite.src.domain.entities.feed import Feed
from astrbot_plugin_rsshub_lite.src.domain.entities.subscription import Subscription
from astrbot_plugin_rsshub_lite.src.shared.profile_options import NEW_PROFILE_FIELDS


def make_export_record(
    *,
    feed_id: int = 1,
    link: str = "https://example.com/feed.xml",
    feed_title: str = "Example Feed",
    **fields: object,
) -> SubscriptionExportRecord:
    """Create an export read model from a Subscription and Feed metadata."""
    data = {
        "user_id": "user-001",
        "feed_id": feed_id,
        **fields,
    }
    subscription = Subscription(**data)
    return build_subscription_export_record(
        subscription,
        link=link,
        feed_title=feed_title,
    )


class TestTOMLRoundtrip:
    """Verify export and parse are stable for subscription settings."""

    def test_roundtrip_single_subscription(self) -> None:
        record = make_export_record(
            title="Timeline",
            tags="twitter,art",
            notify=1,
            send_mode=1,
        )

        content = serialize_subscriptions_to_toml(
            user_id="user-001",
            records=[record],
        )
        payload = parse_subscriptions_toml(content)

        assert payload.errors == []
        assert len(payload.records) == 1
        record = payload.records[0]
        assert record.link == "https://example.com/feed.xml"
        assert record.feed_title == "Example Feed"
        assert record.options["title"] == "Timeline"
        assert record.options["tags"] == "twitter,art"
        assert record.options["notify"] == 1
        assert record.options["send_mode"] == 1

    def test_roundtrip_multiple_subscriptions(self) -> None:
        subscriptions = [
            make_export_record(
                feed_id=1,
                link="https://example.com/feed-1.xml",
                feed_title="Feed 1",
            ),
            make_export_record(
                feed_id=2,
                link="https://example.com/feed-2.xml",
                feed_title="Feed 2",
                title="Second",
            ),
            make_export_record(
                feed_id=3,
                link="https://example.com/feed-3.xml",
                feed_title="Feed 3",
                tags="third",
            ),
        ]

        content = serialize_subscriptions_to_toml(
            user_id="user-001",
            records=subscriptions,
        )
        payload = parse_subscriptions_toml(content)

        assert payload.errors == []
        assert [record.link for record in payload.records] == [
            "https://example.com/feed-1.xml",
            "https://example.com/feed-2.xml",
            "https://example.com/feed-3.xml",
        ]
        assert [record.feed_title for record in payload.records] == [
            "Feed 1",
            "Feed 2",
            "Feed 3",
        ]

    def test_roundtrip_preserves_options(self) -> None:
        record = make_export_record(
            title="Configured",
            tags="alerts,news",
            platform_name="telegram",
            handlers_mode="override",
            handlers=[
                {
                    "id": "builtin.ai_transform.default",
                    "type": "builtin",
                    "name": "ai_transform",
                    "status": 1,
                    "config": {"prompt": "总结为三条要点"},
                }
            ],
            interval=15,
            notify=1,
            send_mode=1,
            length_limit=500,
            display_author=1,
            display_via=0,
            display_title=1,
            display_entry_tags=1,
            style=2,
            display_media=0,
        )

        content = serialize_subscriptions_to_toml(
            user_id="user-001",
            records=[record],
        )
        payload = parse_subscriptions_toml(content)

        assert payload.errors == []
        assert "handlers" not in content
        options = payload.records[0].options
        assert options == {
            **{key: -100 for key in NEW_PROFILE_FIELDS},
            "display_author": 1,
            "display_entry_tags": 1,
            "display_media": 0,
            "display_title": 1,
            "display_via": 0,
            "interval": 15,
            "length_limit": 500,
            "notify": 1,
            "platform_name": "telegram",
            "send_mode": 1,
            "style": 2,
            "tags": "alerts,news",
            "title": "Configured",
        }

    def test_parse_legacy_send_mode_telegraph_is_migrated_to_direct(self) -> None:
        payload = parse_subscriptions_toml(
            """
            [[subscriptions]]
            link = "https://example.com/feed.xml"
            send_mode = 1
            """
        )

        assert payload.errors == []
        assert payload.records[0].options["send_mode"] == 1

    def test_parse_legacy_send_mode_direct_message_is_migrated_to_direct_send(
        self,
    ) -> None:
        payload = parse_subscriptions_toml(
            """
            [[subscriptions]]
            link = "https://example.com/feed.xml"
            send_mode = 2
            """
        )

        assert payload.errors == []
        assert payload.records[0].options["send_mode"] == 1

    def test_parse_legacy_link_preview_is_ignored(self) -> None:
        payload = parse_subscriptions_toml(
            """
            version = 2

            [[subscriptions]]
            link = "https://example.com/feed.xml"
            link_preview = 1
            send_mode = 1
            """
        )

        assert payload.errors == []
        assert payload.records[0].options == {"send_mode": 1}


class TestTOMLParsing:
    """Verify parser validation and best-effort import behavior."""

    @pytest.mark.parametrize(
        "key,value",
        [
            ("send_mode", -1),
            ("send_mode", 0),
            ("style", 1),
            ("display_author", -1),
            ("display_via", -2),
            ("display_media", -1),
            ("merge_media", 2),
            ("feed_style", 1),
            ("feed_display_title", -1),
        ],
    )
    def test_current_exports_reject_removed_choices(self, key, value):
        payload = parse_subscriptions_toml(
            'version = 3\n[[subscriptions]]\nlink = "https://example.com/rss"\n'
            f"{key} = {value}\n"
        )
        assert payload.errors
        assert payload.records == []

    def test_legacy_numeric_display_values_convert_once(self):
        fields = "display_author = -1\ndisplay_via = -1\ndisplay_title = 0\ndisplay_media = 0\ndisplay_entry_tags = -1\nsend_mode = 0\nstyle = 1\n"
        payload = parse_subscriptions_toml(
            'version = 2\n[[subscriptions]]\nlink = "https://example.com/rss"\n'
            + fields
        )
        assert not payload.errors
        assert payload.records[0].options == {
            "display_author": 0,
            "display_via": 1,
            "display_title": 1,
            "display_media": 1,
            "display_entry_tags": 0,
            "send_mode": 1,
            "style": 0,
        }
        current = parse_subscriptions_toml(
            'version = 3\n[[subscriptions]]\nlink = "https://example.com/rss"\n'
            "display_author = 0\ndisplay_via = 0\nstyle = 0\nsend_mode = 2\n"
        )
        assert not current.errors
        assert current.records[0].options == {
            "display_author": 0,
            "display_via": 0,
            "style": 0,
            "send_mode": 2,
        }

    @pytest.mark.parametrize(
        "handlers",
        [
            '\'[{"name":"ai_transform","status":1}]\'',
            '[{name="ai_transform", status=1}]',
            "42",
        ],
    )
    def test_legacy_handlers_are_ignored_without_losing_basic_options(self, handlers):
        payload = parse_subscriptions_toml(
            'version = 2\n[[subscriptions]]\nlink = "https://example.com/feed.xml"\n'
            f'handlers = {handlers}\nhandlers_mode = "override"\n'
            'title = "News"\ninterval = 15\nsend_mode = 1\n'
        )
        assert payload.errors == []
        assert payload.records[0].options == {
            "title": "News",
            "interval": 15,
            "send_mode": 1,
        }
        assert len(payload.warnings) == 2
        assert all("ignored" in warning for warning in payload.warnings)

    def test_parse_empty_string(self) -> None:
        payload = parse_subscriptions_toml("")

        assert payload.records == []
        assert payload.errors

    def test_parse_invalid_toml(self) -> None:
        payload = parse_subscriptions_toml("[[subscriptions]")

        assert payload.records == []
        assert payload.errors

    def test_parse_missing_link(self) -> None:
        payload = parse_subscriptions_toml(
            """
            [[subscriptions]]
            title = "No link"
            """
        )

        assert payload.records == []
        assert payload.errors

    def test_parse_minimal_valid(self) -> None:
        payload = parse_subscriptions_toml(
            """
            [[subscriptions]]
            link = "https://example.com/feed.xml"
            """
        )

        assert payload.errors == []
        assert len(payload.records) == 1
        assert payload.records[0].link == "https://example.com/feed.xml"
        assert payload.records[0].feed_title is None
        assert payload.records[0].options == {}

    def test_roundtrip_omits_default_inherit_handlers_mode(self) -> None:
        record = make_export_record(
            title="Configured",
            handlers_mode="inherit",
        )

        content = serialize_subscriptions_to_toml(
            user_id="user-001",
            records=[record],
        )
        payload = parse_subscriptions_toml(content)

        assert payload.errors == []
        assert "handlers_mode" not in payload.records[0].options

    def test_parse_warns_on_version_mismatch(self) -> None:
        payload = parse_subscriptions_toml(
            """
            format = "another-format"
            version = 999

            [[subscriptions]]
            link = "https://example.com/feed.xml"
            """
        )

        assert payload.errors == []
        assert len(payload.records) == 1
        assert len(payload.warnings) == 2


class TestExportCommand:
    """Verify the export command uses Feed data without mutating subscriptions."""

    @pytest.mark.asyncio
    async def test_export_hydrates_feed_for_subscription(self) -> None:
        subscription = Subscription(user_id="user-001", feed_id=1, title="Hydrated")
        feed = Feed(id=1, link="https://example.com/feed.xml", title="Hydrated Feed")

        class SubscriptionRepo:
            async def get_by_user(self, user_id: str) -> list[Subscription]:
                assert user_id == "user-001"
                return [subscription]

        class FeedRepo:
            calls: list[list[int]]

            def __init__(self) -> None:
                self.calls = []

            async def get_by_ids(self, feed_ids: list[int]) -> list[Feed]:
                self.calls.append(feed_ids)
                return [feed]

        feed_repo = FeedRepo()
        command = ExportSubscriptionsCommand(
            subscription_repo=SubscriptionRepo(),
            feed_repo=feed_repo,
        )

        result = await command.execute("user-001")
        payload = parse_subscriptions_toml(result.data.content)

        assert result.success is True
        assert payload.errors == []
        assert len(payload.records) == 1
        assert payload.records[0].link == "https://example.com/feed.xml"
        assert payload.records[0].feed_title == "Hydrated Feed"
        assert payload.records[0].options["title"] == "Hydrated"
        assert "feed" not in subscription.model_dump()
        assert not hasattr(subscription, "feed")
        assert feed_repo.calls == [[1]]

    @pytest.mark.asyncio
    async def test_export_uses_bulk_feed_lookup_for_multiple_subscriptions(
        self,
    ) -> None:
        subscriptions = [
            Subscription(user_id="user-001", feed_id=1, title="First"),
            Subscription(user_id="user-001", feed_id=2, title="Second"),
            Subscription(user_id="user-001", feed_id=1, title="Duplicate feed"),
        ]
        feeds = {
            1: Feed(id=1, link="https://example.com/feed-1.xml", title="Feed 1"),
            2: Feed(id=2, link="https://example.com/feed-2.xml", title="Feed 2"),
        }

        class SubscriptionRepo:
            async def get_by_user(self, user_id: str) -> list[Subscription]:
                assert user_id == "user-001"
                return subscriptions

        class FeedRepo:
            calls: list[list[int]]

            def __init__(self) -> None:
                self.calls = []

            async def get_by_ids(self, feed_ids: list[int]) -> list[Feed]:
                self.calls.append(feed_ids)
                return [feeds[feed_id] for feed_id in feed_ids]

            async def get_by_id(self, feed_id: int) -> Feed | None:
                raise AssertionError("export should use bulk feed lookup")

        feed_repo = FeedRepo()
        command = ExportSubscriptionsCommand(
            subscription_repo=SubscriptionRepo(),
            feed_repo=feed_repo,
        )

        result = await command.execute("user-001")
        payload = parse_subscriptions_toml(result.data.content)

        assert result.success is True
        assert payload.errors == []
        assert [record.link for record in payload.records] == [
            "https://example.com/feed-1.xml",
            "https://example.com/feed-2.xml",
            "https://example.com/feed-1.xml",
        ]
        assert feed_repo.calls == [[1, 2]]

    @pytest.mark.asyncio
    async def test_export_without_feed_repo_reports_explicit_error(self) -> None:
        class SubscriptionRepo:
            async def get_by_user(self, user_id: str) -> list[Subscription]:
                assert user_id == "user-001"
                return [Subscription(user_id="user-001", feed_id=1)]

        command = ExportSubscriptionsCommand(
            subscription_repo=SubscriptionRepo(),
            feed_repo=None,
        )

        result = await command.execute("user-001")

        assert result.success is False
        assert "feed repository" in result.message


class TestImportCommand:
    @pytest.mark.asyncio
    async def test_import_ensures_user_before_saving_subscription(self) -> None:
        class SubscriptionRepo:
            async def get_by_user_feed_session(
                self, user_id: str, feed_id: int, target_session: str | None
            ) -> Subscription | None:
                assert user_id == "user-001"
                assert feed_id == 1
                assert target_session is None
                return None

            async def save(self, subscription: Subscription) -> Subscription:
                subscription.id = 7
                return subscription

        class FeedRepo:
            async def get_by_link(self, link: str) -> Feed | None:
                assert link == "https://example.com/feed.xml"
                return Feed(id=1, link=link, title="Example Feed")

        class UserRepo:
            def __init__(self) -> None:
                self.calls: list[str] = []

            async def get_or_create(self, user_id: str):
                self.calls.append(user_id)
                return None

        user_repo = UserRepo()
        command = ImportSubscriptionsCommand(
            subscription_repo=SubscriptionRepo(),
            feed_repo=FeedRepo(),
            user_repo=user_repo,
        )

        result = await command.execute(
            "[[subscriptions]]\nlink='https://example.com/feed.xml'\n",
            user_id=" user-001 ",
        )

        assert result.success is True
        assert user_repo.calls == ["user-001"]


def test_subscription_model_dump_does_not_include_feed_relation() -> None:
    subscription = Subscription(user_id="user-001", feed_id=1)

    assert "feed" not in subscription.model_dump()
    assert not hasattr(subscription, "feed")
