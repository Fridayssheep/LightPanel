<template>
  <section class="page-shell resource-view">
    <header class="page-header">
      <div>
        <p class="eyebrow">Docker 卷管理</p>
        <h1 class="page-title">卷管理</h1>
        <p class="page-subtitle">查看卷占用、挂载路径和完整 inspect 信息。</p>
      </div>
      <div class="header-actions">
        <button class="secondary-button" type="button" :disabled="batchBusy" @click="openCreateDialog">
          <span class="material-symbol">add_circle</span>
          新建卷
        </button>
        <button class="toolbar-button" type="button" :disabled="loading" @click="loadVolumes">
          <span class="material-symbol" :class="{ spinning: loading }">{{ loading ? 'progress_activity' : 'refresh' }}</span>
          {{ loading ? '刷新中' : '刷新' }}
        </button>
      </div>
    </header>

    <NoticeBanner v-if="notice" :ok="notice.ok" :message="notice.message" />
    <div v-if="response?.error" class="error-banner">Docker 连接异常：{{ response.error }}</div>

    <div class="resource-workbench">
      <MotionSurface class="resource-list-card" :interactive="false" :delay="35">
        <div class="list-summary">
          <span class="summary-count">总计 {{ volumes.length }} 个卷</span>
          <button class="secondary-button danger compact" type="button" :disabled="pruning || batchBusy" @click="handlePruneVolumes">
            <span class="material-symbol" :class="{ spinning: pruning }">{{ pruning ? 'progress_activity' : 'delete_sweep' }}</span>
            清理未使用
          </button>
        </div>

        <BatchToolbar
          :selected-count="volumeSelection.selectedCount.value"
          :total-count="volumes.length"
          :all-selected="allVolumesSelected"
          :disabled="batchBusy"
          @toggle-all="volumeSelection.toggleAll(selectableVolumeNames)"
          @clear="volumeSelection.clear"
        >
          <button class="secondary-button danger compact" type="button" :disabled="!canRemoveSelectedVolumes" @click="handleBatchRemoveVolumes">
            <span class="material-symbol">delete</span>
            删除卷
          </button>
        </BatchToolbar>

        <div v-if="!volumes.length" class="empty-state">没有可显示的卷</div>
        <div v-else class="resource-table">
          <div class="table-head">
            <span></span>
            <span>名称</span>
            <span>驱动</span>
            <span>挂载点</span>
            <span>使用容器</span>
            <span>操作</span>
          </div>
          <article
            v-for="(volume, index) in volumes"
            :key="volume.name"
            class="resource-row motion-item"
            :class="{ expanded: expandedVolume === volume.name }"
            :style="{ '--motion-delay': `${Math.min(index, 12) * 28}ms` }"
          >
            <div class="table-row-main">
              <label class="selection-cell control-item" title="选择卷">
                <input
                  type="checkbox"
                  :checked="volumeSelection.isSelected(volume.name)"
                  :disabled="batchBusy"
                  aria-label="选择卷"
                  @change="volumeSelection.toggle(volume.name, ($event.target as HTMLInputElement).checked)"
                  @click.stop
                />
              </label>
              <div>
                <strong>{{ volume.name }}</strong>
              </div>
              <span class="mono">{{ volume.driver || 'local' }}</span>
              <span class="mono path-cell">{{ volume.mountpoint || '-' }}</span>
              <span class="status-pill" :class="{ running: volume.containers.length > 0 }">
                <span class="status-dot"></span>
                {{ volume.containers.length }} 个容器
              </span>
              <div class="row-actions">
                <button class="icon-action" type="button" title="详情" @click="toggleDetail(volume.name)">
                  <span class="material-symbol">info</span>
                </button>
                <button
                  class="icon-action danger"
                  type="button"
                  title="删除卷"
                  :disabled="busyVolume === volume.name || batchBusy"
                  @click="handleRemoveVolume(volume.name)"
                >
                  <span class="material-symbol" :class="{ spinning: busyVolume === volume.name }">
                    {{ busyVolume === volume.name ? 'progress_activity' : 'delete' }}
                  </span>
                </button>
              </div>
            </div>

            <div class="expand-collapse" :class="{ open: expandedVolume === volume.name }">
              <div class="expand-inner">
                <DetailPanel
                  v-if="renderedVolume === volume.name"
                  :tabs="detailTabs"
                  v-model="activeTab"
                  :loading="detailLoading"
                  :error="detail?.error"
                  loading-text="卷详情读取中"
                  aria-label="卷详情面板"
                  tabs-label="Volume detail tabs"
                  @close="closeDetail"
                >
                  <template v-if="activeTab === 'detail'">
                    <HighlightedText :content="detailJson" mode="json" empty-text="暂无详情" />
                  </template>
                  <template v-else>
                    <div v-if="activeContainers.length" class="container-chip-list">
                      <span v-for="container in activeContainers" :key="container" class="status-pill running">
                        <span class="status-dot"></span>
                        {{ container }}
                      </span>
                    </div>
                    <div v-else class="empty-state compact">当前没有容器使用这个卷</div>
                  </template>
                </DetailPanel>
              </div>
            </div>
          </article>
        </div>
      </MotionSurface>
    </div>

    <Teleport to="body">
      <Transition name="dialog-fade">
        <div v-if="createDialogOpen" class="resource-dialog-backdrop" role="presentation" @click.self="closeCreateDialog">
          <section class="resource-dialog" role="dialog" aria-modal="true" aria-labelledby="volume-create-title">
            <header class="dialog-header">
              <div>
                <p class="eyebrow">Docker volume</p>
                <h2 id="volume-create-title">新建卷</h2>
              </div>
              <button class="icon-button" type="button" title="关闭" :disabled="creating" @click="closeCreateDialog">
                <span class="material-symbol">close</span>
              </button>
            </header>

            <form class="dialog-body" @submit.prevent="handleCreateVolume">
              <div class="form-grid">
                <label class="field-row">
                  <span>名称</span>
                  <input v-model.trim="createForm.name" class="themed-input" placeholder="ops-data" autocomplete="off" />
                </label>
                <label class="field-row">
                  <span>驱动</span>
                  <input v-model.trim="createForm.driver" class="themed-input" placeholder="local" autocomplete="off" />
                </label>
              </div>
            </form>

            <footer class="dialog-footer">
              <button class="secondary-button" type="button" :disabled="creating" @click="closeCreateDialog">取消</button>
              <button class="primary-button" type="button" :disabled="creating || !createForm.name" @click="handleCreateVolume">
                <span class="material-symbol" :class="{ spinning: creating }">{{ creating ? 'progress_activity' : 'add' }}</span>
                创建卷
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
import { createVolume, getVolumeDetail, listVolumes, runVolumeAction } from '../api'
import type { OperationResponse, VolumeCreateRequest, VolumeDetailResponse, VolumeListResponse } from '../api/types'
import BatchToolbar from '../components/BatchToolbar.vue'
import DetailPanel from '../components/DetailPanel.vue'
import HighlightedText from '../components/HighlightedText.vue'
import MotionSurface from '../components/MotionSurface.vue'
import NoticeBanner from '../components/NoticeBanner.vue'
import type { TabItem } from '../components/types'
import { batchNotice, runBatchOperation, useBatchSelection } from '../utils/batch'
import { requestConfirm } from '../utils/confirmDialog'

