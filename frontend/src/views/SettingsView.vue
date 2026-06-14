<template>
  <section class="page-shell settings-view">
    <header class="page-header">
      <div>
        <p class="eyebrow">运行时设置</p>
        <h1 class="page-title">设置</h1>
        <p class="page-subtitle">调整 WebUI 运行时配置；目录配置会立即影响日志读取和 Compose 扫描。</p>
      </div>
      <button class="toolbar-button" type="button" @click="loadSettings" :disabled="loading">
        <span class="material-symbol">{{ loading ? 'progress_activity' : 'refresh' }}</span>
        {{ loading ? '刷新中' : '刷新' }}
      </button>
    </header>

    <NoticeBanner v-if="notice" :ok="notice.ok" :message="notice.message" />

    <MotionSurface class="settings-panel" :expanded="advancedOpen">
      <div class="settings-section">
        <div class="settings-section-head">
          <span class="section-icon material-symbol">folder_managed</span>
          <div>
            <h2>目录权限</h2>
            <p>项目扫描、Compose 编辑和日志读取的访问范围。</p>
          </div>
        </div>
        <div class="field-stack">
          <label class="field-row">
            <span>项目目录</span>
            <textarea
              ref="projectRootsInput"
              v-model="form.project_roots"
              class="themed-textarea path-input auto-grow-input"
              rows="1"
              placeholder="samples&#10;/projects"
              @input="resizeProjectRootsInput"
            ></textarea>
          </label>
          <label class="field-row">
            <span>日志目录</span>
            <input v-model.trim="form.log_roots" class="themed-input path-input" placeholder="samples/logs" />
          </label>
        </div>
        <div class="settings-note">
          <span class="material-symbol">info</span>
          <p>
            项目目录可以添加多个，一行一份  
          </p>
        </div>
      </div>

      <div class="settings-section">
        <div class="settings-section-head">
          <span class="section-icon material-symbol">verified_user</span>
          <div>
            <h2>操作确认</h2>
            <p>停止容器和停止 Compose 项目等高危操作的确认策略。</p>
          </div>
        </div>
        <div class="field-stack">
          <label class="switch-row">
            <input v-model="form.require_dangerous_approval" type="checkbox" />
            <span>高危操作需要确认</span>
          </label>
        </div>
      </div>

      <div class="settings-section">
        <div class="settings-section-head">
          <span class="section-icon material-symbol">psychology</span>
          <div>
            <h2>模型配置</h2>
            <p>配置 OpenAI-compatible 接口；API Key 留空时保留当前值。</p>
          </div>
        </div>
        <div class="field-stack">
          <label class="field-row">
            <span>接口地址</span>
            <input v-model.trim="form.llm_base_url" class="themed-input" placeholder="https://example.com/v1" />
          </label>
          <label class="field-row">
            <span>模型名称</span>
            <input v-model.trim="form.llm_model" class="themed-input" placeholder="gpt-5.5" />
          </label>
          <label class="field-row">
            <span>API Key</span>
            <input v-model.trim="form.llm_api_key" class="themed-input" type="password" placeholder="留空则不修改" />
          </label>
        </div>
      </div>

      <div class="settings-section advanced-section">
        <button class="advanced-trigger" type="button" :aria-expanded="advancedOpen" @click="advancedOpen = !advancedOpen">
          <span class="section-icon material-symbol">tune</span>
          <span class="advanced-title">
            <strong>高级设置</strong>
            <small>Docker CLI 代理与社区部署选项。</small>
          </span>
          <span class="material-symbol advanced-chevron">{{ advancedOpen ? 'expand_less' : 'expand_more' }}</span>
        </button>
        <Transition name="panel-rise">
          <div v-if="advancedOpen" class="advanced-body">
            <div class="field-stack">
              <label class="field-row">
                <span>HTTP 代理</span>
                <input v-model.trim="form.docker_http_proxy" class="themed-input" placeholder="http://127.0.0.1:7890" />
              </label>
              <label class="field-row">
                <span>HTTPS 代理</span>
                <input v-model.trim="form.docker_https_proxy" class="themed-input" placeholder="http://127.0.0.1:7890" />
              </label>
              <label class="field-row">
                <span>排除项</span>
                <textarea
                  v-model.trim="form.docker_no_proxy"
                  class="themed-textarea"
                  rows="2"
                  placeholder="localhost,127.0.0.1,.local"
                ></textarea>
              </label>
              <section class="mcp-settings-panel public-mcp-panel">
                <div class="mcp-panel-head">
                  <div>
                    <h3>内置 MCP 暴露</h3>
                    <p>允许外部 MCP 客户端连接本项目的 Docker 运维工具。</p>
                  </div>
                  <label class="switch-row compact-switch">
                    <input v-model="form.enable_public_mcp" type="checkbox" />
                    <span>{{ form.enable_public_mcp ? '已开启' : '已关闭' }}</span>
                  </label>
                </div>
                <div class="endpoint-chip">
                  <span class="material-symbol">link</span>
                  <code>/api/mcp</code>
                </div>
                <div class="settings-note">
                  <span class="material-symbol">security</span>
                  <p>只建议在可信网络使用。外部客户端能访问 Docker 运维工具；停止、删除、清理等高危操作仍不会从公开 MCP 入口接受隐藏确认参数。</p>
                </div>
              </section>
              <section class="mcp-settings-panel">
                <div class="mcp-panel-head">
                  <div>
                    <h3>外部 MCP 引用</h3>
                    <p>把可信 MCP stdio server 接入 AI 工具列表。</p>
                  </div>
                  <div class="mcp-panel-actions">
                    <button class="toolbar-button compact-button" type="button" @click="addMcpServer">
                      <span class="material-symbol">add</span>
                      添加
                    </button>
                    <button class="toolbar-button compact-button" type="button" @click="loadMcpFetchExample">
                      <span class="material-symbol">auto_stories</span>
                      示例
                    </button>
                  </div>
                </div>

                <div v-if="externalMcpServers.length === 0" class="mcp-empty-state">
                  <span class="material-symbol">extension_off</span>
                  <p>还没有外部 MCP。添加后，AI 会看到“服务名__工具名”格式的工具。</p>
                </div>

                <div v-else class="mcp-server-list">
                  <article v-for="(server, index) in externalMcpServers" :key="server.id" class="mcp-server-card">
                    <button class="mcp-server-summary" type="button" @click="server.expanded = !server.expanded">
                      <span class="section-icon material-symbol">extension</span>
                      <span class="mcp-server-title">
                        <strong>{{ server.name.trim() || `外部 MCP ${index + 1}` }}</strong>
                        <small>{{ server.command.trim() || '尚未配置启动命令' }}</small>
                      </span>
                      <span class="material-symbol">{{ server.expanded ? 'expand_less' : 'expand_more' }}</span>
                    </button>

                    <Transition name="panel-rise">
                      <div v-if="server.expanded" class="mcp-server-fields">
                        <label class="field-row">
                          <span>服务名</span>
                          <input
                            v-model.trim="server.name"
                            class="themed-input"
                            placeholder="web"
                            @input="syncExternalMcpJsonFromEntries"
                          />
                        </label>
                        <label class="field-row">
                          <span>命令</span>
                          <input
                            v-model.trim="server.command"
                            class="themed-input"
                            placeholder="uvx"
                            @input="syncExternalMcpJsonFromEntries"
                          />
                        </label>
                        <label class="field-row">
                          <span>参数</span>
                          <textarea
                            v-model="server.argsText"
                            class="themed-textarea mcp-lines-input"
                            rows="3"
                            placeholder="--from&#10;mcp-server-fetch&#10;mcp-server-fetch"
                            @input="syncExternalMcpJsonFromEntries"
                          ></textarea>
                        </label>
                        <label class="field-row">
                          <span>工作目录</span>
                          <input
                            v-model.trim="server.cwd"
                            class="themed-input"
                            placeholder="可选"
                            @input="syncExternalMcpJsonFromEntries"
                          />
                        </label>
                        <label class="field-row">
                          <span>环境变量</span>
                          <textarea
                            v-model="server.envText"
                            class="themed-textarea mcp-lines-input"
                            rows="3"
                            placeholder="HTTP_PROXY=http://127.0.0.1:7890&#10;NO_PROXY=localhost,127.0.0.1"
                            @input="syncExternalMcpJsonFromEntries"
                          ></textarea>
                        </label>
                        <label class="field-row">
                          <span>说明</span>
                          <input
                            v-model.trim="server.description"
                            class="themed-input"
                            placeholder="读取网页教程"
                            @input="syncExternalMcpJsonFromEntries"
                          />
                        </label>
                        <div class="mcp-card-actions">
                          <button class="toolbar-button danger-button" type="button" @click="removeMcpServer(index)">
                            <span class="material-symbol">delete</span>
                            删除
                          </button>
                        </div>
                      </div>
                    </Transition>
                  </article>
                </div>

                <div v-if="mcpSettingsError" class="settings-note error-note">
                  <span class="material-symbol">error</span>
                  <p>{{ mcpSettingsError }}</p>
                </div>
                <details class="mcp-json-details">
                  <summary>
                    <span class="material-symbol">data_object</span>
                    原始 JSON
                  </summary>
                  <textarea
                    v-model="rawMcpJsonPreview"
                    class="themed-textarea mcp-config-input"
                    rows="8"
                    spellcheck="false"
                    readonly
                  ></textarea>
                </details>
                <div class="settings-note">
                  <span class="material-symbol">security</span>
                  <p>这里会启动后端环境内的命令，只添加可信 MCP；Docker 部署时命令必须存在于后端容器内。</p>
                </div>
              </section>
            </div>  
          </div>
        </Transition>
      </div>

      <div class="settings-actions">
        <button class="primary-button" type="button" :disabled="saving" @click="saveSettings">
          <span class="material-symbol">{{ saving ? 'progress_activity' : 'save' }}</span>
          保存设置
        </button>
      </div>
    </MotionSurface>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { getRuntimeSettings, updateRuntimeSettings } from '../api'
