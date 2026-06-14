from __future__ import annotations

import platform
import socket
from pathlib import Path
from typing import Any

import psutil

from app.tools.base import ToolContext, error, success

# 预热 cpu_percent：首次调用 interval=None 返回 0.0，之后才有意义
psutil.cpu_percent(interval=None)


def get_system_status(ctx: ToolContext | None = None) -> dict[str, Any]:
    cpu = psutil.cpu_percent(interval=None)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage(str(Path.cwd()))
    return success(
        "系统资源状态已采集。",
        platform=platform.platform(),
        cpu_percent=cpu,
        memory_percent=memory.percent,
        memory_available_mb=round(memory.available / 1024 / 1024, 2),
        disk_percent=disk.percent,
        disk_free_gb=round(disk.free / 1024 / 1024 / 1024, 2),
    )


def check_port(port: int, ctx: ToolContext | None = None) -> dict[str, Any]:
    if port < 1 or port > 65535:
        return error("端口号必须在 1 到 65535 之间。", port=port)
    listeners = []
    try:
        connections = psutil.net_connections(kind="inet")
    except psutil.AccessDenied:
        occupied = _probe_tcp_port(port)
        summary = f"端口 {port} 当前被占用，但当前权限无法读取占用进程详情。" if occupied else f"端口 {port} 当前未被占用。"
        return success(
            summary,
            port=port,
            occupied=occupied,
            listeners=[],
            probe_method="tcp_connect",
            process_details_available=False,
        )
    for conn in connections:
        if not conn.laddr or conn.laddr.port != port:
            continue
        process_name = None
        if conn.pid:
            try:
                process_name = psutil.Process(conn.pid).name()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                process_name = "unknown"
        listeners.append(
            {
                "pid": conn.pid,
                "process_name": process_name,
                "status": conn.status,
                "address": conn.laddr.ip,
                "port": conn.laddr.port,
            }
        )
    if listeners:
        return success(f"端口 {port} 当前被占用。", port=port, occupied=True, listeners=listeners)
    return success(f"端口 {port} 当前未被占用。", port=port, occupied=False, listeners=[])


def _probe_tcp_port(port: int) -> bool:
    for host in ("127.0.0.1", "::1"):
        family = socket.AF_INET6 if ":" in host else socket.AF_INET
        with socket.socket(family, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.3)
            if sock.connect_ex((host, port)) == 0:
                return True
    return False