const detailTabs: TabItem[] = [
  { key: 'detail', label: 'Inspect', icon: 'data_object' },
  { key: 'containers', label: '使用容器', icon: 'deployed_code' },
]

const response = ref<VolumeListResponse | null>(null)
const detail = ref<VolumeDetailResponse | null>(null)
const loading = ref(false)
const creating = ref(false)
const pruning = ref(false)
const detailLoading = ref(false)
const busyVolume = ref<string | null>(null)
const batchBusy = ref(false)
const notice = ref<OperationResponse | null>(null)
const createDialogOpen = ref(false)
const expandedVolume = ref<string | null>(null)
const renderedVolume = ref<string | null>(null)
const activeTab = ref<'detail' | 'containers'>('detail')
let collapseTimer: ReturnType<typeof setTimeout> | null = null
const volumeSelection = useBatchSelection<string>()

const createForm = ref<VolumeCreateRequest>({
  name: '',
  driver: 'local',
  labels: {},
})

const volumes = computed(() => response.value?.volumes ?? [])
const selectableVolumeNames = computed(() => volumes.value.map((volume) => volume.name))
const selectedVolumes = computed(() => volumes.value.filter((volume) => volumeSelection.isSelected(volume.name)))
const allVolumesSelected = computed(() => volumeSelection.areAllSelected(selectableVolumeNames.value))
const canRemoveSelectedVolumes = computed(() => !batchBusy.value && selectedVolumes.value.length > 0)
const detailJson = computed(() => JSON.stringify(detail.value?.detail ?? {}, null, 2))
const activeContainers = computed(() => detail.value?.containers ?? [])