import type { OperationResponse, RuntimeSettingsResponse } from '../api/types'
import MotionSurface from '../components/MotionSurface.vue'
import NoticeBanner from '../components/NoticeBanner.vue'
import { requestConfirm } from '../utils/confirmDialog'

const loading = ref(false)
const saving = ref(false)
const notice = ref<{ ok: boolean; message: string } | null>(null)
const advancedOpen = ref(false)
const projectRootsInput = ref<HTMLTextAreaElement | null>(null)
const mcpSettingsError = ref('')

interface ExternalMcpServerForm {
  id: string
  name: string
  command: string
  argsText: string
  envText: string
  cwd: string
  description: string
  expanded: boolean
}

const form = reactive({
  project_roots: '',
  log_roots: '',
  require_dangerous_approval: true,
  llm_base_url: '',
  llm_model: '',
  llm_api_key: '',
  docker_http_proxy: '',
  docker_https_proxy: '',
  docker_no_proxy: '',
  external_mcp_servers: '',
  enable_public_mcp: false,
})

const externalMcpServers = ref<ExternalMcpServerForm[]>([])

const rawMcpJsonPreview = computed(() => form.external_mcp_servers || '{}')

function formatPathRoots(value: string) {
  // 把逗号或换行分隔的路径统一成每行一个，方便编辑。
  return value
    .split(/[\n,]+/)
    .map((item) => item.trim())
    .filter(Boolean)
    .join('\n')
}

