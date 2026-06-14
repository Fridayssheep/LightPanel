<template>
  <section class="page-shell compose-view">
    <header class="page-header">
      <div>
        <p class="eyebrow">Docker Compose管理</p>
        <h1 class="page-title">Compose 查看</h1>
        <p class="page-subtitle">扫描项目目录中与存在的 Compose 文件</p>
      </div>
      <div class="header-actions">
        <button class="secondary-button" type="button" @click="openCreateDialog">
          <span class="material-symbol">note_add</span>
          创建 Compose
        </button>
        <button class="toolbar-button refresh-button" type="button" @click="loadCompose" :disabled="loading">
          <span class="material-symbol">{{ loading ? 'progress_activity' : 'refresh' }}</span>
          {{ loading ? '刷新中' : '刷新' }}
        </button>
      </div>
    </header>

    <div v-if="response?.error" class="error-banner">Docker 连接异常：{{ response.error }}</div>

    <NoticeBanner v-if="notice" :ok="notice.ok" :message="notice.message" :detail="noticeDetail(notice)" />

    <div v-if="scanErrors.length" class="warning-banner">
      <span class="material-symbol">warning</span>
      <div>
        <strong>部分 Compose 文件扫描失败</strong>
        <p v-for="item in scanErrors" :key="item">{{ item }}</p>
      </div>
    </div>

    <div v-if="!projects.length" class="empty-state">
      扫描范围内没有发现 Compose 文件，也没有运行中的 Compose 项目
    </div>

    <div v-else class="compose-workbench">
      <MotionSurface as="aside" class="project-sidebar" :interactive="false" :delay="20">
        <div class="project-sidebar-header">
          <div>
            <h2>扫描项目</h2>
            <span>{{ projects.length }} 个项目</span>
          </div>
          <span class="material-symbol">account_tree</span>
        </div>

        <div class="project-index" role="listbox" aria-label="Compose 项目列表">
          <button
            v-for="(project, index) in projects"
            :key="projectKey(project)"
            class="project-index-item"
            :class="{ selected: isProjectSelected(project) }"
            :style="{ '--motion-delay': `${Math.min(index, 8) * 26}ms` }"
            type="button"
            role="option"
            :aria-selected="isProjectSelected(project)"
            @click="selectProject(project)"
          >
            <div class="index-title-line">
              <strong>{{ project.name }}</strong>
              <span class="state-chip" :class="project.state">{{ project.state }}</span>
            </div>
            <div class="index-meta">
              <span class="index-stat">
                <span class="material-symbol">deployed_code</span>
                {{ project.running_count }}/{{ project.container_count }}
              </span>
              <span class="index-stat">
                <span class="material-symbol">{{ sourceIcon(project) }}</span>
                {{ sourceLabel(project) }}
              </span>
            </div>
            <p class="index-path">
              {{ project.compose_file || project.working_dir || '未记录路径' }}
            </p>
          </button>
        </div>
      </MotionSurface>

      <Transition name="route-surface" mode="out-in">
        <MotionSurface
          v-if="selectedProject"
          :key="projectKey(selectedProject)"
          as="article"
          class="project-detail-card"
          :interactive="false"
          :expanded="isProjectExpanded(selectedProject)"
          :delay="50"
        >
          <div class="project-header">
            <div class="project-main">
              <div class="project-title-line">
                <h2>{{ selectedProject.name }}</h2>
                <span class="source-chip" :class="sourceClass(selectedProject)">
                  <span class="material-symbol">{{ sourceIcon(selectedProject) }}</span>
                  {{ sourceLabel(selectedProject) }}
                </span>
                <span class="state-chip" :class="selectedProject.state">{{ selectedProject.state }}</span>
              </div>
              <p v-if="selectedProject.compose_file" class="project-path">
                <span class="material-symbol">description</span>
                {{ selectedProject.compose_file }}
              </p>
              <p v-else-if="selectedProject.working_dir" class="project-path">
                <span class="material-symbol">folder</span>
                {{ selectedProject.working_dir }}
              </p>
            </div>

            <div class="project-stats">
              <div class="stat-cell">
                <span>运行</span>
                <strong>{{ selectedProject.running_count }}/{{ selectedProject.container_count }}</strong>
              </div>
              <div class="stat-cell">
                <span>容器</span>
                <strong>{{ projectDeclaredServices(selectedProject).length || projectServices(selectedProject).length }}</strong>
              </div>
            </div>
          </div>

          <div v-if="projectComposeFiles(selectedProject).length > 1" class="file-stack">
            <span v-for="file in projectComposeFiles(selectedProject)" :key="file">{{ file }}</span>
          </div>

          <div class="project-actions">
            <button
              class="action-button"
              :class="{ active: isProjectExpanded(selectedProject) && activeProjectTab === 'file' }"
              type="button"
              :disabled="!canManageProject(selectedProject)"
              :title="canManageProject(selectedProject) ? '编辑 Compose 文件' : '项目不在暴露目录内，不能编辑'"
              @click="openEditor(selectedProject, true)"
            >
              <span class="material-symbol">edit_document</span>
              编辑
            </button>
            <button
              class="action-button"
              type="button"
              :disabled="!canManageProject(selectedProject) || isBusy(selectedProject.name)"
              @click="handleComposeAction(selectedProject, 'up')"
            >
              <span class="material-symbol" :class="{ spinning: isBusy(selectedProject.name) }">
                {{ isBusy(selectedProject.name) ? 'progress_activity' : 'play_arrow' }}
              </span>
              启动
            </button>
            <button
              class="action-button danger"
              type="button"
              :disabled="!canManageProject(selectedProject) || isBusy(selectedProject.name)"
              @click="handleComposeAction(selectedProject, 'stop')"
            >
              <span class="material-symbol" :class="{ spinning: isBusy(selectedProject.name) }">
                {{ isBusy(selectedProject.name) ? 'progress_activity' : 'stop' }}
              </span>
              停止
            </button>
            <button
              class="action-button"
              type="button"
              :disabled="!canManageProject(selectedProject) || isBusy(selectedProject.name)"
              @click="handleComposeAction(selectedProject, 'restart')"
            >
              <span class="material-symbol" :class="{ spinning: isBusy(selectedProject.name) }">
                {{ isBusy(selectedProject.name) ? 'progress_activity' : 'restart_alt' }}
              </span>
              重启
            </button>
            <button
              class="action-button"
              type="button"
              :disabled="!canManageProject(selectedProject) || isBusy(selectedProject.name)"
              @click="handleComposeAction(selectedProject, 'pull')"
            >
              <span class="material-symbol" :class="{ spinning: isBusy(selectedProject.name) }">
                {{ isBusy(selectedProject.name) ? 'progress_activity' : 'download' }}
              </span>
              拉取
            </button>
            <button
              class="action-button"
              type="button"
              :disabled="!canManageProject(selectedProject) || isBusy(selectedProject.name)"
              @click="handleComposeAction(selectedProject, 'update')"
            >
              <span class="material-symbol" :class="{ spinning: isBusy(selectedProject.name) }">
                {{ isBusy(selectedProject.name) ? 'progress_activity' : 'upgrade' }}
              </span>
              更新
            </button>
            <button
              class="action-button"
              :class="{ active: isProjectExpanded(selectedProject) && activeProjectTab === 'logs' }"
              type="button"
              :disabled="isBusy(selectedProject.name)"
              @click="handleComposeLogs(selectedProject, true)"
            >
              <span class="material-symbol">article</span>
              日志
            </button>
          </div>

          <Transition name="panel-rise">
            <div v-if="composeProgress && busyProject === selectedProject.name" class="compose-progress-panel">
              <div class="compose-progress-head">
                <span class="material-symbol spinning">sync</span>
                <strong>{{ composeProgress.message }}</strong>
              </div>
              <HighlightedText v-if="composeProgress.output" :content="composeProgress.output" mode="log" empty-text="" />
            </div>
          </Transition>

          <div class="expand-collapse" :class="{ open: isProjectExpanded(selectedProject) }">
            <div class="expand-inner">
            <DetailPanel
              v-if="renderedProjectKey"
              class="project-detail-panel"
              :tabs="composeDetailTabs(selectedProject)"
              :model-value="activeProjectTab"
              :loading="composeDetailLoading"
              :error="composeDetailError"
              :loading-text="activeProjectTab === 'logs' ? '日志读取中' : 'Compose 文件读取中'"
              aria-label="Compose 项目详情"
              tabs-label="Compose project detail tabs"
              @update:model-value="handleDetailTabSwitch(selectedProject, $event)"
              @close="closeProjectPanel"
            >
              <template v-if="activeProjectTab === 'logs'">
                <HighlightedText class="detail-log" :content="projectLogPanel?.content" mode="log" empty-text="暂无日志" />
              </template>

              <template v-else>
                <div v-if="!canManageProject(selectedProject)" class="empty-state compact">
                  internal 项目在非项目目录内只允许查看运行态和日志。
                </div>
                <template v-else>
                  <div class="editor-heading">
                    <span class="material-symbol">description</span>
                    <strong>{{ editorPath || selectedProject.compose_file }}</strong>
                  </div>
                  <div class="compose-editor-shell">
                    <HighlightedText
                      ref="editorHighlight"
                      class="compose-editor-highlight"
                      :content="editorContent"
                      mode="yaml"
                      empty-text=""
                      aria-hidden="true"
                    />
                    <textarea
                      v-model="editorContent"
                      class="compose-editor"
                      spellcheck="false"
                      @scroll="syncEditorScroll"
                    ></textarea>
                  </div>
                  <div class="panel-actions">
                    <button class="primary-button" type="button" :disabled="savingFile || !editorPath" @click="saveEditor">
                      <span class="material-symbol" :class="{ spinning: savingFile }">
                        {{ savingFile ? 'progress_activity' : 'save' }}
                      </span>
                      保存
                    </button>
                  </div>
                </template>
              </template>
            </DetailPanel>
            </div>
          </div>

          <div class="detail-section-header">
            <h3>服务与容器</h3>
            <span>{{ projectServices(selectedProject).length }} 个服务</span>
          </div>

          <div v-if="projectServices(selectedProject).length" class="service-grid">
            <article
              v-for="(service, sIdx) in projectServices(selectedProject)"
              :key="service.name"
              class="service-row motion-item"
              :class="{ 'cold-service': service.container_count === 0 }"
              :style="{ '--motion-delay': `${Math.min(sIdx, 8) * 32}ms` }"
            >
              <div class="service-title">
                <div>
                  <strong>{{ service.name }}</strong>
                  <span>{{ service.image || service.container_name || serviceSourceLabel(service) }}</span>
                </div>
                <span class="service-count">{{ serviceStateLabel(service) }}</span>
              </div>

              <div class="service-actions">
                <button
                  class="icon-action"
                  type="button"
                  title="启动服务"
                  :disabled="!canManageProject(selectedProject) || isServiceBusy(service.name)"
                  @click="handleServiceAction(selectedProject, service.name, 'up')"
                >
                  <span class="material-symbol" :class="{ spinning: isServiceBusy(service.name) }">
                    {{ isServiceBusy(service.name) ? 'progress_activity' : 'play_arrow' }}
                  </span>
                </button>
                <button
                  class="icon-action danger"
                  type="button"
                  title="停止服务"
                  :disabled="!canManageProject(selectedProject) || isServiceBusy(service.name)"
                  @click="handleServiceAction(selectedProject, service.name, 'stop')"
                >
                  <span class="material-symbol" :class="{ spinning: isServiceBusy(service.name) }">
                    {{ isServiceBusy(service.name) ? 'progress_activity' : 'stop' }}
                  </span>
                </button>
                <button
                  class="icon-action"
                  type="button"
                  title="重启服务"
                  :disabled="!canManageProject(selectedProject) || isServiceBusy(service.name)"
                  @click="handleServiceAction(selectedProject, service.name, 'restart')"
                >
                  <span class="material-symbol" :class="{ spinning: isServiceBusy(service.name) }">
                    {{ isServiceBusy(service.name) ? 'progress_activity' : 'restart_alt' }}
                  </span>
                </button>
                <button
                  class="icon-action"
                  type="button"
                  title="服务日志"
                  :disabled="isServiceBusy(service.name)"
                  @click="handleServiceLogs(selectedProject, service.name)"
                >
                  <span class="material-symbol">article</span>
                </button>
              </div>

              <div v-if="serviceContainers(service).length" class="service-containers">
                <span
                  v-for="container in serviceContainers(service)"
                  :key="container.id"
                  class="status-pill"
                  :class="container.status"
                >
                  <span class="status-dot"></span>
                  {{ container.name }}
                </span>
              </div>
              <div v-else class="pending-label">
                <span class="material-symbol">power_settings_new</span>
                未启动
              </div>
            </article>
          </div>

          <div v-else class="empty-state compact">这个 Compose 文件没有容器</div>
        </MotionSurface>
      </Transition>
    </div>

    <Teleport to="body">
      <Transition name="wizard-fade">
        <div v-if="createDialogOpen" class="compose-modal-backdrop" role="presentation" @click.self="closeCreateDialog">
          <section class="compose-modal" role="dialog" aria-modal="true" aria-labelledby="compose-create-title">
            <header class="compose-modal-header">
              <div>
                <p class="eyebrow">Compose project</p>
                <h2 id="compose-create-title">创建并运行 Compose</h2>
              </div>
              <button class="icon-button" type="button" title="关闭" :disabled="creatingCompose" @click="closeCreateDialog">
                <span class="material-symbol">close</span>
              </button>
            </header>

            <div class="compose-create-body">
              <NoticeBanner
                v-if="notice && !notice.ok"
                :ok="notice.ok"
                :message="notice.message"
                :detail="noticeDetail(notice)"
              />

              <div class="source-segmented" role="tablist" aria-label="Compose 创建来源">
                <button
                  v-for="option in createSourceOptions"
                  :key="option.key"
                  type="button"
                  :class="{ active: createSource === option.key }"
                  @click="createSource = option.key"
                >
                  <span class="material-symbol">{{ option.icon }}</span>
                  {{ option.label }}
                </button>
              </div>

              <label class="field-row">
                <span>项目名称</span>
                <input v-model.trim="createForm.project_name" class="themed-input" placeholder="demo-app" autocomplete="off" />
              </label>
              <label class="field-row">
                <span>放置目录</span>
                <input
                  v-model.trim="createForm.directory"
                  class="themed-input"
                  list="compose-root-options"
                  placeholder="/app/samples"
                  autocomplete="off"
                />
                <datalist id="compose-root-options">
                  <option v-for="root in createDirectoryOptions" :key="root" :value="root"></option>
                </datalist>
              </label>
              <label class="field-row">
                <span>文件名</span>
                <select v-model="createForm.filename" class="themed-input">
                  <option value="compose.yaml">compose.yaml</option>
                  <option value="compose.yml">compose.yml</option>
                  <option value="docker-compose.yml">docker-compose.yml</option>
                  <option value="docker-compose.yaml">docker-compose.yaml</option>
                </select>
              </label>

              <label v-if="createSource === 'url'" class="field-row">
                <span>Compose URL</span>
                <input v-model.trim="createForm.url" class="themed-input" placeholder="https://example.com/compose.yaml" autocomplete="off" />
              </label>

              <template v-if="createSource === 'git'">
                <label class="field-row">
                  <span>Git 仓库</span>
                  <input v-model.trim="createForm.repository_url" class="themed-input" placeholder="https://github.com/user/repo.git" autocomplete="off" />
                </label>
                <label class="field-row">
                  <span>分支</span>
                  <input v-model.trim="createForm.branch" class="themed-input" placeholder="main，可留空" autocomplete="off" />
                </label>
                <label class="field-row">
                  <span>Compose 相对路径</span>
                  <input v-model.trim="createForm.compose_path" class="themed-input" placeholder="compose.yaml" autocomplete="off" />
                </label>
              </template>

              <div v-if="createSource === 'manual'" class="compose-create-editor">
                <div class="editor-heading">
                  <span class="material-symbol">description</span>
                  <strong>{{ createPreviewPath }}</strong>
                </div>
                <div class="compose-editor-shell">
                  <HighlightedText
                    ref="createEditorHighlight"
                    class="compose-editor-highlight"
                    :content="createForm.content"
                    mode="yaml"
                    empty-text=""
                    aria-hidden="true"
                  />
                  <textarea
                    v-model="createForm.content"
                    class="compose-editor"
                    spellcheck="false"
                    @scroll="syncCreateEditorScroll"
                  ></textarea>
                </div>
              </div>
            </div>

            <footer class="compose-modal-footer">
              <button class="secondary-button" type="button" :disabled="creatingCompose" @click="closeCreateDialog">取消</button>
              <button class="primary-button" type="button" :disabled="!canCreateCompose || creatingCompose" @click="submitCreateCompose">
                <span class="material-symbol" :class="{ spinning: creatingCompose }">
                  {{ creatingCompose ? 'progress_activity' : 'play_arrow' }}
                </span>
                {{ creatingCompose ? '创建中' : '创建并运行' }}
              </button>
            </footer>
          </section>
        </div>
      </Transition>
    </Teleport>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  createComposeProject,
  createComposeProjectFromGit,
  createComposeProjectFromUrl,
  getComposeFile,
  getComposeLogs,
  getComposeServiceLogs,
  listComposeProjects,
  runComposeAction,
  runComposeActionWithProgress,
  runComposeServiceAction,
  saveComposeFile,
} from '../api'
import type {
  ComposeActionRequest,
  ComposeProgressEvent,
  ComposeServiceActionRequest,
  ComposeListResponse,
  ComposeProjectSummary,
  ComposeServiceSummary,
  ContainerLogResponse,
  OperationResponse,
} from '../api/types'
import MotionSurface from '../components/MotionSurface.vue'
import DetailPanel from '../components/DetailPanel.vue'
import HighlightedText from '../components/HighlightedText.vue'
import type { TabItem } from '../components/types'
import NoticeBanner from '../components/NoticeBanner.vue'
import { requestConfirm } from '../utils/confirmDialog'

