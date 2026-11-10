"""批量启用订阅命令

处理批量启用 RSS 订阅的业务用例。
"""

from __future__ import annotations

from dataclasses import dataclass

from ...domain.repositories.subscription_repository import SubscriptionRepository
from ..dto.result_dto import CommandResult


@dataclass
class BatchActivateItem:
    """批量启用单项结果"""

    sub_id: int
    success: bool
    message: str


@dataclass
class BatchActivateResult:
    """批量启用结果"""

    total: int
    success_count: int
    failure_count: int
    items: list[BatchActivateItem]


class BatchActivateCommand:
    """批量启用订阅命令

    处理批量启用 RSS 订阅的业务用例。
    """

    def __init__(self, subscription_repo: SubscriptionRepository):
        self._subscription_repo = subscription_repo

    async def execute(
        self,
        sub_ids: list[int],
        user_id: str,
        current_session: str | None = None,
    ) -> CommandResult:
        """执行批量启用命令

        Args:
            sub_ids: 订阅 ID 列表
            user_id: 用户 ID
            current_session: 可选的当前会话范围；聊天入口必须传入

        Returns:
            CommandResult: 命令执行结果
        """
        if not sub_ids:
            return CommandResult(
                success=False,
                message="未提供订阅 ID",
            )

        if current_session is not None and not current_session.strip():
            return CommandResult(success=False, message="无法确认当前会话，未修改订阅")
        sub_ids = list(dict.fromkeys(sub_ids))

        items: list[BatchActivateItem] = []
        success_count = 0
        failure_count = 0

        for sub_id in sub_ids:
            item = await self._process_single(sub_id, user_id, current_session)
            items.append(item)
            if item.success:
                success_count += 1
            else:
                failure_count += 1

        result = BatchActivateResult(
            total=len(sub_ids),
            success_count=success_count,
            failure_count=failure_count,
            items=items,
        )

        if success_count == len(sub_ids):
            return CommandResult(
                success=True,
                message=f"成功启用 {success_count} 个订阅",
                data=result,
            )
        elif success_count > 0:
            return CommandResult(
                success=True,
                message=f"部分成功: {success_count} 个启用, {failure_count} 个失败",
                data=result,
            )
        else:
            return CommandResult(
                success=False,
                message=f"全部失败: {failure_count} 个订阅启用失败",
                data=result,
            )

    async def _process_single(
        self,
        sub_id: int,
        user_id: str,
        current_session: str | None = None,
    ) -> BatchActivateItem:
        """处理单个启用

        Args:
            sub_id: 订阅 ID
            user_id: 用户 ID
            current_session: 可选的当前会话范围；聊天入口必须传入

        Returns:
            BatchActivateItem: 单项结果
        """
        subscription = await self._subscription_repo.get_by_id(sub_id)
        if not subscription:
            return BatchActivateItem(
                sub_id=sub_id,
                success=False,
                message=f"订阅不存在 (ID: {sub_id})",
            )

        if subscription.user_id != user_id:
            return BatchActivateItem(
                sub_id=sub_id,
                success=False,
                message="无权操作此订阅",
            )

        if (
            current_session is not None
            and (subscription.target_session or current_session) != current_session
        ):
            return BatchActivateItem(
                sub_id=sub_id,
                success=False,
                message="该订阅不属于当前会话",
            )

        if subscription.state == 1:
            return BatchActivateItem(
                sub_id=sub_id,
                success=True,
                message=f"订阅已经是启用状态 (ID: {sub_id})",
            )

        subscription.enable()
        updated = await self._subscription_repo.update_options(
            sub_id,
            user_id,
            state=subscription.state,
            updated_at=subscription.updated_at,
        )
        if updated is None:
            return BatchActivateItem(
                sub_id=sub_id,
                success=False,
                message=f"订阅不存在或已变更 (ID: {sub_id})",
            )

        return BatchActivateItem(
            sub_id=sub_id,
            success=True,
            message=f"已启用订阅 (ID: {sub_id})",
        )

    async def execute_all(
        self,
        user_id: str,
    ) -> CommandResult:
        """启用用户的所有订阅

        Args:
            user_id: 用户 ID

        Returns:
            CommandResult: 命令执行结果
        """
        subscriptions = await self._subscription_repo.get_by_user(user_id)
        if not subscriptions:
            return CommandResult(
                success=False,
                message="没有可启用的订阅",
            )

        # 只选择当前禁用的订阅
        disabled_subs = [sub for sub in subscriptions if sub.state != 1]
        if not disabled_subs:
            return CommandResult(
                success=False,
                message="所有订阅已经是启用状态",
            )

        sub_ids = [sub.id for sub in disabled_subs]
        return await self.execute(sub_ids, user_id)

    async def execute_by_session(
        self,
        user_id: str,
        current_session: str,
    ) -> CommandResult:
        """启用当前用户在当前会话中的订阅，保留原版空目标兼容。"""
        if not current_session.strip():
            return CommandResult(success=False, message="无法确认当前会话，未修改订阅")
        subscriptions = await self._subscription_repo.get_by_user(user_id)
        sub_ids = [
            sub.id
            for sub in subscriptions
            if sub.id is not None
            and (sub.target_session or current_session) == current_session
        ]
        if not sub_ids:
            return CommandResult(success=True, message="当前会话没有可操作的订阅")
        return await self.execute(
            sub_ids=sub_ids, user_id=user_id, current_session=current_session
        )
