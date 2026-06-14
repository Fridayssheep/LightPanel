from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


ToolStatus = Literal["success", "error", "approval_required", "skipped"]
ChatRole = Literal["user", "assistant"]
AgentTraceType = Literal["analysis", "tool_call", "summary"]
ComposeProjectState = Literal["active", "inactive", "internal"]
ContainerAction = Literal["start", "stop", "restart", "update", "pause", "unpause", "delete"]
ComposeAction = Literal["up", "stop", "restart", "pull", "update", "down"]
ComposeServiceAction = Literal["up", "stop", "restart"]
RestartPolicyName = Literal["no", "on-failure", "always", "unless-stopped"]
VolumeMode = Literal["ro", "rw"]


class ChatMessage(BaseModel):
    role: ChatRole
    content: str = Field(..., min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User request in natural language.")
    session_id: str | None = Field(default=None, description="Optional conversation/session id.")
    history: list[ChatMessage] = Field(default_factory=list, description="Short-term conversation context.")
    approve_actions: bool = Field(default=False, description="Whether state-changing tools may run.")
    dry_run: bool = Field(default=False, description="Plan actions without executing state changes.")
    max_tool_rounds: int = Field(default=3, ge=1, le=5)


class ToolCallRecord(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    status: ToolStatus
    summary: str
    data: dict[str, Any] = Field(default_factory=dict)
    destructive: bool = False
    requires_approval: bool = False


class AgentTraceStep(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    type: AgentTraceType
    title: str
    summary: str
    tool_name: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    status: ToolStatus | None = None


class PendingAction(BaseModel):
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    reason: str


class ChatResponse(BaseModel):
    incident_id: str
    session_id: str
    answer: str
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    agent_trace: list[AgentTraceStep] = Field(default_factory=list)
    pending_actions: list[PendingAction] = Field(default_factory=list)
    used_llm: bool = False
    created_at: datetime


class IncidentRecord(ChatResponse):
    user_message: str


class IncidentContinueResponse(BaseModel):
    source_incident_id: str
    session_id: str
    history: list[ChatMessage]


class HealthResponse(BaseModel):
    status: str
    llm_enabled: bool
    docker_available: bool
    timestamp: datetime


class OperationResponse(BaseModel):
    ok: bool
    message: str
    data: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now().astimezone())


class ContainerSummary(BaseModel):
    id: str
    name: str
    image: str | None = None
    status: str
    ports: dict[str, Any] = Field(default_factory=dict)
    created: str | None = None
    compose_project: str | None = None
    compose_service: str | None = None
    compose_working_dir: str | None = None
    compose_config_files: str | None = None


class ContainerListResponse(BaseModel):
    docker_available: bool
    containers: list[ContainerSummary] = Field(default_factory=list)
    error: str | None = None
    timestamp: datetime


class ContainerResourceUsage(BaseModel):
    id: str
    name: str
    image: str | None = None
    status: str
    cpu_percent: float = 0
    memory_usage: int = 0
    memory_limit: int | None = None
    memory_percent: float = 0
    storage_size: int = 0
    storage_virtual_size: int = 0
    error: str | None = None


class ContainerActionRequest(BaseModel):
    action: ContainerAction
    approve: bool = False


class ContainerPortBinding(BaseModel):
    container_port: str = Field(..., min_length=1, max_length=32)
    host_port: str | None = Field(default=None, max_length=16)
    protocol: Literal["tcp", "udp", "tcp/udp"] = "tcp"
    host_ip: str = Field(default="0.0.0.0", max_length=64)


class ContainerEnvVar(BaseModel):
    key: str = Field(..., min_length=1, max_length=200)
    value: str = Field(default="", max_length=4000)


class ContainerVolumeMount(BaseModel):
    host_path: str = Field(..., min_length=1, max_length=1000)
    container_path: str = Field(..., min_length=1, max_length=1000)
    mode: VolumeMode = "rw"


class ContainerCreateRequest(BaseModel):
    image: str = Field(..., min_length=1, max_length=300)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    command: str | None = Field(default=None, max_length=4000)
    env: list[ContainerEnvVar] = Field(default_factory=list)
    ports: list[ContainerPortBinding] = Field(default_factory=list)
    volumes: list[ContainerVolumeMount] = Field(default_factory=list)
    restart_policy: RestartPolicyName = "unless-stopped"
    network: str | None = Field(default=None, max_length=120)
    privileged: bool = False
    cap_add: list[str] = Field(default_factory=list)
    resource_limits_enabled: bool = False
    cpu_priority: int | None = Field(default=None, ge=2, le=262_144)
    memory_limit_mb: int | None = Field(default=None, ge=4, le=4_194_304)
    pull_if_missing: bool = False
    start: bool = True


class ContainerLogResponse(BaseModel):
    docker_available: bool
    container_name: str
    tail: int
    content: str = ""
    error: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now().astimezone())


class ContainerInspectResponse(BaseModel):
    docker_available: bool
    container_name: str
    inspect: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now().astimezone())


