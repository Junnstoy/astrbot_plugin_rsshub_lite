"""批量操作命令处理器（纯函数）"""

from __future__ import annotations

from pathlib import Path

from astrbot.api.event import AstrMessageEvent

from ...infrastructure.utils import get_plugin_export_dir
from ...shared.constants import ONEBOT_PLATFORMS

_INLINE_EXPORT_LIMIT = 5000


async def handle_batch_activate(
    event: AstrMessageEvent, sub_ids: str, deps: dict
) -> dict:
    """启用订阅"""
    user_id = event.get_sender_id()
    current_session = event.unified_msg_origin

    if sub_ids:
        ids = [int(x.strip()) for x in sub_ids.split(",") if x.strip().isdigit()]
        if not ids:
            return {"plain": "请提供订阅 ID 列表\n用法: /activate_subs 1,2,3"}
        result = await deps["batch_activate_cmd"].execute(sub_ids=ids, user_id=user_id)
    else:
        result = await deps["batch_activate_cmd"].execute_by_session(
            user_id=user_id,
            current_session=current_session,
        )
    return {"plain": result.message}


async def handle_batch_deactivate(
    event: AstrMessageEvent, sub_ids: str, deps: dict
) -> dict:
    """禁用订阅"""
    user_id = event.get_sender_id()
    current_session = event.unified_msg_origin

    if sub_ids:
        ids = [int(x.strip()) for x in sub_ids.split(",") if x.strip().isdigit()]
        if not ids:
            return {"plain": "请提供订阅 ID 列表\n用法: /deactivate_subs 1,2,3"}
        result = await deps["batch_deactivate_cmd"].execute(
            sub_ids=ids, user_id=user_id
        )
    else:
        result = await deps["batch_deactivate_cmd"].execute_by_session(
            user_id=user_id,
            current_session=current_session,
        )
    return {"plain": result.message}


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
