from __future__ import annotations

from typing import Any

from app.docker import tools as docker_tools
from app.schemas import ToolCallRecord, ToolInfo
from app.tools import log_tools, system_tools
from app.tools.base import ToolContext, ToolDefinition, error


def _object_schema(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


def build_registry() -> dict[str, ToolDefinition]:
    tools = [
        ToolDefinition(
            name="docker_health",
            description="检查 Docker 服务是否可用，返回 Docker 版本、容器数量等基础信息。",
            parameters=_object_schema({}),
            handler=docker_tools.docker_health,
        ),
        ToolDefinition(
            name="list_containers",
            description="列出 Docker 容器，适合排查服务是否运行。",
            parameters=_object_schema({"all": {"type": "boolean", "description": "是否包含已停止容器。", "default": True}}),
            handler=docker_tools.list_containers,
        ),
        ToolDefinition(
            name="deploy_nginx",
            description="部署一个 Nginx Docker 容器，并映射到指定宿主机端口。",
            parameters=_object_schema(
                {
                    "host_port": {"type": "integer", "minimum": 1, "maximum": 65535, "default": 8080},
                    "container_name": {"type": "string", "default": "lightpanel-nginx"},
                    "image": {"type": "string", "default": "nginx:latest"},
                }
            ),
            handler=docker_tools.deploy_nginx,
            destructive=False,
            requires_approval=False,
        ),
        ToolDefinition(
            name="inspect_container",
            description="查看指定 Docker 容器的状态、端口映射和运行详情。",
            parameters=_object_schema({"container_name": {"type": "string"}}, required=["container_name"]),
            handler=docker_tools.inspect_container,
        ),
        ToolDefinition(
            name="get_container_logs",
            description="读取指定 Docker 容器的最近日志。",
            parameters=_object_schema(
                {
                    "container_name": {"type": "string"},
                    "tail": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 120},
                },
                required=["container_name"],
            ),
            handler=docker_tools.get_container_logs,
        ),
        ToolDefinition(
            name="restart_container",
            description="重启指定 Docker 容器。该操作会改变服务状态，需要用户确认。",
            parameters=_object_schema({"container_name": {"type": "string"}}, required=["container_name"]),
            handler=docker_tools.restart_container,
            destructive=False,
            requires_approval=False,
        ),
        ToolDefinition(
            name="stop_container",
            description="停止指定 Docker 容器。该操作会改变服务状态，需要用户确认。",
            parameters=_object_schema({"container_name": {"type": "string"}}, required=["container_name"]),
            handler=docker_tools.stop_container,
            destructive=True,
            requires_approval=True,
        ),
        ToolDefinition(
            name="get_system_status",
            description="采集当前系统 CPU、内存、磁盘等资源状态。",
            parameters=_object_schema({}),
            handler=system_tools.get_system_status,
        ),
        ToolDefinition(
            name="check_port",
            description="检查宿主机端口是否被占用，并返回占用进程信息。",
            parameters=_object_schema({"port": {"type": "integer", "minimum": 1, "maximum": 65535}}, required=["port"]),
            handler=system_tools.check_port,
        ),
        ToolDefinition(
            name="read_log_tail",
            description="读取允许目录下的日志文件尾部内容。",
            parameters=_object_schema(
                {
                    "path": {"type": "string"},
                    "lines": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 120},
                },
                required=["path"],
            ),
            handler=log_tools.read_log_tail,
        ),
        ToolDefinition(
            name="analyze_log_text",
            description="对用户粘贴的日志文本做规则分析，识别端口冲突、权限、数据库、超时等常见问题。",
            parameters=_object_schema({"log_text": {"type": "string"}}, required=["log_text"]),
            handler=log_tools.analyze_log_text,
        ),
    ]
    return {tool.name: tool for tool in tools}


class ToolRegistry:
    def __init__(self) -> None:
        self._tools = build_registry()

    def list_infos(self) -> list[ToolInfo]:
        return [
            ToolInfo(
                name=tool.name,
                description=tool.description,
                destructive=tool.destructive,
                requires_approval=tool.requires_approval,
                parameters=tool.parameters,
            )
            for tool in self._tools.values()
        ]

    def openai_tools(self) -> list[dict[str, Any]]:
        return [tool.as_openai_tool() for tool in self._tools.values()]

    def execute(self, tool_name: str, arguments: dict[str, Any] | None, ctx: ToolContext) -> ToolCallRecord:
        tool = self._tools.get(tool_name)
        args = arguments or {}
        if not tool:
            result = error("未知工具。", tool_name=tool_name)
            return ToolCallRecord(tool_name=tool_name, arguments=args, status="error", summary=result["summary"], data=result["data"])
        try:
            result = tool.handler(ctx=ctx, **args)
        except TypeError as exc:
            result = error("工具参数不匹配。", detail=str(exc), arguments=args)
        except Exception as exc:  # noqa: BLE001 - tools must not crash the agent loop.
            result = error("工具执行异常。", detail=str(exc), arguments=args)
        status = result.get("status", "error")
        return ToolCallRecord(
            tool_name=tool_name,
            arguments=args,
            status=status if status in {"success", "error", "approval_required", "skipped"} else "error",
            summary=result.get("summary", ""),
            data=result.get("data", {}),
            destructive=tool.destructive,
            requires_approval=tool.requires_approval,
        )
