<template>
  <section class="page-shell containers-view">
    <header class="page-header">
      <div>
        <p class="eyebrow">Docker 容器管理</p>
        <h1 class="page-title">容器管理</h1>
        <p class="page-subtitle">查看容器状态，执行启动、停止、重启、更新和查看日志</p>
      </div>
      <div class="header-actions">
        <button class="secondary-button" type="button" @click="createWizardOpen = true">
          <span class="material-symbol">add_box</span>
          创建容器
        </button>
        <button class="toolbar-button" type="button" @click="loadContainers" :disabled="loading">
          <span class="material-symbol" :class="{ spinning: loading }">{{ loading ? 'progress_activity' : 'refresh' }}</span>
          {{ loading ? '刷新中' : '刷新' }}
        </button>
      </div>
    </header>

    <NoticeBanner v-if="notice" :ok="notice.ok" :message="notice.message" />

    <CreateContainerWizard
      :open="createWizardOpen"
      @close="createWizardOpen = false"
      @created="handleContainerCreated"
      @notice="notice = $event"
    />

    <div v-if="response?.error" class="error-banner">Docker 连接异常：{{ response.error }}</div>

    <MotionSurface class="table-panel" :interactive="false" :delay="45">
      <div class="table-summary">
        <span class="summary-count">总计 {{ containers.length }} 个容器</span>
      </div>

      <div v-if="!containers.length" class="empty-state">没有可显示的容器</div>
      <div v-else class="container-table">
        <div key="container-table-head" class="table-head">
          <span>名称</span>
          <span>镜像</span>
          <span>状态</span>
          <span>端口</span>
          <span>Compose</span>
          <span>操作</span>
        </div>
        <article
          v-for="(container, idx) in containers"
          :key="container.id"
          class="container-row motion-item"
          :class="{ expanded: expandedContainerName === container.name }"
          :style="{ '--motion-delay': `${Math.min(idx, 12) * 30}ms` }"
        >
          <div class="table-row-main">
            <div>
              <strong>{{ container.name }}</strong>
              <small>{{ container.id }}</small>
            </div>
            <span class="mono">{{ container.image || '-' }}</span>
            <span class="status-pill" :class="container.status">
              <span class="status-dot"></span>
              {{ container.status }}
            </span>
            <span class="mono">{{ formatPorts(container.ports) }}</span>
            <span>{{ composeLabel(container) }}</span>
            <div class="row-actions">
              <button
                class="icon-action"
                type="button"
                title="启动"
                :disabled="isBusy(container.name) || container.status === 'running'"
                @click="handleContainerAction(container, 'start')"
              >
                <span class="material-symbol" :class="{ spinning: isBusy(container.name) }">
                  {{ isBusy(container.name) ? 'progress_activity' : 'play_arrow' }}
                </span>
              </button>
              <button
                class="icon-action danger"
                type="button"
                title="停止"
                :disabled="isBusy(container.name) || container.status !== 'running'"
                @click="handleContainerAction(container, 'stop')"
              >
                <span class="material-symbol" :class="{ spinning: isBusy(container.name) }">
                  {{ isBusy(container.name) ? 'progress_activity' : 'stop' }}
                </span>
              </button>
              <button
                class="icon-action"
                type="button"
                title="重启"
                :disabled="isBusy(container.name)"
                @click="handleContainerAction(container, 'restart')"
              >
                <span class="material-symbol" :class="{ spinning: isBusy(container.name) }">
                  {{ isBusy(container.name) ? 'progress_activity' : 'restart_alt' }}
                </span>
              </button>
              <button
                class="icon-action"
                type="button"
                title="暂停"
                :disabled="isBusy(container.name) || container.status !== 'running'"
                @click="handleContainerAction(container, 'pause')"
              >
                <span class="material-symbol" :class="{ spinning: isBusy(container.name) }">
                  {{ isBusy(container.name) ? 'progress_activity' : 'pause' }}
                </span>
              </button>
              <button
                class="icon-action"
                type="button"
                title="恢复"
                :disabled="isBusy(container.name) || container.status !== 'paused'"
                @click="handleContainerAction(container, 'unpause')"
              >
                <span class="material-symbol" :class="{ spinning: isBusy(container.name) }">
                  {{ isBusy(container.name) ? 'progress_activity' : 'play_circle' }}
                </span>
              </button>
              <button
                class="icon-action danger"
                type="button"
                title="删除"
                :disabled="isBusy(container.name)"
                @click="handleContainerAction(container, 'delete')"
              >
                <span class="material-symbol" :class="{ spinning: isBusy(container.name) }">
                  {{ isBusy(container.name) ? 'progress_activity' : 'delete' }}
                </span>
              </button>
              <button
                class="icon-action"
                type="button"
                title="更新"
                :disabled="isBusy(container.name)"
                @click="handleContainerAction(container, 'update')"
              >
                <span class="material-symbol" :class="{ spinning: isBusy(container.name) }">
                  {{ isBusy(container.name) ? 'progress_activity' : 'upgrade' }}
                </span>
              </button>
              <button
                class="icon-action"
                :class="{ active: expandedContainerName === container.name }"
                type="button"
                title="详情"
                @click="toggleContainerDetail(container)"
              >
                <span class="material-symbol">info</span>
              </button>
            </div>
          </div>

          <div class="expand-collapse" :class="{ open: expandedContainerName === container.name }">
            <div class="expand-inner">
            <DetailPanel
              v-if="renderedContainerName === container.name"
              class="inline-detail"
              :tabs="containerDetailTabs"
              v-model="activeContainerTab"
              :loading="containerDetailLoading"
              :error="containerDetailError"
              :loading-text="containerDetailLoadingText"
              aria-label="容器详情面板"
              tabs-label="Container detail tabs"
              @update:model-value="handleContainerTabSwitch(container, $event)"
              @close="closeContainerDetail"
            >
              <template v-if="activeContainerTab === 'logs'">
                <div class="log-panel">
                  <div class="log-toolbar">
                    <label>
                      <span>最近</span>
                      <select v-model.number="logTail" class="log-tail-select" @change="reloadActiveContainerLogs(container)">
                        <option :value="100">100 条</option>
                        <option :value="300">300 条</option>
                        <option :value="500">500 条</option>
                        <option :value="1000">1000 条</option>
                      </select>
                    </label>
                    <button class="secondary-button compact" type="button" @click="scrollActiveLogToBottom('smooth')">
                      <span class="material-symbol">vertical_align_bottom</span>
                      最新
                    </button>
                  </div>
                  <div :ref="setLogViewport" class="detail-log-viewport" @scroll="handleLogScroll">
                    <HighlightedText class="detail-log" :content="containerLog?.content" mode="log" empty-text="暂无日志" />
                  </div>
                </div>
              </template>
              <template v-else-if="activeContainerTab === 'details'">
                <div class="detail-grid">
                  <div class="detail-item">
                    <span>容器 ID</span>
                    <strong>{{ container.id }}</strong>
                  </div>
                  <div class="detail-item">
                    <span>镜像</span>
                    <strong>{{ container.image || '-' }}</strong>
                  </div>
                  <div class="detail-item">
                    <span>状态</span>
                    <strong>{{ container.status }}</strong>
                  </div>
                  <div class="detail-item">
                    <span>创建时间</span>
                    <strong>{{ formatDate(container.created) }}</strong>
                  </div>
                  <div class="detail-item">
                    <span>端口</span>
                    <strong>{{ formatPorts(container.ports) }}</strong>
                  </div>
                  <div class="detail-item">
                    <span>Compose 项目</span>
                    <strong>{{ container.compose_project || '-' }}</strong>
                  </div>
                  <div class="detail-item">
                    <span>Compose 服务</span>
                    <strong>{{ container.compose_service || '-' }}</strong>
                  </div>
                  <div class="detail-item wide">
                    <span>工作目录</span>
                    <strong>{{ container.compose_working_dir || '-' }}</strong>
                  </div>
                  <div class="detail-item wide">
                    <span>配置文件</span>
                    <strong>{{ container.compose_config_files || '-' }}</strong>
                  </div>
                </div>
              </template>
              <template v-else-if="activeContainerTab === 'inspect'">
                <HighlightedText class="detail-log" :content="containerInspectJson" mode="json" empty-text="暂无 Inspect 信息" />
              </template>
              <template v-else>
                <HighlightedText class="detail-log" :content="containerProcessesJson" mode="json" empty-text="暂无进程信息" />
              </template>
            </DetailPanel>
            </div>
          </div>
        </article>
      </div>
    </MotionSurface>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import type { ComponentPublicInstance } from 'vue'
