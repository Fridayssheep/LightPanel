from __future__ import annotations

from typing import Any

from app.config import get_settings
from app.docker.actions import (
    connect_network as connect_docker_network,
    control_compose,
    control_compose_service,
    control_container,
    create_compose_project_from_git as create_docker_compose_project_from_git,
    create_compose_project_from_url as create_docker_compose_project_from_url,
    create_compose_project as create_docker_compose_project,
    create_container as create_docker_container,
    create_network as create_docker_network,
    create_volume as create_docker_volume,
    disconnect_network as disconnect_docker_network,
    export_image as export_docker_image,
    get_runtime_settings as read_runtime_settings,
    import_image as import_docker_image,
    inspect_container as inspect_docker_container,
    inspect_network as inspect_docker_network,
    inspect_volume as inspect_docker_volume,
    list_networks as read_networks,
    list_volumes as read_volumes,
    process_container as process_docker_container,
    prune_networks as prune_docker_networks,
    prune_volumes as prune_docker_volumes,
    prune_images as prune_docker_images,
    pull_image as pull_docker_image,
    read_compose_file as read_allowed_compose_file,
    read_compose_logs,
    read_compose_service_logs,
    remove_network as remove_docker_network,
    remove_volume as remove_docker_volume,
    remove_image as remove_docker_image,
    tag_image as tag_docker_image,
    update_runtime_settings as write_runtime_settings,
    untag_image as untag_docker_image,
    write_compose_file as write_allowed_compose_file,
)
from app.docker.state import list_compose_projects as read_compose_projects
from app.docker.state import get_overview as read_overview
from app.docker.state import list_image_summaries as read_image_summaries
from pathlib import Path

from app.schemas import (
    ComposeCreateRequest,
    ComposeGitCreateRequest,
    ComposeUrlCreateRequest,
    ContainerCreateRequest,
    NetworkCreateRequest,
    RuntimeSettingsUpdateRequest,
    VolumeCreateRequest,
)
from app.tools.base import ToolContext, approval_required, error, skipped, success


def _model_data(value: Any) -> dict[str, Any]:
    return value.model_dump(mode="json") if hasattr(value, "model_dump") else dict(value)


def _operation_result(value: Any) -> dict[str, Any]:
    # 把 API 的 OperationResponse 转成 MCP 工具使用的紧凑结果结构。
    data = _model_data(value)
    payload = data.get("data") or {}
    if data.get("error"):
        payload["error"] = data["error"]
    payload["timestamp"] = data.get("timestamp")
    return success(data.get("message", "操作完成。"), **payload) if data.get("ok") else error(
        data.get("message", "操作失败。"),
        **payload,
    )


def start_container(container_name: str, ctx: ToolContext | None = None) -> dict[str, Any]:
    ctx = ctx or ToolContext()
    if ctx.dry_run:
        return skipped("dry_run 已开启，未真正启动容器。", container_name=container_name)
    return _operation_result(control_container(container_name, "start", approve=True, settings=get_settings()))


def stop_container(container_name: str, ctx: ToolContext | None = None) -> dict[str, Any]:
    ctx = ctx or ToolContext()
    if ctx.dry_run:
        return skipped("dry_run 已开启，未真正停止容器。", container_name=container_name)
    response = control_container(container_name, "stop", approve=ctx.approve_actions, settings=get_settings())
    # 保留 approval_required 状态，便于聊天界面提示用户确认后重试。
    if not response.ok and response.data.get("requires_approval"):
        return approval_required(response.message, **response.data)
    return _operation_result(response)


def update_container(container_name: str, ctx: ToolContext | None = None) -> dict[str, Any]:
    ctx = ctx or ToolContext()
    if ctx.dry_run:
        return skipped("dry_run 已开启，未真正更新容器。", container_name=container_name)
    return _operation_result(control_container(container_name, "update", approve=True, settings=get_settings()))


