from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import docker
import psutil
from docker.errors import DockerException

from app.config import get_settings
from app.docker.compose_scanner import DiscoveredComposeProject, scan_compose_files
from app.schemas import (
    ComposeListResponse,
    ComposeProjectSummary,
    ComposeServiceSummary,
    ContainerListResponse,
    ContainerResourceUsage,
    ContainerSummary,
    ImageListResponse,
    ImageSummary,
    OverviewResponse,
)


def _client():
    return docker.from_env()


def _container_summary(container: Any) -> ContainerSummary:
    attrs = container.attrs
    config = attrs.get("Config", {})
    labels = config.get("Labels") or {}
    return ContainerSummary(
        id=container.short_id,
        name=container.name,
        image=config.get("Image"),
        status=container.status,
        ports=attrs.get("NetworkSettings", {}).get("Ports") or {},
        created=attrs.get("Created"),
        compose_project=labels.get("com.docker.compose.project"),
        compose_service=labels.get("com.docker.compose.service"),
        compose_working_dir=labels.get("com.docker.compose.project.working_dir"),
        compose_config_files=labels.get("com.docker.compose.project.config_files"),
    )


def list_container_summaries(all: bool = True) -> ContainerListResponse:
    timestamp = datetime.now().astimezone()
    try:
        client = _client()
        client.ping()
        containers = [_container_summary(container) for container in client.containers.list(all=all)]
        # 运行中的服务优先展示，让运维页面先看到当前活跃负载。
        containers.sort(key=lambda item: (item.status != "running", item.name))
        return ContainerListResponse(docker_available=True, containers=containers, timestamp=timestamp)
    except DockerException as exc:
        return ContainerListResponse(
            docker_available=False,
            containers=[],
            error=str(exc),
            timestamp=timestamp,
        )


def list_image_summaries() -> ImageListResponse:
    timestamp = datetime.now().astimezone()
    try:
        client = _client()
        client.ping()
        containers = client.containers.list(all=True)
        image_usage = _image_usage_counts(containers, running_only=False)
        running_image_usage = _image_usage_counts(containers, running_only=True)
        images = [_image_summary(image, image_usage) for image in client.images.list()]
        for image in images:
            image.running_containers = running_image_usage.get(image.id, 0)
        images.sort(key=lambda item: ((item.tags[0] if item.tags else "<none>").lower(), item.short_id))
        return ImageListResponse(docker_available=True, images=images, timestamp=timestamp)
    except DockerException as exc:
        return ImageListResponse(
            docker_available=False,
            images=[],
            error=str(exc),
            timestamp=timestamp,
        )


def list_compose_projects() -> ComposeListResponse:
    settings = get_settings()
    scan_result = scan_compose_files(settings.parsed_project_roots)
    containers_response = list_container_summaries(all=True)
    projects_by_name = _projects_from_containers(containers_response.containers)

    # 合并文件扫描服务和 Docker 标签运行态，让未启动的声明服务也能显示。
    for discovered_project in scan_result.projects:
        _merge_discovered_project(projects_by_name, discovered_project)

    projects = sorted(projects_by_name.values(), key=lambda item: item.name.lower())
    for project in projects:
        _refresh_project_state(project)

    return ComposeListResponse(
        docker_available=containers_response.docker_available,
        projects=projects,
        error=containers_response.error,
        scan_roots=[str(root) for root in scan_result.scan_roots],
        scan_errors=scan_result.errors,
        timestamp=containers_response.timestamp,
    )


def get_overview(llm_enabled: bool, recent_incidents: list[Any]) -> OverviewResponse:
    containers_response = list_container_summaries(all=True)
    compose_response = list_compose_projects()
    containers = containers_response.containers
    running = sum(1 for item in containers if item.status == "running")
    total = len(containers)
    return OverviewResponse(
        llm_enabled=llm_enabled,
        docker_available=containers_response.docker_available,
        containers_total=total,
        running_containers=running,
        stopped_containers=max(total - running, 0),
        compose_projects=len(compose_response.projects) if compose_response else 0,
        host_memory_total=_host_memory_total(),
        container_resources=list_container_resource_usage(containers),
        recent_incidents=recent_incidents,
        error=containers_response.error,
        timestamp=containers_response.timestamp,
    )


def _host_memory_total() -> int | None:
    try:
        client = _client()
        value = client.info().get("MemTotal")
        if isinstance(value, int) and value > 0:
            return value
    except DockerException:
        pass

    try:
        # 测试环境或 Docker info 缺少 MemTotal 时使用宿主机内存作为兜底。
        value = int(psutil.virtual_memory().total)
        return value if value > 0 else None
    except (OSError, ValueError):
        return None


