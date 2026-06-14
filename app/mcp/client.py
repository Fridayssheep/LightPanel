"""用于和 MCP 工具服务通信的客户端。"""
from __future__ import annotations

import json
import os
import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Callable

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.types import ContentBlock

from app.schemas import ToolCallRecord, ToolInfo
from app.tools.base import ToolContext, approval_required, error, skipped


# 策略元数据放在客户端侧，避免模型通过改变 MCP schema 绕过审批规则。
TOOL_METADATA = {
    "docker_health": {"destructive": False, "requires_approval": False},
    "list_containers": {"destructive": False, "requires_approval": False},
    "docker_overview": {"destructive": False, "requires_approval": False},
    "deploy_nginx": {"destructive": True, "requires_approval": False},
    "inspect_container": {"destructive": False, "requires_approval": False},
    "get_container_logs": {"destructive": False, "requires_approval": False},
    "start_container": {"destructive": True, "requires_approval": False},
    "create_container": {"destructive": True, "requires_approval": False},
    "restart_container": {"destructive": True, "requires_approval": False},
    "stop_container": {"destructive": True, "requires_approval": True},
    "update_container": {"destructive": True, "requires_approval": False},
    "pause_container": {"destructive": True, "requires_approval": False},
    "unpause_container": {"destructive": True, "requires_approval": False},
    "delete_container": {"destructive": True, "requires_approval": True},
    "process_container": {"destructive": False, "requires_approval": False},
    "list_images": {"destructive": False, "requires_approval": False},
    "pull_image": {"destructive": True, "requires_approval": False},
    "remove_image": {"destructive": True, "requires_approval": True},
    "prune_images": {"destructive": True, "requires_approval": True},
    "tag_image": {"destructive": True, "requires_approval": False},
    "untag_image": {"destructive": True, "requires_approval": False},
    "import_image": {"destructive": True, "requires_approval": False},
    "export_image": {"destructive": False, "requires_approval": False},
    "list_networks": {"destructive": False, "requires_approval": False},
    "inspect_network": {"destructive": False, "requires_approval": False},
    "create_network": {"destructive": True, "requires_approval": False},
    "remove_network": {"destructive": True, "requires_approval": True},
    "prune_networks": {"destructive": True, "requires_approval": True},
    "connect_network": {"destructive": True, "requires_approval": False},
    "disconnect_network": {"destructive": True, "requires_approval": False},
    "list_volumes": {"destructive": False, "requires_approval": False},
    "inspect_volume": {"destructive": False, "requires_approval": False},
    "create_volume": {"destructive": True, "requires_approval": False},
    "remove_volume": {"destructive": True, "requires_approval": True},
    "prune_volumes": {"destructive": True, "requires_approval": True},
    "list_compose_projects": {"destructive": False, "requires_approval": False},
    "read_compose_file": {"destructive": False, "requires_approval": False},
    "write_compose_file": {"destructive": True, "requires_approval": True},
    "create_compose_project": {"destructive": True, "requires_approval": True},
    "create_compose_project_from_url": {"destructive": True, "requires_approval": True},
    "create_compose_project_from_git": {"destructive": True, "requires_approval": True},
    "compose_up": {"destructive": True, "requires_approval": False},
    "compose_stop": {"destructive": True, "requires_approval": True},
    "compose_restart": {"destructive": True, "requires_approval": False},
    "compose_pull": {"destructive": True, "requires_approval": False},
    "compose_update": {"destructive": True, "requires_approval": False},
    "compose_down": {"destructive": True, "requires_approval": True},
    "compose_service_up": {"destructive": True, "requires_approval": False},
    "compose_service_stop": {"destructive": True, "requires_approval": True},
    "compose_service_restart": {"destructive": True, "requires_approval": False},
    "get_compose_logs": {"destructive": False, "requires_approval": False},
    "get_compose_service_logs": {"destructive": False, "requires_approval": False},
    "get_runtime_settings": {"destructive": False, "requires_approval": False},
    "update_runtime_settings": {"destructive": True, "requires_approval": True},
    "get_system_status": {"destructive": False, "requires_approval": False},
    "check_port": {"destructive": False, "requires_approval": False},
    "read_log_tail": {"destructive": False, "requires_approval": False},
    "analyze_log_text": {"destructive": False, "requires_approval": False},
}


@dataclass(frozen=True)
class ExternalMCPServerConfig:
    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    cwd: str | None = None
    description: str = ""