def pause_container(container_name: str, ctx: ToolContext | None = None) -> dict[str, Any]:
    ctx = ctx or ToolContext()
    if ctx.dry_run:
        return skipped("dry_run 已开启，未真正暂停容器。", container_name=container_name)
    return _operation_result(control_container(container_name, "pause", approve=True, settings=get_settings()))


def unpause_container(container_name: str, ctx: ToolContext | None = None) -> dict[str, Any]:
    ctx = ctx or ToolContext()
    if ctx.dry_run:
        return skipped("dry_run 已开启，未真正恢复容器。", container_name=container_name)
    return _operation_result(control_container(container_name, "unpause", approve=True, settings=get_settings()))


def delete_container(container_name: str, ctx: ToolContext | None = None) -> dict[str, Any]:
    ctx = ctx or ToolContext()
    if ctx.dry_run:
        return skipped("dry_run 已开启，未真正删除容器。", container_name=container_name)
    response = control_container(container_name, "delete", approve=ctx.approve_actions, settings=get_settings())
    if not response.ok and response.data.get("requires_approval"):
        return approval_required(response.message, **response.data)
    return _operation_result(response)


def inspect_container(container_name: str, ctx: ToolContext | None = None) -> dict[str, Any]:
    response = inspect_docker_container(container_name)
    data = _model_data(response)
    if response.error:
        return error(response.error, **data)
    return success("已读取容器 inspect 信息。", **data)


def process_container(container_name: str, ctx: ToolContext | None = None) -> dict[str, Any]:
    response = process_docker_container(container_name)
    data = _model_data(response)
    if response.error:
        return error(response.error, **data)
    return success("已读取容器进程列表。", **data)


def pull_image(image: str, ctx: ToolContext | None = None) -> dict[str, Any]:
    ctx = ctx or ToolContext()
    if ctx.dry_run:
        return skipped("dry_run 已开启，未真正拉取镜像。", image=image)
    return _operation_result(pull_docker_image(image))


def list_images(ctx: ToolContext | None = None) -> dict[str, Any]:
    response = read_image_summaries()
    data = _model_data(response)
    if not response.docker_available:
        return error(response.error or "读取 Docker 镜像失败。", **data)
    return success(f"已获取 {len(response.images)} 个镜像。", **data)


def tag_image(source: str, repository: str, tag: str = "latest", ctx: ToolContext | None = None) -> dict[str, Any]:
    ctx = ctx or ToolContext()
    if ctx.dry_run:
        return skipped("dry_run 已开启，未真正添加镜像标签。", source=source, repository=repository, tag=tag)
    return _operation_result(tag_docker_image(source, repository, tag))


def untag_image(image: str, ctx: ToolContext | None = None) -> dict[str, Any]:
    ctx = ctx or ToolContext()
    if ctx.dry_run:
        return skipped("dry_run 已开启，未真正删除镜像标签。", image=image)
    return _operation_result(untag_docker_image(image))


def import_image(path: str, ctx: ToolContext | None = None) -> dict[str, Any]:
    ctx = ctx or ToolContext()
    if ctx.dry_run:
        return skipped("dry_run 已开启，未真正导入镜像。", path=path)
    return _operation_result(import_docker_image(Path(path)))


def export_image(image: str, output_dir: str | None = None, ctx: ToolContext | None = None) -> dict[str, Any]:
    ctx = ctx or ToolContext()
    if ctx.dry_run:
        return skipped("dry_run 已开启，未真正导出镜像。", image=image, output_dir=output_dir)
    target_dir = Path(output_dir) if output_dir else get_settings().data_dir / "exports"
    return _operation_result(export_docker_image(image, target_dir))


def list_networks(ctx: ToolContext | None = None) -> dict[str, Any]:
    response = read_networks()
    data = _model_data(response)
    if response.error:
        return error(response.error, **data)
    return success(f"已获取 {len(response.networks)} 个网络。", **data)


