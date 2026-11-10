"""RSSHub 事件系统

提供事件发布/订阅机制，支持插件和 AI 介入处理流程。

事件类型:
    - FeedFetchEvent: RSS 抓取事件
    - FeedParseEvent: RSS 解析事件
    - MessageFormatEvent: 消息格式化事件
    - MessageSendEvent: 消息发送事件
    - MessageSentEvent: 消息发送完成事件

Examples:
    >>> @event_bus.on(FeedParseEvent)
    ... async def on_parse(event: FeedParseEvent):
    ...     # AI 可以在这里修改解析结果
    ...     event.entries[0].title = ai_rewrite(event.entries[0].title)

    >>> @event_bus.on(MessageFormatEvent)
    ... async def on_format(event: MessageFormatEvent):
    ...     # 插件可以修改消息格式
    ...     event.content = plugin_add_signature(event.content)
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, TypeVar

from ...domain.entities.feed import Feed
from ...domain.entities.push_history import PushHistory
from ...domain.entities.subscription import Subscription
from ..utils import get_logger

if TYPE_CHECKING:
    from ..fetcher.rss.parser import EntryParsed

logger = get_logger()

T = TypeVar("T", bound="BaseEvent")


class BaseEvent:
    """事件基类"""

    def __init__(self) -> None:
        self.timestamp: datetime = datetime.now()
        self.cancelled: bool = False
        self._metadata: dict[str, Any] = {}

    def cancel(self) -> None:
        """取消事件（阻止后续处理）"""
        self.cancelled = True

    def set_metadata(self, key: str, value: Any) -> None:
        """设置元数据（供插件传递数据）"""
        self._metadata[key] = value

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """获取元数据"""
        return self._metadata.get(key, default)


@dataclass
class FeedFetchEvent(BaseEvent):
    """RSS 抓取事件

    触发时机: HTTP 请求获取 RSS 内容后
    用途: AI 可以在这里修改原始 XML，插件可以记录抓取日志

    Attributes:
        url: 抓取的 URL
        content: 原始 XML 内容（可被修改）
        status_code: HTTP 状态码
        headers: HTTP 响应头
        error: 错误信息（如果有）
    """

    url: str = ""
    content: str = ""
    status_code: int = 0
    headers: dict[str, str] = field(default_factory=dict)
    error: str = ""

    def __post_init__(self) -> None:
        super().__init__()


@dataclass
class FeedParseEvent(BaseEvent):
    """RSS 解析事件

    触发时机: XML 解析为条目后
    用途: AI 可以修改条目内容，插件可以过滤条目

    Attributes:
        feed: Feed 实体
        entries: 解析出的条目列表（可被修改、增删）
        raw_xml: 原始 XML 内容
    """

    feed: Feed | None = None
    entries: list[EntryParsed] = field(default_factory=list)
    raw_xml: str = ""

    def __post_init__(self) -> None:
        super().__init__()

    def filter_entries(self, predicate: Callable[[EntryParsed], bool]) -> None:
        """过滤条目（插件可以使用此方法移除不想要的条目）"""
        self.entries = [e for e in self.entries if predicate(e)]


@dataclass
class EntryProcessEvent(BaseEvent):
    """单个条目处理事件

    触发时机: 每个条目被处理时（格式化前）
    用途: AI 重写内容，插件添加自定义内容

    Attributes:
        entry: 当前条目（可被修改）
        subscription: 订阅配置
        feed: Feed 配置
    """

    entry: EntryParsed | None = None
    subscription: Subscription | None = None
    feed: Feed | None = None

    def __post_init__(self) -> None:
        super().__init__()


@dataclass
class MessageFormatEvent(BaseEvent):
    """消息格式化事件

    触发时机: 消息内容格式化后，发送前
    用途: 插件修改消息格式，AI 优化文案

    Attributes:
        content: 消息内容（可被修改）
        entry: 原始条目
        subscription: 订阅配置
        platform_name: 平台名称
    """

    content: str = ""
    entry: EntryParsed | None = None
    subscription: Subscription | None = None
    platform_name: str = ""

    def __post_init__(self) -> None:
        super().__init__()


@dataclass
class MessageSendEvent(BaseEvent):
    """消息发送事件

    触发时机: 消息即将发送时
    用途: 插件可以阻止发送，AI 可以最后修改

    Attributes:
        session_id: 目标会话 ID
        content: 消息内容（可被修改）
        media_paths: 媒体文件路径（可被修改）
        subscription: 订阅配置
    """

    session_id: str = ""
    content: str = ""
    media_paths: list[str] = field(default_factory=list)
    subscription: Subscription | None = None

    def __post_init__(self) -> None:
        super().__init__()


@dataclass
class MessageSentEvent(BaseEvent):
    """消息发送完成事件

    触发时机: 消息发送完成后（无论成功失败）
    用途: 插件记录发送日志，统计发送成功率

    Attributes:
        session_id: 目标会话 ID
        content: 发送的内容
        success: 是否成功
        error: 错误信息
        push_history: 推送历史记录
    """

    session_id: str = ""
    content: str = ""
    success: bool = False
    error: str = ""
    push_history: PushHistory | None = None

    def __post_init__(self) -> None:
        super().__init__()


@dataclass
class DeduplicationEvent(BaseEvent):
    """去重检查事件

    触发时机: 条目去重检查时
    用途: 插件自定义去重逻辑，AI 判断内容相似度

    Attributes:
        entry: 待检查条目
        existing_hashes: 已有哈希值
        is_duplicate: 是否重复（可被修改）
        confidence: 重复置信度（0-1）
    """

    entry: EntryParsed | None = None
    existing_hashes: set[str] = field(default_factory=set)
    is_duplicate: bool = False
    confidence: float = 0.0

    def __post_init__(self) -> None:
        super().__init__()


class EventBus:
    """事件总线

    管理事件的发布和订阅，支持处理器优先级。

    优先级规则:
        - 数字越小，优先级越高（越早执行）
        - 默认优先级为 100
        - 建议: 系统扩展 0-50，普通扩展 100，后置处理 200+

    Examples:
        >>> bus = EventBus()
        >>> @bus.on(FeedParseEvent, priority=10)  # 高优先级
        ... async def handler(event: FeedParseEvent):
        ...     pass
        >>> await bus.emit(FeedParseEvent(entries=[]))
    """

    DEFAULT_PRIORITY: int = 100

    def __init__(self) -> None:
        # 存储元组 (priority, handler) 以保持顺序
        self._handlers: dict[type[BaseEvent], list[tuple[int, Callable]]] = {}
        self._logger = get_logger()

    def on(
        self,
        event_type: type[T],
        priority: int = DEFAULT_PRIORITY,
    ) -> Callable[[Callable[[T], Any]], Callable[[T], Any]]:
        """订阅事件

        Args:
            event_type: 事件类型

        Returns:
            装饰器函数
        """

        def decorator(handler: Callable[[T], Any]) -> Callable[[T], Any]:
            if event_type not in self._handlers:
                self._handlers[event_type] = []
            self._handlers[event_type].append((priority, handler))
            self._handlers[event_type].sort(key=lambda item: item[0])
            self._logger.debug(
                "注册事件处理器: %s -> %s",
                event_type.__name__,
                handler.__name__,
            )
            return handler

        return decorator

    async def emit(self, event: BaseEvent) -> None:
        """发布事件

        Args:
            event: 事件实例
        """
        event_type = type(event)
        handlers = self._handlers.get(event_type, [])

        if not handlers:
            return

        self._logger.debug(
            "发布事件: %s (处理器数: %d)",
            event_type.__name__,
            len(handlers),
        )

        for _, handler in handlers:
            try:
                if event.cancelled:
                    self._logger.debug(
                        "事件 %s 已被取消，停止处理",
                        event_type.__name__,
                    )
                    break

                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)

            except Exception as e:
                self._logger.exception(
                    "事件处理器 %s 执行失败: %s",
                    handler.__name__,
                    e,
                )

    def off(self, event_type: type[BaseEvent], handler: Callable | None = None) -> None:
        """取消订阅

        Args:
            event_type: 事件类型
            handler: 要移除的处理器，None 则移除所有
        """
        if event_type not in self._handlers:
            return

        if handler is None:
            self._handlers[event_type].clear()
        else:
            self._handlers[event_type] = [
                item for item in self._handlers[event_type] if item[1] != handler
            ]


# 全局事件总线实例
_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """获取全局事件总线"""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


def reset_event_bus() -> None:
    """重置事件总线（主要用于测试）"""
    global _event_bus
    _event_bus = None


__all__ = [
    # Events
    "BaseEvent",
    "FeedFetchEvent",
    "FeedParseEvent",
    "EntryProcessEvent",
    "MessageFormatEvent",
    "MessageSendEvent",
    "MessageSentEvent",
    "DeduplicationEvent",
    # EventBus
    "EventBus",
    "get_event_bus",
    "reset_event_bus",
]
