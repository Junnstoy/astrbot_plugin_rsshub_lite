"""领域层

包含业务实体、值对象、领域事件和领域异常。
"""

from ..shared.constants import INHERIT_VALUE
from .entities.feed import Feed
from .entities.push_history import PushHistory
from .entities.subscription import Subscription
from .entities.user import User
from .exceptions import (
    ConfigurationError,
    DomainException,
    FeedNotFoundError,
    PermissionDeniedError,
    RateLimitError,
    RSSFetchError,
    SubscriptionNotFoundError,
    UserNotFoundError,
    ValidationError,
    WebError,
)
from .repositories.feed_repository import FeedRepository
from .repositories.push_history_repository import PushHistoryRepository
from .repositories.subscription_repository import SubscriptionRepository
from .repositories.user_repository import UserRepository

__all__ = [
    # Constants
    "INHERIT_VALUE",
    # Entities
    "Feed",
    "PushHistory",
    "Subscription",
    "User",
    # Repositories (Protocol)
    "FeedRepository",
    "PushHistoryRepository",
    "SubscriptionRepository",
    "UserRepository",
    # Exceptions
    "DomainException",
    "WebError",
    "RSSFetchError",
    "FeedNotFoundError",
    "SubscriptionNotFoundError",
    "UserNotFoundError",
    "ConfigurationError",
    "ValidationError",
    "PermissionDeniedError",
    "RateLimitError",
]
