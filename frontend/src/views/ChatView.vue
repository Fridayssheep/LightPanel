<template>
  <div class="chat-view page-shell">
    <MotionSurface as="div" class="chat-header">
      <div>
        <p class="eyebrow">Agent console</p>
        <h1 class="chat-title">对话诊断</h1>
      </div>
      <div class="chat-controls">
        <label class="control-item">
          <input type="checkbox" v-model="approveActions" />
          <span>允许高危操作</span>
        </label>
        <label class="control-item">
          <input type="checkbox" v-model="dryRun" />
          <span>Dry Run</span>
        </label>
      </div>
    </MotionSurface>

    <NoticeBanner v-if="resumeNotice" :ok="true" :message="resumeNotice" />

    <MotionSurface as="div" class="messages-container" :interactive="false" :delay="45" ref="messagesSurface">
      <TransitionGroup name="msg-rise">
        <div
          v-for="msg in messages"
          :key="msg.id"
          class="message-wrapper"
          :class="msg.role"
        >
          <div class="message-bubble">
            <div class="message-content" v-html="renderSimpleMarkdown(msg.content)"></div>
            <div v-if="msg.agent_trace && msg.agent_trace.length && !msg.typing" class="agent-trace">
              <div class="agent-trace-header">
                <span class="material-symbol">route</span>
                执行过程
              </div>
              <div
                v-for="(step, idx) in msg.agent_trace"
                :key="step.id"
                class="agent-trace-item"
                :class="[step.type, step.status || '']"
                :style="{ transitionDelay: `${Math.min(idx, 6) * 35}ms` }"
              >
                <span class="trace-rail"></span>
                <span class="trace-icon material-symbol">{{ traceIcon(step) }}</span>
                <div class="trace-body">
                  <div class="trace-title-row">
                    <strong>{{ step.title }}</strong>
                    <span v-if="step.status" class="trace-status" :class="step.status">{{ step.status }}</span>
                  </div>
                  <p>{{ step.summary }}</p>
                  <code v-if="step.tool_name" class="trace-tool">{{ step.tool_name }}</code>
                  <div v-if="formatTraceArguments(step.arguments)" class="trace-args">
                    {{ formatTraceArguments(step.arguments) }}
                  </div>
                </div>
              </div>
            </div>
            <div v-if="msg.tool_calls && msg.tool_calls.length && !msg.typing" class="tool-calls">
              <div class="tool-calls-header">
                <span class="material-symbol">construction</span>
                工具调用
              </div>
              <div class="tool-call-item" v-for="call in msg.tool_calls" :key="call.id">
                <div class="tool-call-name">{{ call.tool_name }}</div>
                <div class="tool-call-status" :class="call.status">{{ call.status }}</div>
                <div class="tool-call-summary">{{ call.summary }}</div>
              </div>
            </div>
            <div v-if="msg.pending_actions && msg.pending_actions.length && !msg.typing" class="pending-actions">
              <div class="pending-header">
                <span class="material-symbol">warning</span>
                待确认操作
              </div>
              <div class="pending-item" v-for="(action, idx) in msg.pending_actions" :key="idx">
                <div class="pending-tool">{{ action.tool_name }}</div>
                <div class="pending-reason">{{ action.reason }}</div>
              </div>
              <div class="pending-tip">请勾选“允许高危操作”后重新发送</div>
            </div>
          </div>
          <div v-if="msg.role === 'assistant' && msg.incident_id" class="message-actions">
            <button @click="viewReport(msg.incident_id)" class="btn-action" :disabled="loadingReportId === msg.incident_id">
              <span class="material-symbol">{{ loadingReportId === msg.incident_id ? 'progress_activity' : 'analytics' }}</span>
              {{ loadingReportId === msg.incident_id ? '生成中' : '生成诊断报告' }}
            </button>
          </div>
        </div>
      </TransitionGroup>
      <div v-if="loading" class="loading-indicator">
        <div class="tool-progress">
          <div class="tool-progress-orb">
            <span class="material-symbol">psychology</span>
          </div>
          <div class="tool-progress-body">
            <strong>{{ loadingStage }}</strong>
            <span>{{ loadingHint }}</span>
            <div v-if="activeToolName" class="active-tool-chip">
              <span class="material-symbol">terminal</span>
              {{ activeToolName }}
              <small>{{ activeToolStatus }}</small>
            </div>
            <div class="tool-progress-track">
              <span
                v-for="step in toolProgressSteps"
                :key="step"
                class="tool-progress-dot"
              ></span>
            </div>
          </div>
        </div>
      </div>
    </MotionSurface>

    <MotionSurface as="div" class="input-area" :interactive="false" :delay="90">
      <textarea
        v-model="inputMessage"
        @keydown.enter.ctrl="sendMessage"
        class="themed-textarea"
        placeholder="描述遇到的运维问题，例如：查看 Docker 容器状态"
        :disabled="loading || typing"
        rows="3"
      ></textarea>
      <button @click="sendMessage" :disabled="loading || typing || !inputMessage.trim()" class="btn-send">
        发送
      </button>
    </MotionSurface>

    <DiagnosisReportModal :report="currentReport" @close="currentReport = null" />
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { sendChatStream, generateReport } from '../api'
import type { AgentTraceStep, ChatMessage, ChatResponse, ChatStreamEvent, DiagnosisReport, ToolCallRecord, PendingAction } from '../api/types'
import DiagnosisReportModal from '../components/DiagnosisReportModal.vue'
import MotionSurface from '../components/MotionSurface.vue'
import NoticeBanner from '../components/NoticeBanner.vue'
import { takeChatResume } from '../utils/chatResume'
import { renderSimpleMarkdown } from '../utils/text'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  tool_calls?: ToolCallRecord[]
  agent_trace?: AgentTraceStep[]
  pending_actions?: PendingAction[]
  incident_id?: string
  typing?: boolean
}

