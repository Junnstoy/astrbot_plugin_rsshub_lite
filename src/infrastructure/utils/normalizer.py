"""文本标准化工具

提供通用的文本、标识符、路径和配置值标准化函数。
"""

from __future__ import annotations

import html
import math
import numbers
import re
from typing import Any

from ..utils import get_logger

logger = get_logger()


def normalize_text(value: str, max_length: int = 1024) -> str:
    """标准化文本：去 HTML 实体、合并空白、小写、截断

    Args:
        value: 原始文本
        max_length: 最大长度

    Returns:
        标准化后的文本
    """
    text = html.unescape(value or "")
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text[:max_length]


def normalize_identifier(value: str, max_length: int = 1024) -> str:
    """标准化标识符：保留大小写和内部空白，截断

    Args:
        value: 原始标识符
        max_length: 最大长度

    Returns:
        标准化后的标识符
    """
    return (value or "").strip()[:max_length]


def normalize_path(path: str) -> str:
    """标准化 URL 路径

    Args:
        path: URL 路径

    Returns:
        标准化后的路径
    """
    normalized = path or ""
    if normalized != "/":
        normalized = normalized.rstrip("/")
    return normalized


def normalize_config_positive_int(raw: Any, key: str, default: int) -> int:
    """将配置值标准化为正整数

    Args:
        raw: 原始值
        key: 配置键名（用于日志）
        default: 默认值

    Returns:
        正整数
    """
    if isinstance(raw, bool):
        logger.warning("Invalid %s=%r; expected positive integer", key, raw)
        return default

    if isinstance(raw, numbers.Integral):
        if raw > 0:
            return int(raw)
        logger.warning("Invalid %s=%r; expected positive integer", key, raw)
        return default

    if isinstance(raw, numbers.Real):
        if math.isfinite(float(raw)) and raw > 0 and float(raw).is_integer():
            coerced = int(raw)
            logger.info(
                "Coerced %s=%r (non-integral type) to positive integer %d",
                key,
                raw,
                coerced,
            )
            return coerced
        logger.warning(
            "Invalid %s=%r; expected positive integer (got non-integral numeric type)",
            key,
            raw,
        )
        return default

    if isinstance(raw, str):
        stripped = raw.strip()
        if not stripped:
            return default
        if re.fullmatch(r"\d+", stripped):
            parsed = int(stripped)
            return parsed if parsed > 0 else default
        logger.warning("Invalid %s=%r; expected positive integer", key, raw)
        return default

    return default
