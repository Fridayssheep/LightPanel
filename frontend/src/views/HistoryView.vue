<template>
  <div class="history-view page-shell">
    <div class="history-header">
      <div>
        <p class="eyebrow">历史对话</p>
        <h1 class="history-title">历史诊断记录</h1>
      </div>
      <button @click="loadIncidents" class="toolbar-button" :disabled="loading">
        {{ loading ? '加载中' : '刷新' }}
      </button>
    </div>

    <NoticeBanner v-if="notice" :ok="notice.ok" :message="notice.message" />

    <BatchToolbar
      :selected-count="historySelection.selectedCount.value"
      :total-count="incidents.length"
      :all-selected="allIncidentsSelected"
      :disabled="batchBusy"
      @toggle-all="historySelection.toggleAll(selectableIncidentIds)"
      @clear="historySelection.clear"
    >
      <button class="incident-action danger batch-delete" type="button" :disabled="!canDeleteSelectedIncidents" @click="handleBatchDeleteIncidents">
        <span class="material-symbol">delete</span>
        删除历史
      </button>
    </BatchToolbar>

    <div class="history-body">
      <div v-if="loading && !incidents.length" class="empty-state">加载中...</div>
      <div v-else-if="!incidents.length" class="empty-state">暂无诊断记录</div>
      <TransitionGroup v-else name="msg-rise" tag="div" class="incident-list">
        <MotionSurface
          v-for="(incident, idx) in incidents"
          :key="incident.incident_id"
          as="article"
          class="incident-card"
          :class="{ selected: historySelection.isSelected(incident.incident_id) }"
          :delay="Math.min(idx, 8) * 30"
        >
          <label class="selection-cell control-item" title="选择历史记录">
            <input
              type="checkbox"
              :checked="historySelection.isSelected(incident.incident_id)"
              :disabled="batchBusy"
              aria-label="选择历史记录"
              @change="historySelection.toggle(incident.incident_id, ($event.target as HTMLInputElement).checked)"
              @click.stop
            />
          </label>
          <div class="incident-main">
            <div class="incident-question">{{ incident.user_message }}</div>
            <div class="incident-answer">{{ truncateText(incident.answer, 160) }}</div>
            <div class="incident-meta">
              <span class="meta-time">{{ formatShortDateTime(incident.created_at) }}</span>
              <span v-if="incidentToolCalls(incident).length" class="meta-tools">
                <span class="material-symbol">construction</span>
                {{ incidentToolCalls(incident).length }} 个工具
              </span>
            </div>
          </div>
          <div class="incident-actions">
            <button
              class="incident-action primary"
              type="button"
              :disabled="isContinuing(incident.incident_id)"
              title="带着这条历史上下文继续对话"
              @click="resumeChat(incident.incident_id)"
            >
              <span class="material-symbol" :class="{ spinning: isContinuing(incident.incident_id) }">
                {{ isContinuing(incident.incident_id) ? 'progress_activity' : 'forum' }}
              </span>
              {{ isContinuing(incident.incident_id) ? '载入中' : '继续' }}
            </button>
            <button
              class="incident-action"
              type="button"
              :disabled="loadingReportId === incident.incident_id"
              title="生成诊断报告"
              @click="viewReport(incident.incident_id)"
            >
              <span class="material-symbol" :class="{ spinning: loadingReportId === incident.incident_id }">
                {{ loadingReportId === incident.incident_id ? 'progress_activity' : 'analytics' }}
              </span>
              {{ loadingReportId === incident.incident_id ? '生成中' : '报告' }}
            </button>
            <button
              class="incident-action danger"
              type="button"
              :disabled="isDeleting(incident.incident_id)"
              title="删除这条历史记录"
              @click="removeIncident(incident)"
            >
              <span class="material-symbol" :class="{ spinning: isDeleting(incident.incident_id) }">
                {{ isDeleting(incident.incident_id) ? 'progress_activity' : 'delete' }}
              </span>
            </button>
          </div>
        </MotionSurface>
      </TransitionGroup>
    </div>

    <DiagnosisReportModal :report="currentReport" @close="currentReport = null" />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { listIncidents, generateReport, continueIncident, deleteIncident } from '../api'
import type { IncidentRecord, DiagnosisReport } from '../api/types'
import BatchToolbar from '../components/BatchToolbar.vue'
import DiagnosisReportModal from '../components/DiagnosisReportModal.vue'
import MotionSurface from '../components/MotionSurface.vue'
import NoticeBanner from '../components/NoticeBanner.vue'
import { batchNotice, runBatchOperation, useBatchSelection } from '../utils/batch'
import { saveChatResume } from '../utils/chatResume'
import { requestConfirm } from '../utils/confirmDialog'
import { formatShortDateTime, truncateText } from '../utils/text'

const router = useRouter()
const incidents = ref<IncidentRecord[]>([])
const loading = ref(false)
const currentReport = ref<DiagnosisReport | null>(null)
const loadingReportId = ref<string | null>(null)
const continuingIncidentId = ref<string | null>(null)
const deletingIncidentId = ref<string | null>(null)
const batchBusy = ref(false)
const notice = ref<{ ok: boolean; message: string } | null>(null)
const historySelection = useBatchSelection<string>()

const selectableIncidentIds = computed(() => incidents.value.map((incident) => incident.incident_id))
const selectedIncidents = computed(() => incidents.value.filter((incident) => historySelection.isSelected(incident.incident_id)))
const allIncidentsSelected = computed(() => historySelection.areAllSelected(selectableIncidentIds.value))
const canDeleteSelectedIncidents = computed(() => !batchBusy.value && selectedIncidents.value.length > 0)

function incidentToolCalls(incident: IncidentRecord): IncidentRecord['tool_calls'] {
  return incident.tool_calls ?? []
}

