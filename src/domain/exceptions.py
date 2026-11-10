"""
领域异常 - 领域层自定义异常

该模块包含插件中使用的所有领域特定异常。
这些异常是平台无关的，表示业务逻辑错误。
"""

from __future__ import annotations


class DomainException(Exception):
    """所有领域错误的基础异常。"""

    def __init__(self, message: str, code: str = "DOMAIN_ERROR"):
        self.message = message
        self.code = code
        super().__init__(self.message)


class RSSFetchError(DomainException):
    """RSS 抓取错误"""

    def __init__(self, url: str, reason: str = ""):
        self.url = url
        self.reason = reason
        super().__init__(
            message=f"Failed to fetch RSS from {url}: {reason}",
            code="RSS_FETCH_ERROR",
        )


class WebError(DomainException):
    """网络请求错误"""

    def __init__(
        self,
        error_name: str,
        url: str,
        status: str | None = None,
        base_error: Exception | None = None,
        log_level: int = 30,
    ):
        self.error_name = error_name
        self.url = url
        self.status = status
        self.base_error = base_error
        self.log_level = log_level

        message = f"{error_name}: {url}"
        if status:
            message += f" ({status})"

        super().__init__(message=message, code="WEB_ERROR")

    def __str__(self) -> str:
        return f"{self.error_name}: {self.url}"


class FeedNotFoundError(DomainException):
    """Feed 不存在错误"""

    def __init__(self, feed_id: int | None = None, url: str | None = None):
        self.feed_id = feed_id
        self.url = url
        message = "Feed not found"
        if feed_id:
            message += f" (id={feed_id})"
        if url:
            message += f" (url={url})"
        super().__init__(message=message, code="FEED_NOT_FOUND")


class SubscriptionNotFoundError(DomainException):
    """订阅不存在错误"""

    def __init__(self, sub_id: int | None = None, user_id: str | None = None):
        self.sub_id = sub_id
        self.user_id = user_id
        message = "Subscription not found"
        if sub_id:
            message += f" (id={sub_id})"
        if user_id:
            message += f" for user {user_id}"
        super().__init__(message=message, code="SUBSCRIPTION_NOT_FOUND")


class UserNotFoundError(DomainException):
    """用户不存在错误"""

    def __init__(self, user_id: str):
        self.user_id = user_id
        super().__init__(
            message=f"User not found: {user_id}",
            code="USER_NOT_FOUND",
        )


class ConfigurationError(DomainException):
    """配置错误"""

    def __init__(self, field: str, reason: str):
        self.field = field
        self.reason = reason
        super().__init__(
            message=f"Configuration error for '{field}': {reason}",
            code="CONFIGURATION_ERROR",
        )


class ValidationError(DomainException):
    """验证错误"""

    def __init__(self, field: str, reason: str):
        self.field = field
        self.reason = reason
        super().__init__(
            message=f"Validation failed for '{field}': {reason}",
            code="VALIDATION_ERROR",
        )


class PermissionDeniedError(DomainException):
    """权限不足错误"""

    def __init__(self, action: str, user_id: str | None = None):
        self.action = action
        self.user_id = user_id
        message = f"Permission denied: {action}"
        if user_id:
            message += f" for user {user_id}"
        super().__init__(message=message, code="PERMISSION_DENIED")


class RateLimitError(DomainException):
    """速率限制错误"""

    def __init__(self, resource: str, retry_after: int | None = None):
        self.resource = resource
        self.retry_after = retry_after
        message = f"Rate limit exceeded for {resource}"
        if retry_after:
            message += f", retry after {retry_after}s"
        super().__init__(message=message, code="RATE_LIMIT_EXCEEDED")
