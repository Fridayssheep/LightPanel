import axios from 'axios'
import type {
  ChatRequest,
  ChatResponse,
  ChatStreamEvent,
  ComposeActionRequest,
  ComposeCreateRequest,
  ComposeFileResponse,
  ComposeFileUpdateRequest,
  ComposeGitCreateRequest,
  ComposeListResponse,
  ComposeLogRequest,
  ComposeProgressEvent,
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
  ImageListResponse,
  ImagePruneRequest,
  ImagePullRequest,
  ImagePullProgressEvent,
  ImageRemoveRequest,
  ImageTagRequest,
  ImageUntagRequest,
  IncidentRecord,
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
} from './types'

const http = axios.create({
  baseURL: '/api',
  // 项目更新和镜像拉取在慢 Registry 下可能需要几分钟。
  timeout: 240000,
})

export async function getHealth(): Promise<HealthResponse> {
  const { data } = await http.get<HealthResponse>('/health')
  return data
}

export async function getTools(): Promise<ToolInfo[]> {
  const { data } = await http.get<ToolInfo[]>('/tools')
  return data
}

export async function getOverview(): Promise<OverviewResponse> {
  const { data } = await http.get<OverviewResponse>('/overview')
  return data
}

export async function listContainers(): Promise<ContainerListResponse> {
  const { data } = await http.get<ContainerListResponse>('/containers')
  return data
}

export async function createContainer(payload: ContainerCreateRequest): Promise<OperationResponse> {
  const { data } = await http.post<OperationResponse>('/containers', payload)
  return data
}

export async function runContainerAction(
  containerName: string,
  payload: ContainerActionRequest,
): Promise<OperationResponse> {
  const { data } = await http.post<OperationResponse>(`/containers/${encodeURIComponent(containerName)}/action`, payload)
  return data
}

export async function getContainerLogs(containerName: string, tail = 200): Promise<ContainerLogResponse> {
  const { data } = await http.get<ContainerLogResponse>(`/containers/${encodeURIComponent(containerName)}/logs`, {
    params: { tail },
  })
  return data
}

export async function getContainerInspect(containerName: string): Promise<ContainerInspectResponse> {
  const { data } = await http.get<ContainerInspectResponse>(`/containers/${encodeURIComponent(containerName)}/inspect`)
  return data
}

export async function getContainerProcesses(containerName: string): Promise<ContainerProcessResponse> {
  const { data } = await http.get<ContainerProcessResponse>(`/containers/${encodeURIComponent(containerName)}/processes`)
  return data
}

export async function pullImage(payload: ImagePullRequest): Promise<OperationResponse> {
  const { data } = await http.post<OperationResponse>('/images/pull', payload)
  return data
}

export async function listImages(): Promise<ImageListResponse> {
  const { data } = await http.get<ImageListResponse>('/images')
  return data
}

export async function removeImage(payload: ImageRemoveRequest): Promise<OperationResponse> {
  const { data } = await http.post<OperationResponse>('/images/remove', payload)
  return data
}

export async function pruneImages(payload: ImagePruneRequest): Promise<OperationResponse> {
  const { data } = await http.post<OperationResponse>('/images/prune', payload)
  return data
}

export async function tagImage(payload: ImageTagRequest): Promise<OperationResponse> {
  const { data } = await http.post<OperationResponse>('/images/tag', payload)
  return data
}

export async function untagImage(payload: ImageUntagRequest): Promise<OperationResponse> {
  const { data } = await http.request<OperationResponse>({
    method: 'DELETE',
    url: '/images/tag',
    data: payload,
  })
  return data
}

export async function importImage(file: File): Promise<OperationResponse> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await http.post<OperationResponse>('/images/import', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 600000,
  })
  return data
}

export function imageExportUrl(image: string): string {
  return `/api/images/${encodeURIComponent(image)}/export`
}