def inspect_network(name: str, ctx: ToolContext | None = None) -> dict[str, Any]:
    response = inspect_docker_network(name)
    data = _model_data(response)
    if response.error:
        return error(response.error, **data)
    return success("已读取网络详情。", **data)


def create_network(
    name: str,
    driver: str = "bridge",
    subnet: str | None = None,
    gateway: str | None = None,
    internal: bool = False,
    attachable: bool = False,
    ctx: ToolContext | None = None,
) -> dict[str, Any]:
    ctx = ctx or ToolContext()
    if ctx.dry_run:
        return skipped("dry_run 已开启，未真正创建网络。", name=name)
    try:
        request = NetworkCreateRequest(
            name=name,
            driver=driver,
            subnet=subnet,
            gateway=gateway,
            internal=internal,
            attachable=attachable,
        )
    except ValueError as exc:
        return error("创建网络参数不合法。", detail=str(exc))
    return _operation_result(create_docker_network(request))


def remove_network(name: str, ctx: ToolContext | None = None) -> dict[str, Any]:
    ctx = ctx or ToolContext()
    if ctx.dry_run:
        return skipped("dry_run 已开启，未真正删除网络。", name=name)
    response = remove_docker_network(name, approve=ctx.approve_actions, settings=get_settings())
    if not response.ok and response.data.get("requires_approval"):
        return approval_required(response.message, **response.data)
    return _operation_result(response)


def prune_networks(ctx: ToolContext | None = None) -> dict[str, Any]:
    ctx = ctx or ToolContext()
    if ctx.dry_run:
        return skipped("dry_run 已开启，未真正清理网络。")
    response = prune_docker_networks(approve=ctx.approve_actions, settings=get_settings())
    if not response.ok and response.data.get("requires_approval"):
        return approval_required(response.message, **response.data)
    return _operation_result(response)


def connect_network(name: str, container: str, ctx: ToolContext | None = None) -> dict[str, Any]:
    ctx = ctx or ToolContext()
    if ctx.dry_run:
        return skipped("dry_run 已开启，未真正连接网络。", name=name, container=container)
    return _operation_result(connect_docker_network(name, container))


def disconnect_network(name: str, container: str, ctx: ToolContext | None = None) -> dict[str, Any]:
    ctx = ctx or ToolContext()
    if ctx.dry_run:
        return skipped("dry_run 已开启，未真正断开网络。", name=name, container=container)
    return _operation_result(disconnect_docker_network(name, container))


def list_volumes(ctx: ToolContext | None = None) -> dict[str, Any]:
    response = read_volumes()
    data = _model_data(response)
    if response.error:
        return error(response.error, **data)
    return success(f"已获取 {len(response.volumes)} 个卷。", **data)


def inspect_volume(name: str, ctx: ToolContext | None = None) -> dict[str, Any]:
    response = inspect_docker_volume(name)
    data = _model_data(response)
    if response.error:
        return error(response.error, **data)
    return success("已读取卷详情。", **data)


def create_volume(name: str, driver: str = "local", ctx: ToolContext | None = None) -> dict[str, Any]:
    ctx = ctx or ToolContext()
    if ctx.dry_run:
        return skipped("dry_run 已开启，未真正创建卷。", name=name)
    try:
        request = VolumeCreateRequest(name=name, driver=driver)
    except ValueError as exc:
        return error("创建卷参数不合法。", detail=str(exc))
    return _operation_result(create_docker_volume(request))


def remove_volume(name: str, force: bool = False, ctx: ToolContext | None = None) -> dict[str, Any]:
    ctx = ctx or ToolContext()
    if ctx.dry_run:
        return skipped("dry_run 已开启，未真正删除卷。", name=name, force=force)
    response = remove_docker_volume(name, force=force, approve=ctx.approve_actions, settings=get_settings())
    if not response.ok and response.data.get("requires_approval"):
        return approval_required(response.message, **response.data)
    return _operation_result(response)