const response = ref<ComposeListResponse | null>(null)
const loading = ref(false)
const busyProject = ref<string | null>(null)
const busyService = ref<string | null>(null)
const notice = ref<OperationResponse | null>(null)
const selectedProjectKey = ref<string | null>(null)
const expandedProjectKey = ref<string | null>(null)
/** 延迟清理 v-if 内容，等收起动画结束后再销毁 DOM。 */
const renderedProjectKey = ref<string | null>(null)
let composeCollapseTimer: ReturnType<typeof setTimeout> | null = null
const activeProjectTab = ref<'logs' | 'file'>('logs')
const editorPath = ref('')
const editorContent = ref('')
const loadingEditor = ref(false)
const savingFile = ref(false)
const projectLogPanel = ref<ContainerLogResponse | null>(null)
const loadingProjectLogs = ref(false)
const editorHighlight = ref<InstanceType<typeof HighlightedText> | null>(null)
const createEditorHighlight = ref<InstanceType<typeof HighlightedText> | null>(null)
const createDialogOpen = ref(false)
const creatingCompose = ref(false)
type ComposeCreateSource = 'manual' | 'url' | 'git'
const createSource = ref<ComposeCreateSource>('manual')
const createSourceOptions: Array<{ key: ComposeCreateSource; label: string; icon: string }> = [
  { key: 'manual', label: '手写', icon: 'edit_document' },
  { key: 'url', label: 'URL', icon: 'link' },
  { key: 'git', label: 'Git', icon: 'commit' },
]
const createForm = ref({
  project_name: 'demo-app',
  directory: '',
  filename: 'compose.yaml',
  content: defaultComposeContent('demo-app'),
  url: '',
  repository_url: '',
  branch: '',
  compose_path: 'compose.yaml',
})
const composeProgress = ref<ComposeProgressEvent | null>(null)

