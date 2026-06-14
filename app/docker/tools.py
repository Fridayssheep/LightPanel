from __future__ import annotations

from typing import Any

import docker
from docker.errors import DockerException, NotFound

from app.tools.base import ToolContext, error, skipped, success


def _client():
    return docker.from_env()


def docker_available() -> bool:
    try:
        client = _client()
        client.ping()
        return True
    except DockerException:
        return False


def docker_health(ctx: ToolContext | None = None) -> dict[str, Any]:
    try:
        client = _client()
        info = client.info()
        return success(
            "Docker 服务可用。",
            server_version=info.get("ServerVersion"),
            containers=info.get("Containers"),
            images=info.get("Images"),
            operating_system=info.get("OperatingSystem"),
        )
    except DockerException as exc:
        return error("Docker 服务不可用。", detail=str(exc))


def list_containers(all: bool = True, ctx: ToolContext | None = None) -> dict[str, Any]:
    try:
        client = _client()
        containers = []
        for container in client.containers.list(all=all):
            attrs = container.attrs
            ports = attrs.get("NetworkSettings", {}).get("Ports", {})
            containers.append(
                {
                    "id": container.short_id,
                    "name": container.name,
                    "image": attrs.get("Config", {}).get("Image"),
                    "status": container.status,
                    "ports": ports,
                    "created": attrs.get("Created"),
                }
            )
        return success(f"已获取 {len(containers)} 个容器。", containers=containers)
    except DockerException as exc:
        return error("读取 Docker 容器失败。", detail=str(exc))


def deploy_nginx(
    host_port: int = 8080,
    container_name: str = "lightpanel-nginx",
    image: str = "nginx:latest",
    ctx: ToolContext | None = None,
) -> dict[str, Any]:
    ctx = ctx or ToolContext()
    if host_port < 1 or host_port > 65535:
        return error("端口号必须在 1 到 65535 之间。", host_port=host_port)
    if ctx.dry_run:
        return skipped("dry_run 已开启，未真正创建容器。", image=image, host_port=host_port, container_name=container_name)
    try:
        client = _client()
        try:
            existing = client.containers.get(container_name)
            if existing.status != "running":
                existing.start()
            return success(
                f"容器 {container_name} 已存在，已确认处于运行状态。",
                container_id=existing.short_id,
                name=existing.name,
                status=existing.status,
                url=f"http://127.0.0.1:{host_port}",
            )
        except NotFound:
            pass
        container = client.containers.run(
            image,
            detach=True,
            name=container_name,
            ports={"80/tcp": host_port},
            labels={"managed-by": "lightpanel"},
        )
        return success(
            f"已部署 Nginx 容器 {container_name}。",
            container_id=container.short_id,
            name=container.name,
            image=image,
            host_port=host_port,
            url=f"http://127.0.0.1:{host_port}",
        )
    except DockerException as exc:
        return error("部署 Nginx 容器失败。", detail=str(exc), image=image, host_port=host_port, container_name=container_name)


def inspect_container(container_name: str, ctx: ToolContext | None = None) -> dict[str, Any]:
    try:
        container = _client().containers.get(container_name)
        attrs = container.attrs
        state = attrs.get("State", {})
        network = attrs.get("NetworkSettings", {})
        return success(
            f"已读取容器 {container_name} 详情。",
            id=container.short_id,
            name=container.name,
            image=attrs.get("Config", {}).get("Image"),
            status=container.status,
            state=state,
            ports=network.get("Ports"),
            ip_address=network.get("IPAddress"),
        )
    except NotFound:
        return error("容器不存在。", container_name=container_name)
    except DockerException as exc:
        return error("读取容器详情失败。", detail=str(exc), container_name=container_name)


def get_container_logs(container_name: str, tail: int = 120, ctx: ToolContext | None = None) -> dict[str, Any]:
    safe_tail = max(1, min(tail, 1000))
    try:
        container = _client().containers.get(container_name)
        raw = container.logs(tail=safe_tail, stdout=True, stderr=True)
        content = raw.decode("utf-8", errors="replace")
        return success(
            f"已读取容器 {container_name} 日志尾部。",
            container_name=container_name,
            tail=safe_tail,
            content=content[-12000:],
        )
    except NotFound:
        return error("容器不存在。", container_name=container_name)
    except DockerException as exc:
        return error("读取容器日志失败。", detail=str(exc), container_name=container_name)


def restart_container(container_name: str, ctx: ToolContext | None = None) -> dict[str, Any]:
    ctx = ctx or ToolContext()
    if ctx.dry_run:
        return skipped("dry_run 已开启，未真正重启容器。", container_name=container_name)
    try:
        container = _client().containers.get(container_name)
        container.restart(timeout=5)
        container.reload()
        return success(f"容器 {container_name} 已重启。", container_name=container_name, status=container.status)
    except NotFound:
        return error("容器不存在。", container_name=container_name)
    except DockerException as exc:
        return error("重启容器失败。", detail=str(exc), container_name=container_name)


def stop_container(container_name: str, ctx: ToolContext | None = None) -> dict[str, Any]:
    ctx = ctx or ToolContext()
    if ctx.dry_run:
        return skipped("dry_run 已开启，未真正停止容器。", container_name=container_name)
    try:
        container = _client().containers.get(container_name)
        container.stop(timeout=5)
        container.reload()
        return success(f"容器 {container_name} 已停止。", container_name=container_name, status=container.status)
    except NotFound:
        return error("容器不存在。", container_name=container_name)
    except DockerException as exc:
        return error("停止容器失败。", detail=str(exc), container_name=container_name)
