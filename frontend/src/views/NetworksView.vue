<template>
  <section class="page-shell resource-view">
    <header class="page-header">
      <div>
        <p class="eyebrow">Docker 网络管理</p>
        <h1 class="page-title">网络管理</h1>
        <p class="page-subtitle">查看网络详情，创建网络，并连接或断开容器。</p>
      </div>
      <div class="header-actions">
        <button class="secondary-button" type="button" @click="openCreateDialog">
          <span class="material-symbol">add_circle</span>
          新建网络
        </button>
        <button class="toolbar-button" type="button" :disabled="loading" @click="loadNetworks">
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
          <span class="summary-count">总计 {{ networks.length }} 个网络</span>
          <button class="secondary-button danger compact" type="button" :disabled="pruning" @click="handlePruneNetworks">
            <span class="material-symbol" :class="{ spinning: pruning }">{{ pruning ? 'progress_activity' : 'delete_sweep' }}</span>
            清理未使用
          </button>
        </div>

        <div v-if="!networks.length" class="empty-state">没有可显示的网络</div>
        <div v-else class="resource-table">
          <div class="table-head">
            <span>名称</span>
            <span>驱动</span>
            <span>Scope</span>
            <span>容器</span>
            <span>属性</span>
            <span>操作</span>
          </div>
          <article
            v-for="(network, index) in networks"
            :key="network.id || network.name"
            class="resource-row motion-item"
            :class="{ expanded: expandedNetwork === network.name }"
            :style="{ '--motion-delay': `${Math.min(index, 12) * 28}ms` }"
          >
            <div class="table-row-main">
              <div>
                <strong>{{ network.name }}</strong>
              </div>
              <span class="mono">{{ network.driver || 'bridge' }}</span>
              <span>{{ network.scope || 'local' }}</span>
              <span class="status-pill" :class="{ running: network.containers > 0 }">
                <span class="status-dot"></span>
                {{ network.containers }} 个容器
              </span>
              <span class="flag-line">
                <span v-if="network.internal" class="flag-chip">internal</span>
                <span v-if="network.attachable" class="flag-chip">attachable</span>
                <span v-if="!network.internal && !network.attachable">-</span>
              </span>
              <div class="row-actions">
                <button class="icon-action" type="button" title="详情" @click="toggleDetail(network.name)">
                  <span class="material-symbol">info</span>
                </button>
                <button
                  class="icon-action danger"
                  type="button"
                  title="删除网络"
                  :disabled="busyNetwork === network.name"
                  @click="handleRemoveNetwork(network.name)"
                >
                  <span class="material-symbol" :class="{ spinning: busyNetwork === network.name }">
                    {{ busyNetwork === network.name ? 'progress_activity' : 'delete' }}
                  </span>
                </button>
              </div>
            </div>

            <div class="expand-collapse" :class="{ open: expandedNetwork === network.name }">
              <div class="expand-inner">
                <DetailPanel
                  v-if="renderedNetwork === network.name"
                  :tabs="detailTabs"
                  v-model="activeTab"
                  :loading="detailLoading"
                  :error="detail?.error"
                  loading-text="网络详情读取中"
                  aria-label="网络详情面板"
                  tabs-label="Network detail tabs"
                  @close="closeDetail"
                >
                  <template v-if="activeTab === 'detail'">
                    <HighlightedText :content="detailJson" mode="json" empty-text="暂无详情" />
                  </template>
                  <template v-else>
                    <div class="attach-form">
                      <input v-model.trim="containerName" class="themed-input" placeholder="容器名称或 ID" />
                      <button class="secondary-button" type="button" :disabled="!containerName || busyNetwork === network.name" @click="handleNetworkLink(network.name, 'connect')">
                        <span class="material-symbol">link</span>
                        连接
                      </button>
                      <button class="secondary-button danger" type="button" :disabled="!containerName || busyNetwork === network.name" @click="handleNetworkLink(network.name, 'disconnect')">
                        <span class="material-symbol">link_off</span>
                        断开
                      </button>
                    </div>
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
          <section class="resource-dialog" role="dialog" aria-modal="true" aria-labelledby="network-create-title">
            <header class="dialog-header">
              <div>
                <p class="eyebrow">Docker network</p>
                <h2 id="network-create-title">新建网络</h2>
              </div>
              <button class="icon-button" type="button" title="关闭" :disabled="creating" @click="closeCreateDialog">
                <span class="material-symbol">close</span>
              </button>
            </header>

            <form class="dialog-body" @submit.prevent="handleCreateNetwork">
              <div class="form-grid">
                <label class="field-row">
                  <span>名称</span>
                  <input v-model.trim="createForm.name" class="themed-input" placeholder="ops-net" autocomplete="off" />
                </label>
                <label class="field-row">
                  <span>驱动</span>
                  <select v-model="createForm.driver" class="themed-input">
                    <option value="bridge">bridge</option>
                    <option value="macvlan">macvlan</option>
                    <option value="ipvlan">ipvlan</option>
                    <option value="overlay">overlay</option>
                  </select>
                </label>
                <label class="field-row">
                  <span>子网</span>
                  <input v-model.trim="createForm.subnet" class="themed-input" placeholder="172.30.0.0/24" autocomplete="off" />
                </label>
                <label class="field-row">
                  <span>网关</span>
                  <input v-model.trim="createForm.gateway" class="themed-input" placeholder="172.30.0.1" autocomplete="off" />
                </label>
                <label class="switch-row">
                  <input v-model="createForm.internal" type="checkbox" />
                  <span>内部网络</span>
                </label>
                <label class="switch-row">
                  <input v-model="createForm.attachable" type="checkbox" />
                  <span>允许独立容器接入</span>
                </label>
              </div>
            </form>

            <footer class="dialog-footer">
              <button class="secondary-button" type="button" :disabled="creating" @click="closeCreateDialog">取消</button>
              <button class="primary-button" type="button" :disabled="creating || !createForm.name" @click="handleCreateNetwork">
                <span class="material-symbol" :class="{ spinning: creating }">{{ creating ? 'progress_activity' : 'add' }}</span>
                创建网络
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
import { createNetwork, getNetworkDetail, listNetworks, runNetworkAction } from '../api'
import type { NetworkCreateRequest, NetworkDetailResponse, NetworkListResponse, OperationResponse } from '../api/types'
import DetailPanel from '../components/DetailPanel.vue'
import HighlightedText from '../components/HighlightedText.vue'
import MotionSurface from '../components/MotionSurface.vue'
import NoticeBanner from '../components/NoticeBanner.vue'
import type { TabItem } from '../components/types'
import { requestConfirm } from '../utils/confirmDialog'