import {
  getContainerInspect,
  getContainerLogs,
  getContainerProcesses,
  listContainers,
  runContainerAction,
} from '../api'
import type {
  ContainerActionRequest,
  ContainerInspectResponse,
  ContainerListResponse,
  ContainerLogResponse,
  ContainerProcessResponse,
  ContainerSummary,
  OperationResponse,
} from '../api/types'
import CreateContainerWizard from '../components/CreateContainerWizard.vue'
import DetailPanel from '../components/DetailPanel.vue'
import HighlightedText from '../components/HighlightedText.vue'
import MotionSurface from '../components/MotionSurface.vue'
import NoticeBanner from '../components/NoticeBanner.vue'
import type { TabItem } from '../components/types'
import { requestConfirm } from '../utils/confirmDialog'

const containerDetailTabs: TabItem[] = [
  { key: 'logs', label: '日志', icon: 'article' },
  { key: 'details', label: '基本信息', icon: 'info' },
  { key: 'inspect', label: 'Inspect', icon: 'data_object' },
  { key: 'processes', label: '进程', icon: 'list_alt' },
]

const response = ref<ContainerListResponse | null>(null)
const loading = ref(false)
const busyContainer = ref<string | null>(null)
const notice = ref<OperationResponse | null>(null)
const expandedContainerName = ref<string | null>(null)
/** 控制 v-if 渲染（关闭时延迟清除，等动画结束再销毁 DOM） */
const renderedContainerName = ref<string | null>(null)
let collapseTimer: ReturnType<typeof setTimeout> | null = null
const activeContainerTab = ref<'logs' | 'details' | 'inspect' | 'processes'>('details')
const containerLog = ref<ContainerLogResponse | null>(null)
const containerInspect = ref<ContainerInspectResponse | null>(null)
const containerProcesses = ref<ContainerProcessResponse | null>(null)
const loadingContainerLog = ref(false)
const loadingContainerInspect = ref(false)
const loadingContainerProcesses = ref(false)
const createWizardOpen = ref(false)
const logTail = ref(300)
const logViewport = ref<HTMLElement | null>(null)
const shouldStickToLatestLog = ref(true)

