"""导出订阅命令

处理用户导出订阅配置的业务用例。
"""

from __future__ import annotations

from dataclasses import dataclass

from ...domain.repositories.feed_repository import FeedRepository
from ...domain.repositories.subscription_repository import SubscriptionRepository
from ..dto.result_dto import CommandResult
from ..queries.get_subscription_exports_query import GetSubscriptionExportsQuery
from ..services.subscription_serializer import serialize_subscriptions_to_toml


@dataclass
class ExportResult:
    """导出结果"""

    content: str
    filename: str
    count: int


class ExportSubscriptionsCommand:
    """导出订阅命令

    处理用户导出订阅配置的业务用例。
    """

    def __init__(
        self,
        subscription_repo: SubscriptionRepository,
        feed_repo: FeedRepository | None = None,
    ):
        self._export_query = GetSubscriptionExportsQuery(
            subscription_repo=subscription_repo,
            feed_repo=feed_repo,
        )

    async def execute(
        self,
        user_id: str,
        is_admin: bool = False,
        scope: str = "",
        current_session: str = "",
    ) -> CommandResult:
        """执行导出命令

        Args:
            user_id: 用户 ID

        Returns:
            CommandResult: 命令执行结果
        """
        try:
            if scope == "all" and not is_admin:
                return CommandResult(
                    success=False, message="导出所有订阅需要管理员权限"
                )
            records = await self._export_query.execute(
                user_id,
                scope=scope,
                current_session=current_session,
                is_admin=is_admin,
            )
        except RuntimeError as e:
            return CommandResult(
                success=False,
                message=f"导出失败: {e}",
            )

        if not records:
            return CommandResult(
                success=False,
                message="您当前没有可导出的订阅",
            )

        try:
            content = serialize_subscriptions_to_toml(
                user_id=user_id,
                records=records,
            )

            from datetime import datetime

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"rsshub_subscriptions_{user_id}_{timestamp}.toml"

            result = ExportResult(
                content=content,
                filename=filename,
                count=len(records),
            )

            return CommandResult(
                success=True,
                message=f"成功导出 {len(records)} 个订阅",
                data=result,
            )

        except Exception as e:
            return CommandResult(
                success=False,
                message=f"导出失败: {e}",
            )
