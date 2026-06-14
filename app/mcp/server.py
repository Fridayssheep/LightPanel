"""通过 Model Context Protocol 暴露 Docker 和系统工具的 MCP 服务端。"""
from __future__ import annotations

import json
import os
import sys
from typing import Any

import jsonschema
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from app.docker import tools as docker_tools
from app.tools import log_tools, ops_tools, system_tools
from app.tools.base import ToolContext


mcp_server = Server("ops-agent-mcp-server")
public_mcp_server = Server("ops-agent-public-mcp-server")


def object_schema(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


def tool(name: str, description: str, properties: dict[str, Any], required: list[str] | None = None) -> Tool:
    return Tool(
        name=name,
        description=description,
        inputSchema=object_schema(properties, required),
    )


# 复用 schema 片段，保证多个 MCP 工具的参数描述一致。
CONTAINER_NAME = {"type": "string", "description": "容器名称或容器 ID。"}
COMPOSE_PATH = {"type": "string", "description": "允许项目目录内的 Compose 文件绝对路径。"}
IMAGE_NAME = {"type": "string", "description": "镜像名、镜像 ID 或 tag，例如 nginx:latest。"}
NETWORK_NAME = {"type": "string", "description": "Docker 网络名称或 ID。"}
VOLUME_NAME = {"type": "string", "description": "Docker 卷名称。"}
SERVICE_NAME = {"type": "string", "description": "Compose service 名称。"}
LINUX_CAPABILITY_NAMES = [
    "AUDIT_WRITE",
    "CHOWN",
    "DAC_OVERRIDE",
    "FOWNER",
    "FSETID",
    "KILL",
    "MKNOD",
    "NET_BIND_SERVICE",
    "NET_RAW",
    "SETFCAP",
    "SETGID",
    "SETPCAP",
    "SETUID",
    "SYS_CHROOT",
    "AUDIT_CONTROL",
    "AUDIT_READ",
    "BLOCK_SUSPEND",
    "BPF",
    "CHECKPOINT_RESTORE",
    "DAC_READ_SEARCH",
    "IPC_LOCK",
    "IPC_OWNER",
    "LEASE",
    "LINUX_IMMUTABLE",
    "MAC_ADMIN",
    "MAC_OVERRIDE",
    "NET_ADMIN",
    "NET_BROADCAST",
    "PERFMON",
    "SYS_ADMIN",
    "SYS_BOOT",
    "SYS_MODULE",
    "SYS_NICE",
    "SYS_PACCT",
    "SYS_PTRACE",
    "SYS_RAWIO",
    "SYS_RESOURCE",
    "SYS_TIME",
    "SYS_TTY_CONFIG",
    "SYSLOG",
    "WAKE_ALARM",
]


ENV_VAR_SCHEMA = {
    "type": "object",
    "properties": {
        "key": {"type": "string", "description": "环境变量名。"},
        "value": {"type": "string", "description": "环境变量值。"},
    },
    "required": ["key"],
    "additionalProperties": False,
}

PORT_BINDING_SCHEMA = {
    "type": "object",
    "properties": {
        "container_port": {"type": "string", "description": "容器端口，例如 80 或 80/tcp。"},
        "host_port": {"type": "string", "description": "宿主机端口，可留空让 Docker 自动分配。"},
        "protocol": {"type": "string", "enum": ["tcp", "udp", "tcp/udp"], "default": "tcp"},
        "host_ip": {"type": "string", "default": "0.0.0.0"},
    },
    "required": ["container_port"],
    "additionalProperties": False,
}

VOLUME_MOUNT_SCHEMA = {
    "type": "object",
    "properties": {
        "host_path": {"type": "string", "description": "宿主机路径。"},
        "container_path": {"type": "string", "description": "容器内路径。"},
        "mode": {"type": "string", "enum": ["rw", "ro"], "default": "rw"},
    },
    "required": ["host_path", "container_path"],
    "additionalProperties": False,
}

COMPOSE_FILENAME = {
    "type": "string",
    "enum": ["compose.yaml", "compose.yml", "docker-compose.yml", "docker-compose.yaml"],
    "default": "compose.yaml",
}


@mcp_server.list_tools()
async def list_tools() -> list[Tool]:
    """列出所有可用工具。"""
    return build_tool_list()


@public_mcp_server.list_tools()
async def list_public_tools() -> list[Tool]:
    """列出公开 HTTP MCP 入口可用的工具。"""
    return build_tool_list()


def build_tool_list() -> list[Tool]:
    return [
        tool("docker_health", "检查 Docker 服务是否可用，返回 Docker 版本、容器数量等基础信息。", {}),
        tool(
            "list_containers",
            "列出 Docker 容器，适合排查服务是否运行。",
            {"all": {"type": "boolean", "description": "是否包含已停止容器。", "default": True}},
        ),
        tool(
            "docker_overview",
            "读取 Docker 控制台总览，包含容器运行分布、Compose 项目数量、宿主内存总量以及各容器 CPU/内存占用。",
            {},
        ),
        tool(
            "deploy_nginx",
            "部署一个 Nginx Docker 容器，并映射到指定宿主机端口。",
            {
                "host_port": {"type": "integer", "minimum": 1, "maximum": 65535, "default": 8080},
                "container_name": {"type": "string", "default": "ops-agent-nginx"},
                "image": {"type": "string", "default": "nginx:latest"},
            },
        ),
        tool("inspect_container", "读取指定 Docker 容器的完整 inspect 信息。", {"container_name": CONTAINER_NAME}, ["container_name"]),
        tool(
            "get_container_logs",
            "读取指定 Docker 容器的最近日志。",
            {
                "container_name": CONTAINER_NAME,
                "tail": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 120},
            },
            ["container_name"],
        ),
        tool(
            "create_container",
            "按镜像创建一个 Docker 容器，可配置名称、命令、端口、环境变量、挂载、网络和重启策略。",
            {
                "image": IMAGE_NAME,
                "name": {"type": "string", "description": "容器名称，留空则由 Docker 自动生成。"},
                "command": {"type": "string", "description": "覆盖镜像默认启动命令。"},
                "env": {"type": "array", "items": ENV_VAR_SCHEMA, "default": []},
                "ports": {"type": "array", "items": PORT_BINDING_SCHEMA, "default": []},
                "volumes": {"type": "array", "items": VOLUME_MOUNT_SCHEMA, "default": []},
                "restart_policy": {
                    "type": "string",
                    "enum": ["no", "on-failure", "always", "unless-stopped"],
                    "default": "unless-stopped",
                },
                "network": {"type": "string", "description": "Docker 网络名。"},
                "privileged": {"type": "boolean", "default": False},
                "cap_add": {
                    "type": "array",
                    "items": {"type": "string", "enum": LINUX_CAPABILITY_NAMES},
                    "default": [],
                    "description": "额外添加的 Linux capability，支持 Docker run 文档中的默认能力和可额外授予能力。privileged=true 时通常不需要设置。",
                },
                "resource_limits_enabled": {"type": "boolean", "default": False, "description": "是否启用容器资源限制。"},
                "cpu_priority": {
                    "type": "integer",
                    "minimum": 2,
                    "maximum": 262144,
                    "description": "CPU 相对优先顺序，对应 Docker cpu_shares。数值越大，相对优先级越高。",
                },
                "memory_limit_mb": {
                    "type": "integer",
                    "minimum": 4,
                    "maximum": 4194304,
                    "description": "内存上限，单位 MB。",
                },
                "pull_if_missing": {"type": "boolean", "default": True},
                "start": {"type": "boolean", "default": True},
            },
            ["image"],
        ),
        tool("start_container", "启动指定 Docker 容器。", {"container_name": CONTAINER_NAME}, ["container_name"]),
        tool("restart_container", "重启指定 Docker 容器。", {"container_name": CONTAINER_NAME}, ["container_name"]),
        tool("stop_container", "停止指定 Docker 容器。该操作需要用户确认。", {"container_name": CONTAINER_NAME}, ["container_name"]),
        tool("pause_container", "暂停指定 Docker 容器。", {"container_name": CONTAINER_NAME}, ["container_name"]),
        tool("unpause_container", "恢复已暂停的 Docker 容器。", {"container_name": CONTAINER_NAME}, ["container_name"]),
        tool("delete_container", "删除指定 Docker 容器。该操作需要用户确认。", {"container_name": CONTAINER_NAME}, ["container_name"]),
        tool("process_container", "查看指定 Docker 容器内的进程列表。", {"container_name": CONTAINER_NAME}, ["container_name"]),
        tool(
            "update_container",
            "更新 Compose 管理的容器所属服务，会拉取镜像并重建该 service。",
            {"container_name": CONTAINER_NAME},
            ["container_name"],
        ),
        tool("list_images", "列出本机 Docker 镜像，包含 tag、大小、创建时间和被容器引用的数量。", {}),
        tool("pull_image", "拉取指定 Docker 镜像。", {"image": IMAGE_NAME}, ["image"]),
        tool("remove_image", "删除指定 Docker 镜像。该操作需要用户确认。", {"image": IMAGE_NAME, "force": {"type": "boolean", "default": False}}, ["image"]),
        tool(
            "prune_images",
            "清理 Docker 镜像。默认只清理悬空镜像；关闭 dangling_only 会清理所有未使用镜像。该操作需要用户确认。",
            {"dangling_only": {"type": "boolean", "default": True}},
        ),
        tool(
            "tag_image",
            "给已有 Docker 镜像添加 repository:tag 标签。",
            {
                "source": IMAGE_NAME,
                "repository": {"type": "string", "description": "目标 repository，例如 myapp/web。"},
                "tag": {"type": "string", "default": "latest"},
            },
            ["source", "repository"],
        ),
        tool("untag_image", "删除 Docker 镜像的某个 tag。", {"image": IMAGE_NAME}, ["image"]),
        tool("import_image", "从后端可访问的 tar/tar.gz 文件路径导入 Docker 镜像。", {"path": {"type": "string"}}, ["path"]),
        tool(
            "export_image",
            "把 Docker 镜像导出为后端 data/exports 或指定目录下的 tar 文件。",
            {"image": IMAGE_NAME, "output_dir": {"type": "string"}},
            ["image"],
        ),
        tool("list_networks", "列出 Docker 网络。", {}),
        tool("inspect_network", "查看 Docker 网络完整详情。", {"name": NETWORK_NAME}, ["name"]),
        tool(
            "create_network",
            "创建 Docker 网络。",
            {
                "name": NETWORK_NAME,
                "driver": {"type": "string", "enum": ["bridge", "macvlan", "ipvlan", "overlay"], "default": "bridge"},
                "subnet": {"type": "string"},
                "gateway": {"type": "string"},
                "internal": {"type": "boolean", "default": False},
                "attachable": {"type": "boolean", "default": False},
            },
            ["name"],
        ),
        tool("remove_network", "删除 Docker 网络。该操作需要用户确认。", {"name": NETWORK_NAME}, ["name"]),
        tool("prune_networks", "清理未使用的 Docker 网络。该操作需要用户确认。", {}),
        tool(
            "connect_network",
            "把容器连接到指定 Docker 网络。",
            {"name": NETWORK_NAME, "container": CONTAINER_NAME},
            ["name", "container"],
        ),
        tool(
            "disconnect_network",
            "把容器从指定 Docker 网络断开。",
            {"name": NETWORK_NAME, "container": CONTAINER_NAME},
            ["name", "container"],
        ),
        tool("list_volumes", "列出 Docker 卷，并显示被哪些容器使用。", {}),
        tool("inspect_volume", "查看 Docker 卷完整详情。", {"name": VOLUME_NAME}, ["name"]),
        tool(
            "create_volume",
            "创建 Docker 卷。",
            {"name": VOLUME_NAME, "driver": {"type": "string", "default": "local"}},
            ["name"],
        ),
        tool(
            "remove_volume",
            "删除 Docker 卷。该操作需要用户确认。",
            {"name": VOLUME_NAME, "force": {"type": "boolean", "default": False}},
            ["name"],
        ),
        tool("prune_volumes", "清理未使用的 Docker 卷。该操作需要用户确认。", {}),
        tool("list_compose_projects", "扫描允许目录下的 Compose 文件，并合并 Docker socket 中的运行态项目。", {}),
        tool("read_compose_file", "读取允许项目目录内的 Compose 文件内容。", {"path": COMPOSE_PATH}, ["path"]),
        tool(
            "write_compose_file",
            "保存允许项目目录内的 Compose 文件内容。该操作需要用户确认。",
            {"path": COMPOSE_PATH, "content": {"type": "string", "maxLength": 200000}},
            ["path", "content"],
        ),
        tool(
            "create_compose_project",
            "在允许项目目录内创建新的 Compose 项目目录和 Compose 文件，然后执行 docker compose up -d。该操作需要用户确认。",
            {
                "project_name": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 120,
                    "description": "Compose 项目名，同时会作为新建子目录名，不能包含路径分隔符。",
                },
                "directory": {
                    "type": "string",
                    "description": "放置项目的允许目录绝对路径，工具会在其中创建 project_name 子目录。",
                },
                "filename": COMPOSE_FILENAME,
                "content": {"type": "string", "minLength": 1, "maxLength": 200000, "description": "Compose YAML 内容。"},
            },
            ["project_name", "directory", "content"],
        ),
        tool(
            "create_compose_project_from_url",
            "从 raw URL 下载 Compose YAML，在允许项目目录内创建项目并执行 up -d。该操作需要用户确认。",
            {
                "project_name": {"type": "string", "minLength": 1, "maxLength": 120},
                "directory": {"type": "string", "description": "放置项目的允许目录绝对路径。"},
                "url": {"type": "string", "description": "可直接返回 Compose YAML 内容的 URL。"},
                "filename": COMPOSE_FILENAME,
            },
            ["project_name", "directory", "url"],
        ),
        tool(
            "create_compose_project_from_git",
            "从 Git 仓库 clone Compose 项目到允许目录并执行 up -d。该操作需要用户确认。",
            {
                "project_name": {"type": "string", "minLength": 1, "maxLength": 120},
                "directory": {"type": "string", "description": "放置项目的允许目录绝对路径。"},
                "repository_url": {"type": "string", "description": "Git 仓库 URL。"},
                "branch": {"type": "string", "description": "可选分支名。"},
                "compose_path": {"type": "string", "default": "compose.yaml", "description": "仓库内 Compose 文件相对路径。"},
            },
            ["project_name", "directory", "repository_url"],
        ),
        tool("compose_up", "对指定 Compose 文件执行 docker compose up -d。", {"path": COMPOSE_PATH}, ["path"]),
        tool("compose_stop", "对指定 Compose 文件执行 docker compose stop。该操作需要用户确认。", {"path": COMPOSE_PATH}, ["path"]),
        tool("compose_restart", "对指定 Compose 文件执行 docker compose restart。", {"path": COMPOSE_PATH}, ["path"]),
        tool("compose_pull", "对指定 Compose 文件执行 docker compose pull。", {"path": COMPOSE_PATH}, ["path"]),
        tool("compose_update", "对指定 Compose 文件执行 docker compose up -d --pull always。", {"path": COMPOSE_PATH}, ["path"]),
        tool("compose_down", "对指定 Compose 文件执行 docker compose down。该操作需要用户确认。", {"path": COMPOSE_PATH}, ["path"]),
        tool("compose_service_up", "对指定 Compose service 执行 up -d。", {"path": COMPOSE_PATH, "service": SERVICE_NAME}, ["path", "service"]),
        tool(
            "compose_service_stop",
            "停止指定 Compose service。该操作需要用户确认。",
            {"path": COMPOSE_PATH, "service": SERVICE_NAME},
            ["path", "service"],
        ),
        tool(
            "compose_service_restart",
            "重启指定 Compose service。",
            {"path": COMPOSE_PATH, "service": SERVICE_NAME},
            ["path", "service"],
        ),
        tool(
            "get_compose_logs",
            "读取指定 Compose 项目下所有容器的最近日志。",
            {
                "project": {"type": "string", "description": "Compose 项目名。"},
                "tail": {"type": "integer", "minimum": 1, "maximum": 2000, "default": 200},
            },
            ["project"],
        ),
        tool(
            "get_compose_service_logs",
            "读取指定 Compose service 的最近日志。",
            {
                "project": {"type": "string", "description": "Compose 项目名。"},
                "service": SERVICE_NAME,
                "tail": {"type": "integer", "minimum": 1, "maximum": 2000, "default": 200},
            },
            ["project", "service"],
        ),
        tool("get_runtime_settings", "读取当前运行时设置，包括扫描目录、日志目录和模型配置状态。", {}),
        tool(
            "update_runtime_settings",
            "更新运行时设置并保存到 data/settings.json。该操作需要用户确认。",
            {
                "log_roots": {"type": "string"},
                "project_roots": {"type": "string"},
                "require_dangerous_approval": {"type": "boolean"},
                "llm_base_url": {"type": "string"},
                "llm_model": {"type": "string"},
                "llm_api_key": {"type": "string"},
                "docker_http_proxy": {"type": "string"},
                "docker_https_proxy": {"type": "string"},
                "docker_no_proxy": {"type": "string"},
                "external_mcp_servers": {"type": "string", "description": "外部 MCP stdio server JSON 配置。"},
                "enable_public_mcp": {"type": "boolean", "description": "是否把内置 MCP server 暴露到 /api/mcp。"},
            },
        ),
        tool("get_system_status", "采集当前系统 CPU、内存、磁盘等资源状态。", {}),
        tool("check_port", "检查宿主机端口是否被占用，并返回占用进程信息。", {"port": {"type": "integer", "minimum": 1, "maximum": 65535}}, ["port"]),
        tool(
            "read_log_tail",
            "读取允许目录下的日志文件尾部内容。",
            {
                "path": {"type": "string"},
                "lines": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 120},
            },
            ["path"],
        ),
        tool("analyze_log_text", "对用户粘贴的日志文本做规则分析，识别端口冲突、权限、数据库、超时等常见问题。", {"log_text": {"type": "string"}}, ["log_text"]),
    ]