const containers = computed(() => response.value?.containers ?? [])
const containerInspectJson = computed(() => JSON.stringify(containerInspect.value?.inspect ?? {}, null, 2))
const containerProcessesJson = computed(() => JSON.stringify({
  titles: containerProcesses.value?.titles ?? [],
  processes: containerProcesses.value?.processes ?? [],
}, null, 2))
const containerDetailLoading = computed(() => {
  if (activeContainerTab.value === 'logs') return loadingContainerLog.value
  if (activeContainerTab.value === 'inspect') return loadingContainerInspect.value
  if (activeContainerTab.value === 'processes') return loadingContainerProcesses.value
  return false
})
const containerDetailError = computed(() => {
  if (activeContainerTab.value === 'logs') return containerLog.value?.error ?? null
  if (activeContainerTab.value === 'inspect') return containerInspect.value?.error ?? null
  if (activeContainerTab.value === 'processes') return containerProcesses.value?.error ?? null
  return null
})
const containerDetailLoadingText = computed(() => {
  if (activeContainerTab.value === 'inspect') return 'Inspect 读取中'
  if (activeContainerTab.value === 'processes') return '进程读取中'
  return '日志读取中'
})

function formatPorts(ports: Record<string, unknown>): string {
  const values: string[] = []
  // 端口结构来自 Docker SDK，形如 {"80/tcp": [{HostPort: "..."}]}。
  for (const [containerPort, bindings] of Object.entries(ports || {})) {
    if (Array.isArray(bindings) && bindings.length) {
      for (const binding of bindings) {
        if (binding && typeof binding === 'object' && 'HostPort' in binding) {
          const hostPort = String((binding as { HostPort?: unknown }).HostPort ?? '')
          values.push(`${hostPort}->${containerPort}`)
        }
      }
    }
  }
  return values.length ? values.join(', ') : '-'
}

