"""订阅相关命令处理器（纯函数）"""

from __future__ import annotations

from astrbot.api.event import AstrMessageEvent

from ...application.services.session_push_queue import SessionPushQueue
from .config import _get_session_defaults


async def handle_sub(
    event: AstrMessageEvent, url: str, deps: dict, *, ctx=None
) -> dict:
    """订阅 RSS 源"""
    if not url:
        return {"plain": "请提供 RSS 源的 URL\n用法: /sub <url>"}

    user_id = event.get_sender_id()
    target_session = event.unified_msg_origin
    platform_name = event.get_platform_name()

    url_list = [u.strip() for u in url.split() if u.strip()]
    valid_urls = [
        u
        for u in url_list
        if u.startswith(("http://", "https://"))
        or (u.startswith("/") and not u.startswith("//"))
    ]

    if not valid_urls:
        return {"plain": "请提供 http(s) RSS 链接或以 / 开头的 RSSHub 路由"}

    options = {}
    if ctx is not None:
        defaults = await _get_session_defaults(ctx, target_session)
        if defaults:
            options["session_defaults"] = defaults

    if len(valid_urls) == 1:
        result = await deps["subscribe_cmd"].execute(
            url=valid_urls[0],
            user_id=user_id,
            target_session=target_session,
            platform_name=platform_name,
            **options,
        )
        return {"plain": result.message}

    results = []
    for single_url in valid_urls:
        r = await deps["subscribe_cmd"].execute(
            url=single_url,
            user_id=user_id,
            target_session=target_session,
            platform_name=platform_name,
            **options,
        )
        results.append(r)

    success_count = sum(1 for r in results if r.success)
    failed_count = len(results) - success_count

    if failed_count == 0:
        return {"plain": f"成功订阅 {success_count} 个 RSS 源"}
    elif success_count == 0:
        return {"plain": f"全部失败: {failed_count} 个订阅失败"}
    else:
        return {"plain": f"部分成功: {success_count} 个订阅成功, {failed_count} 个失败"}


async def handle_unsub(event: AstrMessageEvent, sub_id: str, deps: dict) -> dict:
    """取消订阅"""
    args = sub_id.strip() if isinstance(sub_id, str) else str(sub_id).strip()
    if not args:
        return {"plain": "请提供订阅 ID 或 URL\n用法: /unsub <ID/URL...>"}

    parts = [p.strip() for p in args.split() if p.strip()]
    if not parts:
        return {"plain": "请提供订阅 ID 或 URL\n用法: /unsub <ID/URL...>"}

    user_id = event.get_sender_id()
    current_session = event.unified_msg_origin
    is_admin = event.is_admin()
    results: list[str] = []
    for token in parts:
        if token.startswith(("http://", "https://")):
            result = await deps["unsubscribe_cmd"].execute_by_url(
                url=token,
                user_id=user_id,
                current_session=current_session,
                is_admin=is_admin,
            )
        else:
            try:
                sub_id_int = int(token)
            except ValueError:
                results.append(f"参数无效: {token}（需为订阅 ID 或 URL）")
                continue
            result = await deps["unsubscribe_cmd"].execute(
                sub_id=sub_id_int,
                user_id=user_id,
                current_session=current_session,
                is_admin=is_admin,
            )
        results.append(result.message)

    return {"plain": "\n".join(results)}