TOOL_HANDLERS = {
    "docker_health": docker_tools.docker_health,
    "list_containers": docker_tools.list_containers,
    "docker_overview": ops_tools.docker_overview,
    "deploy_nginx": docker_tools.deploy_nginx,
    "inspect_container": ops_tools.inspect_container,
    "get_container_logs": docker_tools.get_container_logs,
    "create_container": ops_tools.create_container,
    "start_container": ops_tools.start_container,
    "restart_container": docker_tools.restart_container,
    "stop_container": ops_tools.stop_container,
    "update_container": ops_tools.update_container,
    "pause_container": ops_tools.pause_container,
    "unpause_container": ops_tools.unpause_container,
    "delete_container": ops_tools.delete_container,
    "process_container": ops_tools.process_container,
    "list_images": ops_tools.list_images,
    "pull_image": ops_tools.pull_image,
    "remove_image": ops_tools.remove_image,
    "prune_images": ops_tools.prune_images,
    "tag_image": ops_tools.tag_image,
    "untag_image": ops_tools.untag_image,
    "import_image": ops_tools.import_image,
    "export_image": ops_tools.export_image,
    "list_networks": ops_tools.list_networks,
    "inspect_network": ops_tools.inspect_network,
    "create_network": ops_tools.create_network,
    "remove_network": ops_tools.remove_network,
    "prune_networks": ops_tools.prune_networks,
    "connect_network": ops_tools.connect_network,
    "disconnect_network": ops_tools.disconnect_network,
    "list_volumes": ops_tools.list_volumes,
    "inspect_volume": ops_tools.inspect_volume,
    "create_volume": ops_tools.create_volume,
    "remove_volume": ops_tools.remove_volume,
    "prune_volumes": ops_tools.prune_volumes,
    "list_compose_projects": ops_tools.list_compose_projects,
    "read_compose_file": ops_tools.read_compose_file,
    "write_compose_file": ops_tools.write_compose_file,
    "create_compose_project": ops_tools.create_compose_project,
    "create_compose_project_from_url": ops_tools.create_compose_project_from_url,
    "create_compose_project_from_git": ops_tools.create_compose_project_from_git,
    "compose_up": ops_tools.compose_up,
    "compose_stop": ops_tools.compose_stop,
    "compose_restart": ops_tools.compose_restart,
    "compose_pull": ops_tools.compose_pull,
    "compose_update": ops_tools.compose_update,
    "compose_down": ops_tools.compose_down,
    "compose_service_up": ops_tools.compose_service_up,
    "compose_service_stop": ops_tools.compose_service_stop,
    "compose_service_restart": ops_tools.compose_service_restart,
    "get_compose_logs": ops_tools.get_compose_logs,
    "get_compose_service_logs": ops_tools.get_compose_service_logs,
    "get_runtime_settings": ops_tools.get_runtime_settings,
    "update_runtime_settings": ops_tools.update_runtime_settings,
    "get_system_status": system_tools.get_system_status,
    "check_port": system_tools.check_port,
    "read_log_tail": log_tools.read_log_tail,
    "analyze_log_text": log_tools.analyze_log_text,
}