const messages = ref<Message[]>([])
const inputMessage = ref('')
const loading = ref(false)
const typing = ref(false)
const loadingStage = ref('准备上下文')
const loadingHint = ref('模型正在判断是否需要调用 Docker 工具')
const approveActions = ref(false)
const dryRun = ref(false)
const sessionId = ref(Math.random().toString(36).slice(2))
const messagesSurface = ref<InstanceType<typeof MotionSurface> | null>(null)
const currentReport = ref<DiagnosisReport | null>(null)
const loadingReportId = ref<string | null>(null)
const resumeNotice = ref<string | null>(null)
const activeToolName = ref('')
const activeToolStatus = ref('')
const toolProgressSteps = ['context', 'model', 'tool', 'summary']
let loadingStageTimer: number | undefined
let typingTimer: number | undefined

async function sendMessage() {
  if (loading.value || typing.value || !inputMessage.value.trim()) return

  const userMsg: Message = {
    id: Date.now().toString(),
    role: 'user',
    content: inputMessage.value.trim(),
  }
  messages.value.push(userMsg)
  const userInput = inputMessage.value.trim()
  inputMessage.value = ''

  loading.value = true
  startLoadingStages()
  await nextTick()
  scrollToBottom()

  try {
    // 短期上下文长度与后端最大窗口保持一致。
    const history: ChatMessage[] = messages.value.slice(0, -1).slice(-60).map(m => ({
      role: m.role,
      content: m.content,
    }))

    const response: ChatResponse = await sendChatStream(
      {
        message: userInput,
        session_id: sessionId.value,
        history,
        approve_actions: approveActions.value,
        dry_run: dryRun.value,
      },
      handleChatStreamEvent,
    )
    sessionId.value = response.session_id

    const assistantMsg: Message = {
      id: Date.now().toString() + '-assistant',
      role: 'assistant',
      content: '',
      tool_calls: response.tool_calls,
      agent_trace: response.agent_trace,
      pending_actions: response.pending_actions,
      incident_id: response.incident_id,
      typing: true,
    }
    messages.value.push(assistantMsg)
    typing.value = true
    loading.value = false
    activeToolName.value = ''
    activeToolStatus.value = ''
    loadingHint.value = '模型正在判断是否需要调用 Docker 工具'
    stopLoadingStages()
    await typeAssistantMessage(assistantMsg.id, response.answer)
  } catch (err: any) {
    const errorMsg: Message = {
      id: Date.now().toString() + '-error',
      role: 'assistant',
      content: `❌ 请求失败：${err.response?.data?.detail || err.message}`,
    }
    messages.value.push(errorMsg)
  } finally {
    typing.value = false
    loading.value = false
    activeToolName.value = ''
    activeToolStatus.value = ''
    loadingHint.value = '模型正在判断是否需要调用 Docker 工具'
    stopLoadingStages()
    await nextTick()
    scrollToBottom()
  }
}