export function pullImageWithProgress(
  image: string,
  onProgress: (event: ImagePullProgressEvent) => void,
): Promise<OperationResponse> {
  return new Promise((resolve, reject) => {
    // 使用 EventSource 的轻量单向流接收 Docker 拉取进度。
    const source = new EventSource(`/api/images/pull/stream?image=${encodeURIComponent(image)}`)
    let finished = false

    source.onmessage = (message) => {
      const event = JSON.parse(message.data) as ImagePullProgressEvent
      onProgress(event)
      if (event.type === 'success') {
        // 把流式完成事件统一成普通 POST API 使用的 OperationResponse 结构。
        finished = true
        source.close()
        resolve({
          ok: true,
          message: event.message || '镜像拉取完成。',
          data: event as unknown as Record<string, unknown>,
          timestamp: new Date().toISOString(),
        })
      }
      if (event.type === 'error') {
        finished = true
        source.close()
        resolve({
          ok: false,
          message: event.message || '镜像拉取失败。',
          data: event as unknown as Record<string, unknown>,
          error: event.error,
          timestamp: new Date().toISOString(),
        })
      }
    }

    source.onerror = () => {
      source.close()
      if (!finished) {
        // 流关闭后 EventSource 也可能触发 error，只拒绝尚未完成的拉取。
        reject(new Error('镜像拉取进度连接失败。'))
      }
    }
  })
}

export async function listComposeProjects(): Promise<ComposeListResponse> {
  const { data } = await http.get<ComposeListResponse>('/compose')
  return data
}

export async function listNetworks(): Promise<NetworkListResponse> {
  const { data } = await http.get<NetworkListResponse>('/networks')
  return data
}

export async function createNetwork(payload: NetworkCreateRequest): Promise<OperationResponse> {
  const { data } = await http.post<OperationResponse>('/networks', payload)
  return data
}

export async function getNetworkDetail(name: string): Promise<NetworkDetailResponse> {
  const { data } = await http.get<NetworkDetailResponse>(`/networks/${encodeURIComponent(name)}`)
  return data
}

export async function runNetworkAction(name: string, payload: NetworkActionRequest): Promise<OperationResponse> {
  const { data } = await http.post<OperationResponse>(`/networks/${encodeURIComponent(name)}/action`, payload)
  return data
}

export async function listVolumes(): Promise<VolumeListResponse> {
  const { data } = await http.get<VolumeListResponse>('/volumes')
  return data
}

export async function createVolume(payload: VolumeCreateRequest): Promise<OperationResponse> {
  const { data } = await http.post<OperationResponse>('/volumes', payload)
  return data
}

export async function getVolumeDetail(name: string): Promise<VolumeDetailResponse> {
  const { data } = await http.get<VolumeDetailResponse>(`/volumes/${encodeURIComponent(name)}`)
  return data
}

export async function runVolumeAction(name: string, payload: VolumeActionRequest): Promise<OperationResponse> {
  const { data } = await http.post<OperationResponse>(`/volumes/${encodeURIComponent(name)}/action`, payload)
  return data
}

export async function getComposeFile(path: string): Promise<ComposeFileResponse> {
  const { data } = await http.get<ComposeFileResponse>('/compose/file', { params: { path } })
  return data
}

export async function saveComposeFile(payload: ComposeFileUpdateRequest): Promise<OperationResponse> {
  const { data } = await http.put<OperationResponse>('/compose/file', payload)
  return data
}

export async function createComposeProject(payload: ComposeCreateRequest): Promise<OperationResponse> {
  const { data } = await http.post<OperationResponse>('/compose/create', payload)
  return data
}

export async function createComposeProjectFromUrl(payload: ComposeUrlCreateRequest): Promise<OperationResponse> {
  const { data } = await http.post<OperationResponse>('/compose/create/from-url', payload)
  return data
}

export async function createComposeProjectFromGit(payload: ComposeGitCreateRequest): Promise<OperationResponse> {
  const { data } = await http.post<OperationResponse>('/compose/create/from-git', payload)
  return data
}

export async function runComposeAction(payload: ComposeActionRequest): Promise<OperationResponse> {
  const { data } = await http.post<OperationResponse>('/compose/action', payload)
  return data
}

export async function getComposeLogs(payload: ComposeLogRequest): Promise<ContainerLogResponse> {
  const { data } = await http.post<ContainerLogResponse>('/compose/logs', payload)
  return data
}