// ─── DetailPanel 辅助 ──────────────────────────────────────────────────
const composeDetailLoading = computed(() => {
  if (activeProjectTab.value === 'logs') return loadingProjectLogs.value
  return loadingEditor.value
})

const composeDetailError = computed(() => {
  if (activeProjectTab.value === 'logs') return projectLogPanel.value?.error ?? null
  return null
})
const createDirectoryOptions = computed(() => response.value?.scan_roots ?? [])
const canCreateCompose = computed(() => (
  Boolean(createForm.value.project_name.trim())
  && Boolean(createForm.value.directory.trim())
  && Boolean(createForm.value.filename.trim())
  && (
    createSource.value === 'manual'
      ? Boolean(createForm.value.content.trim())
      : createSource.value === 'url'
        ? Boolean(createForm.value.url.trim())
        : Boolean(createForm.value.repository_url.trim()) && Boolean(createForm.value.compose_path.trim())
  )
))
const createPreviewPath = computed(() => {
  const directory = createForm.value.directory || createDirectoryOptions.value[0] || '项目目录'
  const project = createForm.value.project_name || '项目名'
  const filename = createForm.value.filename || 'compose.yaml'
  return `${directory.replace(/\/$/, '')}/${project}/${filename}`
})

/** 根据项目生成 tab 配置（file tab 在 internal 项目禁用） */
function composeDetailTabs(project: ComposeProjectSummary): TabItem[] {
  return [
    { key: 'logs', label: '日志', icon: 'article' },
    {
      key: 'file',
      label: 'Compose 文件',
      icon: 'edit_document',
      disabled: !canManageProject(project),
      title: canManageProject(project) ? '编辑 Compose 文件' : '内部项目无法编辑 Compose 文件',
    },
  ]
}