function handleChatStreamEvent(event: ChatStreamEvent) {
  if (event.type === 'tool_call_start') {
    loadingStage.value = '正在调用工具'
    activeToolName.value = event.tool_name
    activeToolStatus.value = '运行中'
    loadingHint.value = `正在调用 ${event.tool_name}`
    return
  }
  if (event.type === 'tool_call_done') {
    loadingStage.value = '工具调用完成'
    activeToolName.value = event.tool_name
    activeToolStatus.value = statusLabel(event.status)
    loadingHint.value = event.summary ? `${event.tool_name}：${event.summary}` : `工具 ${event.tool_name} 已完成`
    return
  }
}

function statusLabel(status: string): string {
  return {
    success: '完成',
    error: '失败',
    approval_required: '待确认',
    skipped: '已跳过',
  }[status] || status
}

function startLoadingStages() {
  const stages = ['准备上下文', '请求模型判断', '等待工具调用', '整理诊断结果']
  let index = 0
  loadingStage.value = stages[index]
  window.clearInterval(loadingStageTimer)
  // 这是感知进度提示，真正的完成状态由请求 Promise 控制。
  loadingStageTimer = window.setInterval(() => {
    if (activeToolName.value) return
    index = Math.min(index + 1, stages.length - 1)
    loadingStage.value = stages[index]
  }, 1800)
}

function stopLoadingStages() {
  window.clearInterval(loadingStageTimer)
  loadingStageTimer = undefined
  loadingStage.value = '准备上下文'
}

async function typeAssistantMessage(messageId: string, fullText: string) {
  window.clearInterval(typingTimer)
  updateMessage(messageId, { content: '' })
  const chunks = splitTypeChunks(fullText)
  const delay = 16
  let visibleText = ''

  try {
    for (const chunk of chunks) {
      visibleText += chunk
      updateMessage(messageId, { content: visibleText })
      await nextTick()
      scrollToBottom()
      await wait(delay)
    }
  } finally {
    updateMessage(messageId, { typing: false })
  }
}

function updateMessage(messageId: string, patch: Partial<Message>) {
  const index = messages.value.findIndex((item) => item.id === messageId)
  if (index < 0) return
  messages.value[index] = { ...messages.value[index], ...patch }
}

function splitTypeChunks(text: string): string[] {
  const chunks: string[] = []
  const normalized = text.replace(/\r\n/g, '\n')
  let buffer = ''
  for (const char of normalized) {
    buffer += char
    if (buffer.length >= 4 || /[\s，。！？；：\n]/.test(char)) {
      chunks.push(buffer)
      buffer = ''
    }
  }
  if (buffer) chunks.push(buffer)
  return chunks.length ? chunks : [text]
}

function wait(ms: number): Promise<void> {
  return new Promise((resolve) => {
    typingTimer = window.setTimeout(resolve, ms)
  })
}

function traceIcon(step: AgentTraceStep): string {
  if (step.type === 'analysis') return 'psychology'
  if (step.type === 'summary') return 'task_alt'
  if (step.status === 'approval_required') return 'approval'
  if (step.status === 'error') return 'error'
  if (step.status === 'skipped') return 'skip_next'
  return 'terminal'
}

