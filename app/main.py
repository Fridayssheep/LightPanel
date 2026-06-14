from __future__ import annotations

from contextlib import asynccontextmanager
import json
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.responses import JSONResponse

from app.agent.report import ReportService
from app.agent.service import AgentService
from app.config import get_settings
from app.docker.actions import (
    compose_file_approval_error,
    compose_create_approval_error,
    compose_command_events,
    connect_network,
    control_compose,
    control_compose_service,
    control_container,
    create_compose_project_from_git,
    create_compose_project_from_url,
    create_compose_project,
    create_container,
    create_network,
    create_volume,
    disconnect_network,
    export_image,
    get_runtime_settings,
    import_image,
    inspect_container,
    inspect_network,
    inspect_volume,
    list_networks,
    list_volumes,
    prune_networks,
    prune_volumes,
    process_container,
    prune_images,
    pull_image,
    pull_image_events,
    read_compose_file,
    read_compose_logs,
    read_compose_service_logs,
    read_container_logs,
    remove_network,
    remove_volume,
    remove_image,
    runtime_settings_approval_error,
    tag_image,
    update_runtime_settings,
    untag_image,
    write_compose_file,
)
from app.docker.overview_cache import OverviewCache
from app.docker.state import get_overview, list_compose_projects, list_container_summaries, list_image_summaries
from app.docker.tools import docker_available
from app.errors import AgentConfigError, AgentExecutionError
from app.mcp.client import MCPToolClient
from app.mcp.server import public_mcp_server
from app.schemas import (
    ChatRequest,
    ChatResponse,
    ComposeActionRequest,
    ComposeCreateRequest,
    ComposeGitCreateRequest,
    ComposeFileResponse,
    ComposeFileUpdateRequest,
    ComposeListResponse,
    ComposeLogRequest,
    ComposeServiceActionRequest,
    ComposeServiceLogRequest,
    ComposeUrlCreateRequest,
    ContainerActionRequest,
    ContainerCreateRequest,
    ContainerInspectResponse,
    ContainerListResponse,
    ContainerLogResponse,
    ContainerProcessResponse,
    DiagnosisReport,
    HealthResponse,
    IncidentContinueResponse,
    IncidentRecord,
    ImageListResponse,
    ImagePruneRequest,
    ImagePullRequest,
    ImageRemoveRequest,
    ImageTagRequest,
    ImageUntagRequest,
    NetworkActionRequest,
    NetworkCreateRequest,
    NetworkDetailResponse,
    NetworkListResponse,
    OperationResponse,
    OverviewResponse,
    RuntimeSettingsResponse,
    RuntimeSettingsUpdateRequest,
    ToolInfo,
    VolumeActionRequest,
    VolumeCreateRequest,
    VolumeDetailResponse,
    VolumeListResponse,
)
from app.storage.history import IncidentStore


settings = get_settings()

# 后端会启动自己的 stdio MCP server，让聊天工具调用和 CLI 走同一套实现。
mcp_server_script = Path(__file__).parent / "mcp" / "server.py"
mcp_client = MCPToolClient(mcp_server_script, external_config_provider=lambda: settings.external_mcp_servers)

store = IncidentStore(settings.history_file)
agent = AgentService(settings=settings, mcp_client=mcp_client, store=store)
report_service = ReportService(settings=settings)
overview_cache = OverviewCache(lambda: get_overview(settings.llm_enabled, store.list(limit=5)))
public_mcp_manager: StreamableHTTPSessionManager | None = None


def create_public_mcp_manager() -> StreamableHTTPSessionManager:
    return StreamableHTTPSessionManager(
        app=public_mcp_server,
        json_response=True,
        stateless=True,
    )


@asynccontextmanager
async def lifespan(_: FastAPI):
    global public_mcp_manager
    overview_cache.start()
    public_mcp_manager = create_public_mcp_manager()
    try:
        async with public_mcp_manager.run():
            yield
    finally:
        public_mcp_manager = None
        overview_cache.stop()


app = FastAPI(title="Ops Agent Backend", version="0.1.0", lifespan=lifespan)


class PublicMCPApp:
    async def __call__(self, scope, receive, send) -> None:  # noqa: ANN001
        if not settings.enable_public_mcp:
            response = JSONResponse({"detail": "MCP endpoint is disabled."}, status_code=404)
            await response(scope, receive, send)
            return
        if public_mcp_manager is None:
            response = JSONResponse({"detail": "MCP endpoint is not ready."}, status_code=503)
            await response(scope, receive, send)
            return
        await public_mcp_manager.handle_request(scope, receive, send)


app.add_route("/api/mcp", PublicMCPApp(), methods=["GET", "POST", "DELETE"], include_in_schema=False)