function resizeProjectRootsInput() {
  const input = projectRootsInput.value
  if (!input) return
  // 先重置高度，删除行时 textarea 才会缩小而不是保留旧高度。
  input.style.height = 'auto'
  input.style.height = `${input.scrollHeight}px`
}

function createMcpServerForm(value: Partial<ExternalMcpServerForm> = {}): ExternalMcpServerForm {
  return {
    id: crypto.randomUUID(),
    name: value.name || '',
    command: value.command || '',
    argsText: value.argsText || '',
    envText: value.envText || '',
    cwd: value.cwd || '',
    description: value.description || '',
    expanded: value.expanded ?? true,
  }
}

function parseExternalMcpServers(value: string): ExternalMcpServerForm[] {
  mcpSettingsError.value = ''
  const trimmed = value.trim()
  if (!trimmed) return []
  try {
    const payload = JSON.parse(trimmed) as unknown
    if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
      mcpSettingsError.value = '外部 MCP JSON 顶层必须是对象。'
      return []
    }
    return Object.entries(payload as Record<string, unknown>).map(([name, raw]) => {
      const server = raw && typeof raw === 'object' && !Array.isArray(raw) ? raw as Record<string, unknown> : {}
      const args = Array.isArray(server.args) ? server.args.map((item) => String(item)).join('\n') : ''
      const env = server.env && typeof server.env === 'object' && !Array.isArray(server.env)
        ? Object.entries(server.env as Record<string, unknown>).map(([key, item]) => `${key}=${String(item)}`).join('\n')
        : ''
      return createMcpServerForm({
        name,
        command: typeof server.command === 'string' ? server.command : '',
        argsText: args,
        envText: env,
        cwd: typeof server.cwd === 'string' ? server.cwd : '',
        description: typeof server.description === 'string' ? server.description : '',
        expanded: false,
      })
    })
  } catch (err) {
    mcpSettingsError.value = `外部 MCP JSON 解析失败：${String(err)}`
    return []
  }
}