class MCPToolClient:
    """带策略校验的 MCP 工具服务客户端封装。"""

    def __init__(self, server_script_path: Path, external_config_provider: Callable[[], str] | None = None) -> None:
        self.server_script_path = server_script_path
        self.external_config_provider = external_config_provider
        self._cached_tools: list[dict[str, Any]] | None = None

    @asynccontextmanager
    async def session(self, ctx: ToolContext | None = None) -> AsyncIterator[ClientSession]:
        """模型上下文协议客户端会话管理器。"""
        ctx = ctx or ToolContext()
        # 每次聊天请求使用新的 server 进程，并通过环境变量传递审批和 dry-run。
        server_params = StdioServerParameters(
            command=sys.executable,
            args=[str(self.server_script_path)],
            env={
                "LIGHTPANEL_TOOL_APPROVE_ACTIONS": "true" if ctx.approve_actions else "false",
                "LIGHTPANEL_TOOL_DRY_RUN": "true" if ctx.dry_run else "false",
            },
        )
        async with stdio_client(server_params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                yield session

    @asynccontextmanager
    async def external_session(self, config: ExternalMCPServerConfig) -> AsyncIterator[ClientSession]:
        server_params = StdioServerParameters(
            command=config.command,
            args=config.args,
            env={**os.environ, **config.env},
            cwd=config.cwd,
        )
        async with stdio_client(server_params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                yield session

    def clear_cache(self) -> None:
        self._cached_tools = None

    async def list_tools_info(self) -> list[ToolInfo]:
        """列出工具及其元数据。"""
        tools_info: list[ToolInfo] = []
        async with self.session() as session:
            response = await session.list_tools()
            for tool in response.tools:
                meta = TOOL_METADATA.get(tool.name, {})
                tools_info.append(
                    ToolInfo(
                        name=tool.name,
                        description=tool.description or "",
                        destructive=meta.get("destructive", False),
                        requires_approval=meta.get("requires_approval", False),
                        parameters=tool.inputSchema or {},
                    )
                )
        tools_info.extend(await self._list_external_tools_info())
        return tools_info

    async def list_openai_tools(self) -> list[dict[str, Any]]:
        """按 OpenAI tool calling 格式列出工具。"""
        if self._cached_tools:
            # 工具 schema 在进程内是静态的，缓存后可避免反复启动 MCP。
            return self._cached_tools

        async with self.session() as session:
            response = await session.list_tools()
            openai_tools = []
            for tool in response.tools:
                openai_tools.append(
                    {
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description or "",
                            "parameters": tool.inputSchema or {},
                        },
                    }
                )
        external_tools = await self._list_external_tools_info()
        for tool in external_tools:
            openai_tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    },
                }
            )
        self._cached_tools = openai_tools
        return openai_tools

    async def execute_tool(
        self,
        session: ClientSession | None,
        tool_name: str,
        arguments: dict[str, Any],
        ctx: ToolContext,
    ) -> ToolCallRecord:
        """
        Execute a tool with policy enforcement (approval + dry_run).

        This is the policy layer: checks metadata and context before calling MCP server.
        """
        external_match = self._resolve_external_tool(tool_name)
        if external_match:
            config, external_tool_name = external_match
            return await self._execute_external_tool(config, external_tool_name, tool_name, arguments)

        meta = TOOL_METADATA.get(tool_name, {})
        destructive = meta.get("destructive", False)
        requires_approval = meta.get("requires_approval", False)

        # 策略：试运行会跳过破坏性工具。
        if ctx.dry_run and destructive:
            result = skipped("dry_run 已开启，未真正执行该操作。", **arguments)
            return ToolCallRecord(
                tool_name=tool_name,
                arguments=arguments,
                status="skipped",
                summary=result["summary"],
                data=result["data"],
                destructive=destructive,
                requires_approval=requires_approval,
            )

        # 策略：部分工具必须有用户确认。
        if requires_approval and not ctx.approve_actions:
            result = approval_required("该操作需要用户确认。", **arguments)
            return ToolCallRecord(
                tool_name=tool_name,
                arguments=arguments,
                status="approval_required",
                summary=result["summary"],
                data=result["data"],
                destructive=destructive,
                requires_approval=requires_approval,
            )

        # 策略检查通过后再经 MCP 执行；server 侧 handler 仍会做自身校验。
        try:
            if session is None:
                result = error("内置工具调用缺少 MCP 会话。")
                status = "error"
            else:
                response = await session.call_tool(tool_name, arguments=arguments)
                if not response.content:
                    result = error("工具返回为空。")
                    status = "error"
                else:
                    # 解析 MCP 响应；本项目服务端应返回 JSON 字符串。
                    content_text = response.content[0].text if response.content else "{}"
                    result = json.loads(content_text)
                    status = result.get("status", "error")
        except json.JSONDecodeError:
            result = error("工具返回格式错误。", raw_response=content_text)
            status = "error"
        except Exception as exc:
            result = error("MCP 工具调用失败。", detail=str(exc))
            status = "error"

        return ToolCallRecord(
            tool_name=tool_name,
            arguments=arguments,
            status=status if status in {"success", "error", "approval_required", "skipped"} else "error",
            summary=result.get("summary", ""),
            data=result.get("data", {}),
            destructive=destructive,
            requires_approval=requires_approval,
        )

    async def _execute_external_tool(
        self,
        config: ExternalMCPServerConfig,
        external_tool_name: str,
        public_tool_name: str,
        arguments: dict[str, Any],
    ) -> ToolCallRecord:
        try:
            async with self.external_session(config) as session:
                response = await session.call_tool(external_tool_name, arguments=arguments)
            content = [_content_block_to_data(item) for item in response.content]
            if len(content) == 1:
                content_data: Any = content[0]
            else:
                content_data = content
            result = {"status": "success", "summary": f"外部 MCP 工具 {public_tool_name} 已执行。", "data": {"content": content_data}}
            status = "success"
        except Exception as exc:  # noqa: BLE001 - external MCP servers must not break the agent loop.
            result = error("外部 MCP 工具调用失败。", server=config.name, tool=external_tool_name, detail=str(exc))
            status = "error"

        return ToolCallRecord(
            tool_name=public_tool_name,
            arguments=arguments,
            status=status,
            summary=result["summary"],
            data=result["data"],
            destructive=False,
            requires_approval=False,
        )

    async def _list_external_tools_info(self) -> list[ToolInfo]:
        tools_info: list[ToolInfo] = []
        for config in self._external_configs():
            try:
                async with self.external_session(config) as session:
                    response = await session.list_tools()
            except Exception:
                continue
            for tool in response.tools:
                if not _is_safe_external_tool_name(tool.name):
                    continue
                public_name = f"{config.name}__{tool.name}"
                if len(public_name) > 64:
                    continue
                prefix = f"[外部 MCP:{config.name}]"
                server_description = f"{config.description} " if config.description else ""
                tools_info.append(
                    ToolInfo(
                        name=public_name,
                        description=f"{prefix} {server_description}{tool.description or ''}".strip(),
                        destructive=False,
                        requires_approval=False,
                        parameters=tool.inputSchema or {},
                    )
                )
        return tools_info

    def _external_configs(self) -> list[ExternalMCPServerConfig]:
        if not self.external_config_provider:
            return []
        return parse_external_mcp_servers(self.external_config_provider())

    def _resolve_external_tool(self, public_tool_name: str) -> tuple[ExternalMCPServerConfig, str] | None:
        for config in self._external_configs():
            prefix = f"{config.name}__"
            if public_tool_name.startswith(prefix):
                return config, public_tool_name.removeprefix(prefix)
        return None


