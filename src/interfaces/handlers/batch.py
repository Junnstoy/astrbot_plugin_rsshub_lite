"""批量操作命令处理器（纯函数）"""

from __future__ import annotations

import re
from pathlib import Path

from astrbot.api.event import AstrMessageEvent

from ...application.services.session_push_queue import SessionPushQueue
from ...infrastructure.utils import get_plugin_export_dir
from ...shared.constants import ONEBOT_PLATFORMS

_INLINE_EXPORT_LIMIT = 5000


def _parse_push_targets(args: str) -> list[int] | None:
    """Return None for explicit all; reject an invalid list as a whole."""
    value = (args or "").strip()
    if value.lower() == "all":
        return None
    if not re.fullmatch(r"[0-9]+(?:\s*,\s*[0-9]+)*", value):
        raise ValueError("请提供订阅 ID、逗号分隔的 ID 列表或 all")
    ids = list(dict.fromkeys(int(item.strip()) for item in value.split(",")))
    if not all(sub_id > 0 for sub_id in ids):
        raise ValueError("订阅 ID 必须是正整数")
    return ids


async def _handle_push_state(
    event: AstrMessageEvent,
    args: str,
    deps: dict,
    *,
    enabled: bool,
    queue: SessionPushQueue | None = None,
) -> dict:
    command = "push" if enabled else "unpush"
    usage = (
        f"用法: /{command} <订阅ID[,ID...]|all>\n示例: /{command} 1,2 或 /{command} all"
    )
    try:
        ids = _parse_push_targets(args)
    except ValueError as exc:
        return {"plain": f"{exc}\n{usage}"}

    user_id = str(event.get_sender_id() or "").strip()
    current_session = str(event.unified_msg_origin or "").strip()
    if not user_id or not current_session:
        return {"plain": "无法确认当前用户或会话，未修改订阅"}
    action = deps["batch_activate_cmd" if enabled else "batch_deactivate_cmd"]
    if ids is None:
        result = await action.execute_by_session(
            user_id=user_id, current_session=current_session
        )
    else:
        result = await action.execute(
            sub_ids=ids, user_id=user_id, current_session=current_session
        )

    message = result.message
    items = getattr(result.data, "items", ()) if result.data is not None else ()
    succeeded = {item.sub_id for item in items if item.success}
    failures = [f"[{item.sub_id}] {item.message}" for item in items if not item.success]
    if failures:
        message += "\n" + "\n".join(failures)
    if succeeded and enabled:
        message += "\n已开启所选订阅，后续按现有通知配置自动推送。"
    elif succeeded:
        # Never stop all session/feed jobs: another user may subscribe to the
        # same feed in this group. Cancel only successfully disabled sub IDs.
        stopped = 0
        if queue is not None:
            for job in queue.get_jobs(current_session):
                if job.sub_id in succeeded:
                    stopped += int(
                        queue.stop_by_job_id(current_session, job.job_id).stopped
                    )
        message += "\n已持续停止所选订阅的自动推送，订阅仍保留。"
        if stopped:
            message += f"已请求停止对应的 {stopped} 个运行中或排队任务。"
        message += "\n使用 /push <订阅ID[,ID...]|all> 可重新开启。"
    return {"plain": message}


async def handle_push(event: AstrMessageEvent, args: str, deps: dict) -> dict:
    """Persistently enable the sender's subscriptions in the current session."""
    return await _handle_push_state(event, args, deps, enabled=True)


async def handle_unpush(
    event: AstrMessageEvent,
    args: str,
    deps: dict,
    queue: SessionPushQueue | None = None,
) -> dict:
    """Persistently disable subscriptions and stop their known queued jobs."""
    return await _handle_push_state(event, args, deps, enabled=False, queue=queue)


async def handle_unsub_all(event: AstrMessageEvent, scope: str, deps: dict) -> dict:
    """取消全部订阅"""
    user_id = event.get_sender_id()
    is_admin = event.is_admin()
    current_session = event.unified_msg_origin

    scope_value = scope.strip().lower() if scope else ""
    is_global = scope_value == "global"

    if is_global and not is_admin:
        return {"plain": "清除所有会话订阅需要管理员权限"}

    subscriptions = await deps["subscription_repo"].get_by_user(user_id)
    if not subscriptions:
        return {"plain": "您当前没有可删除的订阅"}

    if is_global:
        to_delete = subscriptions
        scope_desc = "所有会话"
    else:
        to_delete = [
            sub
            for sub in subscriptions
            if (sub.target_session or current_session) == current_session
        ]
        scope_desc = "当前会话"

    if not to_delete:
        return {"plain": f"当前{scope_desc}没有订阅"}

    # 导出备份
    export_result = await deps["export_cmd"].execute(user_id=user_id, is_admin=is_admin)
    result: dict = {}

    if export_result.success and export_result.data and export_result.data.content:
        temp_dir = _get_export_dir()
        filename = export_result.data.filename
        file_path = temp_dir / filename
        file_path.write_text(export_result.data.content, encoding="utf-8")
        platform = _get_platform_name(event)
        if platform in ONEBOT_PLATFORMS and not _has_callback_file_service():
            result["plain"] = _build_inline_export_message(
                f"已取消{scope_desc}订阅前已生成备份，共导出 {export_result.data.count} 条",
                export_result.data.content,
                file_path,
            )
        else:
            from astrbot.api.message_components import File

            result["chain"] = [File(name=filename, file=str(file_path.resolve()))]

    # 删除订阅
    deleted_count = 0
    for sub in to_delete:
        await deps["subscription_repo"].delete(sub)
        deleted_count += 1

    result["plain"] = f"已取消{scope_desc}订阅，共删除 {deleted_count} 条"
    return result


async def handle_batch_unsub(event: AstrMessageEvent, sub_ids: str, deps: dict) -> dict:
    """批量取消订阅"""
    if not sub_ids:
        return {"plain": "请提供订阅 ID 列表\n用法: /batch_unsub 1,2,3"}
    ids = [int(x.strip()) for x in sub_ids.split(",") if x.strip().isdigit()]
    user_id = event.get_sender_id()
    result = await deps["batch_unsub_cmd"].execute(sub_ids=ids, user_id=user_id)
    return {"plain": result.message}


def _get_export_dir() -> Path:
    export_dir = get_plugin_export_dir()
    export_dir.mkdir(parents=True, exist_ok=True)
    return export_dir


def _get_platform_name(event: AstrMessageEvent) -> str:
    try:
        return str(event.get_platform_name() or "").strip().lower()
    except Exception:
        return ""


def _build_inline_export_message(message: str, content: str, file_path: Path) -> str:
    tip = (
        "检测到 OneBot 平台且未配置 callback_api_base，"
        "已回退为内联 TOML。若需直接发送文件，请在 AstrBot 配置 callback_api_base。"
    )
    if len(content) <= _INLINE_EXPORT_LIMIT:
        return (
            f"{message}\n{tip}\n\n```toml\n{content}\n```\n\n"
            f"备份文件已保存到宿主机: {file_path.resolve()}"
        )
    snippet = content[:_INLINE_EXPORT_LIMIT]
    return (
        f"{message}\n{tip}\n\n备份内容较长，以下仅展示前 {_INLINE_EXPORT_LIMIT} 字符:\n"
        f"```toml\n{snippet}\n```\n\n完整备份文件已保存到宿主机: {file_path.resolve()}"
    )


def _has_callback_file_service() -> bool:
    try:
        from astrbot.core import astrbot_config

        callback_api_base = str(astrbot_config.get("callback_api_base", "")).strip()
        return bool(callback_api_base)
    except Exception:
        return False
