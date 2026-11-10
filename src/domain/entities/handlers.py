"""Read and serialize legacy handler columns without registering or running handlers.

The models here only preserve the shape of historical database values. Their
status and config are inert data; there is no registry, enabled-state resolver,
provider access, or user-facing handler builder in the trimmed plugin.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from ...shared.constants import HandlerStatus, HandlerType

HANDLER_STATUS_INHERIT = int(HandlerStatus.INHERIT)
HANDLER_STATUS_DISABLED = int(HandlerStatus.DISABLED)
HANDLER_STATUS_ENABLED = int(HandlerStatus.ENABLED)
SUPPORTED_HANDLER_TYPES = {item.value for item in HandlerType}


class HandlerSpec(BaseModel):
    """Historical storage record; never an executable handler definition."""

    id: str = Field(..., min_length=1, max_length=255, description="Handler 唯一标识")
    type: str = Field(default=HandlerType.BUILTIN.value, description="Handler 类型")
    name: str = Field(..., min_length=1, max_length=64, description="Handler 名称")
    status: int = Field(
        default=HANDLER_STATUS_INHERIT,
        description="状态: 1=启用, 0=禁用, -100=跟随默认值",
    )
    config: dict[str, Any] = Field(default_factory=dict, description="Handler 私有配置")

    def normalized(self) -> HandlerSpec:
        """Return a normalized copy."""
        handler_type = str(self.type or "").strip().lower() or HandlerType.BUILTIN.value
        if handler_type not in SUPPORTED_HANDLER_TYPES:
            handler_type = HandlerType.EXTERNAL.value

        status = self.status
        if status not in {
            HANDLER_STATUS_ENABLED,
            HANDLER_STATUS_DISABLED,
            HANDLER_STATUS_INHERIT,
        }:
            status = HANDLER_STATUS_INHERIT

        return HandlerSpec(
            id=str(self.id or "").strip(),
            type=handler_type,
            name=str(self.name or "").strip(),
            status=status,
            config=dict(self.config),
        )


def normalize_handlers(value: Any) -> list[HandlerSpec]:
    """Read legacy JSON/dicts/specs idempotently without interpreting config."""
    if value is None or value == "":
        return []

    payload = value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        try:
            payload = json.loads(stripped)
        except (ValueError, TypeError):
            return []

    if not isinstance(payload, list):
        return []

    normalized: list[HandlerSpec] = []
    seen_ids: set[str] = set()
    for item in payload:
        if isinstance(item, HandlerSpec):
            item = item.model_dump()
        if not isinstance(item, dict):
            continue
        try:
            spec = HandlerSpec.model_validate(item).normalized()
        except (ValidationError, ValueError, TypeError):
            continue
        if not spec.id or not spec.name or spec.id in seen_ids:
            continue
        # Preserve the original cleanup of the already retired XML parser.
        if spec.type == HandlerType.BUILTIN.value and spec.name == "xml_parse":
            continue
        seen_ids.add(spec.id)
        normalized.append(spec)
    return normalized


def dump_handlers(value: Any) -> list[dict[str, Any]]:
    """Dump handler payload to stable JSON-serializable list."""
    return [spec.model_dump() for spec in normalize_handlers(value)]


def handlers_json(value: Any) -> str:
    """Serialize handlers to compact stable JSON for persistence."""
    return json.dumps(dump_handlers(value), ensure_ascii=False, separators=(",", ":"))