/** 处理 DetailPanel 的 tab 切换事件 */
function handleDetailTabSwitch(project: ComposeProjectSummary, key: string) {
  if (key === 'logs') {
    handleComposeLogs(project)
  } else {
    openEditor(project)
  }
}

const scanErrors = computed(() => response.value?.scan_errors ?? [])
const projects = computed(() => response.value?.projects ?? [])
const selectedProject = computed(() => {
  if (!projects.value.length) return null
  const selected = projects.value.find((project) => projectKey(project) === selectedProjectKey.value)
  return selected ?? projects.value[0]
})

function projectServices(project: ComposeProjectSummary): ComposeServiceSummary[] {
  return project.services ?? []
}

function projectComposeFiles(project: ComposeProjectSummary): string[] {
  return project.compose_files ?? []
}

function projectDeclaredServices(project: ComposeProjectSummary): string[] {
  return project.declared_services ?? []
}

function projectSources(project: ComposeProjectSummary): string[] {
  return project.sources ?? []
}

function serviceContainers(service: ComposeServiceSummary): ComposeProjectSummary['services'][number]['containers'] {
  return service.containers ?? []
}

function projectKey(project: ComposeProjectSummary): string {
  // 扫描目录重叠时项目名不一定全局唯一，所以拼上稳定的路径或来源后缀。
  return `${project.name}:${project.compose_file || project.working_dir || projectSources(project).join(',')}`
}

function sourceLabel(project: ComposeProjectSummary): string {
  const sources = projectSources(project)
  const hasDocker = sources.includes('docker')
  const hasFile = sources.includes('file')
  // 来源 docker 表示 Docker 标签中的运行态；file 表示允许目录里扫描到的 Compose YAML。
  if (hasDocker && hasFile) return '文件运行态'
  if (hasFile) return '文件发现'
  if (hasDocker) return 'Docker 运行态'
  return '未知来源'
}

function sourceClass(project: ComposeProjectSummary): string {
  const sources = projectSources(project)
  const hasDocker = sources.includes('docker')
  const hasFile = sources.includes('file')
  if (hasDocker && hasFile) return 'mixed'
  if (hasFile) return 'file'
  if (hasDocker) return 'docker'
  return 'unknown'
}

function sourceIcon(project: ComposeProjectSummary): string {
  const sources = projectSources(project)
  const hasDocker = sources.includes('docker')
  const hasFile = sources.includes('file')
  if (hasDocker && hasFile) return 'hub'
  if (hasFile) return 'description'
  if (hasDocker) return 'deployed_code'
  return 'help'
}

function serviceStateLabel(service: ComposeServiceSummary): string {
  if (service.container_count === 0) return service.declared ? 'declared' : '0/0'
  return `${service.running_count}/${service.container_count} running`
}

function serviceSourceLabel(service: ComposeServiceSummary): string {
  return service.declared ? '已声明容器' : 'Docker 服务'
}

function noticeDetail(value: OperationResponse | null): string {
  if (!value || value.ok) return ''
  const detailItems: string[] = []
  if (value.error && value.error !== value.message) {
    detailItems.push(value.error)
  }
  for (const key of ['output', 'raw_output', 'stderr', 'stdout', 'logs']) {
    const item = value.data?.[key]
    if (typeof item === 'string' && item.trim() && !detailItems.includes(item)) {
      detailItems.push(item)
    }
  }
  const returncode = value.data?.returncode
  if (returncode !== undefined && returncode !== null) {
    detailItems.push(`exit code ${String(returncode)}`)
  }
  return detailItems.join('\n\n').trim()
}

function isBusy(projectName: string): boolean {
  return busyProject.value === projectName
}

function isServiceBusy(serviceName: string): boolean {
  return busyService.value === serviceName
}

function canManageProject(project: ComposeProjectSummary): boolean {
  // 只允许修改暴露目录内发现的 Compose 文件，避免误写 Docker 运行态推断出的内部项目。
  return Boolean(project.compose_file && projectSources(project).includes('file'))
}

function isProjectExpanded(project: ComposeProjectSummary): boolean {
  return expandedProjectKey.value === projectKey(project)
}

function isProjectSelected(project: ComposeProjectSummary): boolean {
  return selectedProject.value ? projectKey(selectedProject.value) === projectKey(project) : false
}

function selectProject(project: ComposeProjectSummary) {
  const key = projectKey(project)
  if (selectedProjectKey.value === key) return
  selectedProjectKey.value = key
  closeProjectPanel()
}

function syncSelectedProject() {
  // 创建或编辑后刷新可能改变项目 key，需要把选中项保持在仍然存在的项目上。
  if (!projects.value.length) {
    selectedProjectKey.value = null
    closeProjectPanel()
    return
  }

  const hasSelectedProject = projects.value.some((project) => projectKey(project) === selectedProjectKey.value)
  if (!hasSelectedProject) {
    selectedProjectKey.value = projectKey(projects.value[0])
    closeProjectPanel()
  }

  if (expandedProjectKey.value) {
    const hasExpandedProject = projects.value.some((project) => projectKey(project) === expandedProjectKey.value)
    if (!hasExpandedProject) {
      closeProjectPanel()
    }
  }
}

function closeProjectPanel() {
  expandedProjectKey.value = null
  if (composeCollapseTimer) clearTimeout(composeCollapseTimer)
  composeCollapseTimer = setTimeout(() => {
    renderedProjectKey.value = null
    projectLogPanel.value = null
    editorPath.value = ''
    editorContent.value = ''
    loadingProjectLogs.value = false
    loadingEditor.value = false
  }, 340)
}