function resetCreateForm() {
  createForm.value = {
    name: '',
    driver: 'local',
    labels: {},
  }
}

function openCreateDialog() {
  resetCreateForm()
  createDialogOpen.value = true
}

function closeCreateDialog() {
  if (creating.value) return
  createDialogOpen.value = false
}

async function loadVolumes() {
  loading.value = true
  try {
    response.value = await listVolumes()
    volumeSelection.sync((response.value.volumes ?? []).map((volume) => volume.name))
  } catch (err) {
    notice.value = { ok: false, message: '读取卷列表失败。', data: {}, error: String(err), timestamp: new Date().toISOString() }
  } finally {
    loading.value = false
  }
}

async function handleCreateVolume() {
  creating.value = true
  notice.value = null
  try {
    notice.value = await createVolume({ ...createForm.value, driver: createForm.value.driver || 'local' })
    if (notice.value.ok) {
      createDialogOpen.value = false
      await loadVolumes()
    }
  } catch (err) {
    notice.value = { ok: false, message: '创建卷请求失败。', data: {}, error: String(err), timestamp: new Date().toISOString() }
  } finally {
    creating.value = false
  }
}

async function toggleDetail(name: string) {
  if (expandedVolume.value === name && activeTab.value === 'detail') {
    closeDetail()
    return
  }
  if (collapseTimer) clearTimeout(collapseTimer)
  expandedVolume.value = name
  renderedVolume.value = name
  activeTab.value = 'detail'
  detailLoading.value = true
  try {
    detail.value = await getVolumeDetail(name)
  } catch (err) {
    detail.value = { docker_available: false, name, detail: {}, containers: [], error: String(err), timestamp: new Date().toISOString() }
  } finally {
    detailLoading.value = false
  }
}

function closeDetail() {
  expandedVolume.value = null
  if (collapseTimer) clearTimeout(collapseTimer)
  collapseTimer = setTimeout(() => {
    renderedVolume.value = null
    detail.value = null
  }, 280)
}

async function handleRemoveVolume(name: string) {
  const approve = await requestConfirm({
    title: '删除卷',
    message: `确认删除卷 ${name}？`,
    detail: '如果卷正在被容器使用，Docker 会拒绝删除。',
    confirmText: '删除',
    intent: 'danger',
    icon: 'delete',
  })
  if (!approve) return
  busyVolume.value = name
  try {
    notice.value = await runVolumeAction(name, { action: 'remove', force: false, approve })
    if (notice.value.ok) {
      closeDetail()
      await loadVolumes()
    }
  } catch (err) {
    notice.value = { ok: false, message: '删除卷请求失败。', data: {}, error: String(err), timestamp: new Date().toISOString() }
  } finally {
    busyVolume.value = null
  }
}

async function handleBatchRemoveVolumes() {
  const targets = selectedVolumes.value
  if (!targets.length) return
  const approve = await requestConfirm({
    title: '批量删除卷',
    message: `确认删除选中的 ${targets.length} 个 Docker 卷？`,
    detail: '如果卷正在被容器使用，Docker 会拒绝删除。',
    confirmText: '批量删除',
    intent: 'danger',
    icon: 'delete',
  })
  if (!approve) return

  batchBusy.value = true
  notice.value = null
  try {
    const outcome = await runBatchOperation(
      targets,
      (volume) => runVolumeAction(volume.name, { action: 'remove', force: false, approve }),
      (volume) => volume.name,
    )
    notice.value = batchNotice('卷', '删除', outcome)
    volumeSelection.clear()
    closeDetail()
    await loadVolumes()
  } finally {
    batchBusy.value = false
  }
}

async function handlePruneVolumes() {
  const approve = await requestConfirm({
    title: '清理卷',
    message: '确认清理所有未使用的 Docker 卷？',
    confirmText: '清理',
    intent: 'danger',
    icon: 'delete_sweep',
  })
  if (!approve) return
  pruning.value = true
  try {
    notice.value = await runVolumeAction('_', { action: 'prune', approve })
    await loadVolumes()
  } catch (err) {
    notice.value = { ok: false, message: '清理卷请求失败。', data: {}, error: String(err), timestamp: new Date().toISOString() }
  } finally {
    pruning.value = false
  }
}

