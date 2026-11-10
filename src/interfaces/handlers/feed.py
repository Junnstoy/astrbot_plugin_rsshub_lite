"""Manual current-session feed delivery command adapter."""

from __future__ import annotations

from astrbot.api.event import AstrMessageEvent

USAGE = "用法: /feed <订阅ID> <N>\n示例: /feed 12 5\n订阅 ID 可通过 /sub_list 查看。"


async def handle_feed(event: AstrMessageEvent, args: str, deps: dict) -> dict:
    """The AstrBot command entry point restricts this action to administrators."""
    parts = str(args or "").split()
    if len(parts) != 2:
        return {"plain": USAGE}
    try:
        sub_id, count = (int(part) for part in parts)
    except ValueError:
        return {"plain": f"订阅 ID 和推送条数 N 必须是正整数。\n{USAGE}"}
    if sub_id <= 0 or count <= 0:
        return {"plain": f"订阅 ID 和推送条数 N 必须是正整数。\n{USAGE}"}
    result = await deps["push_feed_cmd"].execute(
        sub_id=sub_id,
        count=count,
        user_id=event.get_sender_id(),
        target_session=event.unified_msg_origin,
        platform_name=event.get_platform_name(),
    )
    return {"plain": result.message}