function defaultComposeContent(projectName: string): string {
  const safeName = projectName.trim() || 'demo-app'
  return `name: ${safeName}
services:
  web:
    image: nginx:alpine
    ports:
      - "8080:80"
`
}

function openCreateDialog() {
  createForm.value = {
    project_name: 'demo-app',
    directory: createDirectoryOptions.value[0] || '',
    filename: 'compose.yaml',
    content: defaultComposeContent('demo-app'),
    url: '',
    repository_url: '',
    branch: '',
    compose_path: 'compose.yaml',
  }
  createSource.value = 'manual'
  createDialogOpen.value = true
}

function closeCreateDialog() {
  if (creatingCompose.value) return
  createDialogOpen.value = false
}

function syncEditorScroll(event: Event) {
  const textarea = event.target as HTMLTextAreaElement
  const highlight = editorHighlight.value?.rootElement
  if (!highlight) return
  // 输入框透明叠在高亮层上方，需要同步两层滚动位置。
  highlight.scrollTop = textarea.scrollTop
  highlight.scrollLeft = textarea.scrollLeft
}

function syncCreateEditorScroll(event: Event) {
  const textarea = event.target as HTMLTextAreaElement
  const highlight = createEditorHighlight.value?.rootElement
  if (!highlight) return
  highlight.scrollTop = textarea.scrollTop
  highlight.scrollLeft = textarea.scrollLeft
}

async function submitCreateCompose() {
  if (!canCreateCompose.value) return
  const approve = await requestConfirm({
    title: '创建 Compose 项目',
    message: `确认创建并运行 Compose 项目 ${createForm.value.project_name.trim()}？`,
    confirmText: '创建并运行',
    icon: 'rocket_launch',
  })
  if (!approve) return

  creatingCompose.value = true
  notice.value = null
  try {
    const commonPayload = {
      project_name: createForm.value.project_name.trim(),
      directory: createForm.value.directory.trim(),
      filename: createForm.value.filename,
      approve,
    }
    if (createSource.value === 'url') {
      notice.value = await createComposeProjectFromUrl({
        ...commonPayload,
        url: createForm.value.url.trim(),
      })
    } else if (createSource.value === 'git') {
      notice.value = await createComposeProjectFromGit({
        project_name: commonPayload.project_name,
        directory: commonPayload.directory,
        repository_url: createForm.value.repository_url.trim(),
        branch: createForm.value.branch.trim() || null,
        compose_path: createForm.value.compose_path.trim() || 'compose.yaml',
        approve,
      })
    } else {
      // 后端会在选中的允许目录下用 project_name 创建子目录。
      notice.value = await createComposeProject({
        ...commonPayload,
        content: createForm.value.content,
      })
    }
    if (notice.value.ok) {
      createDialogOpen.value = false
      await loadCompose()
    }
  } catch (err) {
    notice.value = { ok: false, message: '创建 Compose 请求失败。', data: {}, error: String(err), timestamp: new Date().toISOString() }
  } finally {
    creatingCompose.value = false
  }
}

async function openEditor(project: ComposeProjectSummary, toggle = false) {
  if (!project.compose_file || !canManageProject(project)) return
  const key = projectKey(project)
  if (toggle && expandedProjectKey.value === key && activeProjectTab.value === 'file') {
    closeProjectPanel()
    return
  }
  if (composeCollapseTimer) clearTimeout(composeCollapseTimer)
  // 先渲染详情面板再请求数据，让加载状态可以在原位动画显示。
  renderedProjectKey.value = key
  expandedProjectKey.value = key
  activeProjectTab.value = 'file'
  projectLogPanel.value = null
  loadingEditor.value = true
  notice.value = null
  try {
    const response = await getComposeFile(project.compose_file)
    if (!response.editable) {
      notice.value = {
        ok: false,
        message: response.error || 'Compose 文件不可编辑。',
        data: {},
        error: response.error,
        timestamp: new Date().toISOString(),
      }
      return
    }
    editorPath.value = response.path
    editorContent.value = response.content
  } catch (err) {
    notice.value = {
      ok: false,
      message: '读取 Compose 文件请求失败。',
      data: {},
      error: String(err),
      timestamp: new Date().toISOString(),
    }
  } finally {
    loadingEditor.value = false
  }
}

async function saveEditor() {
  if (!editorPath.value) return
  const approve = await requestConfirm({
    title: '保存 Compose 文件',
    message: `确认保存 Compose 文件 ${editorPath.value}？`,
    confirmText: '保存',
    icon: 'save',
  })
  if (!approve) return
  savingFile.value = true
  notice.value = null
  try {
    notice.value = await saveComposeFile({ path: editorPath.value, content: editorContent.value, approve })
    if (notice.value.ok) {
      await loadCompose()
    }
  } catch (err) {
    notice.value = { ok: false, message: '保存 Compose 文件请求失败。', data: {}, error: String(err), timestamp: new Date().toISOString() }
  } finally {
    savingFile.value = false
  }
}

async function handleComposeAction(project: ComposeProjectSummary, action: ComposeActionRequest['action']) {
  if (!project.compose_file || !canManageProject(project)) return
  let approve = false
  if (action === 'stop') {
    // 后端仍会校验确认标记；这里先拦住误触停止请求。
    approve = await requestConfirm({
      title: '停止 Compose 项目',
      message: `确认停止 Compose 项目 ${project.name}？`,
      confirmText: '停止',
      intent: 'danger',
      icon: 'stop_circle',
    })
    if (!approve) return
  }
  if (action === 'update') {
    approve = await requestConfirm({
      title: '更新 Compose 项目',
      message: `更新会拉取镜像并重新启动 ${project.name}，继续？`,
      confirmText: '继续更新',
      intent: 'warning',
      icon: 'sync',
    })
    if (!approve) return
  }

  busyProject.value = project.name
  notice.value = null
  composeProgress.value = null
  try {
    if (['up', 'restart', 'pull', 'update'].includes(action)) {
      notice.value = await runComposeActionWithProgress(
        { path: project.compose_file, action, approve },
        (event) => {
          composeProgress.value = event
        },
      )
    } else {
      notice.value = await runComposeAction({ path: project.compose_file, action, approve })
    }
    await loadCompose()
  } catch (err) {
    notice.value = { ok: false, message: 'Compose 操作请求失败。', data: {}, error: String(err), timestamp: new Date().toISOString() }
  } finally {
    busyProject.value = null
  }
}