onMounted(loadVolumes)
</script>

<style scoped>
.resource-workbench {
  display: grid;
  gap: 18px;
}

.resource-list-card {
  padding: 18px;
}

.header-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: flex-end;
}

.panel-heading,
.list-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.panel-heading h2 {
  margin: 0;
  font-size: 18px;
}

.panel-heading > .material-symbol {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  border-radius: 14px;
  background: var(--md-sys-color-primary-container);
  color: var(--md-sys-color-primary);
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.resource-table {
  display: grid;
}

.table-head,
.table-row-main {
  display: grid;
  grid-template-columns: 30px minmax(180px, 1fr) minmax(90px, 0.5fr) minmax(240px, 1.5fr) minmax(100px, 0.6fr) minmax(110px, auto);
  gap: 12px;
  align-items: center;
}

.selection-cell {
  display: inline-flex;
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

.resource-row {
  border-bottom: 1px solid var(--md-sys-color-outline-variant);
  font-size: 14px;
}

.resource-row.expanded {
  border-radius: 16px;
  background: var(--md-sys-color-surface-container-low);
  border-color: color-mix(in srgb, var(--md-sys-color-primary) 30%, var(--md-sys-color-outline-variant));
  box-shadow: var(--md-elevation-1);
}

.resource-row:last-child {
  border-bottom: none;
}

.table-row-main {
  min-height: 68px;
  padding: 12px;
}

.table-row-main strong {
  display: block;
  min-width: 0;
  overflow-wrap: anywhere;
}

.path-cell {
  display: block;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.row-actions,
.container-chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
}

.container-chip-list {
  justify-content: flex-start;
}

.compact {
  min-height: 34px;
  padding: 0 12px;
  border-radius: 17px;
}

.resource-dialog-backdrop {
  position: fixed;
  inset: 0;
  z-index: 80;
  display: grid;
  place-items: center;
  padding: 28px;
  background: color-mix(in srgb, #101418 42%, transparent);
  backdrop-filter: blur(10px);
}

.resource-dialog {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  width: min(620px, 100%);
  max-height: min(560px, calc(100vh - 56px));
  overflow: hidden;
  border: 1px solid var(--md-sys-color-outline-variant);
  border-radius: 28px;
  background: var(--md-sys-color-surface);
  box-shadow: var(--md-elevation-3);
}

.dialog-header,
.dialog-footer {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 18px 20px;
}

.dialog-header {
  justify-content: space-between;
  border-bottom: 1px solid var(--md-sys-color-outline-variant);
}

.dialog-header h2 {
  margin: 0;
  color: var(--md-sys-color-on-surface);
  font-size: 24px;
  line-height: 1.2;
  font-weight: 800;
}

.dialog-body {
  min-height: 0;
  overflow: auto;
  padding: 20px;
}

.dialog-footer {
  justify-content: flex-end;
  border-top: 1px solid var(--md-sys-color-outline-variant);
  background: var(--md-sys-color-surface-container-lowest);
}

.dialog-fade-enter-active,
.dialog-fade-leave-active {
  transition: opacity 0.2s ease;
}

.dialog-fade-enter-active .resource-dialog,
.dialog-fade-leave-active .resource-dialog {
  transition: opacity 0.22s ease, transform 0.26s var(--ease-standard);
}

.dialog-fade-enter-from,
.dialog-fade-leave-to {
  opacity: 0;
}

.dialog-fade-enter-from .resource-dialog,
.dialog-fade-leave-to .resource-dialog {
  opacity: 0;
  transform: translateY(12px) scale(0.985);
}

@media (max-width: 980px) {
  .form-grid,
  .table-head,
  .table-row-main {
    grid-template-columns: 1fr;
  }

  .table-head {
    display: none;
  }

  .row-actions {
    justify-content: flex-start;
  }

  .header-actions {
    justify-content: flex-start;
  }
}

@media (max-width: 680px) {
  .resource-dialog-backdrop {
    padding: 14px;
  }

  .dialog-footer {
    align-items: stretch;
    flex-direction: column-reverse;
  }

  .dialog-footer > button {
    width: 100%;
  }
}
</style>
