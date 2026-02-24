from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ToolResult:
    success: bool
    data: Optional[dict[str, Any]]
    error: Optional[str]
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def ok(cls, data: dict[str, Any], **meta: Any) -> "ToolResult":
        return cls(success=True, data=data, error=None, metadata=meta)

    @classmethod
    def fail(cls, error: str, **meta: Any) -> "ToolResult":
        return cls(success=False, data=None, error=error, metadata=meta)
