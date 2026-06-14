from __future__ import annotations

import json
import os
import select
import subprocess
import time
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

import docker
import httpx
from docker.errors import DockerException, ImageNotFound, NotFound

from app.config import Settings, save_runtime_settings_file
from app.docker.compose_scanner import COMPOSE_FILENAMES
from app.schemas import (
    ComposeCreateRequest,
    ComposeGitCreateRequest,
    ComposeFileResponse,
    ComposeUrlCreateRequest,
    ContainerInspectResponse,
    ContainerCreateRequest,
    ContainerLogResponse,
    ContainerProcessResponse,
    NetworkCreateRequest,
    NetworkDetailResponse,
    NetworkListResponse,
    NetworkSummary,
    OperationResponse,
    RuntimeSettingsResponse,
    RuntimeSettingsUpdateRequest,
    VolumeCreateRequest,
    VolumeDetailResponse,
    VolumeListResponse,
    VolumeSummary,
)


def _client():
    return docker.from_env()


def operation_error(message: str, error: str | None = None, **data: Any) -> OperationResponse:
    return OperationResponse(ok=False, message=message, error=error, data=data)


def operation_ok(message: str, **data: Any) -> OperationResponse:
    return OperationResponse(ok=True, message=message, data=data)


def control_container(container_name: str, action: str, approve: bool, settings: Settings) -> OperationResponse:
    # 停止会中断运行中的服务，因此按高危操作处理。
    if action in {"stop", "delete"} and settings.require_dangerous_approval and not approve:
        message = "删除容器需要确认。" if action == "delete" else "停止容器需要确认。"
        return operation_error(message, container_name=container_name, action=action, requires_approval=True)

    try:
        container = _client().containers.get(container_name)
        if action == "start":
            container.start()
        elif action == "stop":
            container.stop(timeout=8)
        elif action == "restart":
            container.restart(timeout=8)
        elif action == "pause":
            container.pause()
        elif action == "unpause":
            container.unpause()
        elif action == "delete":
            container.remove(force=True)
            return operation_ok(
                f"容器 {container_name} 已删除。",
                container_name=container_name,
                action=action,
            )
        elif action == "update":
            return _update_container(container_name, container, settings)
        else:
            return operation_error("不支持的容器操作。", container_name=container_name, action=action)
        if hasattr(container, "reload"):
            container.reload()
        return operation_ok(
            f"容器 {container_name} 已执行 {action}。",
            container_name=container_name,
            action=action,
            status=getattr(container, "status", None),
        )
    except NotFound:
        return operation_error("容器不存在。", container_name=container_name)
    except (DockerException, OSError) as exc:
        return operation_error("容器操作失败。", str(exc), container_name=container_name, action=action)


def create_container(request: ContainerCreateRequest, settings: Settings) -> OperationResponse:
    client = _client()
    image = request.image.strip()
    name = request.name.strip() if request.name else None
    command = request.command.strip() if request.command else None

    try:
        if request.pull_if_missing:
            try:
                client.images.get(image)
            except ImageNotFound:
                client.images.pull(image)

        container = client.containers.create(
            image=image,
            name=name,
            command=command or None,
            detach=True,
            environment=_container_environment(request),
            ports=_container_ports(request),
            volumes=_container_volumes(request),
            restart_policy=_restart_policy(request.restart_policy),
            network=request.network.strip() if request.network else None,
            privileged=request.privileged,
            cap_add=_container_cap_add(request),
            **_container_resource_limits(request),
        )
        if request.start:
            container.start()
        container.reload()
        return operation_ok(
            f"容器 {container.name} 已创建。",
            container_id=container.short_id,
            container_name=container.name,
            image=image,
            status=container.status,
            started=request.start,
        )
    except ImageNotFound:
        return operation_error("镜像不存在或无法访问。", image=image)
    except (DockerException, OSError) as exc:
        return operation_error("容器创建失败。", str(exc), image=image, name=name)


def _update_container(container_name: str, container: Any, settings: Settings) -> OperationResponse:
    config = container.attrs.get("Config", {})
    labels = config.get("Labels") or {}
    service = labels.get("com.docker.compose.service")

    # 更新独立容器需要猜测原始 run 参数，风险太高，因此只支持 Compose 管理的容器。
    if not service:
        return operation_error(
            "该容器不是 Compose 管理的容器，暂不能安全自动更新。",
            container_name=container_name,
            hint="请通过 Compose 项目执行更新，或先把该容器迁移到 Compose 文件中。",
        )

    try:
        compose_path = _compose_file_from_container_labels(labels, settings)
    except ValueError as exc:
        return operation_error(
            "找到了 Compose 标签，但对应文件不在允许项目目录内或不可访问。",
            str(exc),
            container_name=container_name,
            service=service,
        )

    command = [
        "docker",
        "compose",
        "-f",
        str(compose_path),
        "up",
        "-d",
        "--pull",
        "always",
        "--no-deps",
        service,
    ]
    return _run_compose_command(
        command,
        compose_path,
        success_message=f"容器 {container_name} 所属服务 {service} 已更新。",
        settings=settings,
        action="update",
        container_name=container_name,
        service=service,
    )


def read_container_logs(container_name: str, tail: int = 200) -> ContainerLogResponse:
    # 限制日志读取行数，避免单次请求把无限 Docker 日志拉进内存。
    safe_tail = max(1, min(tail, 2000))
    timestamp = datetime.now().astimezone()
    try:
        container = _client().containers.get(container_name)
        raw = container.logs(tail=safe_tail, stdout=True, stderr=True)
        content = raw.decode("utf-8", errors="replace")
        return ContainerLogResponse(
            docker_available=True,
            container_name=container_name,
            tail=safe_tail,
            content=content[-24000:],
            timestamp=timestamp,
        )
    except NotFound:
        return ContainerLogResponse(
            docker_available=True,
            container_name=container_name,
            tail=safe_tail,
            error="容器不存在。",
            timestamp=timestamp,
        )
    except DockerException as exc:
        return ContainerLogResponse(
            docker_available=False,
            container_name=container_name,
            tail=safe_tail,
            error=str(exc),
            timestamp=timestamp,
        )