function composeLabel(container: ContainerSummary): string {
  if (!container.compose_project) return '-'
  return container.compose_service
    ? `${container.compose_project} / ${container.compose_service}`
    : container.compose_project
}

function isBusy(name: string): boolean {
  return busyContainer.value === name
}

function formatDate(value?: string | null): string {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { hour12: false })
}

function closeContainerDetail() {
  // 先移除 open 类触发 CSS 收起动画，再在动画后销毁内容。
  expandedContainerName.value = null
  if (collapseTimer) clearTimeout(collapseTimer)
  collapseTimer = setTimeout(() => {
    renderedContainerName.value = null
    containerLog.value = null
    containerInspect.value = null
    containerProcesses.value = null
    loadingContainerLog.value = false
    loadingContainerInspect.value = false
    loadingContainerProcesses.value = false
    shouldStickToLatestLog.value = true
  }, 340)
}

async function handleContainerCreated(response: OperationResponse) {
  notice.value = response
  createWizardOpen.value = false
  await loadContainers()
}

async function handleContainerAction(container: ContainerSummary, action: ContainerActionRequest['action']) {
  let approve = false
  if (action === 'stop') {
    // 前端确认与后端审批门禁保持一致；后端仍会强制校验。
    approve = await requestConfirm({
      title: '停止容器',
      message: `确认停止容器 ${container.name}？`,
      confirmText: '停止',
      intent: 'danger',
      icon: 'stop_circle',
    })
    if (!approve) return
  }
  if (action === 'delete') {
    approve = await requestConfirm({
      title: '删除容器',
      message: `确认删除容器 ${container.name}？`,
      confirmText: '删除',
      intent: 'danger',
      icon: 'delete',
    })
    if (!approve) return
  }
  if (action === 'update') {
    approve = await requestConfirm({
      title: '更新容器',
      message: `更新会拉取镜像并重建 ${container.name} 所属 Compose 服务，继续？`,
      confirmText: '继续更新',
      intent: 'warning',
      icon: 'sync',
    })
    if (!approve) return
  }

  busyContainer.value = container.name
  notice.value = null
  try {
    notice.value = await runContainerAction(container.name, { action, approve })
    await loadContainers()
  } catch (err) {
    notice.value = { ok: false, message: '容器操作请求失败。', data: {}, error: String(err), timestamp: new Date().toISOString() }
  } finally {
    busyContainer.value = null
  }
}

async function toggleContainerDetail(container: ContainerSummary) {
  if (expandedContainerName.value === container.name && activeContainerTab.value === 'details') {
    closeContainerDetail()
    return
  }

  // 先渲染再标记展开，让 CSS 有真实内容高度可用于动画。
  if (collapseTimer) clearTimeout(collapseTimer)
  renderedContainerName.value = container.name
  expandedContainerName.value = container.name
  activeContainerTab.value = 'details'
  containerLog.value = null
  containerInspect.value = null
  containerProcesses.value = null
  shouldStickToLatestLog.value = true
}

async function handleContainerTabSwitch(container: ContainerSummary, key: string) {
  activeContainerTab.value = key as typeof activeContainerTab.value
  if (key === 'logs') {
    shouldStickToLatestLog.value = true
    await loadContainerLogs(container)
  }
  if (key === 'inspect') await loadContainerInspect(container)
  if (key === 'processes') await loadContainerProcesses(container)
}

async function loadContainerLogs(container: ContainerSummary) {
  const shouldAutoScroll = shouldStickToLatestLog.value
  loadingContainerLog.value = true
  try {
    containerLog.value = await getContainerLogs(container.name, logTail.value)
  } catch (err) {
    containerLog.value = {
      docker_available: false,
      container_name: container.name,
      tail: logTail.value,
      content: '',
      error: String(err),
      timestamp: new Date().toISOString(),
    }
  } finally {
    loadingContainerLog.value = false
    await nextTick()
    await waitForLogViewport()
    if (activeContainerTab.value === 'logs' && shouldAutoScroll) scrollActiveLogToBottom()
  }
}