async function handleComposeLogs(project: ComposeProjectSummary, toggle = false) {
  const key = projectKey(project)
  if (toggle && expandedProjectKey.value === key && activeProjectTab.value === 'logs') {
    closeProjectPanel()
    return
  }
  if (composeCollapseTimer) clearTimeout(composeCollapseTimer)
  // 即使 Compose 文件不可编辑，只要 Docker 能发现项目，也可以查看日志。
  renderedProjectKey.value = key
  expandedProjectKey.value = key
  activeProjectTab.value = 'logs'
  editorPath.value = ''
  editorContent.value = ''
  projectLogPanel.value = null
  loadingProjectLogs.value = true
  try {
    projectLogPanel.value = await getComposeLogs({ project: project.name, tail: 300 })
  } catch (err) {
    projectLogPanel.value = {
      docker_available: false,
      container_name: project.name,
      tail: 300,
      content: '',
      error: String(err),
      timestamp: new Date().toISOString(),
    }
  } finally {
    loadingProjectLogs.value = false
  }
}

async function handleServiceAction(
  project: ComposeProjectSummary,
  service: string,
  action: ComposeServiceActionRequest['action'],
) {
  if (!project.compose_file || !canManageProject(project)) return
  let approve = false
  if (action === 'stop') {
    approve = await requestConfirm({
      title: '停止 Compose 服务',
      message: `确认停止 Compose 服务 ${project.name}/${service}？`,
      confirmText: '停止',
      intent: 'danger',
      icon: 'stop_circle',
    })
    if (!approve) return
  }
  busyService.value = service
  notice.value = null
  try {
    notice.value = await runComposeServiceAction({
      path: project.compose_file,
      service,
      action,
      approve,
    })
    await loadCompose()
  } catch (err) {
    notice.value = { ok: false, message: 'Compose 服务操作请求失败。', data: {}, error: String(err), timestamp: new Date().toISOString() }
  } finally {
    busyService.value = null
  }
}

async function handleServiceLogs(project: ComposeProjectSummary, service: string) {
  const key = projectKey(project)
  if (composeCollapseTimer) clearTimeout(composeCollapseTimer)
  renderedProjectKey.value = key
  expandedProjectKey.value = key
  activeProjectTab.value = 'logs'
  editorPath.value = ''
  editorContent.value = ''
  projectLogPanel.value = null
  loadingProjectLogs.value = true
  try {
    projectLogPanel.value = await getComposeServiceLogs({ project: project.name, service, tail: 300 })
  } catch (err) {
    projectLogPanel.value = {
      docker_available: false,
      container_name: `${project.name}/${service}`,
      tail: 300,
      content: '',
      error: String(err),
      timestamp: new Date().toISOString(),
    }
  } finally {
    loadingProjectLogs.value = false
  }
}

async function loadCompose() {
  loading.value = true
  try {
    response.value = await listComposeProjects()
    syncSelectedProject()
  } catch (err) {
    console.error('Failed to load compose projects:', err)
  } finally {
    loading.value = false
  }
}

onMounted(loadCompose)
</script>

<style scoped>
.header-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: flex-end;
}

.refresh-button {
  gap: 8px;
}

.primary-button,
.secondary-button {
  gap: 8px;
}

.refresh-button .material-symbol,
.secondary-button .material-symbol {
  font-size: 18px;
}

.primary-button .material-symbol {
  font-size: 18px;
}

.refresh-button:disabled .material-symbol,
.primary-button:disabled .material-symbol {
  animation: spin 0.9s linear infinite;
}

.secondary-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 40px;
  padding: 0 18px;
  border-radius: 20px;
  background: var(--md-sys-color-surface-container);
  color: var(--md-sys-color-on-surface-variant);
  font-weight: 700;
  cursor: pointer;
  transition: background-color 0.18s ease, box-shadow 0.18s ease, transform 0.18s ease;
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

.warning-banner {
  display: flex;
  gap: 12px;
  margin-bottom: 18px;
  padding: 14px 16px;
  border-radius: 16px;
  background: var(--state-warning-container);
  color: var(--state-warning);
  font-size: 13px;
}

.warning-banner > .material-symbol {
  margin-top: 1px;
  font-size: 20px;
}

.warning-banner strong {
  display: block;
  margin-bottom: 4px;
}

.warning-banner p {
  margin: 4px 0 0;
  overflow-wrap: anywhere;
}

.compose-workbench {
  display: grid;
  grid-template-columns: minmax(280px, 360px) minmax(0, 1fr);
  gap: 18px;
  align-items: start;
}

.project-sidebar {
  position: sticky;
  top: 24px;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  gap: 14px;
  max-height: calc(100vh - 168px);
  overflow: hidden;
  padding: 16px;
}

.project-sidebar-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--md-sys-color-outline-variant);
}

.project-sidebar-header h2 {
  margin: 0;
  color: var(--md-sys-color-on-surface);
  font-size: 18px;
  font-weight: 800;
}

.project-sidebar-header span {
  color: var(--md-sys-color-on-surface-variant);
  font-size: 12px;
  font-weight: 700;
}

.project-sidebar-header > .material-symbol {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  border-radius: 14px;
  background: var(--md-sys-color-primary-container);
  color: var(--md-sys-color-primary);
  font-size: 21px;
}

.project-index {
  display: grid;
  gap: 8px;
  min-height: 0;
  overflow-y: auto;
  padding-right: 4px;
}

.project-index-item {
  --motion-delay: 0ms;
  position: relative;
  display: grid;
  gap: 9px;
  width: 100%;
  padding: 13px 14px 13px 16px;
  border: 1px solid transparent;
  border-radius: 18px;
  background: var(--md-sys-color-surface-container-low);
  color: var(--md-sys-color-on-surface);
  text-align: left;
  cursor: pointer;
  animation: surface-material-in 0.34s var(--ease-standard) var(--motion-delay) both;
  transition:
    background-color 0.2s ease,
    border-color 0.2s ease,
    box-shadow 0.24s ease,
    transform 0.24s var(--ease-standard);
}

.project-index-item::before {
  content: '';
  position: absolute;
  inset: 10px auto 10px 8px;
  width: 3px;
  border-radius: 999px;
  background: transparent;
  transition: background-color 0.2s ease;
}

.project-index-item:hover {
  transform: translateY(-1px);
  border-color: color-mix(in srgb, var(--md-sys-color-primary) 22%, var(--md-sys-color-outline-variant));
  background: var(--md-sys-color-surface-container);
}

.project-index-item.selected {
  border-color: color-mix(in srgb, var(--md-sys-color-primary) 34%, var(--md-sys-color-outline-variant));
  background: var(--md-sys-color-primary-container);
  box-shadow: var(--md-elevation-1);
}

.project-index-item.selected::before {
  background: var(--md-sys-color-primary);
}

.index-title-line {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  justify-content: space-between;
  min-width: 0;
}

.index-title-line strong {
  min-width: 0;
  color: var(--md-sys-color-on-surface);
  font-size: 14px;
  font-weight: 800;
  overflow-wrap: anywhere;
}