def inspect_container(container_name: str) -> ContainerInspectResponse:
    timestamp = datetime.now().astimezone()
    try:
        container = _client().containers.get(container_name)
        return ContainerInspectResponse(
            docker_available=True,
            container_name=container_name,
            inspect=getattr(container, "attrs", {}) or {},
            timestamp=timestamp,
        )
    except NotFound:
        return ContainerInspectResponse(
            docker_available=True,
            container_name=container_name,
            error="容器不存在。",
            timestamp=timestamp,
        )
    except DockerException as exc:
        return ContainerInspectResponse(
            docker_available=False,
            container_name=container_name,
            error=str(exc),
            timestamp=timestamp,
        )


def process_container(container_name: str) -> ContainerProcessResponse:
    timestamp = datetime.now().astimezone()
    try:
        container = _client().containers.get(container_name)
        top = container.top() or {}
        titles = [str(item) for item in top.get("Titles", [])]
        processes = []
        for row in top.get("Processes", []) or []:
            processes.append({titles[index]: str(value) for index, value in enumerate(row) if index < len(titles)})
        return ContainerProcessResponse(
            docker_available=True,
            container_name=container_name,
            titles=titles,
            processes=processes,
            timestamp=timestamp,
        )
    except NotFound:
        return ContainerProcessResponse(
            docker_available=True,
            container_name=container_name,
            error="容器不存在。",
            timestamp=timestamp,
        )
    except DockerException as exc:
        return ContainerProcessResponse(
            docker_available=False,
            container_name=container_name,
            error=str(exc),
            timestamp=timestamp,
        )


def pull_image(image: str) -> OperationResponse:
    try:
        pulled = _client().images.pull(image)
        tags = pulled.tags or [image]
        return operation_ok("镜像拉取完成。", image=image, tags=tags, id=pulled.short_id)
    except ImageNotFound:
        return operation_error("镜像不存在或无法访问。", image=image)
    except DockerException as exc:
        return operation_error("镜像拉取失败。", str(exc), image=image)


def remove_image(image_id: str, force: bool, approve: bool, settings: Settings) -> OperationResponse:
    if settings.require_dangerous_approval and not approve:
        return operation_error("删除镜像需要确认。", image=image_id, requires_approval=True)

    try:
        _client().images.remove(image=image_id, force=force)
        return operation_ok("镜像已删除。", image=image_id, force=force)
    except ImageNotFound:
        return operation_error("镜像不存在。", image=image_id)
    except DockerException as exc:
        return operation_error("镜像删除失败。", str(exc), image=image_id, force=force)


def prune_images(dangling_only: bool, approve: bool, settings: Settings) -> OperationResponse:
    if settings.require_dangerous_approval and not approve:
        return operation_error("清理镜像需要确认。", dangling_only=dangling_only, requires_approval=True)

    try:
        filters = {"dangling": dangling_only}
        result = _client().images.prune(filters=filters)
        deleted = result.get("ImagesDeleted") or []
        reclaimed = int(result.get("SpaceReclaimed") or 0)
        return operation_ok(
            "镜像清理完成。",
            dangling_only=dangling_only,
            deleted_count=len(deleted),
            deleted=deleted,
            space_reclaimed=reclaimed,
        )
    except DockerException as exc:
        return operation_error("镜像清理失败。", str(exc), dangling_only=dangling_only)


def tag_image(source: str, repository: str, tag: str = "latest") -> OperationResponse:
    client = _client()
    try:
        image = client.images.get(source)
        running_containers = _running_containers_using_image(client, source, image)
        if running_containers:
            return operation_error(
                "镜像正在被运行中的容器使用，不能修改标签。",
                image=source,
                containers=running_containers,
            )
        image.tag(repository.strip(), tag=tag.strip())
        return operation_ok("镜像标签已添加。", source=source, repository=repository, tag=tag)
    except ImageNotFound:
        return operation_error("镜像不存在。", image=source)
    except DockerException as exc:
        return operation_error("添加镜像标签失败。", str(exc), image=source, repository=repository, tag=tag)


def untag_image(image: str) -> OperationResponse:
    client = _client()
    try:
        docker_image = client.images.get(image)
        tags = list(getattr(docker_image, "tags", None) or [])
        if image not in tags:
            return operation_error(
                "只能删除镜像标签，请选择具体 repository:tag。",
                image=image,
                tags=tags,
            )
        if len(tags) <= 1:
            return operation_error(
                "不能删除镜像的最后一个标签。请先给镜像添加新标签，或使用删除镜像操作。",
                image=image,
                tags=tags,
            )
        running_containers = _running_containers_using_image(client, image, docker_image)
        if running_containers:
            return operation_error(
                "镜像正在被运行中的容器使用，不能修改标签。",
                image=image,
                containers=running_containers,
            )
        client.api.remove_image(image=image, noprune=True)
        return operation_ok("镜像标签已删除。", image=image)
    except ImageNotFound:
        return operation_error("镜像不存在。", image=image)
    except DockerException as exc:
        return operation_error("删除镜像标签失败。", str(exc), image=image)


def import_image(tar_path: Path) -> OperationResponse:
    try:
        loaded = _client().images.load(tar_path.read_bytes())
        images = [
            {
                "id": getattr(image, "short_id", None),
                "tags": getattr(image, "tags", []),
            }
            for image in loaded
        ]
        return operation_ok("镜像已导入。", images=images, count=len(images))
    except OSError as exc:
        return operation_error("读取镜像 tar 失败。", str(exc), path=str(tar_path))
    except DockerException as exc:
        return operation_error("导入镜像失败。", str(exc), path=str(tar_path))