async function reloadActiveContainerLogs(container: ContainerSummary) {
  shouldStickToLatestLog.value = true
  await loadContainerLogs(container)
}

function setLogViewport(element: Element | ComponentPublicInstance | null) {
  logViewport.value = element instanceof HTMLElement ? element : null
}

function handleLogScroll() {
  const viewport = logViewport.value
  if (!viewport) return
  const distanceToBottom = viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight
  shouldStickToLatestLog.value = distanceToBottom < 24
}

function waitForLogViewport(timeout = 800): Promise<HTMLElement | null> {
  const startedAt = performance.now()
  return new Promise((resolve) => {
    const check = () => {
      const viewport = logViewport.value
      if (viewport) {
        requestAnimationFrame(() => requestAnimationFrame(() => resolve(viewport)))
        return
      }
      if (performance.now() - startedAt >= timeout) {
        resolve(null)
        return
      }
      requestAnimationFrame(check)
    }

    check()
  })
}

function scrollActiveLogToBottom(behavior: ScrollBehavior = 'auto') {
  const viewport = logViewport.value
  if (!viewport) return
  const top = viewport.scrollHeight
  if (behavior === 'auto') {
    viewport.scrollTop = top
  } else {
    viewport.scrollTo({ top, behavior })
  }
  shouldStickToLatestLog.value = true
}

async function loadContainerInspect(container: ContainerSummary) {
  loadingContainerInspect.value = true
  try {
    containerInspect.value = await getContainerInspect(container.name)
  } catch (err) {
    containerInspect.value = {
      docker_available: false,
      container_name: container.name,
      inspect: {},
      error: String(err),
      timestamp: new Date().toISOString(),
    }
  } finally {
    loadingContainerInspect.value = false
  }
}

async function loadContainerProcesses(container: ContainerSummary) {
  loadingContainerProcesses.value = true
  try {
    containerProcesses.value = await getContainerProcesses(container.name)
  } catch (err) {
    containerProcesses.value = {
      docker_available: false,
      container_name: container.name,
      titles: [],
      processes: [],
      error: String(err),
      timestamp: new Date().toISOString(),
    }
  } finally {
    loadingContainerProcesses.value = false
  }
}

async function loadContainers() {
  loading.value = true
  try {
    response.value = await listContainers()
  } catch (err) {
    console.error('Failed to load containers:', err)
  } finally {
    loading.value = false
  }
}

onMounted(loadContainers)
</script>

<style scoped>
.header-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: flex-end;
}

.toolbar-button,
.secondary-button {
  gap: 8px;
}

.toolbar-button .material-symbol,
.secondary-button .material-symbol {
  font-size: 18px;
}

.spinning {
  animation: spin 0.9s linear infinite;
}

.table-panel {
  padding: 18px;
}

.secondary-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 40px;
  border-radius: 20px;
  background: var(--md-sys-color-surface-container);
  color: var(--md-sys-color-on-surface-variant);
  font-weight: 700;
  cursor: pointer;
  transition: background-color 0.18s ease, box-shadow 0.18s ease, transform 0.18s ease;
}

.secondary-button {
  padding: 0 18px;
}

.secondary-button:hover:not(:disabled) {
  background: var(--md-sys-color-primary-container);
  color: var(--md-sys-color-on-primary-container);
  box-shadow: var(--md-elevation-1);
}

.secondary-button:active:not(:disabled) {
  transform: scale(0.98);
}

.secondary-button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.table-summary {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
  color: var(--md-sys-color-on-surface-variant);
  font-size: 13px;
  font-weight: 700;
}

.container-table {
  display: grid;
}

.table-head,
.table-row-main {
  display: grid;
  grid-template-columns: minmax(170px, 1fr) minmax(150px, 1fr) 112px minmax(130px, 0.8fr) minmax(140px, 1fr) minmax(210px, auto);
  gap: 12px;
  align-items: center;
}

.table-head {
  padding: 11px 12px;
  border-bottom: 1px solid var(--md-sys-color-outline-variant);
  color: var(--md-sys-color-on-surface-variant);
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
}

.container-row {
  border-bottom: 1px solid var(--md-sys-color-outline-variant);
  border-radius: 16px;
  font-size: 14px;
}

