"""主模块集成测试."""

from __future__ import annotations

import inspect
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_context():
    """模拟 AstrBot 上下文."""
    context = MagicMock()
    context.platform_manager = MagicMock()
    context.platform_manager.platform_insts = []
    return context


@pytest.fixture
def mock_config():
    """模拟 AstrBot 配置."""
    return {
        "rsshub": {
            "db": {"database": "test.db"},
            "basic": {"timeout": 30, "proxy": ""},
        }
    }


@pytest.fixture
def main_module(monkeypatch):
    """导入带最小 AstrBot 假对象的 main 模块."""

    class FakeStar:
        def __init__(self, context):
            self.context = context

    class FakePermissionType:
        ADMIN = "admin"

    class FakeFilter:
        PermissionType = FakePermissionType

        @staticmethod
        def command(name, *, alias=None, **kwargs):
            def decorate(fn):
                fn._test_command_registration = (name, set(alias or ()))
                return fn

            return decorate

        @staticmethod
        def command_group(*_args, **_kwargs):
            class _Group:
                @staticmethod
                def command(*_a, **_k):
                    return lambda fn: fn

            return lambda fn: _Group()

        @staticmethod
        def permission_type(*_args, **_kwargs):
            return lambda fn: fn

        @staticmethod
        def event_message_type(*_args, **_kwargs):
            return lambda fn: fn

        class EventMessageType:
            ALL = "all"

    api_mod = sys.modules["astrbot.api"]
    api_mod.AstrBotConfig = dict

    event_mod = sys.modules["astrbot.api.event"]
    event_mod.AstrMessageEvent = object
    event_mod.filter = FakeFilter()

    star_mod = sys.modules["astrbot.api.star"]
    star_mod.Context = object
    star_mod.Star = FakeStar

    monkeypatch.delitem(sys.modules, "astrbot_plugin_rsshub_lite.main", raising=False)

    import astrbot_plugin_rsshub_lite.main as main  # noqa: PLR0402 - reload this submodule

    return main


class TestRSSHubPluginIntegration:
    """插件入口集成测试."""

    def test_plugin_initialization(self, main_module, mock_context, mock_config):
        """测试插件对象初始化."""
        plugin = main_module.RSSHubPlugin(mock_context, mock_config)

        assert plugin._config == mock_config
        assert plugin._scheduler is None
        assert plugin._deps == {}
        assert not hasattr(main_module, "Main")


async def _invoke_command(plugin, method_name, command_name, argument_text):
    """Run actual host parsing, then the plugin entry and its real adapter."""
    from astrbot.core.star.filter.command import CommandFilter

    event = MagicMock()
    event.get_sender_id.return_value = "alice"
    event.get_platform_name.return_value = "aiocqhttp"
    event.unified_msg_origin = "bot:GroupMessage:123"
    event.is_at_or_wake_command = True
    event.get_message_str.return_value = f"{command_name} {argument_text}".strip()
    event.plain_result.side_effect = lambda text: text
    extras = {}
    event.set_extra.side_effect = extras.__setitem__
    method = getattr(type(plugin), method_name)
    parser = CommandFilter(command_name, handler_md=SimpleNamespace(handler=method))
    assert parser.filter(event, {})
    replies = [
        reply async for reply in method(plugin, event, **extras["parsed_params"])
    ]
    return event, replies