def prune_volumes(ctx: ToolContext | None = None) -> dict[str, Any]:
    ctx = ctx or ToolContext()
    if ctx.dry_run:
        return skipped("dry_run 已开启，未真正清理卷。")
    response = prune_docker_volumes(approve=ctx.approve_actions, settings=get_settings())
    if not response.ok and response.data.get("requires_approval"):
        return approval_required(response.message, **response.data)
    return _operation_result(response)


def docker_overview(ctx: ToolContext | None = None) -> dict[str, Any]:
    response = read_overview(get_settings().llm_enabled, [])
    data = _model_data(response)
    if not response.docker_available:
        return error(response.error or "读取 Docker 总览失败。", **data)
    return success(
        f"Docker 总览已获取：{response.running_containers}/{response.containers_total} 个容器运行中。",
        **data,
    )


def create_container(
    image: str,
    name: str | None = None,
    command: str | None = None,
    env: list[dict[str, str]] | None = None,
    ports: list[dict[str, Any]] | None = None,
    volumes: list[dict[str, str]] | None = None,
    restart_policy: str = "unless-stopped",
    network: str | None = None,
    privileged: bool = False,
    cap_add: list[str] | None = None,
    resource_limits_enabled: bool = False,
    cpu_priority: int | None = None,
    memory_limit_mb: int | None = None,
    pull_if_missing: bool = True,
    start: bool = True,
    ctx: ToolContext | None = None,
) -> dict[str, Any]:
    ctx = ctx or ToolContext()
    if ctx.dry_run:
        return skipped("dry_run 已开启，未真正创建容器。", image=image, name=name)

    try:
        # 复用 API schema 校验，确保 MCP 创建容器与界面创建遵循同一套规则。
        request = ContainerCreateRequest(
            image=image,
            name=name,
            command=command,
            env=env or [],
            ports=ports or [],
            volumes=volumes or [],
            restart_policy=restart_policy,
            network=network,
            privileged=privileged,
            cap_add=cap_add or [],
            resource_limits_enabled=resource_limits_enabled,
            cpu_priority=cpu_priority,
            memory_limit_mb=memory_limit_mb,
            pull_if_missing=pull_if_missing,
            start=start,
        )
    except ValueError as exc:
        return error("创建容器参数不合法。", detail=str(exc))

    return _operation_result(create_docker_container(request, get_settings()))


def remove_image(image: str, force: bool = False, ctx: ToolContext | None = None) -> dict[str, Any]:
    ctx = ctx or ToolContext()
    if ctx.dry_run:
        return skipped("dry_run 已开启，未真正删除镜像。", image=image, force=force)
    response = remove_docker_image(image, force, approve=ctx.approve_actions, settings=get_settings())
    if not response.ok and response.data.get("requires_approval"):
        return approval_required(response.message, **response.data)
    return _operation_result(response)


def prune_images(dangling_only: bool = True, ctx: ToolContext | None = None) -> dict[str, Any]:
    ctx = ctx or ToolContext()
    if ctx.dry_run:
        return skipped("dry_run 已开启，未真正清理镜像。", dangling_only=dangling_only)
    response = prune_docker_images(dangling_only, approve=ctx.approve_actions, settings=get_settings())
    if not response.ok and response.data.get("requires_approval"):
        return approval_required(response.message, **response.data)
    return _operation_result(response)


def list_compose_projects(ctx: ToolContext | None = None) -> dict[str, Any]:
    response = read_compose_projects()
    return success(
        f"已发现 {len(response.projects)} 个 Compose 项目。",
        **_model_data(response),
    )


def read_compose_file(path: str, ctx: ToolContext | None = None) -> dict[str, Any]:
    response = read_allowed_compose_file(path, get_settings())
    data = _model_data(response)
    if not response.editable:
        return error(response.error or "Compose 文件不可读取。", **data)
    return success("已读取 Compose 文件。", **data)