class ContainerProcessResponse(BaseModel):
    docker_available: bool
    container_name: str
    titles: list[str] = Field(default_factory=list)
    processes: list[dict[str, str]] = Field(default_factory=list)
    error: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now().astimezone())


class ImagePullRequest(BaseModel):
    image: str = Field(..., min_length=1, max_length=300)


class ImageSummary(BaseModel):
    id: str
    short_id: str
    tags: list[str] = Field(default_factory=list)
    repo_digests: list[str] = Field(default_factory=list)
    size: int = 0
    created: str | None = None
    labels: dict[str, str] = Field(default_factory=dict)
    containers: int = 0
    running_containers: int = 0


class ImageListResponse(BaseModel):
    docker_available: bool
    images: list[ImageSummary] = Field(default_factory=list)
    error: str | None = None
    timestamp: datetime


class ImageRemoveRequest(BaseModel):
    image: str = Field(..., min_length=1, max_length=300)
    force: bool = False
    approve: bool = False


class ImagePruneRequest(BaseModel):
    dangling_only: bool = True
    approve: bool = False


class ImageTagRequest(BaseModel):
    source: str = Field(..., min_length=1, max_length=300)
    repository: str = Field(..., min_length=1, max_length=300)
    tag: str = Field(default="latest", min_length=1, max_length=128)


class ImageUntagRequest(BaseModel):
    image: str = Field(..., min_length=1, max_length=300)


class NetworkSummary(BaseModel):
    id: str
    short_id: str
    name: str
    driver: str | None = None
    scope: str | None = None
    internal: bool = False
    attachable: bool = False
    containers: int = 0
    ipam: dict[str, Any] = Field(default_factory=dict)
    labels: dict[str, str] = Field(default_factory=dict)


class NetworkListResponse(BaseModel):
    docker_available: bool
    networks: list[NetworkSummary] = Field(default_factory=list)
    error: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now().astimezone())


class NetworkDetailResponse(BaseModel):
    docker_available: bool
    name: str
    detail: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now().astimezone())


class NetworkCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    driver: Literal["bridge", "macvlan", "ipvlan", "overlay"] = "bridge"
    subnet: str | None = Field(default=None, max_length=128)
    gateway: str | None = Field(default=None, max_length=128)
    internal: bool = False
    attachable: bool = False


class NetworkActionRequest(BaseModel):
    action: Literal["remove", "prune", "connect", "disconnect"]
    container: str | None = Field(default=None, max_length=300)
    approve: bool = False


class VolumeSummary(BaseModel):
    name: str
    driver: str | None = None
    mountpoint: str | None = None
    scope: str | None = None
    labels: dict[str, str] = Field(default_factory=dict)
    options: dict[str, str] = Field(default_factory=dict)
    containers: list[str] = Field(default_factory=list)


class VolumeListResponse(BaseModel):
    docker_available: bool
    volumes: list[VolumeSummary] = Field(default_factory=list)
    error: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now().astimezone())


class VolumeDetailResponse(BaseModel):
    docker_available: bool
    name: str
    detail: dict[str, Any] = Field(default_factory=dict)
    containers: list[str] = Field(default_factory=list)
    error: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now().astimezone())


class VolumeCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    driver: str = Field(default="local", max_length=120)
    labels: dict[str, str] = Field(default_factory=dict)


class VolumeActionRequest(BaseModel):
    action: Literal["remove", "prune"]
    force: bool = False
    approve: bool = False


class ComposeServiceSummary(BaseModel):
    name: str
    container_count: int
    running_count: int
    containers: list[ContainerSummary] = Field(default_factory=list)
    declared: bool = False
    image: str | None = None
    container_name: str | None = None


class ComposeProjectSummary(BaseModel):
    name: str
    services: list[ComposeServiceSummary] = Field(default_factory=list)
    container_count: int
    running_count: int
    state: ComposeProjectState = "inactive"
    sources: list[str] = Field(default_factory=list)
    compose_file: str | None = None
    compose_files: list[str] = Field(default_factory=list)
    working_dir: str | None = None
    declared_services: list[str] = Field(default_factory=list)


class ComposeListResponse(BaseModel):
    docker_available: bool
    projects: list[ComposeProjectSummary] = Field(default_factory=list)
    error: str | None = None
    scan_roots: list[str] = Field(default_factory=list)
    scan_errors: list[str] = Field(default_factory=list)
    timestamp: datetime