function parseEnvLines(value: string): Record<string, string> {
  const env: Record<string, string> = {}
  value
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .forEach((line) => {
      const index = line.indexOf('=')
      if (index <= 0) return
      env[line.slice(0, index).trim()] = line.slice(index + 1).trim()
    })
  return env
}

function syncExternalMcpJsonFromEntries() {
  mcpSettingsError.value = ''
  const payload: Record<string, Record<string, unknown>> = {}
  for (const server of externalMcpServers.value) {
    const name = server.name.trim()
    const command = server.command.trim()
    if (!name && !command) continue
    if (!/^[\w-]+$/.test(name)) {
      mcpSettingsError.value = '服务名只能包含字母、数字、下划线和短横线。'
      continue
    }
    const args = server.argsText
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean)
    const env = parseEnvLines(server.envText)
    payload[name] = {
      command,
      ...(args.length ? { args } : {}),
      ...(Object.keys(env).length ? { env } : {}),
      ...(server.cwd.trim() ? { cwd: server.cwd.trim() } : {}),
      ...(server.description.trim() ? { description: server.description.trim() } : {}),
    }
  }
  form.external_mcp_servers = Object.keys(payload).length ? JSON.stringify(payload, null, 2) : ''
}

function addMcpServer() {
  externalMcpServers.value.push(createMcpServerForm())
  syncExternalMcpJsonFromEntries()
}

function removeMcpServer(index: number) {
  externalMcpServers.value.splice(index, 1)
  syncExternalMcpJsonFromEntries()
}

function loadMcpFetchExample() {
  externalMcpServers.value = [
    createMcpServerForm({
      name: 'web',
      command: 'uvx',
      argsText: '--from\nmcp-server-fetch\nmcp-server-fetch',
      description: '读取网页教程',
      expanded: true,
    }),
  ]
  syncExternalMcpJsonFromEntries()
}

function applySettings(value: RuntimeSettingsResponse) {
  form.project_roots = formatPathRoots(value.project_roots)
  form.log_roots = value.log_roots
  form.require_dangerous_approval = value.require_dangerous_approval
  form.llm_base_url = value.llm_base_url
  form.llm_model = value.llm_model
  // 接口密钥在界面里按只写处理；留空表示不修改当前已保存密钥。
  form.llm_api_key = ''
  form.docker_http_proxy = value.docker_http_proxy
  form.docker_https_proxy = value.docker_https_proxy
  form.docker_no_proxy = value.docker_no_proxy
  form.external_mcp_servers = value.external_mcp_servers || ''
  form.enable_public_mcp = value.enable_public_mcp
  externalMcpServers.value = parseExternalMcpServers(form.external_mcp_servers)
  nextTick(resizeProjectRootsInput)
}

function isOperationResponse(value: RuntimeSettingsResponse | OperationResponse): value is OperationResponse {
  return 'ok' in value
}

async function loadSettings() {
  loading.value = true
  notice.value = null
  try {
    applySettings(await getRuntimeSettings())
  } catch (err) {
    notice.value = { ok: false, message: `读取设置失败：${String(err)}` }
  } finally {
    loading.value = false
  }
}

async function saveSettings() {
  const approve = await requestConfirm({
    title: '保存设置',
    message: '确认保存运行时设置？',
    confirmText: '保存',
    icon: 'save',
  })
  if (!approve) return
  saving.value = true
  notice.value = null
  try {
    syncExternalMcpJsonFromEntries()
    if (mcpSettingsError.value) {
      notice.value = { ok: false, message: mcpSettingsError.value }
      return
    }
    // 接口密钥留空时不提交，避免一次普通保存清掉已存密钥。
    const payload = {
      project_roots: formatPathRoots(form.project_roots),
      log_roots: form.log_roots,
      require_dangerous_approval: form.require_dangerous_approval,
      llm_base_url: form.llm_base_url,
      llm_model: form.llm_model,
      docker_http_proxy: form.docker_http_proxy,
      docker_https_proxy: form.docker_https_proxy,
      docker_no_proxy: form.docker_no_proxy,
      external_mcp_servers: form.external_mcp_servers,
      enable_public_mcp: form.enable_public_mcp,
      approve,
      ...(form.llm_api_key ? { llm_api_key: form.llm_api_key } : {}),
    }
    const result = await updateRuntimeSettings(payload)
    if (isOperationResponse(result)) {
      notice.value = { ok: result.ok, message: result.message }
      return
    }
    applySettings(result)
    notice.value = { ok: true, message: '设置已更新。' }
  } catch (err) {
    notice.value = { ok: false, message: `保存设置失败：${String(err)}` }
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  loadSettings()
  nextTick(resizeProjectRootsInput)
})
</script>