def write_compose_file(path: str, content: str, ctx: ToolContext | None = None) -> dict[str, Any]:
    ctx = ctx or ToolContext()
    if ctx.dry_run:
        return skipped("dry_run 已开启，未真正保存 Compose 文件。", path=path)
    if not ctx.approve_actions:
        # 文件写入在到达文件系统 helper 前先在这里做审批门禁。
        return approval_required("保存 Compose 文件需要用户确认。", path=path)
    return _operation_result(write_allowed_compose_file(path, content, get_settings()))


def create_compose_project(
    project_name: str,
    directory: str,
    content: str,
    filename: str = "compose.yaml",
    ctx: ToolContext | None = None,
) -> dict[str, Any]:
    ctx = ctx or ToolContext()
    if ctx.dry_run:
        return skipped(
            "dry_run 已开启，未真正创建并启动 Compose 项目。",
            project_name=project_name,
            directory=directory,
            filename=filename,
        )
    if not ctx.approve_actions:
        return approval_required(
            "创建并启动 Compose 项目需要用户确认。",
            project_name=project_name,
            directory=directory,
            filename=filename,
        )

    try:
        request = ComposeCreateRequest(
            project_name=project_name,
            directory=directory,
            filename=filename,
            content=content,
            approve=True,
        )
    except ValueError as exc:
        return error("创建 Compose 项目参数不合法。", detail=str(exc))

    return _operation_result(create_docker_compose_project(request, get_settings()))


def create_compose_project_from_url(
    project_name: str,
    directory: str,
    url: str,
    filename: str = "compose.yaml",
    ctx: ToolContext | None = None,
) -> dict[str, Any]:
    ctx = ctx or ToolContext()
    if ctx.dry_run:
        return skipped("dry_run 已开启，未真正从 URL 创建 Compose 项目。", project_name=project_name, url=url)
    if not ctx.approve_actions:
        return approval_required("从 URL 创建并启动 Compose 项目需要用户确认。", project_name=project_name, url=url)
    try:
        request = ComposeUrlCreateRequest(
            project_name=project_name,
            directory=directory,
            url=url,
            filename=filename,
            approve=True,
        )
    except ValueError as exc:
        return error("从 URL 创建 Compose 项目参数不合法。", detail=str(exc))
    return _operation_result(create_docker_compose_project_from_url(request, get_settings()))


def create_compose_project_from_git(
    project_name: str,
    directory: str,
    repository_url: str,
    branch: str | None = None,
    compose_path: str = "compose.yaml",
    ctx: ToolContext | None = None,
) -> dict[str, Any]:
    ctx = ctx or ToolContext()
    if ctx.dry_run:
        return skipped("dry_run 已开启，未真正从 Git 创建 Compose 项目。", project_name=project_name, repository_url=repository_url)
    if not ctx.approve_actions:
        return approval_required("从 Git 创建并启动 Compose 项目需要用户确认。", project_name=project_name, repository_url=repository_url)
    try:
        request = ComposeGitCreateRequest(
            project_name=project_name,
            directory=directory,
            repository_url=repository_url,
            branch=branch,
            compose_path=compose_path,
            approve=True,
        )
    except ValueError as exc:
        return error("从 Git 创建 Compose 项目参数不合法。", detail=str(exc))
    return _operation_result(create_docker_compose_project_from_git(request, get_settings()))


def compose_up(path: str, ctx: ToolContext | None = None) -> dict[str, Any]:
    return _compose_action(path, "up", ctx)


def compose_stop(path: str, ctx: ToolContext | None = None) -> dict[str, Any]:
    return _compose_action(path, "stop", ctx)


def compose_restart(path: str, ctx: ToolContext | None = None) -> dict[str, Any]:
    return _compose_action(path, "restart", ctx)


def compose_pull(path: str, ctx: ToolContext | None = None) -> dict[str, Any]:
    return _compose_action(path, "pull", ctx)


def compose_update(path: str, ctx: ToolContext | None = None) -> dict[str, Any]:
    return _compose_action(path, "update", ctx)