async def handle_sub_list(event: AstrMessageEvent, args: str, deps: dict) -> dict:
    """查看订阅列表"""
    user_id = event.get_sender_id()
    arg_parts = [p.strip() for p in (args or "").split() if p.strip()]

    page = 1
    page_size = 5
    if len(arg_parts) > 2:
        return {"plain": "分页参数过多。用法: /sub_list [页码] [每页数量]"}
    if arg_parts:
        try:
            page = int(arg_parts[0])
        except ValueError:
            return {"plain": "分页参数无效。用法: /sub_list [page] [page_size]"}
    if len(arg_parts) >= 2:
        try:
            page_size = int(arg_parts[1])
        except ValueError:
            return {"plain": "分页参数无效。用法: /sub_list [page] [page_size]"}

    if page < 1 or not 1 <= page_size <= 100:
        return {
            "plain": "页码必须大于 0，每页数量必须在 1～100 之间。示例: /sub_list 2 10"
        }

    result = await deps["get_subs_query"].execute(user_id=user_id)
    if not result.subscriptions:
        return {"plain": "暂无订阅\n使用 /sub <url> 添加订阅"}

    current_session = event.unified_msg_origin
    visible = [
        sub
        for sub in result.subscriptions
        if (sub.target_session or current_session) == current_session
    ]

    if not visible:
        return {"plain": "当前会话没有订阅\n使用 /sub <url> 添加订阅"}

    total_count = len(visible)
    total_pages = max(1, (total_count + page_size - 1) // page_size)
    page = min(page, total_pages)
    start = (page - 1) * page_size
    page_subs = visible[start : start + page_size]

    active_count = sum(1 for sub in visible if sub.state == 1)
    inactive_count = total_count - active_count
    lines = [
        "您的订阅列表（当前会话）:",
        f"共 {total_count} 个订阅 | 启用: {active_count} | 禁用: {inactive_count}",
        f"页码: {page}/{total_pages}  每页: {page_size}",
    ]
    for i, sub in enumerate(page_subs, start + 1):
        state_icon = "✓" if sub.state == 1 else "✗"
        feed_title = sub.feed_title or f"Feed #{sub.feed_id}"
        custom_title = f" ({sub.title})" if sub.title else ""
        lines.append(f"{i}. [{sub.id}] {state_icon} {feed_title}{custom_title}")
        if sub.feed_link:
            lines.append(f"    {sub.feed_link}")
    lines.append("方括号内是订阅 ID；✓ 自动推送已启用，✗ 已停用。")
    lines.append("启停: /push <ID>、/unpush <ID>；立即发送: /feed <ID> <N>")
    if page < total_pages:
        lines.append(f"下一页: /sub_list {page + 1} {page_size}")
    return {"plain": "\n".join(lines)}


async def handle_refresh(event: AstrMessageEvent, feed_id: int, deps: dict) -> dict:
    """刷新订阅"""
    if feed_id <= 0:
        return {"plain": "请提供 Feed ID\n用法: /refresh <feed_id>"}
    result = await deps["polling_service"].poll_feed(feed_id)
    return {"plain": result.message}


def handle_rss_stop(
    event: AstrMessageEvent, queue: SessionPushQueue, args: str
) -> dict:
    """停止当前会话 RSS 推送任务（运行中/排队中）。"""
    current_session = event.unified_msg_origin
    target = (args or "").strip()

    if not target:
        result = queue.stop_current(current_session)
        if result.stopped:
            queued = (
                f"，队列中还有 {result.queued_count} 个任务"
                if result.queued_count
                else ""
            )
            return {"plain": f"{result.message}{queued}"}
        return {"plain": result.message}

    if target.lower() == "all":
        stopped = queue.stop_all_for_session(current_session)
        if stopped["stopped"] <= 0:
            return {"plain": "当前会话没有可停止的任务"}
        return {
            "plain": (
                "已请求停止当前会话任务: "
                f"总计 {stopped['stopped']} 个 "
                f"(running={stopped['running']}, queued={stopped['queued']})"
            )
        }

    if target.isdigit():
        result = queue.stop_by_feed_id(current_session, int(target))
    else:
        result = queue.stop_by_job_id(current_session, target)
    return {"plain": result.message}


def handle_sub_status(event: AstrMessageEvent, queue: SessionPushQueue) -> dict:
    """查看当前会话推送任务状态（运行中与排队中）。"""
    current_session = event.unified_msg_origin
    jobs = queue.get_jobs(current_session)
    if not jobs:
        return {
            "plain": "当前会话没有正在发送或排队的任务。\n这不代表订阅已停用；自动推送开关请看 /sub_list。"
        }

    lines = [f"当前会话任务数: {len(jobs)}"]
    for idx, job in enumerate(jobs, start=1):
        feed_label = (
            f"{job.feed_title or '(未知Feed)'}"
            f" | feed_id={job.feed_id if job.feed_id is not None else '未知'}"
        )
        lines.append(f"{idx}. {job.status} | job_id={job.job_id} | {feed_label}")
    lines.append("取消本次任务: /push_cancel <job_id|feed_id|all>")
    lines.append("持续停用自动推送: /unpush <订阅ID|all>")
    return {"plain": "\n".join(lines)}


async def handle_sub_state(
    event: AstrMessageEvent, sub_id_str: str, deps: dict, *, queue=None
) -> dict:
    """订阅状态管理"""
    if not sub_id_str:
        return {"plain": "用法: /sub_state <订阅ID> on/off\n示例: /sub_state 123 on"}

    parts = sub_id_str.split()
    if len(parts) != 2:
        return {"plain": "用法: /sub_state <订阅ID> on/off\n示例: /sub_state 123 on"}

    try:
        sub_id = int(parts[0])
    except ValueError:
        return {"plain": "订阅 ID 必须是数字"}

    state_str = parts[1].lower()
    if state_str in ("on", "true", "yes", "y", "1", "开启"):
        enable = True
    elif state_str in ("off", "false", "no", "n", "0", "关闭"):
        enable = False
    else:
        return {
            "plain": "不支持的状态值，请使用: on/off, true/false, yes/no, y/n, 1/0, 开启/关闭"
        }

    from .batch import handle_push, handle_unpush

    if enable:
        return await handle_push(event, str(sub_id), deps)
    return await handle_unpush(event, str(sub_id), deps, queue=queue)