@app.get("/api/health", response_model=HealthResponse, include_in_schema=False)
@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        llm_enabled=settings.llm_enabled,
        docker_available=docker_available(),
        timestamp=datetime.now().astimezone(),
    )


@app.get("/api/tools", response_model=list[ToolInfo], include_in_schema=False)
@app.get("/tools", response_model=list[ToolInfo])
async def list_tools() -> list[ToolInfo]:
    """通过 MCP 列出可用工具。"""
    return await mcp_client.list_tools_info()


@app.get("/api/overview", response_model=OverviewResponse, include_in_schema=False)
@app.get("/overview", response_model=OverviewResponse)
def overview() -> OverviewResponse:
    snapshot = overview_cache.get()
    if snapshot:
        return snapshot
    overview_cache.request_refresh()
    return OverviewResponse(
        llm_enabled=settings.llm_enabled,
        docker_available=False,
        containers_total=0,
        running_containers=0,
        stopped_containers=0,
        compose_projects=0,
        host_memory_total=None,
        container_resources=[],
        recent_incidents=store.list(limit=5),
        error=overview_cache.last_error,
        timestamp=datetime.now().astimezone(),
    )


@app.get("/api/containers", response_model=ContainerListResponse, include_in_schema=False)
def containers() -> ContainerListResponse:
    return list_container_summaries(all=True)


@app.post("/api/containers", response_model=OperationResponse, include_in_schema=False)
def container_create(request: ContainerCreateRequest) -> OperationResponse:
    return create_container(request, settings)


@app.post("/api/containers/{container_name}/action", response_model=OperationResponse, include_in_schema=False)
def container_action(container_name: str, request: ContainerActionRequest) -> OperationResponse:
    return control_container(container_name, request.action, request.approve, settings)


@app.get("/api/containers/{container_name}/logs", response_model=ContainerLogResponse, include_in_schema=False)
def container_logs(container_name: str, tail: int = 200) -> ContainerLogResponse:
    return read_container_logs(container_name, tail=tail)


@app.get("/api/containers/{container_name}/inspect", response_model=ContainerInspectResponse, include_in_schema=False)
def container_inspect(container_name: str) -> ContainerInspectResponse:
    return inspect_container(container_name)


@app.get("/api/containers/{container_name}/processes", response_model=ContainerProcessResponse, include_in_schema=False)
def container_processes(container_name: str) -> ContainerProcessResponse:
    return process_container(container_name)


@app.get("/api/networks", response_model=NetworkListResponse, include_in_schema=False)
def networks() -> NetworkListResponse:
    return list_networks()


@app.post("/api/networks", response_model=OperationResponse, include_in_schema=False)
def network_create(request: NetworkCreateRequest) -> OperationResponse:
    return create_network(request)


@app.get("/api/networks/{network_name}", response_model=NetworkDetailResponse, include_in_schema=False)
def network_detail(network_name: str) -> NetworkDetailResponse:
    return inspect_network(network_name)


@app.post("/api/networks/{network_name}/action", response_model=OperationResponse, include_in_schema=False)
def network_action(network_name: str, request: NetworkActionRequest) -> OperationResponse:
    if request.action == "remove":
        return remove_network(network_name, request.approve, settings)
    if request.action == "prune":
        return prune_networks(request.approve, settings)
    if request.action == "connect":
        if not request.container:
            raise HTTPException(status_code=422, detail="container is required for connect")
        return connect_network(network_name, request.container)
    if request.action == "disconnect":
        if not request.container:
            raise HTTPException(status_code=422, detail="container is required for disconnect")
        return disconnect_network(network_name, request.container)
    raise HTTPException(status_code=422, detail="unsupported network action")


@app.get("/api/volumes", response_model=VolumeListResponse, include_in_schema=False)
def volumes() -> VolumeListResponse:
    return list_volumes()


@app.post("/api/volumes", response_model=OperationResponse, include_in_schema=False)
def volume_create(request: VolumeCreateRequest) -> OperationResponse:
    return create_volume(request)


@app.get("/api/volumes/{volume_name}", response_model=VolumeDetailResponse, include_in_schema=False)
def volume_detail(volume_name: str) -> VolumeDetailResponse:
    return inspect_volume(volume_name)


@app.post("/api/volumes/{volume_name}/action", response_model=OperationResponse, include_in_schema=False)
def volume_action(volume_name: str, request: VolumeActionRequest) -> OperationResponse:
    if request.action == "remove":
        return remove_volume(volume_name, request.force, request.approve, settings)
    if request.action == "prune":
        return prune_volumes(request.approve, settings)
    raise HTTPException(status_code=422, detail="unsupported volume action")


@app.get("/api/compose", response_model=ComposeListResponse, include_in_schema=False)
def compose() -> ComposeListResponse:
    return list_compose_projects()


