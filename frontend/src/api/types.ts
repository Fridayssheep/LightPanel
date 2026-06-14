export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface ToolCallRecord {
  id: string
  tool_name: string
  arguments: Record<string, unknown>
  status: 'success' | 'error' | 'approval_required' | 'skipped'
  summary: string
  data: Record<string, unknown>
  destructive: boolean
  requires_approval: boolean
}

export interface AgentTraceStep {
  id: string
  type: 'analysis' | 'tool_call' | 'summary'
  title: string
  summary: string
  tool_name?: string | null
  arguments: Record<string, unknown>
  status?: 'success' | 'error' | 'approval_required' | 'skipped' | null
}

export interface PendingAction {
  tool_name: string
  arguments: Record<string, unknown>
  reason: string
}

export interface ChatResponse {
  incident_id: string
  session_id: string
  answer: string
  tool_calls: ToolCallRecord[]
  agent_trace: AgentTraceStep[]
  pending_actions: PendingAction[]
  used_llm: boolean
  created_at: string
}

export type ChatStreamEvent =
  | {
      type: 'tool_call_start'
      tool_name: string
      arguments: Record<string, unknown>
    }
  | {
      type: 'tool_call_done'
      tool_name: string
      status: 'success' | 'error' | 'approval_required' | 'skipped'
      summary: string
    }
  | {
      type: 'final'
      response: ChatResponse
    }
  | {
      type: 'error'
      status_code?: number
      message: string
    }

export interface IncidentRecord extends ChatResponse {
  user_message: string
}

export interface IncidentContinueResponse {
  source_incident_id: string
  session_id: string
  history: ChatMessage[]
}

export interface HealthResponse {
  status: string
  llm_enabled: boolean
  docker_available: boolean
  timestamp: string
}

export interface ContainerSummary {
  id: string
  name: string
  image?: string | null
  status: string
  ports: Record<string, unknown>
  created?: string | null
  compose_project?: string | null
  compose_service?: string | null
  compose_working_dir?: string | null
  compose_config_files?: string | null
}

export interface ContainerListResponse {
  docker_available: boolean
  containers: ContainerSummary[]
  error?: string | null
  timestamp: string
}

export interface ContainerResourceUsage {
  id: string
  name: string
  image?: string | null
  status: string
  cpu_percent: number
  memory_usage: number
  memory_limit?: number | null
  memory_percent: number
  storage_size: number
  storage_virtual_size: number
  error?: string | null
}

export interface OperationResponse {
  ok: boolean
  message: string
  data: Record<string, unknown>
  error?: string | null
  timestamp: string
}

export interface ContainerActionRequest {
  action: 'start' | 'stop' | 'restart' | 'update' | 'pause' | 'unpause' | 'delete'
  approve?: boolean
}

export type RestartPolicyName = 'no' | 'on-failure' | 'always' | 'unless-stopped'

export interface ContainerPortBinding {
  container_port: string
  host_port?: string | null
  protocol: 'tcp' | 'udp' | 'tcp/udp'
  host_ip: string
}

export interface ContainerEnvVar {
  key: string
  value: string
}

export interface ContainerVolumeMount {
  host_path: string
  container_path: string
  mode: 'ro' | 'rw'
}

export interface ContainerCreateRequest {
  image: string
  name?: string | null
  command?: string | null
  env: ContainerEnvVar[]
  ports: ContainerPortBinding[]
  volumes: ContainerVolumeMount[]
  restart_policy: RestartPolicyName
  network?: string | null
  privileged: boolean
  cap_add: string[]
  resource_limits_enabled?: boolean
  cpu_priority?: number | null
  memory_limit_mb?: number | null
  pull_if_missing: boolean
  start: boolean
}

export interface ContainerLogResponse {
  docker_available: boolean
  container_name: string
  tail: number
  content: string
  error?: string | null
  timestamp: string
}

export interface ContainerInspectResponse {
  docker_available: boolean
  container_name: string
  inspect: Record<string, unknown>
  error?: string | null
  timestamp: string
}

export interface ContainerProcessResponse {
  docker_available: boolean
  container_name: string
  titles: string[]
  processes: Record<string, string>[]
  error?: string | null
  timestamp: string
}

export interface ImagePullRequest {
  image: string
}

export interface ImagePullProgressEvent {
  type: 'start' | 'progress' | 'success' | 'error'
  image: string
  id?: string | null
  status?: string
  message?: string
  current?: number
  total?: number
  percent?: number | null
  tags?: string[]
  error?: string
  detail?: Record<string, unknown>
  proxy_configured?: boolean
}

export interface ImageSummary {
  id: string
  short_id: string
  tags: string[]
  repo_digests: string[]
  size: number
  created?: string | null
  labels: Record<string, string>
  containers: number
  running_containers: number
}

export interface ImageListResponse {
  docker_available: boolean
  images: ImageSummary[]
  error?: string | null
  timestamp: string
}

export interface ImageRemoveRequest {
  image: string
  force?: boolean
  approve?: boolean
}

export interface ImagePruneRequest {
  dangling_only?: boolean
  approve?: boolean
}

export interface ImageTagRequest {
  source: string
  repository: string
  tag: string
}

export interface ImageUntagRequest {
  image: string
}