def export_image(image: str, output_dir: Path) -> OperationResponse:
    safe_name = _safe_export_filename(image)
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / f"{safe_name}.tar"
    try:
        with target.open("wb") as file:
            for chunk in _client().api.get_image(image):
                file.write(chunk)
        return operation_ok("镜像已导出。", image=image, path=str(target), filename=target.name)
    except ImageNotFound:
        return operation_error("镜像不存在。", image=image)
    except (DockerException, OSError) as exc:
        return operation_error("导出镜像失败。", str(exc), image=image)


def _running_containers_using_image(client: Any, image_ref: str, image: Any) -> list[str]:
    tags = {str(tag) for tag in (getattr(image, "tags", None) or []) if tag}
    image_ids = _image_id_candidates(getattr(image, "id", None), getattr(image, "short_id", None))
    names: list[str] = []
    try:
        containers = client.containers.list(all=True)
    except (DockerException, AttributeError):
        return names

    for container in containers:
        if str(getattr(container, "status", "")).lower() != "running":
            continue
        attrs = getattr(container, "attrs", {}) or {}
        config = attrs.get("Config") or {}
        config_image = config.get("Image")
        container_image_ids = _image_id_candidates(attrs.get("Image"), attrs.get("ImageID"))
        try:
            container_image = getattr(container, "image", None)
            container_image_ids.update(
                _image_id_candidates(getattr(container_image, "id", None), getattr(container_image, "short_id", None))
            )
        except DockerException:
            pass

        if config_image == image_ref or config_image in tags or image_ids.intersection(container_image_ids):
            name = str(getattr(container, "name", "") or attrs.get("Name") or attrs.get("Id") or "")
            names.append(name.lstrip("/") or "unknown")
    return names


def _image_id_candidates(*values: Any) -> set[str]:
    candidates: set[str] = set()
    for value in values:
        if not value:
            continue
        raw = str(value)
        candidates.add(raw)
        if raw.startswith("sha256:"):
            digest = raw.removeprefix("sha256:")
            candidates.add(digest)
            candidates.add(digest[:12])
            candidates.add(f"sha256:{digest[:12]}")
    return candidates


def list_networks() -> NetworkListResponse:
    timestamp = datetime.now().astimezone()
    try:
        networks = [_network_summary(item) for item in _client().networks.list()]
        networks.sort(key=lambda item: item.name.lower())
        return NetworkListResponse(docker_available=True, networks=networks, timestamp=timestamp)
    except DockerException as exc:
        return NetworkListResponse(docker_available=False, networks=[], error=str(exc), timestamp=timestamp)


def inspect_network(name: str) -> NetworkDetailResponse:
    timestamp = datetime.now().astimezone()
    try:
        network = _client().networks.get(name)
        return NetworkDetailResponse(
            docker_available=True,
            name=name,
            detail=getattr(network, "attrs", {}) or {},
            timestamp=timestamp,
        )
    except NotFound:
        return NetworkDetailResponse(docker_available=True, name=name, error="网络不存在。", timestamp=timestamp)
    except DockerException as exc:
        return NetworkDetailResponse(docker_available=False, name=name, error=str(exc), timestamp=timestamp)


def create_network(request: NetworkCreateRequest) -> OperationResponse:
    try:
        ipam = None
        if request.subnet or request.gateway:
            ipam_pool = docker.types.IPAMPool(subnet=request.subnet, gateway=request.gateway)
            ipam = docker.types.IPAMConfig(pool_configs=[ipam_pool])
        network = _client().networks.create(
            request.name.strip(),
            driver=request.driver,
            internal=request.internal,
            attachable=request.attachable,
            ipam=ipam,
        )
        return operation_ok("网络已创建。", name=network.name, id=getattr(network, "short_id", getattr(network, "id", None)))
    except DockerException as exc:
        return operation_error("创建网络失败。", str(exc), name=request.name)


def remove_network(name: str, approve: bool, settings: Settings) -> OperationResponse:
    if settings.require_dangerous_approval and not approve:
        return operation_error("删除网络需要确认。", name=name, requires_approval=True)
    try:
        _client().networks.get(name).remove()
        return operation_ok("网络已删除。", name=name)
    except NotFound:
        return operation_error("网络不存在。", name=name)
    except DockerException as exc:
        return operation_error("删除网络失败。", str(exc), name=name)


def prune_networks(approve: bool, settings: Settings) -> OperationResponse:
    if settings.require_dangerous_approval and not approve:
        return operation_error("清理网络需要确认。", requires_approval=True)
    try:
        result = _client().networks.prune()
        deleted = result.get("NetworksDeleted") or []
        return operation_ok("网络清理完成。", deleted=deleted, deleted_count=len(deleted))
    except DockerException as exc:
        return operation_error("清理网络失败。", str(exc))


def connect_network(name: str, container: str) -> OperationResponse:
    try:
        _client().networks.get(name).connect(container)
        return operation_ok("容器已连接到网络。", name=name, container=container)
    except DockerException as exc:
        return operation_error("连接网络失败。", str(exc), name=name, container=container)


def disconnect_network(name: str, container: str) -> OperationResponse:
    try:
        _client().networks.get(name).disconnect(container)
        return operation_ok("容器已断开网络。", name=name, container=container)
    except DockerException as exc:
        return operation_error("断开网络失败。", str(exc), name=name, container=container)