function formatTraceArguments(args: Record<string, unknown> | undefined): string {
  if (!args || !Object.keys(args).length) return ''
  try {
    const text = JSON.stringify(args)
    return text.length > 180 ? `${text.slice(0, 177)}...` : text
  } catch {
    return ''
  }
}

async function viewReport(incidentId: string) {
  loadingReportId.value = incidentId
  try {
    currentReport.value = await generateReport(incidentId)
  } catch (err: any) {
    alert(`报告生成失败：${err.response?.data?.detail || err.message}`)
  } finally {
    loadingReportId.value = null
  }
}

function scrollToBottom() {
  const target = messagesSurface.value?.rootElement
  if (target) {
    target.scrollTop = target.scrollHeight
  }
}

function restoreResumeContext(): boolean {
  const payload = takeChatResume()
  if (!payload) return false

  // 历史页把续聊数据放进 sessionStorage，ChatView 只消费一次。
  sessionId.value = payload.session_id
  messages.value = payload.history.map((item, index) => ({
    id: `resume-${payload.source_incident_id || payload.session_id}-${index}`,
    role: item.role,
    content: item.content,
  }))
  resumeNotice.value = `已载入 ${payload.history.length} 条历史上下文，可以继续追问。`
  return true
}

onMounted(async () => {
  const resumed = restoreResumeContext()
  if (resumed) {
    await nextTick()
    scrollToBottom()
    return
  }

  messages.value.push({
    id: 'welcome',
    role: 'assistant',
    content: '你好！我是 lightpanel，可以帮助你诊断 Docker 容器和系统运维问题。请描述遇到的情况。',
  })
})

onBeforeUnmount(stopLoadingStages)
onBeforeUnmount(() => window.clearTimeout(typingTimer))
</script>

<style scoped>
.chat-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  gap: 16px;
}

.chat-header {
  padding: 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.chat-title {
  margin: 0;
  font-size: 30px;
  font-weight: 700;
  color: var(--md-sys-color-on-surface);
}
.chat-controls {
  display: flex;
  gap: 20px;
}
.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 0;
}

.message-wrapper {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.message-wrapper.user {
  align-items: flex-end;
}
.message-wrapper.assistant {
  align-items: flex-start;
}

.message-bubble {
  max-width: min(760px, 78%);
  padding: 14px 16px;
  border-radius: 24px;
  line-height: 1.6;
}
.user .message-bubble {
  background: var(--md-sys-color-primary);
  color: var(--md-sys-color-on-primary);
  border-bottom-right-radius: 8px;
}
.assistant .message-bubble {
  background: var(--md-sys-color-surface-container-low);
  color: var(--md-sys-color-on-surface);
  border-bottom-left-radius: 8px;
}

.message-content {
  font-size: 15px;
}

.message-content :deep(.inline-code) {
  padding: 2px 6px;
  border-radius: 6px;
  background: var(--md-sys-color-surface-container);
  font-family: var(--font-mono);
  font-size: 0.9em;
}

.message-content :deep(.inline-link) {
  color: var(--md-sys-color-primary);
  text-decoration: underline;
}

.agent-trace {
  margin-top: 16px;
  padding: 14px;
  border: 1px solid color-mix(in srgb, var(--md-sys-color-primary) 18%, var(--md-sys-color-outline-variant));
  border-radius: 18px;
  background:
    linear-gradient(135deg, color-mix(in srgb, var(--md-sys-color-primary) 7%, transparent), transparent 46%),
    var(--md-sys-color-surface);
}

.agent-trace-header {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  margin-bottom: 12px;
  color: var(--md-sys-color-primary);
  font-size: 13px;
  font-weight: 700;
}

.agent-trace-header .material-symbol {
  font-size: 17px;
}

.agent-trace-item {
  position: relative;
  display: grid;
  grid-template-columns: 28px minmax(0, 1fr);
  gap: 10px;
  padding: 0 0 14px;
  animation: tool-card-in 0.28s var(--ease-standard) both;
}

.agent-trace-item:last-child {
  padding-bottom: 0;
}

.trace-rail {
  position: absolute;
  left: 13px;
  top: 28px;
  bottom: -2px;
  width: 2px;
  border-radius: 999px;
  background: var(--md-sys-color-outline-variant);
}

.agent-trace-item:last-child .trace-rail {
  display: none;
}

.trace-icon {
  position: relative;
  z-index: 1;
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--md-sys-color-primary-container);
  color: var(--md-sys-color-primary);
  font-size: 16px;
}