<style scoped>
.toolbar-button,
.primary-button {
  gap: 8px;
}

.toolbar-button .material-symbol,
.primary-button .material-symbol {
  font-size: 18px;
}

.toolbar-button:disabled .material-symbol,
.primary-button:disabled .material-symbol {
  animation: spin 0.9s linear infinite;
}

.settings-panel {
  display: grid;
  max-width: 920px;
  margin: 0 auto;
  overflow: hidden;
  padding: 0;
}

.settings-section {
  display: grid;
  grid-template-columns: 1fr;
  gap: 18px;
  align-items: start;
  padding: 24px;
  border-bottom: 1px solid var(--md-sys-color-outline-variant);
}

.settings-section:last-of-type {
  border-bottom: 1px solid var(--md-sys-color-outline-variant);
}

.settings-section h2 {
  margin: 0;
  font-size: 20px;
}

.settings-section-head {
  display: grid;
  grid-template-columns: 40px minmax(0, 1fr);
  gap: 12px;
  align-items: center;
  min-width: 0;
}

.section-icon {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  border-radius: 20px;
  background: var(--md-sys-color-secondary-container);
  color: var(--md-sys-color-on-primary-container);
  font-size: 20px;
}

.settings-section-head p,
.advanced-title small {
  margin: 4px 0 0;
  color: var(--md-sys-color-on-surface-variant);
  font-size: 13px;
  line-height: 1.6;
}

.field-stack {
  display: grid;
  gap: 14px;
  width: 100%;
}

.field-row {
  display: grid;
  gap: 7px;
  color: var(--md-sys-color-on-surface-variant);
  font-size: 13px;
  font-weight: 700;
}

.field-row .themed-input,
.field-row .themed-textarea {
  width: 100%;
}

.path-input {
  min-width: 0;
  font-family: var(--font-mono);
  font-size: 12px;
}

.auto-grow-input {
  min-height: 48px;
  max-height: 180px;
  overflow-y: auto;
}

.mcp-config-input {
  min-height: 180px;
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.6;
}

.mcp-settings-panel {
  display: grid;
  gap: 14px;
  padding: 16px;
  border: 1px solid var(--md-sys-color-outline-variant);
  border-radius: 24px;
  background: var(--md-sys-color-surface-container-lowest);
}

.public-mcp-panel {
  background:
    linear-gradient(135deg, color-mix(in srgb, var(--md-sys-color-primary) 8%, transparent), transparent 42%),
    var(--md-sys-color-surface-container-lowest);
}

.mcp-panel-head,
.mcp-server-summary {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
}

.mcp-panel-head h3 {
  margin: 0;
  font-size: 16px;
}

.mcp-panel-head p,
.mcp-empty-state p {
  margin: 4px 0 0;
  color: var(--md-sys-color-on-surface-variant);
  font-size: 13px;
  line-height: 1.6;
}

.mcp-panel-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.compact-switch {
  justify-self: end;
  width: auto;
  min-height: 36px;
  padding: 0;
  white-space: nowrap;
}

.endpoint-chip {
  display: inline-flex;
  gap: 8px;
  align-items: center;
  width: fit-content;
  max-width: 100%;
  padding: 8px 12px;
  border: 1px solid color-mix(in srgb, var(--md-sys-color-primary) 24%, var(--md-sys-color-outline-variant));
  border-radius: 999px;
  background: color-mix(in srgb, var(--md-sys-color-primary) 10%, transparent);
  color: var(--md-sys-color-primary);
  font-size: 13px;
  font-weight: 800;
}

.endpoint-chip .material-symbol {
  font-size: 18px;
}