@pytest.mark.asyncio
async def test_real_host_parser_retains_page_and_page_size(main_module):
    plugin = main_module.RSSHubPlugin(MagicMock(), {})
    subs = [
        SimpleNamespace(
            id=index,
            state=1,
            target_session="bot:GroupMessage:123",
            feed_id=index,
            title="",
            feed_title=f"feed-{index}",
            feed_link="",
        )
        for index in range(1, 9)
    ]
    query = SimpleNamespace(
        execute=AsyncMock(return_value=SimpleNamespace(subscriptions=subs))
    )
    plugin._deps = {"get_subs_query": query}
    _, replies = await _invoke_command(plugin, "sub_list", "sub_list", "2 3")
    assert "页码: 2/3  每页: 3" in replies[0]
    assert "[4]" in replies[0] and "[6]" in replies[0]
    assert "[3]" not in replies[0] and "[7]" not in replies[0]
    assert "下一页: /sub_list 3 3" in replies[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("arguments", ["0 5", "1 0", "1 101", "2 3 4", "two 3"])
async def test_list_rejects_invalid_pagination_before_query(main_module, arguments):
    plugin = main_module.RSSHubPlugin(MagicMock(), {})
    query = SimpleNamespace(execute=AsyncMock())
    plugin._deps = {"get_subs_query": query}
    _, replies = await _invoke_command(plugin, "sub_list", "sub_list", arguments)
    assert "分页" in replies[0] or "页码" in replies[0]
    query.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_real_host_parser_retains_old_state_and_multi_id_push(main_module):
    from astrbot_plugin_rsshub_lite.src.application.dto.result_dto import CommandResult

    plugin = main_module.RSSHubPlugin(MagicMock(), {})
    activate = SimpleNamespace(
        execute=AsyncMock(return_value=CommandResult(success=True, message="on"))
    )
    deactivate = SimpleNamespace(
        execute=AsyncMock(return_value=CommandResult(success=True, message="off"))
    )
    plugin._deps = {"batch_activate_cmd": activate, "batch_deactivate_cmd": deactivate}
    await _invoke_command(plugin, "sub_state", "sub_state", "7 off")
    deactivate.execute.assert_awaited_once_with(
        sub_ids=[7],
        user_id="alice",
        current_session="bot:GroupMessage:123",
    )
    await _invoke_command(plugin, "push", "push", "1, 3, 4")
    activate.execute.assert_awaited_once_with(
        sub_ids=[1, 3, 4],
        user_id="alice",
        current_session="bot:GroupMessage:123",
    )


@pytest.mark.asyncio
async def test_real_host_parser_retains_feed_count(main_module):
    plugin = main_module.RSSHubPlugin(MagicMock(), {})
    command = SimpleNamespace(
        execute=AsyncMock(
            return_value=SimpleNamespace(message="sent", success=True, data={})
        )
    )
    plugin._deps = {"push_feed_cmd": command}
    await _invoke_command(plugin, "feed", "feed", "7 3")
    command.execute.assert_awaited_once_with(
        sub_id=7,
        count=3,
        user_id="alice",
        target_session="bot:GroupMessage:123",
        platform_name="aiocqhttp",
    )


@pytest.mark.asyncio
async def test_session_defaults_flow_from_chat_setting_to_new_subscriptions(
    main_module,
):
    plugin = main_module.RSSHubPlugin(MagicMock(), {})
    settings = {}

    async def read(key, default):
        return settings.get(key, default)

    async def write(key, value):
        settings[key] = value

    plugin.get_kv_data = read
    plugin.put_kv_data = write
    subscribe = SimpleNamespace(
        execute=AsyncMock(return_value=SimpleNamespace(success=True, message="ok"))
    )
    plugin._deps = {"subscribe_cmd": subscribe}
    await _invoke_command(
        plugin, "sub_set_session", "sub_session set", "title Daily News"
    )
    await _invoke_command(plugin, "sub_set_session", "sub_session set", "interval 30")
    await _invoke_command(
        plugin, "sub_feed", "sub", "/163/ds/account https://example.com/rss"
    )
    assert subscribe.execute.await_count == 2
    for call in subscribe.execute.await_args_list:
        assert call.kwargs["session_defaults"] == {
            "title": "Daily News",
            "interval": 30,
        }
        assert call.kwargs["target_session"] == "bot:GroupMessage:123"


@pytest.mark.asyncio
async def test_profile_command_preserves_all_fields_and_spaces(main_module):
    plugin = main_module.RSSHubPlugin(MagicMock(), {})
    update = SimpleNamespace(
        execute=AsyncMock(return_value=SimpleNamespace(message="ok"))
    )
    plugin._deps = {"update_sub_cmd": update}
    await _invoke_command(
        plugin, "sub_profile_set", "sub_profile set", "sub 7 title Daily News"
    )
    update.execute.assert_awaited_once_with(
        sub_id=7, user_id="alice", title="Daily News"
    )


class TestCommandIntegration:
    """命令集成测试."""

    def test_command_registration(self, main_module):
        """测试当前插件入口暴露的命令方法."""
        methods = [
            name
            for name, _ in inspect.getmembers(
                main_module.RSSHubPlugin, predicate=inspect.isfunction
            )
        ]

        command_methods = [
            "push",
            "unpush",
            "feed",
            "sub_feed",
            "unsub_feed",
            "sub_list",
            "stop_rss_job",
            "sub_status",
            "sub_state",
            "sub_profile_set",
            "sub_profile_get",
            "sub_set_session",
            "sub_get_session",
            "unsub_all",
            "export_subs",
            "import_subs",
            "import_upload_listener",
            "rsshelp",
            "test_sub",
        ]

        for cmd in command_methods:
            assert cmd in methods, f"Command method {cmd} not found"

    def test_legacy_batch_commands_and_aliases_are_not_registered(self, main_module):
        commands = set()
        for _, method in inspect.getmembers(main_module.RSSHubPlugin):
            registration = getattr(method, "_test_command_registration", None)
            if registration is not None:
                command, aliases = registration
                commands.add(command)
                commands.update(aliases)
        assert {"push", "unpush", "sub_state"} <= commands
        assert commands.isdisjoint(
            {
                "activate_subs",
                "enable_subs",
                "启用全部订阅",
                "deactivate_subs",
                "disable_subs",
                "禁用全部订阅",
            }
        )
        assert not hasattr(main_module.RSSHubPlugin, "batch_activate")
        assert not hasattr(main_module.RSSHubPlugin, "batch_deactivate")

    def test_import_upload_listener_finds_file_like_component(self, main_module):
        plugin = main_module.RSSHubPlugin(MagicMock(), {})

        class UploadedFile:
            async def get_file(self):
                return "/tmp/subs.toml"

        event = MagicMock()
        event.message_obj = MagicMock(message=[UploadedFile()])

        assert plugin._find_uploaded_file(event) is event.message_obj.message[0]

    def test_pending_import_prune_removes_expired_entries(
        self, main_module, monkeypatch
    ):
        plugin = main_module.RSSHubPlugin(MagicMock(), {})
        plugin._pending_imports = {
            "expired": 100.0,
            "active": 300.0,
        }

        monkeypatch.setattr(main_module.time, "time", lambda: 200.0)

        plugin._prune_pending_imports()

        assert plugin._pending_imports == {"active": 300.0}


class TestSchedulerIntegration:
    """调度器集成测试."""

    @pytest.mark.asyncio
    async def test_scheduler_start_stop(self):
        """调度器测试需要完整插件环境."""


class TestConfigurationIntegration:
    """配置集成测试."""

    def test_config_loading(self, mock_config):
        """测试配置加载."""
        from astrbot_plugin_rsshub_lite.src.infrastructure.config import (
            RsshubPluginConfig,
        )

        config = RsshubPluginConfig.from_astrbot_config(mock_config)

        assert config is not None
        assert config.http_config.timeout == 30


class TestPluginLifecycle:
    """裁剪版生命周期不接入模型或工具管理器。"""

    @pytest.mark.asyncio
    async def test_terminate_stops_runtime_without_llm_tools(
        self, main_module, mock_context
    ):
        plugin = main_module.RSSHubPlugin(mock_context, {})
        plugin._runtime = MagicMock()
        plugin._runtime.stop = AsyncMock()

        await plugin.terminate()

        mock_context.unregister_llm_tool.assert_not_called()
        plugin._runtime.stop.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_terminate_without_runtime_stops_queue(
        self, main_module, mock_context
    ):
        plugin = main_module.RSSHubPlugin(mock_context, {})
        plugin._runtime = None
        plugin._push_job_queue.stop_all = AsyncMock()

        await plugin.terminate()

        mock_context.get_llm_tool_manager.assert_not_called()
        plugin._push_job_queue.stop_all.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_initialize_does_not_register_tools_or_knowledge_services(
        self, main_module, mock_context, monkeypatch
    ):
        runtime = MagicMock()
        runtime.deps = {
            "polling_service": object(),
            "notification_dispatcher": object(),
        }
        monkeypatch.setattr(
            main_module, "create_plugin_runtime", AsyncMock(return_value=runtime)
        )
        plugin = main_module.RSSHubPlugin(mock_context, {})
        await plugin.initialize()
        assert plugin._runtime is runtime
        assert plugin._deps is runtime.deps
        mock_context.add_llm_tools.assert_not_called()
        mock_context.get_llm_tool_manager.assert_not_called()
        assert not hasattr(plugin, "rsshub_kb_init")