def compose_down(path: str, ctx: ToolContext | None = None) -> dict[str, Any]:
    return _compose_action(path, "down", ctx)


def compose_service_up(path: str, service: str, ctx: ToolContext | None = None) -> dict[str, Any]:
    return _compose_service_action(path, service, "up", ctx)


def compose_service_stop(path: str, service: str, ctx: ToolContext | None = None) -> dict[str, Any]:
    return _compose_service_action(path, service, "stop", ctx)


def compose_service_restart(path: str, service: str, ctx: ToolContext | None = None) -> dict[str, Any]:
    return _compose_service_action(path, service, "restart", ctx)


def _compose_action(path: str, action: str, ctx: ToolContext | None = None) -> dict[str, Any]:
    ctx = ctx or ToolContext()
    if ctx.dry_run:
        return skipped("dry_run 已开启，未真正执行 Compose 操作。", path=path, action=action)
    response = control_compose(path, action, approve=ctx.approve_actions, settings=get_settings())
    # 停止或删除 Compose 项目需要确认时，会由 app.docker.actions 返回 requires_approval。
    if not response.ok and response.data.get("requires_approval"):
        return approval_required(response.message, **response.data)
    return _operation_result(response)


def _compose_service_action(path: str, service: str, action: str, ctx: ToolContext | None = None) -> dict[str, Any]:
    ctx = ctx or ToolContext()
    if ctx.dry_run:
        return skipped("dry_run 已开启，未真正执行 Compose 服务操作。", path=path, service=service, action=action)
    response = control_compose_service(path, service, action, approve=ctx.approve_actions, settings=get_settings())
    if not response.ok and response.data.get("requires_approval"):
        return approval_required(response.message, **response.data)
    return _operation_result(response)


def get_compose_logs(project: str, tail: int = 200, ctx: ToolContext | None = None) -> dict[str, Any]:
    response = read_compose_logs(project, tail)
    data = _model_data(response)
    if response.error:
        return error(response.error, **data)
    return success("已读取 Compose 项目日志。", **data)


def get_compose_service_logs(project: str, service: str, tail: int = 200, ctx: ToolContext | None = None) -> dict[str, Any]:
    response = read_compose_service_logs(project, service, tail)
    data = _model_data(response)
    if response.error:
        return error(response.error, **data)
    return success("已读取 Compose 服务日志。", **data)


def get_runtime_settings(ctx: ToolContext | None = None) -> dict[str, Any]:
    response = read_runtime_settings(get_settings())
    return success("已读取运行时设置。", **_model_data(response))


def update_runtime_settings(
    log_roots: str | None = None,
    project_roots: str | None = None,
    require_dangerous_approval: bool | None = None,
    llm_base_url: str | None = None,
    llm_model: str | None = None,
    llm_api_key: str | None = None,
    docker_http_proxy: str | None = None,
    docker_https_proxy: str | None = None,
    docker_no_proxy: str | None = None,
    external_mcp_servers: str | None = None,
    enable_public_mcp: bool | None = None,
    ctx: ToolContext | None = None,
) -> dict[str, Any]:
    ctx = ctx or ToolContext()
    if ctx.dry_run:
        return skipped("dry_run 已开启，未真正保存运行时设置。")
    if not ctx.approve_actions:
        return approval_required("修改运行时设置需要用户确认。")
    response = write_runtime_settings(
        RuntimeSettingsUpdateRequest(
            log_roots=log_roots,
            project_roots=project_roots,
            require_dangerous_approval=require_dangerous_approval,
            llm_base_url=llm_base_url,
            llm_model=llm_model,
            llm_api_key=llm_api_key,
            docker_http_proxy=docker_http_proxy,
            docker_https_proxy=docker_https_proxy,
            docker_no_proxy=docker_no_proxy,
            external_mcp_servers=external_mcp_servers,
            enable_public_mcp=enable_public_mcp,
        ),
        get_settings(),
    )
    return success("运行时设置已更新。", **_model_data(response))
