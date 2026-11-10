"""
订阅状态切换命令

处理启用/禁用单个订阅的业务用例。
"""

from __future__ import annotations

from ...domain.repositories.subscription_repository import SubscriptionRepository
from ..dto.result_dto import CommandResult


class SubStateCommand:
    """
    订阅状态切换命令

    处理启用/禁用单个订阅的业务用例。
    """

    def __init__(self, subscription_repo: SubscriptionRepository):
        self._subscription_repo = subscription_repo

    async def execute(
        self,
        sub_id: int,
        user_id: str,
        enable: bool,
    ) -> CommandResult:
        """
        执行状态切换命令

        Args:
            sub_id: 订阅 ID
            user_id: 用户 ID
            enable: True=启用, False=禁用

        Returns:
            CommandResult: 命令执行结果
        """
        subscription = await self._subscription_repo.get_by_id(sub_id)
        if not subscription:
            return CommandResult(
                success=False,
                message="未找到该订阅或无权限",
            )

        if subscription.user_id != user_id:
            return CommandResult(
                success=False,
                message="未找到该订阅或无权限",
            )

        subscription.state = 1 if enable else 0
        await self._subscription_repo.save(subscription)

        action = "启用" if enable else "禁用"
        return CommandResult(
            success=True,
            message=f"已{action}订阅 (ID: {sub_id}) 的推送",
        )