function isContinuing(incidentId: string): boolean {
  return continuingIncidentId.value === incidentId
}

function isDeleting(incidentId: string): boolean {
  return deletingIncidentId.value === incidentId || batchBusy.value
}

async function loadIncidents() {
  loading.value = true
  try {
    incidents.value = await listIncidents(100)
    historySelection.sync(incidents.value.map((incident) => incident.incident_id))
  } catch (err) {
    console.error('Failed to load incidents:', err)
    notice.value = { ok: false, message: '历史记录加载失败。' }
  } finally {
    loading.value = false
  }
}

async function resumeChat(incidentId: string) {
  continuingIncidentId.value = incidentId
  notice.value = null
  try {
    const payload = await continueIncident(incidentId)
    saveChatResume(payload)
    await router.push('/chat')
  } catch (err: any) {
    notice.value = { ok: false, message: `继续对话失败：${err.response?.data?.detail || err.message}` }
  } finally {
    continuingIncidentId.value = null
  }
}

async function removeIncident(incident: IncidentRecord) {
  const confirmed = await requestConfirm({
    title: '删除历史记录',
    message: '确认删除这条历史记录？',
    detail: truncateText(incident.user_message, 80),
    confirmText: '删除',
    intent: 'danger',
    icon: 'delete',
  })
  if (!confirmed) return

  deletingIncidentId.value = incident.incident_id
  notice.value = null
  try {
    const result = await deleteIncident(incident.incident_id)
    if (result.ok) {
      incidents.value = incidents.value.filter((item) => item.incident_id !== incident.incident_id)
    }
    notice.value = { ok: result.ok, message: result.message || '历史记录已删除。' }
  } catch (err: any) {
    notice.value = { ok: false, message: `删除失败：${err.response?.data?.detail || err.message}` }
  } finally {
    deletingIncidentId.value = null
  }
}

async function handleBatchDeleteIncidents() {
  const targets = selectedIncidents.value
  if (!targets.length) return
  const confirmed = await requestConfirm({
    title: '批量删除历史记录',
    message: `确认删除选中的 ${targets.length} 条历史记录？`,
    confirmText: '批量删除',
    intent: 'danger',
    icon: 'delete',
  })
  if (!confirmed) return

  batchBusy.value = true
  notice.value = null
  try {
    const outcome = await runBatchOperation(
      targets,
      (incident) => deleteIncident(incident.incident_id),
      (incident) => truncateText(incident.user_message, 48),
    )
    const result = batchNotice('历史记录', '删除', outcome)
    if (outcome.succeeded > 0) {
      const deleted = new Set(targets.map((incident) => incident.incident_id))
      incidents.value = incidents.value.filter((incident) => !deleted.has(incident.incident_id))
    }
    historySelection.clear()
    notice.value = { ok: result.ok, message: result.message }
  } catch (err: any) {
    notice.value = { ok: false, message: `批量删除失败：${err.response?.data?.detail || err.message}` }
  } finally {
    batchBusy.value = false
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

onMounted(loadIncidents)
</script>

<style scoped>
.history-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  gap: 16px;
}

.history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.history-title {
  margin: 0;
  font-size: 30px;
  font-weight: 700;
  color: var(--md-sys-color-on-surface);
}

.history-body {
  flex: 1;
  overflow-y: auto;
}

.incident-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.incident-card {
  padding: 20px 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}

.incident-card.selected {
  border-color: color-mix(in srgb, var(--md-sys-color-primary) 34%, var(--md-sys-color-outline-variant));
  background: color-mix(in srgb, var(--md-sys-color-primary-container) 42%, var(--md-sys-color-surface));
}

.selection-cell {
  display: inline-flex;
  flex: 0 0 auto;
}
.incident-main {
  flex: 1;
  min-width: 0;
}
.incident-question {
  font-size: 16px;
  font-weight: 600;
  color: var(--md-sys-color-on-surface);
  margin-bottom: 8px;
}
.incident-answer {
  font-size: 14px;
  color: var(--md-sys-color-on-surface-variant);
  line-height: 1.6;
  margin-bottom: 12px;
}
.incident-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  align-items: center;
  font-size: 12px;
  color: var(--text-faint);
}

.meta-tools {
  display: inline-flex;
  gap: 5px;
  align-items: center;
}

.meta-tools .material-symbol {
  font-size: 15px;
}

.incident-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
  flex-shrink: 0;
}

.incident-action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  min-height: 38px;
  padding: 8px 16px;
  border: 1px solid var(--md-sys-color-outline-variant);
  border-radius: 20px;
  background: var(--md-sys-color-surface-container-low);
  color: var(--md-sys-color-on-surface-variant);
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.22s var(--ease-standard);
}

.incident-action:hover:not(:disabled) {
  box-shadow: var(--md-elevation-1);
  transform: translateY(-1px);
}

.incident-action.primary {
  border-color: transparent;
  background: var(--md-sys-color-primary);
  color: var(--md-sys-color-on-primary);
}

.incident-action.danger {
  width: 38px;
  padding: 0;
  color: var(--md-sys-color-error);
}

.incident-action.batch-delete {
  width: auto;
  min-height: 34px;
  padding: 0 12px;
  border-radius: 17px;
}

.incident-action.danger:hover:not(:disabled) {
  border-color: var(--md-sys-color-error);
  background: var(--md-sys-color-error-container);
}

.incident-action:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.incident-action .material-symbol {
  font-size: 16px;
}

.spinning {
  animation: spin 0.9s linear infinite;
}

@media (max-width: 760px) {
  .incident-card {
    align-items: stretch;
    flex-direction: column;
  }

  .incident-actions {
    justify-content: flex-start;
  }
}
</style>