export interface NetworkSummary {
  id: string
  short_id: string
  name: string
  driver?: string | null
  scope?: string | null
  internal: boolean
  attachable: boolean
  containers: number
  ipam: Record<string, unknown>
  labels: Record<string, string>
}

export interface NetworkListResponse {
  docker_available: boolean
  networks: NetworkSummary[]
  error?: string | null
  timestamp: string
}

export interface NetworkDetailResponse {
  docker_available: boolean
  name: string
  detail: Record<string, unknown>
  error?: string | null
  timestamp: string
}

export interface NetworkCreateRequest {
  name: string
  driver: 'bridge' | 'macvlan' | 'ipvlan' | 'overlay'
  subnet?: string | null
  gateway?: string | null
  internal: boolean
  attachable: boolean
}

export interface NetworkActionRequest {
  action: 'remove' | 'prune' | 'connect' | 'disconnect'
  container?: string | null
  approve?: boolean
}

export interface VolumeSummary {
  name: string
  driver?: string | null
  mountpoint?: string | null
  scope?: string | null
  labels: Record<string, string>
  options: Record<string, string>
  containers: string[]
}

export interface VolumeListResponse {
  docker_available: boolean
  volumes: VolumeSummary[]
  error?: string | null
  timestamp: string
}

export interface VolumeDetailResponse {
  docker_available: boolean
  name: string
  detail: Record<string, unknown>
  containers: string[]
  error?: string | null
  timestamp: string
}

export interface VolumeCreateRequest {
  name: string
  driver: string
  labels?: Record<string, string>
}

export interface VolumeActionRequest {
  action: 'remove' | 'prune'
  force?: boolean
  approve?: boolean
}

export interface ComposeServiceSummary {
  name: string
  container_count: number
  running_count: number
  containers: ContainerSummary[]
  declared: boolean
  image?: string | null
  container_name?: string | null
}

export interface ComposeProjectSummary {
  name: string
  services: ComposeServiceSummary[]
  container_count: number
  running_count: number
  state: 'active' | 'inactive' | 'internal'
  sources: string[]
  compose_file?: string | null
  compose_files: string[]
  working_dir?: string | null
  declared_services: string[]
}

export interface ComposeListResponse {
  docker_available: boolean
  projects: ComposeProjectSummary[]
  error?: string | null
  scan_roots: string[]
  scan_errors: string[]
  timestamp: string
}

export interface ComposeFileResponse {
  path: string
  content: string
  editable: boolean
  error?: string | null
  timestamp: string
}

export interface ComposeFileUpdateRequest {
  path: string
  content: string
  approve?: boolean
}

export interface ComposeCreateRequest {
  project_name: string
  directory: string
  filename: string
  content: string
  approve?: boolean
}

export interface ComposeUrlCreateRequest {
  project_name: string
  directory: string
  url: string
  filename: string
  approve?: boolean
}

export interface ComposeGitCreateRequest {
  project_name: string
  directory: string
  repository_url: string
  branch?: string | null
  compose_path: string
  approve?: boolean
}

export interface ComposeActionRequest {
  path: string
  action: 'up' | 'stop' | 'restart' | 'pull' | 'update' | 'down'
  approve?: boolean
}

export interface ComposeLogRequest {
  project: string
  tail?: number
}

export interface ComposeServiceActionRequest {
  path: string
  service: string
  action: 'up' | 'stop' | 'restart'
  approve?: boolean
}

export interface ComposeServiceLogRequest {
  project: string
  service: string
  tail?: number
}

export interface ComposeProgressEvent {
  type: 'start' | 'progress' | 'success' | 'error'
  path: string
  action: string
  message: string
  output?: string
  response?: OperationResponse
  error?: string | null
}

export interface RuntimeSettingsResponse {
  app_name: string
  log_roots: string
  project_roots: string
  require_dangerous_approval: boolean
  llm_enabled: boolean
  llm_base_url: string
  llm_model: string
  docker_http_proxy: string
  docker_https_proxy: string
  docker_no_proxy: string
  external_mcp_servers: string
  enable_public_mcp: boolean
  timestamp: string
}

export interface RuntimeSettingsUpdateRequest {
  log_roots?: string
  project_roots?: string
  require_dangerous_approval?: boolean
  llm_base_url?: string
  llm_model?: string
  llm_api_key?: string
  docker_http_proxy?: string
  docker_https_proxy?: string
  docker_no_proxy?: string
  external_mcp_servers?: string
  enable_public_mcp?: boolean
  approve?: boolean
}

export interface OverviewResponse {
  llm_enabled: boolean
  docker_available: boolean
  containers_total: number
  running_containers: number
  stopped_containers: number
  compose_projects: number
  host_memory_total?: number | null
  container_resources: ContainerResourceUsage[]
  recent_incidents: IncidentRecord[]
  error?: string | null
  timestamp: string
}

export interface ToolInfo {
  name: string
  description: string
  destructive: boolean
  requires_approval: boolean
  parameters: Record<string, unknown>
}

export interface DiagnosisReport {
  incident_id: string
  title: string
  symptom: string
  checked_items: string[]
  findings: string[]
  root_cause: string
  recommendations: string[]
  final_status: string
  severity: 'info' | 'low' | 'medium' | 'high'
  generated_at: string
}

export interface ChatRequest {
  message: string
  session_id?: string
  history?: ChatMessage[]
  approve_actions?: boolean
  dry_run?: boolean
  max_tool_rounds?: number
}