.index-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.index-stat {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  min-height: 24px;
  padding: 0 8px;
  border-radius: 12px;
  background: var(--md-sys-color-surface);
  color: var(--md-sys-color-on-surface-variant);
  font-size: 11px;
  font-weight: 800;
}

.project-index-item.selected .index-stat {
  background: color-mix(in srgb, var(--md-sys-color-surface) 74%, var(--md-sys-color-primary-container));
}

.index-stat .material-symbol {
  color: var(--md-sys-color-primary);
  font-size: 15px;
}

.index-path {
  margin: 0;
  color: var(--md-sys-color-on-surface-variant);
  font-family: var(--font-mono);
  font-size: 11px;
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.project-detail-card {
  min-width: 0;
  padding: 20px;
}

.project-header {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 16px;
  border-bottom: 1px solid var(--md-sys-color-outline-variant);
  padding-bottom: 14px;
}

.project-main {
  min-width: 0;
}

.project-title-line {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.project-title-line h2 {
  margin: 0;
  min-width: 0;
  overflow-wrap: anywhere;
  font-size: 22px;
  font-weight: 700;
}

.source-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 30px;
  padding: 0 10px;
  border-radius: 15px;
  background: var(--md-sys-color-surface-container);
  color: var(--md-sys-color-on-surface-variant);
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}

.source-chip .material-symbol {
  font-size: 16px;
}

.state-chip {
  display: inline-flex;
  align-items: center;
  min-height: 30px;
  padding: 0 11px;
  border-radius: 15px;
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 800;
}

.state-chip.active {
  background: var(--state-success-container);
  color: var(--state-success);
}

.state-chip.inactive {
  background: var(--state-warning-container);
  color: var(--state-warning);
}

.state-chip.internal {
  background: var(--md-sys-color-surface-container-high);
  color: var(--md-sys-color-on-surface-variant);
}

.source-chip.mixed,
.source-chip.docker {
  background: var(--state-success-container);
  color: var(--state-success);
}

.source-chip.file {
  background: var(--state-info-container);
  color: var(--state-info);
}

.project-path {
  display: flex;
  gap: 7px;
  align-items: flex-start;
  margin: 10px 0 0;
  color: var(--md-sys-color-on-surface-variant);
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.project-path .material-symbol {
  margin-top: 1px;
  color: var(--md-sys-color-primary);
  font-size: 16px;
}

.project-stats {
  display: grid;
  grid-template-columns: repeat(2, minmax(86px, 1fr));
  gap: 8px;
}

.stat-cell {
  min-width: 86px;
  padding: 10px 12px;
  border-radius: 16px;
  background: var(--md-sys-color-surface-container-low);
}

.stat-cell span,
.stat-cell strong {
  display: block;
}

.stat-cell span {
  color: var(--md-sys-color-on-surface-variant);
  font-size: 12px;
  font-weight: 700;
}

.stat-cell strong {
  margin-top: 4px;
  color: var(--md-sys-color-primary);
  font-family: var(--font-mono);
  font-size: 15px;
}

.file-stack {
  display: grid;
  gap: 6px;
  margin-bottom: 14px;
  padding: 12px;
  border-radius: 16px;
  background: var(--md-sys-color-surface-container-low);
}

.file-stack span {
  color: var(--md-sys-color-on-surface-variant);
  font-family: var(--font-mono);
  font-size: 12px;
  overflow-wrap: anywhere;
}

.project-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 14px;
}

.compose-progress-panel {
  display: grid;
  gap: 10px;
  width: min(100%, 720px);
  max-width: 100%;
  margin: 0 0 14px;
  padding: 12px;
  border-radius: 16px;
  background: var(--md-sys-color-primary-container);
  color: var(--md-sys-color-on-primary-container);
  font-size: 12px;
  font-weight: 800;
}

.compose-progress-head {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.compose-progress-head strong {
  min-width: 0;
  overflow-wrap: anywhere;
}

.compose-progress-panel :deep(.highlighted-text) {
  max-height: 180px;
  border: none;
  background: #0f1720;
}

.action-button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 34px;
  padding: 0 12px;
  border-radius: 17px;
  background: var(--md-sys-color-surface-container-low);
  color: var(--md-sys-color-on-surface-variant);
  cursor: pointer;
  font-size: 12px;
  font-weight: 700;
  transition: background-color 0.18s ease, color 0.18s ease, transform 0.18s ease;
}

.action-button:hover:not(:disabled) {
  background: var(--md-sys-color-primary-container);
  color: var(--md-sys-color-on-primary-container);
}

.action-button.active {
  background: var(--md-sys-color-primary-container);
  color: var(--md-sys-color-on-primary-container);
}

.action-button.danger:hover:not(:disabled) {
  background: var(--md-sys-color-error-container);
  color: var(--md-sys-color-error);
}

.action-button:active:not(:disabled) {
  transform: scale(0.97);
}

.action-button:disabled {
  opacity: 0.38;
  cursor: not-allowed;
}

.action-button .material-symbol {
  font-size: 17px;
}

.action-button .spinning,
.primary-button .spinning {
  animation: spin 0.9s linear infinite;
}

.service-grid {
  display: grid;
  gap: 12px;
}

.detail-section-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  margin: 18px 0 12px;
}

.detail-section-header h3 {
  margin: 0;
  color: var(--md-sys-color-on-surface);
  font-size: 16px;
  font-weight: 800;
}

.detail-section-header span {
  color: var(--md-sys-color-on-surface-variant);
  font-size: 12px;
  font-weight: 700;
}

.service-row {
  display: grid;
  grid-template-columns: minmax(220px, 280px) auto minmax(0, 1fr);
  gap: 14px;
  align-items: center;
  padding: 12px;
  border: 1px solid transparent;
  border-radius: 18px;
  background: var(--md-sys-color-surface-container-low);
}

.service-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  justify-content: center;
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

.icon-action:hover:not(:disabled) {
  background: var(--md-sys-color-primary-container);
  color: var(--md-sys-color-on-primary-container);
}

.icon-action.danger:hover:not(:disabled) {
  background: var(--md-sys-color-error-container);
  color: var(--md-sys-color-error);
}

.icon-action:active:not(:disabled) {
  transform: scale(0.96);
}

.icon-action:disabled {
  opacity: 0.38;
  cursor: not-allowed;
}

.icon-action .material-symbol {
  font-size: 18px;
}

.service-row.cold-service {
  border-color: var(--md-sys-color-outline-variant);
  background: var(--md-sys-color-surface-container-lowest);
}

.service-title {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  justify-content: space-between;
  min-width: 0;
}

.service-title strong,
.service-title span {
  display: block;
}

.service-title strong {
  overflow-wrap: anywhere;
}

.service-title span {
  margin-top: 4px;
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.4;
  overflow-wrap: anywhere;
}

