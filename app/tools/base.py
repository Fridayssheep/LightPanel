from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class ToolContext:
    approve_actions: bool = False
    dry_run: bool = False


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., dict[str, Any]]
    destructive: bool = False
    requires_approval: bool = False

    def as_openai_tool(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


def success(summary: str, **data: Any) -> dict[str, Any]:
    return {"status": "success", "summary": summary, "data": data}


def error(summary: str, **data: Any) -> dict[str, Any]:
    return {"status": "error", "summary": summary, "data": data}


def approval_required(summary: str, **data: Any) -> dict[str, Any]:
    return {"status": "approval_required", "summary": summary, "data": data}


def skipped(summary: str, **data: Any) -> dict[str, Any]:
    return {"status": "skipped", "summary": summary, "data": data}