.agent-trace-item.error .trace-icon {
  background: rgba(200, 66, 50, 0.14);
  color: #8f2e24;
}

.agent-trace-item.approval_required .trace-icon {
  background: rgba(201, 131, 24, 0.16);
  color: #7a4d0c;
}

.trace-body {
  min-width: 0;
  padding: 2px 0;
}

.trace-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-width: 0;
}

.trace-title-row strong {
  min-width: 0;
  overflow: hidden;
  color: var(--md-sys-color-on-surface);
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.trace-body p {
  margin: 3px 0 0;
  color: var(--md-sys-color-on-surface-variant);
  font-size: 12px;
  line-height: 1.55;
}

.trace-status {
  flex: 0 0 auto;
  padding: 2px 7px;
  border-radius: 999px;
  background: var(--md-sys-color-surface-container);
  color: var(--md-sys-color-on-surface-variant);
  font-size: 10px;
  font-weight: 800;
  text-transform: uppercase;
}

.trace-status.success { background: rgba(31, 157, 112, 0.14); color: #0f6f4d; }
.trace-status.error { background: rgba(200, 66, 50, 0.14); color: #8f2e24; }
.trace-status.approval_required { background: rgba(201, 131, 24, 0.16); color: #7a4d0c; }
.trace-status.skipped { background: rgba(44, 108, 157, 0.14); color: #214f72; }

.trace-tool {
  display: inline-flex;
  margin-top: 8px;
  padding: 2px 7px;
  border-radius: 7px;
  background: var(--md-sys-color-surface-container);
  color: var(--md-sys-color-primary);
  font-family: var(--font-mono);
  font-size: 11px;
}

.trace-args {
  margin-top: 7px;
  padding: 7px 9px;
  border-radius: 10px;
  background: var(--md-sys-color-surface-container-low);
  color: var(--md-sys-color-on-surface-variant);
  font-family: var(--font-mono);
  font-size: 11px;
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.tool-calls {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--md-sys-color-outline-variant);
}
.tool-calls-header {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  font-size: 13px;
  font-weight: 600;
  color: var(--md-sys-color-on-surface-variant);
  margin-bottom: 12px;
}

.tool-calls-header .material-symbol,
.pending-header .material-symbol {
  font-size: 16px;
}
.tool-call-item {
  background: var(--md-sys-color-surface);
  padding: 10px 12px;
  border-radius: 14px;
  margin-bottom: 8px;
  font-size: 13px;
  animation: tool-card-in 0.3s var(--ease-standard) both;
}

.tool-call-item:nth-child(2) {
  animation-delay: 40ms;
}

.tool-call-item:nth-child(3) {
  animation-delay: 80ms;
}

.tool-call-item:nth-child(4) {
  animation-delay: 120ms;
}
.tool-call-name {
  font-weight: 600;
  color: var(--md-sys-color-primary);
  font-family: var(--font-mono);
  margin-bottom: 4px;
}
.tool-call-status {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  margin-bottom: 6px;
}
.tool-call-status.success { background: rgba(31, 157, 112, 0.14); color: #0f6f4d; }
.tool-call-status.error { background: rgba(200, 66, 50, 0.14); color: #8f2e24; }
.tool-call-status.approval_required { background: rgba(201, 131, 24, 0.16); color: #7a4d0c; }
.tool-call-status.skipped { background: rgba(44, 108, 157, 0.14); color: #214f72; }
.tool-call-summary {
  color: var(--md-sys-color-on-surface-variant);
}

.pending-actions {
  margin-top: 16px;
  padding: 12px;
  background: var(--state-warning-container);
  border-radius: 16px;
}
.pending-header {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  font-size: 13px;
  font-weight: 600;
  color: #92400e;
  margin-bottom: 8px;
}
.pending-item {
  margin-bottom: 8px;
}
.pending-tool {
  font-weight: 600;
  font-family: var(--font-mono);
  font-size: 13px;
  color: #78350f;
}
.pending-reason {
  font-size: 12px;
  color: #92400e;
}
.pending-tip {
  margin-top: 8px;
  font-size: 12px;
  color: #92400e;
  font-style: italic;
}

.message-actions {
  display: flex;
  gap: 8px;
  padding-left: 20px;
}
.btn-action {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 6px 12px;
  background: var(--md-sys-color-surface);
  border: 1px solid var(--md-sys-color-outline-variant);
  border-radius: 18px;
  font-size: 13px;
  color: var(--md-sys-color-primary);
  cursor: pointer;
  transition: all 0.22s ease;
}
.btn-action:hover:not(:disabled) {
  background: var(--md-sys-color-primary-container);
  border-color: var(--md-sys-color-primary);
}
.btn-action:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-action .material-symbol {
  font-size: 16px;
}

.btn-action:disabled .material-symbol {
  animation: spin 0.9s linear infinite;
}

.loading-indicator {
  display: block;
  padding: 16px;
  background: var(--md-sys-color-surface-container-low);
  border-radius: 20px;
  align-self: flex-start;
  color: var(--md-sys-color-on-surface-variant);
}

.tool-progress {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: min(360px, 70vw);
}

.tool-progress-orb {
  position: relative;
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: var(--md-sys-color-primary-container);
  color: var(--md-sys-color-primary);
}

.tool-progress-orb::before {
  content: '';
  position: absolute;
  inset: -5px;
  border: 2px solid color-mix(in srgb, var(--md-sys-color-primary) 24%, transparent);
  border-top-color: var(--md-sys-color-primary);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

.tool-progress-body {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.tool-progress-body strong {
  color: var(--md-sys-color-on-surface);
  font-size: 14px;
}

.tool-progress-body span {
  color: var(--md-sys-color-on-surface-variant);
  font-size: 12px;
}

.active-tool-chip {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  width: fit-content;
  max-width: min(420px, 64vw);
  margin-top: 8px;
  padding: 6px 10px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--md-sys-color-primary) 12%, var(--md-sys-color-surface));
  color: var(--md-sys-color-primary);
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 700;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.active-tool-chip .material-symbol {
  flex: 0 0 auto;
  font-size: 16px;
}

.active-tool-chip small {
  flex: 0 0 auto;
  color: var(--md-sys-color-on-surface-variant);
  font-family: inherit;
  font-size: 11px;
  font-weight: 700;
}

.tool-progress-track {
  display: flex;
  gap: 5px;
  margin-top: 5px;
}

.tool-progress-dot {
  width: 28px;
  height: 4px;
  border-radius: 999px;
  background: var(--md-sys-color-outline-variant);
  animation: tool-step 1.6s ease-in-out infinite;
}

.tool-progress-dot:nth-child(2) {
  animation-delay: 0.18s;
}

.tool-progress-dot:nth-child(3) {
  animation-delay: 0.36s;
}

.tool-progress-dot:nth-child(4) {
  animation-delay: 0.54s;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}

@keyframes tool-step {
  0%,
  100% {
    background: var(--md-sys-color-outline-variant);
    transform: scaleX(0.72);
  }
  45% {
    background: var(--md-sys-color-primary);
    transform: scaleX(1);
  }
}

@keyframes tool-card-in {
  from {
    opacity: 0;
    transform: translateY(8px) scale(0.98);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.input-area {
  padding: 14px;
  display: flex;
  gap: 12px;
  align-items: flex-end;
}
.input-area textarea {
  flex: 1;
}
.btn-send {
  min-width: 112px;
  padding: 12px 20px;
  background: var(--md-sys-color-primary);
  color: var(--md-sys-color-on-primary);
  border-radius: 22px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.22s var(--ease-standard);
}
.btn-send:hover:not(:disabled) {
  box-shadow: var(--md-elevation-1);
}
.btn-send:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

</style>
