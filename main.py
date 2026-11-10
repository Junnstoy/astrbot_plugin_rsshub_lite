"""RSSHub 插件入口"""

from __future__ import annotations

import time

from astrbot.api import AstrBotConfig
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import File, Image
from astrbot.api.star import Context, Star
from astrbot.core.star.filter.command import GreedyStr

from .bootstrap import PluginDeps, PluginRuntime, create_plugin_runtime
from .src.application.commands import HelpImageCommand
from .src.application.commands.import_subscriptions_cmd import (
    IMPORT_UPLOAD_WAIT_SECONDS,
)
from .src.application.services.session_push_queue import SessionPushQueue
from .src.infrastructure.config import ApplicationSettings
from .src.infrastructure.schedule import RSSScheduler
from .src.infrastructure.utils import get_logger
from .src.interfaces import WebApiHandler
from .src.interfaces import handlers as _h

logger = get_logger()


class RSSHubPlugin(Star):
    """RSS订阅推送插件"""

    def __init__(self, context: Context, config: AstrBotConfig | None = None):
        super().__init__(context)
        self._config = config
        self._scheduler: RSSScheduler | None = None
        self._db_initialized = False
        self._web_api: WebApiHandler | None = None
        self._deps: PluginDeps = {}
        self._app_settings: ApplicationSettings | None = None
        self._push_job_queue = SessionPushQueue()
        self._notification_dispatcher = None
        self._runtime: PluginRuntime | None = None
        self._pending_imports: dict[str, float] = {}

    async def initialize(self):
        try:
            runtime = await create_plugin_runtime(
                self.context,
                self._config,
                push_job_queue=self._push_job_queue,
            )
            self._runtime = runtime
            self._scheduler = runtime.scheduler
            self._db_initialized = runtime.db_initialized
            self._web_api = runtime.web_api
            self._deps = runtime.deps
            self._app_settings = runtime.app_settings
            self._push_job_queue = runtime.push_job_queue
            self._notification_dispatcher = runtime.notification_dispatcher
        except Exception as e:
            logger.exception("RSSHub 插件初始化失败: %s", e)

    async def terminate(self):
        logger.info("正在停止 RSSHub 插件...")
        if self._runtime:
            await self._runtime.stop()
        else:
            await self._push_job_queue.stop_all()
        logger.info("RSSHub 插件已停止")

    # ── 命令方法（装饰器留在插件入口类，委托到纯函数） ───────────────────────

    @filter.command("sub", alias={"订阅"})
    async def sub_feed(self, event: AstrMessageEvent, args: GreedyStr):
        """订阅 RSS 源。

        用法:
        - /sub <URL或RSSHub路由> [更多URL或路由 ...]
        示例:
        - /sub https://rsshub.app/bilibili/user/dynamic/123456
        """
        result = await _h.handle_sub(event, str(args), self._deps, ctx=self)
        if result.get("chain"):
            yield event.chain_result(result["chain"])
        if result.get("plain"):
            yield event.plain_result(result["plain"])

    @filter.command("unsub", alias={"取消订阅"})
    async def unsub_feed(self, event: AstrMessageEvent, args: GreedyStr):
        """取消订阅（支持 ID/URL 批量）。

        用法:
        - /unsub <ID/URL ...>
        示例:
        - /unsub 12 15
        - /unsub https://rss.atri.rodeo/twitter/home
        """
        result = await _h.handle_unsub(event, str(args), self._deps)
        if result.get("plain"):
            yield event.plain_result(result["plain"])

    @filter.command("sub_list", alias={"订阅列表"})
    async def sub_list(self, event: AstrMessageEvent, args: GreedyStr):
        """查看当前会话订阅列表（分页）。

        用法:
        - /sub_list [page] [page_size]
        示例:
        - /sub_list
        - /sub_list 2 10
        """
        result = await _h.handle_sub_list(event, str(args), self._deps)
        if result.get("plain"):
            yield event.plain_result(result["plain"])

    @filter.command(
        "push_cancel", alias={"sub_stop", "rss_stop", "停止RSS", "取消推送任务"}
    )
    async def stop_rss_job(self, event: AstrMessageEvent, args: GreedyStr):
        """取消本次发送任务，不改变订阅的自动推送开关。

        用法:
        - /push_cancel
        - /push_cancel <job_id|feed_id|all>
        示例:
        - /push_cancel rss-000123
        - /push_cancel all
        """
        result = _h.handle_rss_stop(event, self._push_job_queue, str(args))
        if result.get("plain"):
            yield event.plain_result(result["plain"])

    @filter.command("push_status", alias={"sub_status", "推送状态", "任务状态"})
    async def sub_status(self, event: AstrMessageEvent):
        """查看当前会话正在发送和排队的任务；订阅开关请看 /sub_list。"""
        result = _h.handle_sub_status(event, self._push_job_queue)
        if result.get("plain"):
            yield event.plain_result(result["plain"])

    @filter.command("sub_state", alias={"订阅状态"})
    async def sub_state(self, event: AstrMessageEvent, sub_id_str: GreedyStr):
        """旧启停命令兼容入口，推荐 /push 和 /unpush。

        用法:
        - /sub_state <sub_id> on|off
        示例:
        - /sub_state 12 off
        """
        result = await _h.handle_sub_state(
            event, str(sub_id_str), self._deps, queue=self._push_job_queue
        )
        if result.get("plain"):
            yield event.plain_result(result["plain"])

    @filter.command("push", alias={"sub_start", "启用推送"})
    async def push(self, event: AstrMessageEvent, args: GreedyStr):
        """持续启用自己在当前会话中的订阅，等待定时检查更新。

        用法:
        - /push <订阅ID[,ID...]|all>
        示例:
        - /push 1,3,4
        - /push all
        """
        result = await _h.handle_push(event, str(args), self._deps)
        if result.get("plain"):
            yield event.plain_result(result["plain"])

    @filter.command("unpush", alias={"停用推送", "停止推送"})
    async def unpush(self, event: AstrMessageEvent, args: GreedyStr):
        """持续停用自动推送并取消所选订阅的待发任务，保留订阅。

        用法:
        - /unpush <订阅ID[,ID...]|all>
        示例:
        - /unpush 1,3,4
        - /unpush all
        """
        result = await _h.handle_unpush(
            event, str(args), self._deps, queue=self._push_job_queue
        )
        if result.get("plain"):
            yield event.plain_result(result["plain"])

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("feed", alias={"立即推送"})
    async def feed(self, event: AstrMessageEvent, args: GreedyStr):
        """管理员立即发送该订阅最新 N 条，按从新到旧排列。

        用法:
        - /feed <订阅ID> <N>
        示例:
        - /feed 3 5
        """
        result = await _h.handle_feed(event, str(args), self._deps)
        if result.get("plain"):
            yield event.plain_result(result["plain"])

    @filter.command_group("sub_profile", alias={"订阅配置"})
    def sub_profile_group(self):
        """订阅/用户配置命令组。"""
        pass

    @sub_profile_group.command("set", alias={"设置"})
    async def sub_profile_set(self, event: AstrMessageEvent, args: GreedyStr):
        """修改单个订阅的设置，或自己的默认发送设置。

        用法:
        - /sub_profile set sub <sub_id> <option> <value>
        - /sub_profile set user <key> <value>
        示例:
        - /sub_profile set sub 12 style 2
        - /sub_profile set user display_media 0
        """
        result = await _h.handle_sub_profile_set(event, str(args), self._deps)
        if result.get("plain"):
            yield event.plain_result(result["plain"])

    @sub_profile_group.command("get", alias={"获取"})
    async def sub_profile_get(self, event: AstrMessageEvent, args: GreedyStr):
        """查询用户配置。

        用法:
        - /sub_profile get user [key]
        示例:
        - /sub_profile get user style
        """
        result = await _h.handle_sub_profile_get(event, str(args), self._deps)
        if result.get("plain"):
            yield event.plain_result(result["plain"])

    @filter.command_group("sub_session", alias={"会话设置"})
    def sub_session_group(self):
        """会话默认配置命令组。"""
        pass

    @sub_session_group.command("set", alias={"设置"})
    async def sub_set_session(
        self, event: AstrMessageEvent, key: str, value: GreedyStr
    ):
        """设置当前会话新建订阅的默认值，不修改已有订阅。

        用法:
        - /sub_session set <key> <value>
        示例:
        - /sub_session set interval 30
        """
        result = await _h.handle_sub_set_session(
            event, key, str(value), self._deps, self
        )
        if result.get("plain"):
            yield event.plain_result(result["plain"])

    @sub_session_group.command("get", alias={"获取"})
    async def sub_get_session(self, event: AstrMessageEvent, key: str = ""):
        """查看当前会话默认配置。

        用法:
        - /sub_session get [key]
        """
        result = await _h.handle_sub_get_session(event, key, self._deps, self)
        if result.get("plain"):
            yield event.plain_result(result["plain"])

    @filter.command("activate_subs", alias={"enable_subs", "启用全部订阅"})
    async def batch_activate(self, event: AstrMessageEvent, sub_ids: GreedyStr):
        """旧批量启用命令兼容入口，推荐 /push all。

        用法:
        - /activate_subs
        - /activate_subs 1,2,3
        """
        result = await _h.handle_batch_activate(
            event, str(sub_ids) or "all", self._deps
        )
        if result.get("plain"):
            yield event.plain_result(result["plain"])

    @filter.command("deactivate_subs", alias={"disable_subs", "禁用全部订阅"})
    async def batch_deactivate(self, event: AstrMessageEvent, sub_ids: GreedyStr):
        """旧批量停用命令兼容入口，推荐 /unpush all。

        用法:
        - /deactivate_subs
        - /deactivate_subs 1,2,3
        """
        result = await _h.handle_unpush(
            event, str(sub_ids) or "all", self._deps, queue=self._push_job_queue
        )
        if result.get("plain"):
            yield event.plain_result(result["plain"])

    @filter.command("unsub_all", alias={"取消全部订阅"})
    async def unsub_all(self, event: AstrMessageEvent, scope: str = ""):
        """取消全部订阅（当前会话或全局）。

        用法:
        - /unsub_all
        - /unsub_all global  (管理员)
        """
        result = await _h.handle_unsub_all(event, scope, self._deps)
        if result.get("chain"):
            yield event.chain_result(result["chain"])
        if result.get("plain"):
            yield event.plain_result(result["plain"])

    @filter.command("sub_export", alias={"导出订阅"})
    async def export_subs(self, event: AstrMessageEvent, scope: str = ""):
        """导出订阅为 TOML。

        用法:
        - /sub_export
        - /sub_export all  (管理员)
        """
        result = await _h.handle_export(event, str(scope), self._deps)
        if result.get("chain"):
            yield event.chain_result(result["chain"])
        if result.get("plain"):
            yield event.plain_result(result["plain"])

    @filter.command("sub_import", alias={"导入订阅"})
    async def import_subs(self, event: AstrMessageEvent, args: GreedyStr):
        """导入订阅。

        用法:
        - /sub_import <toml文件路径>
        - /sub_import <toml内容>
        - /sub_import  (进入上传等待)
        """
        result = await _h.handle_import(event, str(args), self._deps)
        if result.get("wait_import"):
            self._prune_pending_imports()
            self._pending_imports[self._import_wait_key(event)] = (
                time.time() + IMPORT_UPLOAD_WAIT_SECONDS
            )
        if result.get("plain"):
            yield event.plain_result(result["plain"])

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def import_upload_listener(self, event: AstrMessageEvent):
        """处理 /sub_import 空参数后的文件上传。"""
        self._prune_pending_imports()
        key = self._import_wait_key(event)
        expire_ts = self._pending_imports.get(key)
        if not expire_ts:
            return
        if expire_ts < time.time():
            self._pending_imports.pop(key, None)
            return

        file_component = self._find_uploaded_file(event)
        if file_component is None:
            return

        self._pending_imports.pop(key, None)
        try:
            file_path = await file_component.get_file()
            if not file_path:
                yield event.plain_result("导入失败: 未能获取上传文件")
                return
            result = await _h.handle_import(event, file_path, self._deps)
        except Exception as ex:
            logger.warning("订阅导入上传文件处理失败: %s", ex, exc_info=True)
            yield event.plain_result(f"导入失败: {ex}")
            return

        if result.get("plain"):
            yield event.plain_result(result["plain"])

    @staticmethod
    def _import_wait_key(event: AstrMessageEvent) -> str:
        return f"{event.unified_msg_origin}:{event.get_sender_id()}"

    def _prune_pending_imports(self) -> None:
        now = time.time()
        expired_keys = [
            key for key, expire_ts in self._pending_imports.items() if expire_ts < now
        ]
        for key in expired_keys:
            self._pending_imports.pop(key, None)

    @staticmethod
    def _find_uploaded_file(event: AstrMessageEvent) -> File | None:
        message = getattr(getattr(event, "message_obj", None), "message", None) or []
        for component in message:
            try:
                if isinstance(component, File):
                    return component
            except TypeError:
                pass
            component_type = component.__class__.__name__.lower()
            if component_type == "file" or hasattr(component, "get_file"):
                return component
        return None

    @filter.command("rsshelp", alias={"RSS帮助", "rss帮助"})
    async def rsshelp(self, event: AstrMessageEvent):
        """查看 RSSHub 命令帮助图片。"""
        help_image_path = HelpImageCommand().execute(self.context)
        if help_image_path.exists():
            yield event.chain_result([Image(file=str(help_image_path.resolve()))])
            return
        yield event.plain_result("没有找到帮助图片")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("sub_test", alias={"测试订阅"})
    async def test_sub(self, event: AstrMessageEvent, args: GreedyStr):
        """管理员测试推送。

        用法:
        - /sub_test <ID|URL>
        示例:
        - /sub_test 5
        """
        result = await _h.handle_test_sub(event, str(args), self._deps)
        if result.get("plain"):
            yield event.plain_result(result["plain"])