def list_volumes() -> VolumeListResponse:
    timestamp = datetime.now().astimezone()
    try:
        client = _client()
        containers = client.containers.list(all=True)
        usage = _volume_usage(containers)
        volumes = [_volume_summary(item, usage) for item in client.volumes.list()]
        volumes.sort(key=lambda item: item.name.lower())
        return VolumeListResponse(docker_available=True, volumes=volumes, timestamp=timestamp)
    except DockerException as exc:
        return VolumeListResponse(docker_available=False, volumes=[], error=str(exc), timestamp=timestamp)


def inspect_volume(name: str) -> VolumeDetailResponse:
    timestamp = datetime.now().astimezone()
    try:
        client = _client()
        volume = client.volumes.get(name)
        usage = _volume_usage(client.containers.list(all=True))
        return VolumeDetailResponse(
            docker_available=True,
            name=name,
            detail=getattr(volume, "attrs", {}) or {},
            containers=usage.get(name, []),
            timestamp=timestamp,
        )
    except NotFound:
        return VolumeDetailResponse(docker_available=True, name=name, error="卷不存在。", timestamp=timestamp)
    except DockerException as exc:
        return VolumeDetailResponse(docker_available=False, name=name, error=str(exc), timestamp=timestamp)


def create_volume(request: VolumeCreateRequest) -> OperationResponse:
    try:
        volume = _client().volumes.create(
            name=request.name.strip(),
            driver=request.driver.strip() or "local",
            labels=request.labels or None,
        )
        return operation_ok("卷已创建。", name=volume.name)
    except DockerException as exc:
        return operation_error("创建卷失败。", str(exc), name=request.name)


def remove_volume(name: str, force: bool, approve: bool, settings: Settings) -> OperationResponse:
    if settings.require_dangerous_approval and not approve:
        return operation_error("删除卷需要确认。", name=name, requires_approval=True)
    try:
        _client().volumes.get(name).remove(force=force)
        return operation_ok("卷已删除。", name=name, force=force)
    except NotFound:
        return operation_error("卷不存在。", name=name)
    except DockerException as exc:
        return operation_error("删除卷失败。", str(exc), name=name, force=force)


def prune_volumes(approve: bool, settings: Settings) -> OperationResponse:
    if settings.require_dangerous_approval and not approve:
        return operation_error("清理卷需要确认。", requires_approval=True)
    try:
        result = _client().volumes.prune()
        deleted = result.get("VolumesDeleted") or []
        return operation_ok(
            "卷清理完成。",
            deleted=deleted,
            deleted_count=len(deleted),
            space_reclaimed=int(result.get("SpaceReclaimed") or 0),
        )
    except DockerException as exc:
        return operation_error("清理卷失败。", str(exc))


def pull_image_events(image: str, settings: Settings) -> Iterator[dict[str, Any]]:
    client = _client()
    proxy_env = _docker_proxy_env(settings)
    # 这个生成器供 SSE 使用，每个 yield 的字典都会被 API 路由序列化。
    yield {
        "type": "start",
        "image": image,
        "message": f"开始拉取 {image}。",
        "proxy_configured": bool(proxy_env),
    }
    try:
        for item in client.api.pull(image, stream=True, decode=True):
            if not isinstance(item, dict):
                continue
            if item.get("error"):
                yield {
                    "type": "error",
                    "image": image,
                    "message": "镜像拉取失败。",
                    "error": str(item.get("error")),
                    "detail": item.get("errorDetail") or {},
                }
                return

            progress = item.get("progressDetail") or {}
            current = int(progress.get("current") or 0)
            total = int(progress.get("total") or 0)
            # 拉取进度按层报告；Registry 等待阶段可能没有 total。
            percent = round((current / total) * 100, 1) if total else None
            status = str(item.get("status") or "拉取中")
            layer_id = item.get("id")
            yield {
                "type": "progress",
                "image": image,
                "id": layer_id,
                "status": status,
                "message": f"{layer_id} {status}" if layer_id else status,
                "current": current,
                "total": total,
                "percent": percent,
            }

        image_id = None
        tags: list[str] = []
        try:
            pulled = client.images.get(image)
            image_id = pulled.short_id
            tags = pulled.tags or [image]
        except DockerException:
            tags = [image]
        yield {
            "type": "success",
            "image": image,
            "message": "镜像拉取完成。",
            "id": image_id,
            "tags": tags,
            "percent": 100,
        }
    except ImageNotFound:
        yield {"type": "error", "image": image, "message": "镜像不存在或无法访问。"}
    except DockerException as exc:
        yield {"type": "error", "image": image, "message": "镜像拉取失败。", "error": str(exc)}
    except OSError as exc:
        yield {"type": "error", "image": image, "message": "镜像拉取执行失败。", "error": str(exc)}


def read_compose_file(path: str, settings: Settings) -> ComposeFileResponse:
    try:
        compose_path = _resolve_compose_file(path, settings)
        return ComposeFileResponse(
            path=str(compose_path),
            content=compose_path.read_text(encoding="utf-8"),
            editable=True,
        )
    except (OSError, ValueError) as exc:
        return ComposeFileResponse(path=path, content="", editable=False, error=str(exc))


def write_compose_file(path: str, content: str, settings: Settings) -> OperationResponse:
    try:
        compose_path = _resolve_compose_file(path, settings)
        compose_path.write_text(content, encoding="utf-8")
        return operation_ok("Compose 文件已保存。", path=str(compose_path))
    except (OSError, ValueError) as exc:
        return operation_error("保存 Compose 文件失败。", str(exc), path=path)