.container-row.expanded {
  background: var(--md-sys-color-surface-container-low);
  border-color: color-mix(in srgb, var(--md-sys-color-primary) 30%, var(--md-sys-color-outline-variant));
  box-shadow: var(--md-elevation-1);
}

.container-row:last-child {
  border-bottom: none;
}

.table-row-main {
  min-height: 68px;
  padding: 12px;
}

.table-row-main strong,
.table-row-main small {
  display: block;
}

.table-row-main small {
  margin-top: 4px;
  color: var(--text-faint);
  font-family: var(--font-mono);
}

.mono {
  color: var(--md-sys-color-on-surface-variant);
  font-family: var(--font-mono);
  font-size: 12px;
  overflow-wrap: anywhere;
}

.row-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  justify-content: flex-end;
}

.icon-action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 17px;
  background: var(--md-sys-color-surface-container);
  color: var(--md-sys-color-on-surface-variant);
  cursor: pointer;
  transition: background-color 0.18s ease, color 0.18s ease, transform 0.18s ease;
}

.icon-action:hover:not(:disabled),
.icon-action.active {
  background: var(--md-sys-color-primary-container);
  color: var(--md-sys-color-on-primary-container);
}

.icon-action:active:not(:disabled) {
  transform: scale(0.96);
}

.icon-action.danger:hover:not(:disabled) {
  background: var(--md-sys-color-error-container);
  color: var(--md-sys-color-error);
}

.icon-action:disabled {
  opacity: 0.38;
  cursor: not-allowed;
}

.icon-action .material-symbol {
  font-size: 18px;
}

.inline-detail {
  margin: 0 12px 12px;
}

.error-banner.inline {
  margin-bottom: 0;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.detail-item {
  min-width: 0;
  padding: 12px;
  border-radius: 16px;
  background: var(--md-sys-color-surface-container-low);
}

.detail-item.wide {
  grid-column: 1 / -1;
}

.detail-item span,
.detail-item strong {
  display: block;
}

.detail-item span {
  color: var(--md-sys-color-on-surface-variant);
  font-size: 12px;
  font-weight: 800;
}

.detail-item strong {
  margin-top: 5px;
  color: var(--md-sys-color-on-surface);
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.log-panel {
  display: grid;
  gap: 10px;
  min-width: 0;
}

.log-toolbar {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 10px;
  align-items: center;
}

.log-toolbar label {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--md-sys-color-on-surface-variant);
  font-size: 12px;
  font-weight: 800;
}

.log-tail-select {
  min-height: 34px;
  padding: 0 34px 0 12px;
  border: 1px solid var(--md-sys-color-outline-variant);
  border-radius: 17px;
  background:
    linear-gradient(45deg, transparent 50%, var(--md-sys-color-on-surface-variant) 50%) right 13px center / 6px 6px no-repeat,
    linear-gradient(135deg, var(--md-sys-color-on-surface-variant) 50%, transparent 50%) right 9px center / 6px 6px no-repeat,
    var(--md-sys-color-surface-container-low);
  color: var(--md-sys-color-on-surface);
  font-size: 12px;
  font-weight: 800;
  outline: none;
  appearance: none;
}

.log-tail-select:focus {
  border-color: var(--md-sys-color-primary);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--md-sys-color-primary) 18%, transparent);
}

.compact {
  min-height: 34px;
  padding: 0 12px;
  border-radius: 17px;
}

.detail-log-viewport {
  max-height: 420px;
  overflow: auto;
  border-radius: 16px;
}

.detail-log {
  min-height: 160px;
  margin: 0;
  padding: 14px;
  border-radius: 16px;
  background: #0f1720;
  color: #d7e3f4;
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.55;
  white-space: pre-wrap;
}

@media (max-width: 1180px) {
  .table-head {
    display: none;
  }

  .table-row-main {
    grid-template-columns: 1fr;
    align-items: start;
    gap: 9px;
  }

  .row-actions {
    justify-content: flex-start;
  }
}

@media (max-width: 820px) {
  .header-actions {
    justify-content: flex-start;
  }

  .detail-grid {
    grid-template-columns: 1fr;
  }
}
</style>