.endpoint-chip code {
  min-width: 0;
  overflow: hidden;
  font-family: var(--font-mono);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.compact-button {
  min-height: 38px;
  padding: 0 14px;
}

.mcp-empty-state {
  display: grid;
  grid-template-columns: 36px minmax(0, 1fr);
  gap: 10px;
  align-items: center;
  min-height: 72px;
  padding: 14px;
  border: 1px dashed var(--md-sys-color-outline-variant);
  border-radius: 18px;
  color: var(--md-sys-color-on-surface-variant);
}

.mcp-empty-state .material-symbol {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border-radius: 18px;
  background: color-mix(in srgb, var(--md-sys-color-primary) 10%, transparent);
  color: var(--md-sys-color-primary);
}

.mcp-server-list {
  display: grid;
  gap: 10px;
}

.mcp-server-card {
  overflow: hidden;
  border: 1px solid var(--md-sys-color-outline-variant);
  border-radius: 22px;
  background: var(--md-sys-color-surface);
  transition: border-color 0.18s ease, box-shadow 0.18s ease, transform 0.18s ease;
}

.mcp-server-card:hover {
  border-color: color-mix(in srgb, var(--md-sys-color-primary) 42%, var(--md-sys-color-outline-variant));
  box-shadow: 0 14px 36px color-mix(in srgb, var(--md-sys-color-primary) 18%, transparent);
  transform: translateY(-1px);
}

.mcp-server-summary {
  grid-template-columns: 40px minmax(0, 1fr) 28px;
  width: 100%;
  padding: 14px;
  background: transparent;
  color: var(--md-sys-color-on-surface);
  cursor: pointer;
  text-align: left;
}

.mcp-server-title {
  min-width: 0;
}

.mcp-server-title strong,
.mcp-server-title small {
  display: block;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mcp-server-title strong {
  font-size: 14px;
}

.mcp-server-title small {
  margin-top: 4px;
  color: var(--md-sys-color-on-surface-variant);
  font-family: var(--font-mono);
  font-size: 12px;
}

.mcp-server-fields {
  display: grid;
  gap: 12px;
  padding: 0 14px 14px;
}

.mcp-lines-input {
  min-height: 86px;
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.6;
}

.mcp-card-actions {
  display: flex;
  justify-content: flex-end;
}

.danger-button {
  color: var(--state-danger);
}

.error-note {
  background: var(--state-danger-container);
  color: var(--state-danger);
}

.mcp-json-details {
  display: grid;
  gap: 10px;
}

.mcp-json-details summary {
  display: inline-flex;
  gap: 8px;
  align-items: center;
  width: fit-content;
  color: var(--md-sys-color-primary);
  cursor: pointer;
  font-size: 13px;
  font-weight: 800;
}

.mcp-json-details summary .material-symbol {
  font-size: 18px;
}

.settings-note {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 10px;
  width: 100%;
  padding: 12px 14px;
  border-radius: 16px;
  background: var(--state-info-container);
  color: var(--state-info);
}

.settings-note .material-symbol {
  margin-top: 1px;
  font-size: 18px;
}

.settings-note p {
  margin: 0;
  color: inherit;
  font-size: 12px;
  font-weight: 700;
  line-height: 1.65;
}

.switch-row {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  min-height: 44px;
  padding: 0 2px;
  color: var(--md-sys-color-on-surface);
  font-size: 13px;
  font-weight: 700;
}

.switch-row input {
  width: 18px;
  height: 18px;
  accent-color: var(--md-sys-color-primary);
}

.advanced-section {
  gap: 0;
  padding: 0;
}

.advanced-trigger {
  display: grid;
  grid-template-columns: 40px minmax(0, 1fr) 32px;
  gap: 12px;
  align-items: center;
  width: 100%;
  min-height: 88px;
  padding: 18px 24px;
  background: transparent;
  color: var(--md-sys-color-on-surface);
  cursor: pointer;
  text-align: left;
}

.advanced-title strong,
.advanced-title small {
  display: block;
  min-width: 0;
}

.advanced-title strong {
  font-size: 15px;
}

.advanced-chevron {
  color: var(--md-sys-color-on-surface-variant);
  justify-self: end;
}

.advanced-body {
  display: grid;
  gap: 14px;
  padding: 0 24px 24px;
}

.settings-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  align-items: center;
  padding: 18px 24px;
  background: var(--md-sys-color-surface-container-lowest);
}

@media (max-width: 860px) {
  .settings-actions {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