@app.get("/api/compose/file", response_model=ComposeFileResponse, include_in_schema=False)
def compose_file(path: str) -> ComposeFileResponse:
    return read_compose_file(path, settings)


@app.put("/api/compose/file", response_model=OperationResponse, include_in_schema=False)
def save_compose_file(request: ComposeFileUpdateRequest) -> OperationResponse:
    # 接口与工具策略保持一致：开启确认策略时，写文件必须带明确确认标记。
    if settings.require_dangerous_approval and not request.approve:
        return compose_file_approval_error(request.path)
    return write_compose_file(request.path, request.content, settings)


@app.post("/api/compose/create", response_model=OperationResponse, include_in_schema=False)
def compose_create(request: ComposeCreateRequest) -> OperationResponse:
    if settings.require_dangerous_approval and not request.approve:
        return compose_create_approval_error(request.project_name)
    return create_compose_project(request, settings)


@app.post("/api/compose/create/from-url", response_model=OperationResponse, include_in_schema=False)
def compose_create_from_url(request: ComposeUrlCreateRequest) -> OperationResponse:
    return create_compose_project_from_url(request, settings)


@app.post("/api/compose/create/from-git", response_model=OperationResponse, include_in_schema=False)
def compose_create_from_git(request: ComposeGitCreateRequest) -> OperationResponse:
    return create_compose_project_from_git(request, settings)


@app.post("/api/compose/action", response_model=OperationResponse, include_in_schema=False)
def compose_action(request: ComposeActionRequest) -> OperationResponse:
    return control_compose(request.path, request.action, request.approve, settings)


@app.get("/api/compose/action/stream", include_in_schema=False)
def compose_action_stream(path: str, action: str, approve: bool = False) -> StreamingResponse:
    def event_stream():
        for event in compose_command_events(path, action, approve, settings):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/compose/service/action", response_model=OperationResponse, include_in_schema=False)
def compose_service_action(request: ComposeServiceActionRequest) -> OperationResponse:
    return control_compose_service(request.path, request.service, request.action, request.approve, settings)


@app.post("/api/compose/logs", response_model=ContainerLogResponse, include_in_schema=False)
def compose_logs(request: ComposeLogRequest) -> ContainerLogResponse:
    return read_compose_logs(request.project, request.tail)


@app.post("/api/compose/service/logs", response_model=ContainerLogResponse, include_in_schema=False)
def compose_service_logs(request: ComposeServiceLogRequest) -> ContainerLogResponse:
    return read_compose_service_logs(request.project, request.service, request.tail)


@app.get("/api/images", response_model=ImageListResponse, include_in_schema=False)
def images() -> ImageListResponse:
    return list_image_summaries()


@app.post("/api/images/pull", response_model=OperationResponse, include_in_schema=False)
def image_pull(request: ImagePullRequest) -> OperationResponse:
    return pull_image(request.image)


@app.get("/api/images/pull/stream", include_in_schema=False)
def image_pull_stream(image: str) -> StreamingResponse:
    image_name = image.strip()
    if not image_name or len(image_name) > 300:
        raise HTTPException(status_code=422, detail="镜像名称不能为空，且不能超过 300 个字符。")

    def event_stream():
        # 每个事件都是一行 JSON payload，供浏览器 EventSource 消费。
        for event in pull_image_events(image_name, settings):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/images/remove", response_model=OperationResponse, include_in_schema=False)
def image_remove(request: ImageRemoveRequest) -> OperationResponse:
    return remove_image(request.image, request.force, request.approve, settings)


@app.post("/api/images/tag", response_model=OperationResponse, include_in_schema=False)
def image_tag(request: ImageTagRequest) -> OperationResponse:
    return tag_image(request.source, request.repository, request.tag)


@app.delete("/api/images/tag", response_model=OperationResponse, include_in_schema=False)
def image_untag(request: ImageUntagRequest) -> OperationResponse:
    return untag_image(request.image)


@app.post("/api/images/import", response_model=OperationResponse, include_in_schema=False)
async def image_import(file: UploadFile = File(...)) -> OperationResponse:
    filename = Path(file.filename or "image.tar").name
    if not filename.endswith((".tar", ".tar.gz", ".tgz")):
        raise HTTPException(status_code=422, detail="只支持 tar/tar.gz/tgz 镜像文件。")
    upload_dir = settings.data_dir / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    target = upload_dir / filename
    try:
        content = await file.read()
        target.write_bytes(content)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return import_image(target)