def list_container_resource_usage(containers: list[ContainerSummary]) -> list[ContainerResourceUsage]:
    if not containers:
        return []

    try:
        client = _client()
        client.ping()
    except DockerException as exc:
        return [
            ContainerResourceUsage(
                id=container.id,
                name=container.name,
                image=container.image,
                status=container.status,
                error=str(exc),
            )
            for container in containers
        ]

    usage: list[ContainerResourceUsage] = []
    for container in containers:
        storage_size, storage_virtual_size = _container_storage_size(client, container.name)
        if container.status != "running":
            # 容器 stats 只对运行中容器有实际意义。
            usage.append(
                ContainerResourceUsage(
                    id=container.id,
                    name=container.name,
                    image=container.image,
                    status=container.status,
                    storage_size=storage_size,
                    storage_virtual_size=storage_virtual_size,
                )
            )
            continue

        try:
            docker_container = client.containers.get(container.name)
            stats = docker_container.stats(stream=False)
            memory_usage, memory_limit, memory_percent = _memory_usage(stats)
            usage.append(
                ContainerResourceUsage(
                    id=container.id,
                    name=container.name,
                    image=container.image,
                    status=container.status,
                    cpu_percent=_cpu_percent(stats),
                    memory_usage=memory_usage,
                    memory_limit=memory_limit,
                    memory_percent=memory_percent,
                    storage_size=storage_size,
                    storage_virtual_size=storage_virtual_size,
                )
            )
        except DockerException as exc:
            usage.append(
                ContainerResourceUsage(
                    id=container.id,
                    name=container.name,
                    image=container.image,
                    status=container.status,
                    storage_size=storage_size,
                    storage_virtual_size=storage_virtual_size,
                    error=str(exc),
                )
            )

    return usage


def _container_storage_size(client: Any, container_name: str) -> tuple[int, int]:
    attrs: dict[str, Any] = {}
    try:
        attrs = client.api.inspect_container(container_name, size=True) or {}
    except TypeError:
        try:
            url = f"{client.api._url('/containers/{0}/json', container_name)}?size=1"
            attrs = client.api._result(client.api._get(url), True) or {}
        except (AttributeError, DockerException, TypeError):
            attrs = {}
    except (AttributeError, DockerException):
        try:
            docker_container = client.containers.get(container_name)
            attrs = getattr(docker_container, "attrs", {}) or {}
        except (AttributeError, DockerException):
            return 0, 0

    return _safe_int(attrs.get("SizeRw")), _safe_int(attrs.get("SizeRootFs"))


def _safe_int(value: Any) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return max(number, 0)


def _cpu_percent(stats: dict[str, Any]) -> float:
    cpu_stats = stats.get("cpu_stats") or {}
    precpu_stats = stats.get("precpu_stats") or {}
    cpu_usage = cpu_stats.get("cpu_usage") or {}
    precpu_usage = precpu_stats.get("cpu_usage") or {}

    cpu_delta = float(cpu_usage.get("total_usage") or 0) - float(precpu_usage.get("total_usage") or 0)
    system_delta = float(cpu_stats.get("system_cpu_usage") or 0) - float(precpu_stats.get("system_cpu_usage") or 0)
    online_cpus = cpu_stats.get("online_cpus") or len(cpu_usage.get("percpu_usage") or []) or 1

    if cpu_delta <= 0 or system_delta <= 0:
        return 0
    # 使用 Docker CLI 同款公式：容器增量除以系统增量，再按 CPU 数放大。
    return round((cpu_delta / system_delta) * float(online_cpus) * 100.0, 2)


def _memory_usage(stats: dict[str, Any]) -> tuple[int, int | None, float]:
    memory_stats = stats.get("memory_stats") or {}
    raw_usage = int(memory_stats.get("usage") or 0)
    memory_detail = memory_stats.get("stats") or {}
    cache = int(memory_detail.get("inactive_file") or memory_detail.get("total_inactive_file") or 0)
    # 与 Docker CLI 行为一致，从 cgroup 原始用量中扣除 inactive file cache。
    usage = max(raw_usage - cache, 0) if raw_usage >= cache else raw_usage
    limit = int(memory_stats.get("limit") or 0) or None
    percent = round((usage / limit) * 100.0, 2) if limit else 0
    return usage, limit, percent