def _env_bool(name: str) -> bool:
    # 当参数里没有私有标记时，CLI 可通过环境变量传递审批和 dry-run。
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """执行工具并返回结果。"""
    return await execute_tool(name, arguments, allow_private_context=True)


@public_mcp_server.call_tool(validate_input=False)
async def call_public_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """执行公开 HTTP MCP 请求，忽略内部审批和 dry-run 私有参数。"""
    return await execute_tool(name, arguments, allow_private_context=False)


async def execute_tool(name: str, arguments: dict[str, Any], *, allow_private_context: bool) -> list[TextContent]:
    handler = TOOL_HANDLERS.get(name)
    if not handler:
        return [TextContent(type="text", text=json.dumps({"status": "error", "summary": f"Unknown tool: {name}", "data": {}}, ensure_ascii=False))]

    arguments = dict(arguments or {})
    # 私有参数由后端 MCP client 注入，不暴露在公开工具 schema 中。
    if allow_private_context:
        ctx = ToolContext(
            approve_actions=bool(arguments.pop("_approve_actions", _env_bool("OPS_AGENT_TOOL_APPROVE_ACTIONS"))),
            dry_run=bool(arguments.pop("_dry_run", _env_bool("OPS_AGENT_TOOL_DRY_RUN"))),
        )
    else:
        arguments.pop("_approve_actions", None)
        arguments.pop("_dry_run", None)
        validation_error = validate_tool_arguments(name, arguments)
        if validation_error:
            return [TextContent(type="text", text=json.dumps(validation_error, ensure_ascii=False))]
        ctx = ToolContext()

    try:
        result = handler(ctx=ctx, **arguments)
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]
    except Exception as exc:  # noqa: BLE001 - tools must not crash the MCP session.
        error_result = {
            "status": "error",
            "summary": f"工具执行异常：{exc}",
            "data": {"tool_name": name, "arguments": arguments},
        }
        return [TextContent(type="text", text=json.dumps(error_result, ensure_ascii=False))]


def validate_tool_arguments(name: str, arguments: dict[str, Any]) -> dict[str, Any] | None:
    schema = next((item.inputSchema for item in build_tool_list() if item.name == name), None)
    if not schema:
        return None
    try:
        jsonschema.validate(instance=arguments, schema=schema)
    except jsonschema.ValidationError as exc:
        return {
            "status": "error",
            "summary": f"参数校验失败：{exc.message}",
            "data": {"tool_name": name, "arguments": arguments},
        }
    return None


async def main():
    """通过 stdio 运行 MCP 服务端。"""
    async with stdio_server() as (read_stream, write_stream):
        await mcp_server.run(
            read_stream,
            write_stream,
            mcp_server.create_initialization_options(),
        )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