def create_compose_project(request: ComposeCreateRequest, settings: Settings) -> OperationResponse:
    try:
        compose_path = _resolve_new_compose_file(request, settings)
        if compose_path.exists():
            return operation_error("Compose 文件已存在。", path=str(compose_path))

        compose_path.parent.mkdir(parents=True, exist_ok=True)
        compose_path.write_text(request.content, encoding="utf-8")
    except (OSError, ValueError) as exc:
        return operation_error("创建 Compose 文件失败。", str(exc), project_name=request.project_name)

    command = ["docker", "compose", "-f", str(compose_path), "up", "-d"]
    result = _run_compose_command(
        command,
        compose_path,
        success_message=f"Compose 项目 {request.project_name.strip()} 已创建并启动。",
        settings=settings,
        action="create_up",
        project_name=request.project_name.strip(),
    )
    if result.ok:
        result.data["created"] = True
        result.data["path"] = str(compose_path)
    return result


def create_compose_project_from_url(request: ComposeUrlCreateRequest, settings: Settings) -> OperationResponse:
    if settings.require_dangerous_approval and not request.approve:
        return compose_create_approval_error(request.project_name)

    try:
        response = httpx.get(str(request.url), timeout=20)
        response.raise_for_status()
        content = response.text
        if not content.strip():
            return operation_error("远程 Compose 文件为空。", url=str(request.url))
        compose_request = ComposeCreateRequest(
            project_name=request.project_name,
            directory=request.directory,
            filename=request.filename,
            content=content,
            approve=True,
        )
    except (httpx.HTTPError, ValueError) as exc:
        return operation_error("读取远程 Compose 文件失败。", str(exc), url=str(request.url))
    return create_compose_project(compose_request, settings)


def create_compose_project_from_git(request: ComposeGitCreateRequest, settings: Settings) -> OperationResponse:
    if settings.require_dangerous_approval and not request.approve:
        return compose_create_approval_error(request.project_name)

    try:
        target_dir = _resolve_new_project_dir(request.project_name, request.directory, settings)
        if target_dir.exists() and any(target_dir.iterdir()):
            return operation_error("目标项目目录已存在且非空。", path=str(target_dir))

        target_dir.parent.mkdir(parents=True, exist_ok=True)
        command = ["git", "clone", "--depth", "1"]
        if request.branch:
            command.extend(["--branch", request.branch.strip()])
        command.extend([str(request.repository_url), str(target_dir)])
        result = subprocess.run(
            command,
            cwd=target_dir.parent,
            env=_docker_command_env(settings),
            text=True,
            capture_output=True,
            timeout=180,
            check=False,
        )
        if result.returncode != 0:
            return operation_error("Git 仓库拉取失败。", (result.stdout + result.stderr)[-24000:], returncode=result.returncode)

        compose_path = (target_dir / request.compose_path).resolve()
        if not _is_under_allowed_root(compose_path, [target_dir]):
            return operation_error("Compose 文件路径不允许。", path=str(compose_path))
        if compose_path.name not in COMPOSE_FILENAMES or not compose_path.is_file():
            return operation_error("Git 仓库中没有找到支持的 Compose 文件。", path=str(compose_path))
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        return operation_error("从 Git 创建 Compose 项目失败。", str(exc), project_name=request.project_name)

    command = ["docker", "compose", "-f", str(compose_path), "up", "-d"]
    return _run_compose_command(
        command,
        compose_path,
        success_message=f"Compose 项目 {request.project_name.strip()} 已从 Git 创建并启动。",
        settings=settings,
        action="git_create_up",
        project_name=request.project_name.strip(),
        path=str(compose_path),
    )


def control_compose(path: str, action: str, approve: bool, settings: Settings) -> OperationResponse:
    # 停止和删除项目会影响项目内所有服务，因此走同一套显式确认门禁。
    if action in {"stop", "down"} and settings.require_dangerous_approval and not approve:
        return operation_error("该 Compose 操作需要确认。", action=action, path=path, requires_approval=True)

    try:
        compose_path = _resolve_compose_file(path, settings)
    except ValueError as exc:
        return operation_error("Compose 文件路径不允许。", str(exc), path=path)

    command = _compose_command_for_action(compose_path, action)
    if command is None:
        return operation_error("不支持的 Compose 操作。", path=str(compose_path), action=action)

    return _run_compose_command(
        command,
        compose_path,
        success_message=f"Compose 已执行 {action}。",
        settings=settings,
        action=action,
    )


def _compose_command_for_action(compose_path: Path, action: str) -> list[str] | None:
    command_map = {
        "up": ["docker", "compose", "-f", str(compose_path), "up", "-d"],
        "stop": ["docker", "compose", "-f", str(compose_path), "stop"],
        "restart": ["docker", "compose", "-f", str(compose_path), "restart"],
        "pull": ["docker", "compose", "-f", str(compose_path), "pull"],
        "update": ["docker", "compose", "-f", str(compose_path), "up", "-d", "--pull", "always"],
        "down": ["docker", "compose", "-f", str(compose_path), "down"],
    }
    return command_map.get(action)


def _compose_event_from_response(path: str, action: str, response: OperationResponse) -> dict[str, Any]:
    payload = response.model_dump(mode="json")
    return {
        "type": "success" if response.ok else "error",
        "path": path,
        "action": action,
        "message": response.message,
        "response": payload,
        "error": response.error,
    }


def control_compose_service(path: str, service: str, action: str, approve: bool, settings: Settings) -> OperationResponse:
    if action == "stop" and settings.require_dangerous_approval and not approve:
        return operation_error("停止 Compose 服务需要确认。", action=action, path=path, service=service, requires_approval=True)

    try:
        compose_path = _resolve_compose_file(path, settings)
    except ValueError as exc:
        return operation_error("Compose 文件路径不允许。", str(exc), path=path)

    service_name = service.strip()
    command_map = {
        "up": ["docker", "compose", "-f", str(compose_path), "up", "-d", service_name],
        "stop": ["docker", "compose", "-f", str(compose_path), "stop", service_name],
        "restart": ["docker", "compose", "-f", str(compose_path), "restart", service_name],
    }
    command = command_map.get(action)
    if command is None:
        return operation_error("不支持的 Compose 服务操作。", path=str(compose_path), service=service_name, action=action)
    return _run_compose_command(
        command,
        compose_path,
        success_message=f"Compose 服务 {service_name} 已执行 {action}。",
        settings=settings,
        action=action,
        service=service_name,
    )