.service-count {
  flex: 0 0 auto;
  margin-top: 0 !important;
  padding: 4px 8px;
  border-radius: 12px;
  background: var(--md-sys-color-surface-container);
  color: var(--md-sys-color-primary) !important;
  font-size: 11px !important;
  font-weight: 700;
  white-space: nowrap;
}

.service-containers {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
  min-width: 0;
}

.service-containers .status-pill {
  max-width: 100%;
  overflow-wrap: anywhere;
  white-space: normal;
}

.pending-label {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  justify-self: end;
  width: fit-content;
  min-height: 32px;
  padding: 0 12px;
  border-radius: 16px;
  background: var(--md-sys-color-surface-container);
  color: var(--md-sys-color-on-surface-variant);
  font-size: 12px;
  font-weight: 700;
}

.pending-label .material-symbol {
  font-size: 16px;
}

.empty-state.compact {
  padding: 22px;
  border-radius: 18px;
}

.project-detail-panel {
  margin-bottom: 14px;
}

.editor-heading {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  margin-bottom: 10px;
  color: var(--md-sys-color-on-surface-variant);
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.editor-heading .material-symbol {
  color: var(--md-sys-color-primary);
  font-size: 17px;
}

.editor-heading strong {
  min-width: 0;
  overflow-wrap: anywhere;
}

.compose-editor-shell {
  position: relative;
  min-height: 360px;
  border: 1px solid var(--md-sys-color-outline-variant);
  border-radius: 18px;
  background: #0f1720;
  overflow: hidden;
}

.compose-editor-highlight {
  position: absolute;
  inset: 0;
  max-height: none;
  min-height: 100%;
  border: none;
  border-radius: 0;
  pointer-events: none;
}

.compose-editor-highlight::-webkit-scrollbar {
  display: none;
}

.compose-editor {
  position: relative;
  width: 100%;
  min-height: 360px;
  resize: vertical;
  border: none;
  background: transparent;
  color: transparent;
  caret-color: #d7e3f4;
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.55;
  outline: none;
  padding: 14px;
  tab-size: 2;
  white-space: pre-wrap;
}

.compose-editor::selection {
  background: color-mix(in srgb, var(--md-sys-color-primary) 38%, transparent);
}

.compose-editor-shell:focus-within {
  border-color: var(--md-sys-color-primary);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--md-sys-color-primary) 18%, transparent);
}

.panel-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}

.error-banner.inline {
  margin-bottom: 0;
}

.detail-log {
  max-height: 420px;
  margin: 0;
  overflow: auto;
  padding: 14px;
  border-radius: 16px;
  background: #0f1720;
  color: #d7e3f4;
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.55;
  white-space: pre-wrap;
}

.compose-modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 80;
  display: grid;
  place-items: center;
  padding: 28px;
  background: color-mix(in srgb, #101418 42%, transparent);
  backdrop-filter: blur(10px);
}

.compose-modal {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  width: min(920px, 100%);
  max-height: min(820px, calc(100vh - 56px));
  overflow: hidden;
  border: 1px solid var(--md-sys-color-outline-variant);
  border-radius: 28px;
  background: var(--md-sys-color-surface);
  box-shadow: var(--md-elevation-3);
}

.compose-modal-header,
.compose-modal-footer {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 18px 20px;
}

.compose-modal-header {
  justify-content: space-between;
  border-bottom: 1px solid var(--md-sys-color-outline-variant);
}

.compose-modal-header h2 {
  margin: 0;
  color: var(--md-sys-color-on-surface);
  font-size: 24px;
  line-height: 1.2;
  font-weight: 800;
}

.compose-create-body {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  min-height: 0;
  overflow: auto;
  padding: 20px;
}

.source-segmented {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  grid-column: 1 / -1;
  padding: 4px;
  border-radius: 20px;
  background: var(--md-sys-color-surface-container-low);
}

.source-segmented button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  min-height: 36px;
  padding: 0 14px;
  border-radius: 18px;
  color: var(--md-sys-color-on-surface-variant);
  cursor: pointer;
  font-size: 13px;
  font-weight: 800;
  transition: background-color 0.18s ease, color 0.18s ease, transform 0.18s ease;
}

.source-segmented button.active,
.source-segmented button:hover {
  background: var(--md-sys-color-primary-container);
  color: var(--md-sys-color-on-primary-container);
}

.source-segmented button:active {
  transform: scale(0.97);
}

.source-segmented .material-symbol {
  font-size: 18px;
}

.field-row {
  display: grid;
  gap: 7px;
  min-width: 0;
}

.field-row span {
  color: var(--md-sys-color-on-surface-variant);
  font-size: 12px;
  font-weight: 800;
}

.compose-create-editor {
  display: grid;
  grid-column: 1 / -1;
  gap: 10px;
  min-width: 0;
}

.compose-create-editor .compose-editor-shell {
  min-height: 390px;
}

.compose-create-editor .compose-editor {
  min-height: 390px;
}

.compose-modal-footer {
  justify-content: flex-end;
  border-top: 1px solid var(--md-sys-color-outline-variant);
  background: var(--md-sys-color-surface-container-lowest);
}

.wizard-fade-enter-active,
.wizard-fade-leave-active {
  transition: opacity 0.2s ease;
}

.wizard-fade-enter-active .compose-modal,
.wizard-fade-leave-active .compose-modal {
  transition: opacity 0.22s ease, transform 0.26s var(--ease-standard);
}

.wizard-fade-enter-from,
.wizard-fade-leave-to {
  opacity: 0;
}

.wizard-fade-enter-from .compose-modal,
.wizard-fade-leave-to .compose-modal {
  opacity: 0;
  transform: translateY(12px) scale(0.985);
}

@media (max-width: 920px) {
  .compose-workbench {
    grid-template-columns: 1fr;
  }

  .project-sidebar {
    position: static;
    max-height: none;
  }

  .project-index {
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    max-height: 360px;
  }

  .project-header {
    grid-template-columns: 1fr;
  }

  .project-stats {
    width: 100%;
  }
}

@media (max-width: 760px) {
  .page-header {
    align-items: stretch;
    flex-direction: column;
  }

  .header-actions {
    justify-content: stretch;
  }

  .header-actions > button {
    flex: 1 1 180px;
  }

  .service-row {
    grid-template-columns: 1fr;
  }

  .service-title {
    flex-direction: column;
  }

  .service-count {
    width: fit-content;
  }

  .service-containers {
    justify-content: flex-start;
  }

  .pending-label {
    justify-self: start;
  }

  .compose-modal-backdrop {
    padding: 14px;
  }

  .compose-create-body {
    grid-template-columns: 1fr;
  }

  .compose-modal-header,
  .compose-modal-footer {
    padding: 16px;
  }

  .compose-modal-footer {
    align-items: stretch;
    flex-direction: column-reverse;
  }

  .compose-modal-footer > button {
    width: 100%;
  }
}
</style>