const detailTabs: TabItem[] = [
  { key: 'detail', label: 'Inspect', icon: 'data_object' },
  { key: 'attach', label: '连接容器', icon: 'link' },
]

const response = ref<NetworkListResponse | null>(null)
const detail = ref<NetworkDetailResponse | null>(null)
const loading = ref(false)
const creating = ref(false)
const pruning = ref(false)
const detailLoading = ref(false)
const busyNetwork = ref<string | null>(null)
const notice = ref<OperationResponse | null>(null)
const createDialogOpen = ref(false)
const expandedNetwork = ref<string | null>(null)
const renderedNetwork = ref<string | null>(null)
const activeTab = ref<'detail' | 'attach'>('detail')
const containerName = ref('')
let collapseTimer: ReturnType<typeof setTimeout> | null = null

const createForm = ref<NetworkCreateRequest>({
  name: '',
  driver: 'bridge',
  subnet: '',
  gateway: '',
  internal: false,
  attachable: false,
})

const networks = computed(() => response.value?.networks ?? [])
const detailJson = computed(() => JSON.stringify(detail.value?.detail ?? {}, null, 2))

function resetCreateForm() {
  createForm.value = {
    name: '',
    driver: 'bridge',
    subnet: '',
    gateway: '',
    internal: false,
    attachable: false,
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

async function loadNetworks() {
  loading.value = true
  try {
    response.value = await listNetworks()
  } catch (err) {
    notice.value = { ok: false, message: '读取网络列表失败。', data: {}, error: String(err), timestamp: new Date().toISOString() }
  } finally {
    loading.value = false
  }
}

async function handleCreateNetwork() {
  creating.value = true
  notice.value = null
  try {
    notice.value = await createNetwork({
      ...createForm.value,
      subnet: createForm.value.subnet || null,
      gateway: createForm.value.gateway || null,
    })
    if (notice.value.ok) {
      createDialogOpen.value = false
      await loadNetworks()
    }
  } catch (err) {
    notice.value = { ok: false, message: '创建网络请求失败。', data: {}, error: String(err), timestamp: new Date().toISOString() }
  } finally {
    creating.value = false
  }
}

async function toggleDetail(name: string) {
  if (expandedNetwork.value === name && activeTab.value === 'detail') {
    closeDetail()
    return
  }
  if (collapseTimer) clearTimeout(collapseTimer)
  expandedNetwork.value = name
  renderedNetwork.value = name
  activeTab.value = 'detail'
  detailLoading.value = true
  try {
    detail.value = await getNetworkDetail(name)
  } catch (err) {
    detail.value = { docker_available: false, name, detail: {}, error: String(err), timestamp: new Date().toISOString() }
  } finally {
    detailLoading.value = false
  }
}

function closeDetail() {
  expandedNetwork.value = null
  if (collapseTimer) clearTimeout(collapseTimer)
  collapseTimer = setTimeout(() => {
    renderedNetwork.value = null
    detail.value = null
    containerName.value = ''
  }, 280)
}

async function handleRemoveNetwork(name: string) {
  const approve = await requestConfirm({
    title: '删除网络',
    message: `确认删除网络 ${name}？`,
    confirmText: '删除',
    intent: 'danger',
    icon: 'delete',
  })
  if (!approve) return
  busyNetwork.value = name
  try {
    notice.value = await runNetworkAction(name, { action: 'remove', approve })
    if (notice.value.ok) {
      closeDetail()
      await loadNetworks()
    }
  } catch (err) {
    notice.value = { ok: false, message: '删除网络请求失败。', data: {}, error: String(err), timestamp: new Date().toISOString() }
  } finally {
    busyNetwork.value = null
  }
}

async function handlePruneNetworks() {
  const approve = await requestConfirm({
    title: '清理网络',
    message: '确认清理所有未使用的 Docker 网络？',
    confirmText: '清理',
    intent: 'danger',
    icon: 'delete_sweep',
  })
  if (!approve) return
  pruning.value = true
  try {
    notice.value = await runNetworkAction('_', { action: 'prune', approve })
    await loadNetworks()
  } catch (err) {
    notice.value = { ok: false, message: '清理网络请求失败。', data: {}, error: String(err), timestamp: new Date().toISOString() }
  } finally {
    pruning.value = false
  }
}

async function handleNetworkLink(name: string, action: 'connect' | 'disconnect') {
  if (!containerName.value) return
  busyNetwork.value = name
  try {
    notice.value = await runNetworkAction(name, { action, container: containerName.value })
    await toggleDetail(name)
  } catch (err) {
    notice.value = { ok: false, message: '网络连接操作请求失败。', data: {}, error: String(err), timestamp: new Date().toISOString() }
  } finally {
    busyNetwork.value = null
  }
}

onMounted(loadNetworks)
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
  grid-template-columns: minmax(180px, 1.2fr) minmax(90px, 0.6fr) minmax(80px, 0.5fr) minmax(100px, 0.6fr) minmax(120px, 0.7fr) minmax(120px, auto);
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

.flag-line {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.flag-chip {
  padding: 4px 8px;
  border-radius: 10px;
  background: var(--md-sys-color-surface-container);
  color: var(--md-sys-color-on-surface-variant);
  font-size: 11px;
  font-weight: 700;
}

.row-actions,
.attach-form {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
}

.attach-form {
  justify-content: flex-start;
}

.attach-form .themed-input {
  max-width: 320px;
}

.switch-row {
  display: grid;
  grid-template-columns: 20px minmax(0, 1fr);
  gap: 10px;
  align-items: start;
  min-width: 0;
  padding: 12px;
  border: 1px solid var(--md-sys-color-outline-variant);
  border-radius: 16px;
  background: var(--md-sys-color-surface-container-low);
  color: var(--md-sys-color-on-surface);
  cursor: pointer;
  transition: border-color 0.18s ease, background-color 0.18s ease, box-shadow 0.18s ease, transform 0.18s ease;
}

.switch-row:hover {
  border-color: color-mix(in srgb, var(--md-sys-color-primary) 38%, var(--md-sys-color-outline-variant));
  background: color-mix(in srgb, var(--md-sys-color-surface) 76%, var(--md-sys-color-primary-container));
  box-shadow: var(--md-elevation-1);
}

.switch-row:active {
  transform: scale(0.99);
}

.switch-row input {
  width: 18px;
  height: 18px;
  margin: 2px 0 0;
  accent-color: var(--md-sys-color-primary);
}

.switch-row span {
  min-width: 0;
  font-size: 13px;
  font-weight: 800;
  line-height: 1.45;
  overflow-wrap: anywhere;
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
  width: min(720px, 100%);
  max-height: min(680px, calc(100vh - 56px));
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