def compose_command_events(path: str, action: str, approve: bool, settings: Settings) -> Iterator[dict[str, Any]]:
    yield {"type": "start", "path": path, "action": action, "message": f"开始执行 Compose {action}。"}
    if action in {"stop", "down"} and settings.require_dangerous_approval and not approve:
        response = operation_error("该 Compose 操作需要确认。", action=action, path=path, requires_approval=True)
        yield _compose_event_from_response(path, action, response)
        return

    try:
        compose_path = _resolve_compose_file(path, settings)
    except ValueError as exc:
        response = operation_error("Compose 文件路径不允许。", str(exc), path=path)
        yield _compose_event_from_response(path, action, response)
        return

    command = _compose_command_for_action(compose_path, action)
    if command is None:
        response = operation_error("不支持的 Compose 操作。", path=str(compose_path), action=action)
        yield _compose_event_from_response(path, action, response)
        return

    output_parts: list[str] = []
    try:
        process = subprocess.Popen(
            command,
            cwd=compose_path.parent,
            env=_docker_command_env(settings),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except FileNotFoundError as exc:
        response = operation_error(
            "找不到 docker compose 命令，后端运行环境需要安装 Docker CLI 和 Compose 插件。",
            str(exc),
            path=str(compose_path),
            action=action,
        )
        yield _compose_event_from_response(path, action, response)
        return
    except OSError as exc:
        response = operation_error("Compose 操作执行失败。", str(exc), path=str(compose_path), action=action)
        yield _compose_event_from_response(path, action, response)
        return

    deadline = time.monotonic() + 240
    stdout = process.stdout
    try:
        while True:
            if stdout and select.select([stdout], [], [], 0.25)[0]:
                line = stdout.readline()
                if line:
                    output_parts.append(line)
                    output = "".join(output_parts)[-24000:]
                    yield {
                        "type": "progress",
                        "path": str(compose_path),
                        "action": action,
                        "message": line.strip() or "Compose 输出更新。",
                        "output": output,
                    }

            returncode = process.poll()
            if returncode is not None:
                if stdout:
                    for line in stdout.readlines():
                        if not line:
                            continue
                        output_parts.append(line)
                        yield {
                            "type": "progress",
                            "path": str(compose_path),
                            "action": action,
                            "message": line.strip() or "Compose 输出更新。",
                            "output": "".join(output_parts)[-24000:],
                        }
                output = "".join(output_parts)[-24000:]
                response = (
                    operation_ok(f"Compose 已执行 {action}。", path=str(compose_path), output=output, action=action)
                    if returncode == 0
                    else operation_error(
                        "Compose 操作失败。",
                        output or f"exit code {returncode}",
                        returncode=returncode,
                        path=str(compose_path),
                        output=output,
                        action=action,
                    )
                )
                yield _compose_event_from_response(path, action, response)
                return

            if time.monotonic() > deadline:
                process.kill()
                response = operation_error("Compose 操作执行超时。", path=str(compose_path), action=action)
                yield _compose_event_from_response(path, action, response)
                return
    finally:
        if stdout:
            stdout.close()


def read_compose_logs(project: str, tail: int = 200) -> ContainerLogResponse:
    # 编排日志通过 Docker 标签反查容器；文件态项目没有容器时会返回空结果。
    safe_tail = max(1, min(tail, 2000))
    try:
        containers = _client().containers.list(
            all=True,
            filters={"label": f"com.docker.compose.project={project}"},
        )
        chunks: list[str] = []
        for container in containers:
            raw = container.logs(tail=safe_tail, stdout=True, stderr=True)
            content = raw.decode("utf-8", errors="replace")
            chunks.append(f"===== {container.name} =====\n{content}")
        return ContainerLogResponse(
            docker_available=True,
            container_name=project,
            tail=safe_tail,
            content="\n".join(chunks)[-30000:],
            error=None if containers else "没有找到该 Compose 项目的容器。",
        )
    except DockerException as exc:
        return ContainerLogResponse(
            docker_available=False,
            container_name=project,
            tail=safe_tail,
            error=str(exc),
        )


def read_compose_service_logs(project: str, service: str, tail: int = 200) -> ContainerLogResponse:
    safe_tail = max(1, min(tail, 2000))
    try:
        containers = _client().containers.list(
            all=True,
            filters={
                "label": [
                    f"com.docker.compose.project={project}",
                    f"com.docker.compose.service={service}",
                ]
            },
        )
        chunks: list[str] = []
        for container in containers:
            raw = container.logs(tail=safe_tail, stdout=True, stderr=True)
            content = raw.decode("utf-8", errors="replace")
            chunks.append(f"===== {container.name} =====\n{content}")
        return ContainerLogResponse(
            docker_available=True,
            container_name=f"{project}/{service}",
            tail=safe_tail,
            content="\n".join(chunks)[-30000:],
            error=None if containers else "没有找到该 Compose 服务的容器。",
        )
    except DockerException as exc:
        return ContainerLogResponse(
            docker_available=False,
            container_name=f"{project}/{service}",
            tail=safe_tail,
            error=str(exc),
        )


def get_runtime_settings(settings: Settings) -> RuntimeSettingsResponse:
    return RuntimeSettingsResponse(
        app_name=settings.app_name,
        log_roots=settings.log_roots,
        project_roots=settings.project_roots,
        require_dangerous_approval=settings.require_dangerous_approval,
        llm_enabled=settings.llm_enabled,
        llm_base_url=settings.llm_base_url,
        llm_model=settings.llm_model,
        docker_http_proxy=settings.docker_http_proxy,
        docker_https_proxy=settings.docker_https_proxy,
        docker_no_proxy=settings.docker_no_proxy,
        external_mcp_servers=getattr(settings, "external_mcp_servers", ""),
        enable_public_mcp=getattr(settings, "enable_public_mcp", False),
    )


def update_runtime_settings(
    request: RuntimeSettingsUpdateRequest,
    settings: Settings,
) -> RuntimeSettingsResponse:
    # 空值 None 表示字段未提交；空字符串是合法值，用于清空可选设置。
    if request.log_roots is not None:
        settings.log_roots = request.log_roots
    if request.project_roots is not None:
        settings.project_roots = request.project_roots
    if request.require_dangerous_approval is not None:
        settings.require_dangerous_approval = request.require_dangerous_approval
    if request.llm_base_url is not None:
        settings.llm_base_url = request.llm_base_url
    if request.llm_model is not None:
        settings.llm_model = request.llm_model
    if request.llm_api_key:
        settings.llm_api_key = request.llm_api_key
    if request.docker_http_proxy is not None:
        settings.docker_http_proxy = request.docker_http_proxy
    if request.docker_https_proxy is not None:
        settings.docker_https_proxy = request.docker_https_proxy
    if request.docker_no_proxy is not None:
        settings.docker_no_proxy = request.docker_no_proxy
    if request.external_mcp_servers is not None:
        settings.external_mcp_servers = request.external_mcp_servers
    if request.enable_public_mcp is not None:
        settings.enable_public_mcp = request.enable_public_mcp
    save_runtime_settings_file(settings)
    return get_runtime_settings(settings)


def runtime_settings_approval_error() -> OperationResponse:
    return operation_error("修改运行时设置需要确认。", requires_approval=True)


def compose_file_approval_error(path: str) -> OperationResponse:
    return operation_error("保存 Compose 文件需要确认。", path=path, requires_approval=True)


def compose_create_approval_error(project_name: str) -> OperationResponse:
    return operation_error("创建并启动 Compose 项目需要确认。", project_name=project_name, requires_approval=True)


def _run_compose_command(
    command: list[str],
    compose_path: Path,
    success_message: str,
    settings: Settings,
    **data: Any,
) -> OperationResponse:
    try:
        # 在 Compose 文件目录执行命令，保持 YAML 中相对路径的 Docker Compose 语义。
        result = subprocess.run(
            command,
            cwd=compose_path.parent,
            env=_docker_command_env(settings),
            text=True,
            capture_output=True,
            timeout=240,
            check=False,
        )
        output = (result.stdout + result.stderr)[-24000:]
        payload = {"path": str(compose_path), "output": output, **data}
        if result.returncode != 0:
            return operation_error(
                "Compose 操作失败。",
                output or f"exit code {result.returncode}",
                returncode=result.returncode,
                **payload,
            )
        return operation_ok(success_message, **payload)
    except FileNotFoundError as exc:
        return operation_error(
            "找不到 docker compose 命令，后端运行环境需要安装 Docker CLI 和 Compose 插件。",
            str(exc),
            path=str(compose_path),
            **data,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return operation_error("Compose 操作执行失败。", str(exc), path=str(compose_path), **data)


def _network_summary(network: Any) -> NetworkSummary:
    attrs = getattr(network, "attrs", {}) or {}
    containers = attrs.get("Containers") or {}
    labels = attrs.get("Labels") or {}
    return NetworkSummary(
        id=str(getattr(network, "id", "") or attrs.get("Id") or ""),
        short_id=str(getattr(network, "short_id", "") or str(attrs.get("Id") or "")[:12]),
        name=str(getattr(network, "name", "") or attrs.get("Name") or ""),
        driver=attrs.get("Driver"),
        scope=attrs.get("Scope"),
        internal=bool(attrs.get("Internal") or False),
        attachable=bool(attrs.get("Attachable") or False),
        containers=len(containers) if isinstance(containers, dict) else 0,
        ipam=attrs.get("IPAM") or {},
        labels=labels if isinstance(labels, dict) else {},
    )


def _volume_summary(volume: Any, usage: dict[str, list[str]]) -> VolumeSummary:
    attrs = getattr(volume, "attrs", {}) or {}
    labels = attrs.get("Labels") or {}
    options = attrs.get("Options") or {}
    name = str(getattr(volume, "name", "") or attrs.get("Name") or "")
    return VolumeSummary(
        name=name,
        driver=attrs.get("Driver"),
        mountpoint=attrs.get("Mountpoint"),
        scope=attrs.get("Scope"),
        labels=labels if isinstance(labels, dict) else {},
        options=options if isinstance(options, dict) else {},
        containers=usage.get(name, []),
    )


def _volume_usage(containers: list[Any]) -> dict[str, list[str]]:
    usage: dict[str, list[str]] = {}
    for container in containers:
        name = str(getattr(container, "name", "") or "")
        attrs = getattr(container, "attrs", {}) or {}
        mounts = getattr(container, "mounts", None) or attrs.get("Mounts") or []
        for mount in mounts:
            volume_name = mount.get("Name") if isinstance(mount, dict) else getattr(mount, "name", None)
            if not volume_name:
                continue
            usage.setdefault(str(volume_name), []).append(name)
    return usage


def _docker_proxy_env(settings: Settings) -> dict[str, str]:
    values = {
        "HTTP_PROXY": str(getattr(settings, "docker_http_proxy", "")).strip(),
        "HTTPS_PROXY": str(getattr(settings, "docker_https_proxy", "")).strip(),
        "NO_PROXY": str(getattr(settings, "docker_no_proxy", "")).strip(),
    }
    env: dict[str, str] = {}
    for key, value in values.items():
        if not value:
            continue
        # 命令行工具和子进程库对大小写处理不完全一致，因此同时设置大小写变量。
        env[key] = value
        env[key.lower()] = value
    return env


def _docker_command_env(settings: Settings) -> dict[str, str]:
    env = os.environ.copy()
    env.update(_docker_proxy_env(settings))
    return env


def _container_environment(request: ContainerCreateRequest) -> dict[str, str]:
    return {item.key.strip(): item.value for item in request.env if item.key.strip()}


def _container_ports(request: ContainerCreateRequest) -> dict[str, Any]:
    if request.network and request.network.strip().lower() == "host":
        # 主机网络模式下 Docker 会拒绝显式端口绑定。
        return {}

    ports: dict[str, Any] = {}
    for binding in request.ports:
        container_port = binding.container_port.strip()
        if not container_port:
            continue
        protocol = binding.protocol or "tcp"
        protocols = ["tcp", "udp"] if protocol == "tcp/udp" and "/" not in container_port else [protocol]
        host_port = binding.host_port.strip() if binding.host_port else None
        host_ip = binding.host_ip.strip() or "0.0.0.0"
        for item in protocols:
            key = container_port if "/" in container_port else f"{container_port}/{item}"
            ports[key] = (host_ip, host_port) if host_port else None
    return ports


def _container_volumes(request: ContainerCreateRequest) -> dict[str, dict[str, str]]:
    volumes: dict[str, dict[str, str]] = {}
    for mount in request.volumes:
        host_path = mount.host_path.strip()
        container_path = mount.container_path.strip()
        if not host_path or not container_path:
            continue
        volumes[host_path] = {"bind": container_path, "mode": mount.mode}
    return volumes


def _container_cap_add(request: ContainerCreateRequest) -> list[str] | None:
    if request.privileged:
        # 特权模式已经授予宽泛能力，再传 cap_add 会显得冗余且容易误解。
        return None
    values = [capability.strip().upper() for capability in request.cap_add if capability.strip()]
    unique_values = list(dict.fromkeys(values))
    return unique_values or None


def _container_resource_limits(request: ContainerCreateRequest) -> dict[str, Any]:
    if not request.resource_limits_enabled:
        return {}

    limits: dict[str, Any] = {}
    if request.cpu_priority is not None:
        limits["cpu_shares"] = request.cpu_priority
    if request.memory_limit_mb is not None:
        limits["mem_limit"] = f"{request.memory_limit_mb}m"
    return limits


def _restart_policy(name: str) -> dict[str, str] | None:
    if name == "no":
        return None
    return {"Name": name}


def encode_sse_event(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _safe_export_filename(image: str) -> str:
    value = "".join(char if char.isalnum() or char in {"-", "_", "."} else "_" for char in image)
    return value.strip("._") or "image"


def _compose_file_from_container_labels(labels: dict[str, Any], settings: Settings) -> Path:
    # 编排标签里可能保存相对配置路径，需要结合记录的 working_dir 解析。
    config_files = labels.get("com.docker.compose.project.config_files")
    working_dir = labels.get("com.docker.compose.project.working_dir")
    if not isinstance(config_files, str) or not config_files.strip():
        raise ValueError("容器缺少 com.docker.compose.project.config_files 标签。")

    first_file = config_files.split(",")[0].strip()
    if not first_file:
        raise ValueError("Compose 配置文件标签为空。")

    compose_path = Path(first_file)
    if not compose_path.is_absolute():
        if not isinstance(working_dir, str) or not working_dir.strip():
            raise ValueError("相对 Compose 文件缺少 working_dir 标签。")
        compose_path = Path(working_dir) / compose_path
    return _resolve_compose_file(str(compose_path), settings)


def _resolve_compose_file(path: str, settings: Settings) -> Path:
    target = Path(path).expanduser().resolve()
    # 所有可编辑或可执行的 Compose 路径都必须位于配置的项目目录内。
    if target.name not in COMPOSE_FILENAMES:
        raise ValueError("不是支持的 Compose 文件名。")
    if not target.is_file():
        raise ValueError("Compose 文件不存在。")
    if not _is_under_allowed_root(target, settings.parsed_project_roots):
        raise ValueError("路径不在允许的项目目录内。")
    return target


def _resolve_new_compose_file(request: ComposeCreateRequest, settings: Settings) -> Path:
    filename = request.filename.strip()
    if filename not in COMPOSE_FILENAMES:
        raise ValueError("不是支持的 Compose 文件名。")
    return _resolve_new_project_dir(request.project_name, request.directory, settings) / filename


def _resolve_new_project_dir(project_name_value: str, directory: str, settings: Settings) -> Path:
    project_name = project_name_value.strip()
    if not project_name:
        raise ValueError("项目名称不能为空。")
    if any(item in project_name for item in ("/", "\\", "\0")) or project_name in {".", ".."}:
        # 项目名会成为目录名，因此禁止路径穿越和 NUL 字符。
        raise ValueError("项目名称不能包含路径分隔符。")

    base_dir = Path(directory).expanduser().resolve()
    if not base_dir.exists():
        raise ValueError("目标目录不存在。")
    if not base_dir.is_dir():
        raise ValueError("目标路径不是目录。")
    if not _is_under_allowed_root(base_dir, settings.parsed_project_roots):
        raise ValueError("目标目录不在允许的项目目录内。")

    target_dir = (base_dir / project_name).resolve()
    if not _is_under_allowed_root(target_dir, settings.parsed_project_roots):
        raise ValueError("目标项目目录不在允许的项目目录内。")
    return target_dir


def _is_under_allowed_root(path: Path, roots: list[Path]) -> bool:
    resolved = path.resolve()
    for root in roots:
        try:
            resolved.relative_to(root.resolve())
            return True
        except ValueError:
            continue
    return False