export async function runComposeServiceAction(payload: ComposeServiceActionRequest): Promise<OperationResponse> {
  const { data } = await http.post<OperationResponse>('/compose/service/action', payload)
  return data
}

export async function getComposeServiceLogs(payload: ComposeServiceLogRequest): Promise<ContainerLogResponse> {
  const { data } = await http.post<ContainerLogResponse>('/compose/service/logs', payload)
  return data
}

export function runComposeActionWithProgress(
  payload: ComposeActionRequest,
  onProgress: (event: ComposeProgressEvent) => void,
): Promise<OperationResponse> {
  return new Promise((resolve, reject) => {
    const params = new URLSearchParams({
      path: payload.path,
      action: payload.action,
      approve: String(Boolean(payload.approve)),
    })
    const source = new EventSource(`/api/compose/action/stream?${params.toString()}`)
    let finished = false

    source.onmessage = (message) => {
      const event = JSON.parse(message.data) as ComposeProgressEvent
      onProgress(event)
      if (event.type === 'success' || event.type === 'error') {
        finished = true
        source.close()
        if (event.response) {
          resolve(event.response)
          return
        }
        resolve({
          ok: event.type === 'success',
          message: event.message,
          data: event as unknown as Record<string, unknown>,
          error: event.error,
          timestamp: new Date().toISOString(),
        })
      }
    }

    source.onerror = () => {
      source.close()
      if (!finished) {
        reject(new Error('Compose 操作进度连接失败。'))
      }
    }
  })
}

export async function getRuntimeSettings(): Promise<RuntimeSettingsResponse> {
  const { data } = await http.get<RuntimeSettingsResponse>('/settings')
  return data
}

export async function updateRuntimeSettings(
  payload: RuntimeSettingsUpdateRequest,
): Promise<RuntimeSettingsResponse | OperationResponse> {
  const { data } = await http.patch<RuntimeSettingsResponse | OperationResponse>('/settings', payload)
  return data
}

export async function sendChat(payload: ChatRequest): Promise<ChatResponse> {
  const { data } = await http.post<ChatResponse>('/agent/chat', payload)
  return data
}

export async function sendChatStream(
  payload: ChatRequest,
  onEvent: (event: ChatStreamEvent) => void,
): Promise<ChatResponse> {
  const response = await fetch('/api/agent/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok || !response.body) {
    throw new Error(`对话流连接失败：HTTP ${response.status}`)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let finalResponse: ChatResponse | null = null

  function consumeChunk(chunk: string) {
    buffer += chunk
    const frames = buffer.split('\n\n')
    buffer = frames.pop() || ''
    for (const frame of frames) {
      const dataLine = frame
        .split('\n')
        .find(line => line.startsWith('data: '))
      if (!dataLine) continue
      const event = JSON.parse(dataLine.slice(6)) as ChatStreamEvent
      onEvent(event)
      if (event.type === 'error') {
        throw new Error(event.message)
      }
      if (event.type === 'final') {
        finalResponse = event.response
      }
    }
  }

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    consumeChunk(decoder.decode(value, { stream: true }))
  }
  consumeChunk(decoder.decode())

  if (!finalResponse) {
    throw new Error('对话流没有返回最终结果。')
  }
  return finalResponse
}

export async function listIncidents(limit = 50): Promise<IncidentRecord[]> {
  const { data } = await http.get<IncidentRecord[]>('/incidents', { params: { limit } })
  return data
}

export async function getIncident(id: string): Promise<IncidentRecord> {
  const { data } = await http.get<IncidentRecord>(`/incidents/${id}`)
  return data
}

export async function continueIncident(id: string): Promise<IncidentContinueResponse> {
  const { data } = await http.post<IncidentContinueResponse>(`/incidents/${id}/continue`)
  return data
}

export async function deleteIncident(id: string): Promise<OperationResponse> {
  const { data } = await http.delete<OperationResponse>(`/incidents/${id}`)
  return data
}

export async function generateReport(id: string): Promise<DiagnosisReport> {
  const { data } = await http.post<DiagnosisReport>(`/incidents/${id}/report`)
  return data
}

export { http }
