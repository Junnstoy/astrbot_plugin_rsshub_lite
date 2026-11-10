"""批量禁用订阅命令

处理批量禁用 RSS 订阅的业务用例。
"""

from __future__ import annotations

from dataclasses import dataclass

from ...domain.repositories.subscription_repository import SubscriptionRepository
from ..dto.result_dto import CommandResult


@dataclass
class BatchDeactivateItem:
    """批量禁用单项结果"""

    sub_id: int
    success: bool
    message: str


@dataclass
class BatchDeactivateResult:
    """批量禁用结果"""

    total: int
    success_count: int
    failure_count: int
    items: list[BatchDeactivateItem]


class BatchDeactivateCommand:
    """批量禁用订阅命令

    处理批量禁用 RSS 订阅的业务用例。
    """

    def __init__(self, subscription_repo: SubscriptionRepository):
        self._subscription_repo = subscription_repo

    async def execute(
        self,
        sub_ids: list[int],
        user_id: str,
    ) -> CommandResult:
        """执行批量禁用命令

        Args:
            sub_ids: 订阅 ID 列表
            user_id: 用户 ID

        Returns:
            CommandResult: 命令执行结果
        """
        if not sub_ids:
            return CommandResult(
                success=False,
                message="未提供订阅 ID",
            )

        items: list[BatchDeactivateItem] = []
        success_count = 0
        failure_count = 0

        for sub_id in sub_ids:
            item = await self._process_single(sub_id, user_id)
            items.append(item)
            if item.success:
                success_count += 1
            else:
                failure_count += 1

        result = BatchDeactivateResult(
            total=len(sub_ids),
            success_count=success_count,
            failure_count=failure_count,
            items=items,
        )

        if success_count == len(sub_ids):
            return CommandResult(
                success=True,
                message=f"成功禁用 {success_count} 个订阅",
                data=result,
            )
        elif success_count > 0:
            return CommandResult(
                success=True,
                message=f"部分成功: {success_count} 个禁用, {failure_count} 个失败",
                data=result,
            )
        else:
            return CommandResult(
                success=False,
                message=f"全部失败: {failure_count} 个订阅禁用失败",
                data=result,
            )

    async def _process_single(
        self,
        sub_id: int,
        user_id: str,
    ) -> BatchDeactivateItem:
        """处理单个禁用

        Args:
            sub_id: 订阅 ID
            user_id: 用户 ID

        Returns:
            BatchDeactivateItem: 单项结果
        """
        subscription = await self._subscription_repo.get_by_id(sub_id)
        if not subscription:
            return BatchDeactivateItem(
                sub_id=sub_id,
                success=False,
                message=f"订阅不存在 (ID: {sub_id})",
            )

        if subscription.user_id != user_id:
            return BatchDeactivateItem(
                sub_id=sub_id,
                success=False,
                message="无权操作此订阅",
            )

        if subscription.state == 0:
            return BatchDeactivateItem(
                sub_id=sub_id,
                success=True,
                message=f"订阅已经是禁用状态 (ID: {sub_id})",
            )

        subscription.state = 0  # 禁用状态
        await self._subscription_repo.save(subscription)

        return BatchDeactivateItem(
            sub_id=sub_id,
            success=True,
            message=f"已禁用订阅 (ID: {sub_id})",
        )

    async def execute_all(
        self,
        user_id: str,
    ) -> CommandResult:
        """禁用用户的所有订阅

        Args:
            user_id: 用户 ID

        Returns:
            CommandResult: 命令执行结果
        """
        subscriptions = await self._subscription_repo.get_by_user(user_id)
        if not subscriptions:
            return CommandResult(
                success=False,
                message="没有可禁用的订阅",
            )

        # 只选择当前启用的订阅
        enabled_subs = [sub for sub in subscriptions if sub.state == 1]
        if not enabled_subs:
            return CommandResult(
                success=False,
                message="所有订阅已经是禁用状态",
            )

        sub_ids = [sub.id for sub in enabled_subs]
        return await self.execute(sub_ids, user_id)

    async def execute_by_session(
        self,
        user_id: str,
        current_session: str,
    ) -> CommandResult:
        """禁用当前会话中的所有订阅

        Args:
            user_id: 用户 ID
            current_session: 当前会话 ID

        Returns:
            CommandResult: 命令执行结果
        """
        subscriptions = await self._subscription_repo.get_by_user(user_id)
        if not subscriptions:
            return CommandResult(
                success=True,
                message="当前会话没有需要禁用的订阅",
            )

        # 过滤当前会话中启用的订阅
        # NULL target_session 视为当前会话
        subs = [
            sub
            for sub in subscriptions
            if sub.state == 1
            and (sub.target_session == current_session or not sub.target_session)
        ]

        if not subs:
            return CommandResult(
                success=True,
                message="当前会话没有需要禁用的订阅",
            )

        # 禁用所有订阅
        deactivated_count = 0
        for sub in subs:
            sub.state = 0
            await self._subscription_repo.save(sub)
            deactivated_count += 1

        return CommandResult(
            success=True,
            message=(
                f"已禁用当前会话的 {deactivated_count} 个订阅\n\n"
                "当前会话订阅已全部禁用，不再推送更新\n"
                "使用 /activate_subs 可随时重新启用"
            ),
        )