@app.get("/api/images/{image:path}/export", include_in_schema=False)
def image_export(image: str) -> FileResponse:
    output_dir = settings.data_dir / "exports"
    response = export_image(image, output_dir)
    if not response.ok:
        raise HTTPException(status_code=404, detail=response.error or response.message)
    return FileResponse(
        response.data["path"],
        media_type="application/x-tar",
        filename=str(response.data.get("filename") or "image.tar"),
    )


@app.post("/api/images/prune", response_model=OperationResponse, include_in_schema=False)
def image_prune(request: ImagePruneRequest) -> OperationResponse:
    return prune_images(request.dangling_only, request.approve, settings)


@app.get("/api/settings", response_model=RuntimeSettingsResponse, include_in_schema=False)
def runtime_settings() -> RuntimeSettingsResponse:
    return get_runtime_settings(settings)


@app.patch("/api/settings", response_model=RuntimeSettingsResponse | OperationResponse, include_in_schema=False)
def update_settings(request: RuntimeSettingsUpdateRequest) -> RuntimeSettingsResponse | OperationResponse:
    if settings.require_dangerous_approval and not request.approve:
        return runtime_settings_approval_error()
    response = update_runtime_settings(request, settings)
    mcp_client.clear_cache()
    return response


@app.post("/api/agent/chat", response_model=ChatResponse, include_in_schema=False)
@app.post("/agent/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    try:
        return await agent.handle_chat(request)
    except AgentConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AgentExecutionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/agent/chat/stream", include_in_schema=False)
@app.post("/agent/chat/stream", include_in_schema=False)
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    async def event_stream():
        try:
            async for event in agent.stream_chat(request):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except AgentConfigError as exc:
            yield f"data: {json.dumps({'type': 'error', 'status_code': 503, 'message': str(exc)}, ensure_ascii=False)}\n\n"
        except AgentExecutionError as exc:
            yield f"data: {json.dumps({'type': 'error', 'status_code': 502, 'message': str(exc)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/incidents", response_model=list[IncidentRecord], include_in_schema=False)
@app.get("/incidents", response_model=list[IncidentRecord])
def list_incidents(limit: int = 50) -> list[IncidentRecord]:
    return store.list(limit=max(1, min(limit, 200)))


@app.get("/api/incidents/{incident_id}", response_model=IncidentRecord, include_in_schema=False)
@app.get("/incidents/{incident_id}", response_model=IncidentRecord)
def get_incident(incident_id: str) -> IncidentRecord:
    record = store.get(incident_id)
    if not record:
        raise HTTPException(status_code=404, detail="Incident not found")
    return record


@app.delete("/api/incidents/{incident_id}", response_model=OperationResponse, include_in_schema=False)
@app.delete("/incidents/{incident_id}", response_model=OperationResponse)
def delete_incident(incident_id: str) -> OperationResponse:
    deleted = store.delete(incident_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Incident not found")
    return OperationResponse(
        ok=True,
        message="历史记录已删除。",
        data={"incident_id": incident_id},
    )


@app.post("/api/incidents/{incident_id}/continue", response_model=IncidentContinueResponse, include_in_schema=False)
@app.post("/incidents/{incident_id}/continue", response_model=IncidentContinueResponse)
def continue_incident(incident_id: str) -> IncidentContinueResponse:
    record = store.get(incident_id)
    if not record:
        raise HTTPException(status_code=404, detail="Incident not found")
    session_records = store.session_until(incident_id)
    # 重建截至所选事件的聊天上下文，便于继续追问。
    return IncidentContinueResponse(
        source_incident_id=record.incident_id,
        session_id=record.session_id,
        history=[
            message
            for item in session_records
            for message in (
                {"role": "user", "content": item.user_message[-4000:]},
                {"role": "assistant", "content": item.answer[-4000:]},
            )
        ],
    )


@app.post("/api/incidents/{incident_id}/report", response_model=DiagnosisReport, include_in_schema=False)
@app.post("/incidents/{incident_id}/report", response_model=DiagnosisReport)
async def generate_report(incident_id: str) -> DiagnosisReport:
    record = store.get(incident_id)
    if not record:
        raise HTTPException(status_code=404, detail="Incident not found")
    try:
        return await report_service.generate(record)
    except AgentConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AgentExecutionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


# 所有 API 路由之后再提供已构建的 Vue 应用。无扩展名路径按 SPA 路由处理，
# 带扩展名但不存在的资源路径仍返回 404。
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    static_root = static_dir.resolve()
    index_file = static_root / "index.html"

    @app.get("/", include_in_schema=False)
    def spa_index() -> FileResponse:
        return FileResponse(index_file)

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str) -> FileResponse:
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")

        target = (static_root / full_path).resolve()
        if target.is_relative_to(static_root) and target.is_file():
            return FileResponse(target)

        if Path(full_path).suffix:
            raise HTTPException(status_code=404, detail="Not found")

        return FileResponse(index_file)