def parse_external_mcp_servers(raw: str | None) -> list[ExternalMCPServerConfig]:
    if not raw or not raw.strip():
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, dict):
        return []

    configs: list[ExternalMCPServerConfig] = []
    for name, value in payload.items():
        if not isinstance(name, str) or not _is_safe_external_server_name(name) or not isinstance(value, dict):
            continue
        command = value.get("command")
        if not isinstance(command, str) or not command.strip():
            continue
        args = value.get("args", [])
        if not isinstance(args, list):
            args = []
        env = value.get("env", {})
        if not isinstance(env, dict):
            env = {}
        cwd = value.get("cwd")
        description = value.get("description", "")
        configs.append(
            ExternalMCPServerConfig(
                name=name,
                command=command.strip(),
                args=[str(item) for item in args],
                env={str(key): str(item) for key, item in env.items()},
                cwd=str(cwd) if cwd else None,
                description=str(description) if description else "",
            )
        )
    return configs


def _is_safe_external_server_name(name: str) -> bool:
    return bool(name) and all(char.isalnum() or char in {"_", "-"} for char in name)


def _is_safe_external_tool_name(name: str) -> bool:
    return bool(name) and all(char.isalnum() or char in {"_", "-"} for char in name)


def _content_block_to_data(content: ContentBlock) -> Any:
    if getattr(content, "type", None) == "text":
        text = getattr(content, "text", "")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
    model_dump = getattr(content, "model_dump", None)
    if callable(model_dump):
        return model_dump(mode="json")
    return str(content)