class ComposeFileResponse(BaseModel):
    path: str
    content: str
    editable: bool
    error: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now().astimezone())


class ComposeFileUpdateRequest(BaseModel):
    path: str = Field(..., min_length=1)
    content: str = Field(..., max_length=200_000)
    approve: bool = False


class ComposeCreateRequest(BaseModel):
    project_name: str = Field(..., min_length=1, max_length=120)
    directory: str = Field(..., min_length=1, max_length=1000)
    filename: str = Field(default="compose.yaml", min_length=1, max_length=64)
    content: str = Field(..., min_length=1, max_length=200_000)
    approve: bool = False


class ComposeUrlCreateRequest(BaseModel):
    project_name: str = Field(..., min_length=1, max_length=120)
    directory: str = Field(..., min_length=1, max_length=1000)
    url: str = Field(..., min_length=1, max_length=2000)
    filename: str = Field(default="compose.yaml", min_length=1, max_length=64)
    approve: bool = False


class ComposeGitCreateRequest(BaseModel):
    project_name: str = Field(..., min_length=1, max_length=120)
    directory: str = Field(..., min_length=1, max_length=1000)
    repository_url: str = Field(..., min_length=1, max_length=2000)
    branch: str | None = Field(default=None, max_length=200)
    compose_path: str = Field(default="compose.yaml", min_length=1, max_length=1000)
    approve: bool = False


class ComposeActionRequest(BaseModel):
    path: str = Field(..., min_length=1)
    action: ComposeAction
    approve: bool = False


class ComposeServiceActionRequest(BaseModel):
    path: str = Field(..., min_length=1)
    service: str = Field(..., min_length=1, max_length=200)
    action: ComposeServiceAction
    approve: bool = False


class ComposeServiceLogRequest(BaseModel):
    project: str = Field(..., min_length=1)
    service: str = Field(..., min_length=1, max_length=200)
    tail: int = Field(default=200, ge=1, le=2000)


class ComposeLogRequest(BaseModel):
    project: str = Field(..., min_length=1)
    tail: int = Field(default=200, ge=1, le=2000)


class RuntimeSettingsResponse(BaseModel):
    app_name: str
    log_roots: str
    project_roots: str
    require_dangerous_approval: bool
    llm_enabled: bool
    llm_base_url: str
    llm_model: str
    docker_http_proxy: str = ""
    docker_https_proxy: str = ""
    docker_no_proxy: str = ""
    external_mcp_servers: str = ""
    enable_public_mcp: bool = False
    timestamp: datetime = Field(default_factory=lambda: datetime.now().astimezone())


class RuntimeSettingsUpdateRequest(BaseModel):
    log_roots: str | None = Field(default=None, max_length=4000)
    project_roots: str | None = Field(default=None, max_length=4000)
    require_dangerous_approval: bool | None = None
    llm_base_url: str | None = Field(default=None, max_length=1000)
    llm_model: str | None = Field(default=None, max_length=300)
    llm_api_key: str | None = Field(default=None, max_length=4000)
    docker_http_proxy: str | None = Field(default=None, max_length=1000)
    docker_https_proxy: str | None = Field(default=None, max_length=1000)
    docker_no_proxy: str | None = Field(default=None, max_length=2000)
    external_mcp_servers: str | None = Field(default=None, max_length=20000)
    enable_public_mcp: bool | None = None
    approve: bool = False


class OverviewResponse(BaseModel):
    llm_enabled: bool
    docker_available: bool
    containers_total: int
    running_containers: int
    stopped_containers: int
    compose_projects: int
    host_memory_total: int | None = None
    container_resources: list[ContainerResourceUsage] = Field(default_factory=list)
    recent_incidents: list[IncidentRecord] = Field(default_factory=list)
    error: str | None = None
    timestamp: datetime


class ToolInfo(BaseModel):
    name: str
    description: str
    destructive: bool = False
    requires_approval: bool = False
    parameters: dict[str, Any] = Field(default_factory=dict)


class DiagnosisReport(BaseModel):
    incident_id: str
    title: str = Field(..., description="One-line incident title.")
    symptom: str = Field(..., description="故障现象描述。")
    checked_items: list[str] = Field(default_factory=list, description="已检查项。")
    findings: list[str] = Field(default_factory=list, description="主要发现。")
    root_cause: str = Field(default="", description="根因分析。")
    recommendations: list[str] = Field(default_factory=list, description="处理建议。")
    final_status: str = Field(default="", description="最终状态。")
    severity: Literal["info", "low", "medium", "high"] = Field(default="info")
    generated_at: datetime