def _projects_from_containers(containers: list[ContainerSummary]) -> dict[str, ComposeProjectSummary]:
    grouped: dict[str, dict[str, list[ContainerSummary]]] = defaultdict(lambda: defaultdict(list))
    for container in containers:
        if container.compose_project:
            service = container.compose_service or "unknown"
            grouped[container.compose_project][service].append(container)

    projects: dict[str, ComposeProjectSummary] = {}
    for project_name, services_map in sorted(grouped.items()):
        services: list[ComposeServiceSummary] = []
        project_containers = [container for group in services_map.values() for container in group]
        working_dir = _first_present(container.compose_working_dir for container in project_containers)
        compose_file = _compose_file_from_labels(
            _first_present(container.compose_config_files for container in project_containers),
            working_dir,
        )

        for service_name, service_containers in sorted(services_map.items()):
            services.append(
                ComposeServiceSummary(
                    name=service_name,
                    container_count=len(service_containers),
                    running_count=sum(1 for item in service_containers if item.status == "running"),
                    containers=service_containers,
                )
            )

        compose_files = [compose_file] if compose_file else []
        projects[project_name] = ComposeProjectSummary(
            name=project_name,
            services=services,
            container_count=sum(service.container_count for service in services),
            running_count=sum(service.running_count for service in services),
            sources=["docker"],
            compose_file=compose_file,
            compose_files=compose_files,
            working_dir=working_dir,
        )

    return projects


def _merge_discovered_project(
    projects_by_name: dict[str, ComposeProjectSummary],
    discovered_project: DiscoveredComposeProject,
) -> None:
    project = projects_by_name.get(discovered_project.name)
    if project is None:
        # 只有文件来源的项目还没有容器，但仍应可见并可管理。
        project = ComposeProjectSummary(
            name=discovered_project.name,
            services=[],
            container_count=0,
            running_count=0,
            sources=[],
        )
        projects_by_name[discovered_project.name] = project

    _add_unique(project.sources, "file")
    compose_file = str(discovered_project.compose_file)
    _add_unique(project.compose_files, compose_file)
    if project.compose_file is None:
        project.compose_file = compose_file
    if project.working_dir is None:
        project.working_dir = str(discovered_project.working_dir)

    services_by_name = {service.name: service for service in project.services}
    for discovered_service in discovered_project.services:
        _add_unique(project.declared_services, discovered_service.name)
        existing_service = services_by_name.get(discovered_service.name)
        if existing_service is None:
            # 已声明但没有容器的服务会在 Compose 页面显示为“未启动”。
            project.services.append(
                ComposeServiceSummary(
                    name=discovered_service.name,
                    container_count=0,
                    running_count=0,
                    containers=[],
                    declared=True,
                    image=discovered_service.image,
                    container_name=discovered_service.container_name,
                )
            )
            continue

        existing_service.declared = True
        if existing_service.image is None:
            existing_service.image = discovered_service.image
        if existing_service.container_name is None:
            existing_service.container_name = discovered_service.container_name

    project.declared_services.sort()
    project.services.sort(key=lambda item: item.name.lower())
    if "docker" in project.sources and "file" in project.sources:
        project.sources[:] = ["docker", "file"]


def _refresh_project_state(project: ComposeProjectSummary) -> None:
    # 活跃表示文件和标签都存在；内部表示只有标签；未启动表示只有文件。
    has_docker = "docker" in project.sources
    has_file = "file" in project.sources
    if has_docker and has_file:
        project.state = "active"
    elif has_docker:
        project.state = "internal"
    else:
        project.state = "inactive"


def _add_unique(values: list[str], value: str | None) -> None:
    if value and value not in values:
        values.append(value)


def _first_present(values: Any) -> str | None:
    for value in values:
        if value:
            return value
    return None


def _image_usage_counts(containers: list[Any], running_only: bool = False) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for container in containers:
        if running_only and getattr(container, "status", None) != "running":
            continue
        try:
            image_id = container.image.id
        except DockerException:
            image_id = None
        except AttributeError:
            image_id = None
        if image_id:
            counts[image_id] += 1
    return counts


def _image_summary(image: Any, image_usage: dict[str, int]) -> ImageSummary:
    attrs = image.attrs or {}
    config = attrs.get("Config") or {}
    labels = config.get("Labels") or {}
    return ImageSummary(
        id=image.id,
        short_id=image.short_id,
        tags=image.tags or [],
        repo_digests=attrs.get("RepoDigests") or [],
        size=int(attrs.get("Size") or 0),
        created=attrs.get("Created"),
        labels=labels if isinstance(labels, dict) else {},
        containers=image_usage.get(image.id, 0),
    )


def _compose_file_from_labels(config_files: str | None, working_dir: str | None) -> str | None:
    if not config_files:
        return None

    first_file = config_files.split(",")[0].strip()
    if not first_file:
        return None

    path = first_file
    if not path.startswith("/") and working_dir:
        path = str(Path(working_dir) / path)
    return path
