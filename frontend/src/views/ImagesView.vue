<template>
  <section class="page-shell images-view">
    <header class="page-header">
      <div>
        <p class="eyebrow">Docker images</p>
        <h1 class="page-title">镜像管理</h1>
        <p class="page-subtitle">拉取、查看、删除和清理本机 Docker 镜像。</p>
      </div>
      <div class="header-actions">
        <button class="secondary-button" type="button" :disabled="batchBusy" @click="openImportWizard">
          <span class="material-symbol">add_box</span>
          导入镜像
        </button>
        <button class="toolbar-button" type="button" @click="loadImages" :disabled="loading">
          <span class="material-symbol" :class="{ spinning: loading }">{{ loading ? 'progress_activity' : 'refresh' }}</span>
          {{ loading ? '刷新中' : '刷新' }}
        </button>
      </div>
    </header>

    <NoticeBanner v-if="notice" :ok="notice.ok" :message="notice.message" />

    <div v-if="response?.error" class="error-banner">Docker 连接异常：{{ response.error }}</div>

    <div class="image-workbench">
      <MotionSurface class="cleanup-panel" :expanded="pruning" :delay="35">
        <div class="panel-heading">
          <div>
            <p class="eyebrow">清理镜像</p>
            <h2>释放未使用空间</h2>
          </div>
          <span class="material-symbol">auto_delete</span>
        </div>
        <label class="toggle-row">
          <input v-model="pruneDanglingOnly" type="checkbox" />
          <span>
            <strong>只清理空置镜像</strong>
            <small>关闭后会清理所有未被容器使用的镜像</small>
          </span>
        </label>
        <button class="secondary-button danger" type="button" :disabled="pruning || batchBusy" @click="handlePruneImages">
          <span class="material-symbol" :class="{ spinning: pruning }">
            {{ pruning ? 'progress_activity' : 'delete_sweep' }}
          </span>
          清理镜像
        </button>
      </MotionSurface>
    </div>

    <MotionSurface class="image-list-panel" :interactive="false" :delay="60">
      <div class="list-summary">
        <span class="summary-count">总计 {{ images.length }} 个镜像</span>
      </div>

      <BatchToolbar
        :selected-count="imageSelection.selectedCount.value"
        :total-count="images.length"
        :all-selected="allImagesSelected"
        :disabled="batchBusy"
        @toggle-all="imageSelection.toggleAll(selectableImageIds)"
        @clear="imageSelection.clear"
      >
        <button class="secondary-button danger compact" type="button" :disabled="!canRemoveSelectedImages" @click="handleBatchRemoveImages">
          <span class="material-symbol">delete</span>
          删除镜像
        </button>
      </BatchToolbar>

      <div v-if="!images.length" class="empty-state">没有可显示的镜像</div>
      <div v-else class="image-groups">
        <section v-for="group in imageGroups" :key="group.key" class="image-group">
          <div class="group-heading">
            <div>
              <h2>{{ group.title }}</h2>
              <span>{{ group.images.length }} 个镜像</span>
            </div>
            <span class="material-symbol">{{ group.icon }}</span>
          </div>

          <div class="image-table">
            <div class="table-head">
              <span></span>
              <span>镜像</span>
              <span>ID</span>
              <span>大小</span>
              <span>创建时间</span>
              <span>使用</span>
              <span>操作</span>
            </div>
            <article
              v-for="(image, index) in group.images"
              :key="image.id"
              class="image-row motion-item"
              :class="{ expanded: expandedImageId === image.id, untagged: !image.tags.length }"
              :style="{ '--motion-delay': `${Math.min(index, 12) * 28}ms` }"
            >
              <div class="table-row-main">
                <label class="selection-cell control-item" title="选择镜像">
                  <input
                    type="checkbox"
                    :checked="imageSelection.isSelected(image.id)"
                    :disabled="batchBusy"
                    aria-label="选择镜像"
                    @change="imageSelection.toggle(image.id, ($event.target as HTMLInputElement).checked)"
                    @click.stop
                  />
                </label>
                <div class="tag-stack">
                  <strong>{{ primaryTag(image) }}</strong>
                  <small v-if="image.tags.length > 1">{{ image.tags.length - 1 }} 个其他标签</small>
                  <small v-else-if="!image.tags.length">无标签镜像</small>
                </div>
                <span class="mono">{{ image.short_id }}</span>
                <span class="mono">{{ formatBytes(image.size) }}</span>
                <span>{{ formatDate(image.created) }}</span>
                <span class="status-pill" :class="{ running: image.containers > 0 }">
                  <span class="status-dot"></span>
                  {{ image.containers }} 个容器
                </span>
                <div class="row-actions">
                  <button
                    class="icon-action"
                    :class="{ active: expandedImageId === image.id }"
                    type="button"
                    title="详情"
                    @click="toggleImageDetail(image.id)"
                  >
                    <span class="material-symbol">info</span>
                  </button>
                  <a
                    class="icon-action"
                    title="导出 tar"
                    :href="imageExportUrl(imageReference(image))"
                    target="_blank"
                    rel="noreferrer"
                  >
                    <span class="material-symbol">archive</span>
                  </a>
                  <button
                    class="icon-action danger"
                    type="button"
                    title="删除镜像"
                    :disabled="busyImage === image.id || batchBusy"
                    @click="handleRemoveImage(image)"
                  >
                    <span class="material-symbol" :class="{ spinning: busyImage === image.id }">
                      {{ busyImage === image.id ? 'progress_activity' : 'delete' }}
                    </span>
                  </button>
                </div>
              </div>

              <div class="expand-collapse" :class="{ open: expandedImageId === image.id }">
                <div class="expand-inner">
                  <DetailPanel
                    v-if="renderedImageId === image.id"
                    class="inline-detail"
                    :tabs="imageDetailTabs"
                    v-model="activeImageTab"
                    aria-label="镜像详情面板"
                    tabs-label="Image detail tabs"
                    @close="closeImageDetail"
                  >
                    <template v-if="activeImageTab === 'summary'">
                      <div class="detail-grid">
                        <div class="detail-item wide">
                          <span>完整 ID</span>
                          <strong>{{ image.id }}</strong>
                        </div>
                        <div class="detail-item wide tag-manager">
                          <span>标签</span>
                          <p v-if="image.running_containers > 0" class="tag-guard">
                            <span class="material-symbol">lock</span>
                            {{ image.running_containers }} 个运行中容器正在使用该镜像，标签暂不可修改。
                          </p>
                          <div v-if="image.tags.length" class="tag-chip-list">
                            <button
                              v-for="tag in image.tags"
                              :key="tag"
                              class="tag-chip"
                              :class="{ locked: !canDeleteImageTag(image) }"
                              type="button"
                              :title="tagDeleteTitle(image)"
                              :disabled="!canDeleteImageTag(image) || busyTag === tag"
                              @click="handleUntagImage(image, tag)"
                            >
                              {{ tag }}
                              <span class="material-symbol" :class="{ spinning: busyTag === tag }">
                                {{ busyTag === tag ? 'progress_activity' : 'close' }}
                              </span>
                            </button>
                          </div>
                          <strong v-else>无标签</strong>
                          <div class="inline-tag-form">
                            <label class="field-row">
                              <span>Repository</span>
                              <input
                                v-model.trim="tagFormFor(image).repository"
                                class="themed-input"
                                placeholder="course/demo"
                                :disabled="!canModifyImageTags(image) || taggingImage === image.id"
                                autocomplete="off"
                              />
                            </label>
                            <label class="field-row">
                              <span>Tag</span>
                              <input
                                v-model.trim="tagFormFor(image).tag"
                                class="themed-input"
                                placeholder="latest"
                                :disabled="!canModifyImageTags(image) || taggingImage === image.id"
                                autocomplete="off"
                              />
                            </label>
                            <button
                              class="secondary-button"
                              type="button"
                              :disabled="!canSubmitImageTag(image) || taggingImage === image.id"
                              @click="handleTagImage(image)"
                            >
                              <span class="material-symbol" :class="{ spinning: taggingImage === image.id }">
                                {{ taggingImage === image.id ? 'progress_activity' : 'new_label' }}
                              </span>
                              添加标签
                            </button>
                          </div>
                        </div>
                        <div class="detail-item">
                          <span>大小</span>
                          <strong>{{ formatBytes(image.size) }}</strong>
                        </div>
                        <div class="detail-item">
                          <span>使用容器</span>
                          <strong>{{ image.containers }}</strong>
                        </div>
                        <div class="detail-item wide">
                          <span>摘要</span>
                          <strong>{{ image.repo_digests.length ? image.repo_digests.join(', ') : '-' }}</strong>
                        </div>
                      </div>
                    </template>
                    <template v-else>
                      <div v-if="Object.keys(image.labels || {}).length" class="label-list">
                        <div v-for="[key, value] in Object.entries(image.labels)" :key="key" class="label-row">
                          <span>{{ key }}</span>
                          <strong>{{ value }}</strong>
                        </div>
                      </div>
                      <div v-else class="empty-state compact">该镜像没有标签元数据</div>
                    </template>
                  </DetailPanel>
                </div>
              </div>
            </article>
          </div>
        </section>
      </div>
    </MotionSurface>

    <Teleport to="body">
      <Transition name="wizard-fade">
        <div v-if="importWizardOpen" class="image-import-backdrop" role="presentation" @click.self="closeImportWizard">
          <section class="image-import-dialog" role="dialog" aria-modal="true" aria-labelledby="image-import-title">
            <header class="wizard-header">
              <div>
                <p class="eyebrow">Image import</p>
                <h2 id="image-import-title">导入镜像</h2>
              </div>
              <button class="icon-button" type="button" title="关闭" :disabled="importSubmitting" @click="closeImportWizard">
                <span class="material-symbol">close</span>
              </button>
            </header>

            <div class="wizard-steps" aria-label="镜像导入流程">
              <button
                v-for="item in importSteps"
                :key="item.key"
                class="step-pill"
                :class="{ active: importStep === item.key, done: importStepOrder(item.key) < importStepOrder(importStep) }"
                type="button"
                :disabled="item.key === 'options' && !canGoImportOptions"
                @click="importStep = item.key"
              >
                <span class="material-symbol">{{ item.icon }}</span>
                {{ item.label }}
              </button>
            </div>

            <form class="image-import-body" @submit.prevent="handleSubmitImportWizard">
              <Transition name="panel-rise" mode="out-in">
                <section v-if="importStep === 'source'" key="source" class="wizard-page">
                  <div class="source-choice-grid">
                    <button
                      type="button"
                      class="source-choice"
                      :class="{ selected: importForm.source === 'pull' }"
                      @click="importForm.source = 'pull'"
                    >
                      <span class="material-symbol">download</span>
                      <strong>从 Registry 拉取</strong>
                      <small>输入镜像名，显示分层拉取进度。</small>
                    </button>
                    <button
                      type="button"
                      class="source-choice"
                      :class="{ selected: importForm.source === 'upload' }"
                      @click="importForm.source = 'upload'"
                    >
                      <span class="material-symbol">upload_file</span>
                      <strong>上传 tar 文件</strong>
                      <small>导入 docker save 导出的 tar/tar.gz/tgz 文件。</small>
                    </button>
                  </div>

                  <label v-if="importForm.source === 'pull'" class="field-row wide">
                    <span>镜像名称</span>
                    <input
                      v-model.trim="importForm.image"
                      class="themed-input"
                      placeholder="例如 nginx:latest 或 redis:7-alpine"
                      autocomplete="off"
                    />
                  </label>

                  <div v-else class="upload-drop">
                    <input ref="importInput" class="file-input" type="file" accept=".tar,.tar.gz,.tgz" @change="handleImportFileChange" />
                    <button class="secondary-button" type="button" @click="importInput?.click()">
                      <span class="material-symbol">upload_file</span>
                      选择 tar 文件
                    </button>
                    <strong>{{ importForm.file?.name || '尚未选择文件' }}</strong>
                  </div>
                </section>

                <section v-else key="options" class="wizard-page">
                  <label class="switch-row">
                    <input v-model="importForm.retag" type="checkbox" />
                    <span>
                      <strong>导入后重新打标签</strong>
                      <small>适合上传无标签镜像，或把远端镜像保存成课程项目自己的 tag。</small>
                    </span>
                  </label>

                  <div v-if="importForm.retag" class="retag-grid">
                    <label class="field-row">
                      <span>Repository</span>
                      <input v-model.trim="importForm.repository" class="themed-input" placeholder="course/demo" autocomplete="off" />
                    </label>
                    <label class="field-row">
                      <span>Tag</span>
                      <input v-model.trim="importForm.tag" class="themed-input" placeholder="latest" autocomplete="off" />
                    </label>
                  </div>

                  <Transition name="panel-rise">
                    <div v-if="showPullProgress" class="pull-progress-panel">
                      <div class="pull-progress-head">
                        <div>
                          <span class="material-symbol" :class="{ spinning: pullingImage }">
                            {{ pullingImage ? 'sync' : latestPullEvent?.type === 'error' ? 'error' : 'check_circle' }}
                          </span>
                          <strong>{{ pullProgressTitle }}</strong>
                        </div>
                        <span v-if="pullOverallPercent !== null" class="pull-percent">{{ pullOverallPercent }}%</span>
                      </div>
                      <div class="pull-track" :class="{ indeterminate: pullingImage && pullOverallPercent === null }">
                        <span :style="{ width: pullProgressWidth }"></span>
                      </div>
                      <div v-if="pullLayerRows.length" class="pull-layer-list">
                        <div
                          v-for="layer in pullLayerRows"
                          :key="layer.id || layer.message || layer.status || layer.image"
                          class="pull-layer-row"
                        >
                          <span class="mono">{{ layer.id || layer.image }}</span>
                          <span>{{ layer.status || layer.message || '拉取中' }}</span>
                          <strong>{{ formatPullPercent(layer.percent) }}</strong>
                        </div>
                      </div>
                      <p v-if="latestPullEvent?.error" class="pull-error">{{ latestPullEvent.error }}</p>
                    </div>
                  </Transition>
                </section>
              </Transition>
            </form>

            <footer class="wizard-footer">
              <button class="secondary-button" type="button" :disabled="importSubmitting" @click="closeImportWizard">取消</button>
              <button
                v-if="importStep === 'source'"
                class="primary-button"
                type="button"
                :disabled="!canGoImportOptions"
                @click="importStep = 'options'"
              >
                下一步
              </button>
              <button
                v-else
                class="primary-button"
                type="button"
                :disabled="!canSubmitImport || importSubmitting"
                @click="handleSubmitImportWizard"
              >
                <span class="material-symbol" :class="{ spinning: importSubmitting }">
                  {{ importSubmitting ? 'progress_activity' : 'inventory_2' }}
                </span>
                {{ importSubmitting ? '导入中' : '开始导入' }}
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
  imageExportUrl,
  importImage,
  listImages,
  pruneImages,
  pullImageWithProgress,
  removeImage,
  tagImage,
  untagImage,
} from '../api'
import type {
  ImageListResponse,
  ImagePullProgressEvent,
  ImageSummary,
  OperationResponse,
} from '../api/types'
import BatchToolbar from '../components/BatchToolbar.vue'
import DetailPanel from '../components/DetailPanel.vue'
import MotionSurface from '../components/MotionSurface.vue'
import NoticeBanner from '../components/NoticeBanner.vue'
import type { TabItem } from '../components/types'
import { batchNotice, runBatchOperation, useBatchSelection } from '../utils/batch'
import { requestConfirm } from '../utils/confirmDialog'

const imageDetailTabs: TabItem[] = [
  { key: 'summary', label: '摘要', icon: 'info' },
  { key: 'labels', label: '标签', icon: 'sell' },
]

const response = ref<ImageListResponse | null>(null)
const loading = ref(false)
const notice = ref<OperationResponse | null>(null)
const pullingImage = ref(false)
const latestPullEvent = ref<ImagePullProgressEvent | null>(null)
const pullLayers = ref<Record<string, ImagePullProgressEvent>>({})
const pruneDanglingOnly = ref(true)
const pruning = ref(false)
const taggingImage = ref<string | null>(null)
const busyTag = ref<string | null>(null)
const busyImage = ref<string | null>(null)
const batchBusy = ref(false)
const expandedImageId = ref<string | null>(null)
/** 延迟清理 v-if 内容，等收起动画结束后再销毁 DOM。 */
const renderedImageId = ref<string | null>(null)
let imageCollapseTimer: ReturnType<typeof setTimeout> | null = null
const activeImageTab = ref<'summary' | 'labels'>('summary')
const importInput = ref<HTMLInputElement | null>(null)
const importWizardOpen = ref(false)
type ImportStep = 'source' | 'options'
type ImportSource = 'pull' | 'upload'
const importStep = ref<ImportStep>('source')
const importSubmitting = ref(false)
const importSteps: Array<{ key: ImportStep; label: string; icon: string }> = [
  { key: 'source', label: '来源', icon: 'input' },
  { key: 'options', label: '选项', icon: 'tune' },
]
const importForm = ref<{
  source: ImportSource
  image: string
  file: File | null
  retag: boolean
  repository: string
  tag: string
}>({
  source: 'pull',
  image: '',
  file: null,
  retag: false,
  repository: '',
  tag: 'latest',
})
const imageTagForms = ref<Record<string, { repository: string; tag: string }>>({})
const imageSelection = useBatchSelection<string>()

const images = computed(() => response.value?.images ?? [])
const selectableImageIds = computed(() => images.value.map((image) => image.id))
const selectedImages = computed(() => images.value.filter((image) => imageSelection.isSelected(image.id)))
const allImagesSelected = computed(() => imageSelection.areAllSelected(selectableImageIds.value))
const canRemoveSelectedImages = computed(() => !batchBusy.value && selectedImages.value.length > 0)
const imageGroups = computed(() => {
  const tagged = images.value.filter((image) => image.tags.length)
  const untagged = images.value.filter((image) => !image.tags.length)
  return [
    { key: 'tagged', title: '有标签', icon: 'sell', images: tagged },
    { key: 'untagged', title: '无标签', icon: 'label_off', images: untagged },
  ].filter((group) => group.images.length)
})
const canGoImportOptions = computed(() => (
  importForm.value.source === 'pull'
    ? Boolean(importForm.value.image.trim())
    : importForm.value.file !== null
))
const canSubmitImport = computed(() => (
  canGoImportOptions.value
  && (
    !importForm.value.retag
    || (Boolean(importForm.value.repository.trim()) && Boolean(importForm.value.tag.trim()))
  )
))
const pullLayerRows = computed(() => Object.values(pullLayers.value).slice(-8))
const showPullProgress = computed(() => pullingImage.value || latestPullEvent.value !== null || pullLayerRows.value.length > 0)
const pullOverallPercent = computed(() => {
  // 镜像拉取进度按层返回；有层级百分比时面板展示平均进度。
  const values = pullLayerRows.value
    .map((item) => (typeof item.percent === 'number' ? item.percent : null))
    .filter((value): value is number => value !== null)
  if (!values.length) {
    return latestPullEvent.value?.type === 'success' ? 100 : null
  }
  return Math.round(values.reduce((sum, value) => sum + value, 0) / values.length)
})
const pullProgressWidth = computed(() => {
  if (pullOverallPercent.value !== null) return `${pullOverallPercent.value}%`
  return pullingImage.value ? '42%' : '100%'
})
const pullProgressTitle = computed(() => latestPullEvent.value?.message || '等待镜像拉取进度')

function primaryTag(image: ImageSummary): string {
  return image.tags[0] || '无标签'
}

function imageReference(image: ImageSummary): string {
  return image.tags[0] || image.id
}

function tagFormFor(image: ImageSummary) {
  if (!imageTagForms.value[image.id]) {
    imageTagForms.value[image.id] = { repository: '', tag: 'latest' }
  }
  return imageTagForms.value[image.id]
}

function canModifyImageTags(image: ImageSummary): boolean {
  return (image.running_containers ?? 0) <= 0
}

function canDeleteImageTag(image: ImageSummary): boolean {
  return canModifyImageTags(image) && image.tags.length > 1
}

function canSubmitImageTag(image: ImageSummary): boolean {
  const form = tagFormFor(image)
  return canModifyImageTags(image) && Boolean(form.repository.trim()) && Boolean(form.tag.trim())
}

function tagDeleteTitle(image: ImageSummary): string {
  if ((image.running_containers ?? 0) > 0) return '运行中容器正在使用该镜像，不能修改标签'
  if (image.tags.length <= 1) return '不能删除镜像的最后一个标签'
  return '删除此标签'
}

function importStepOrder(step: ImportStep): number {
  return importSteps.findIndex((item) => item.key === step)
}

function formatDate(value?: string | null): string {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { hour12: false })
}

function formatBytes(value: number): string {
  if (!Number.isFinite(value) || value <= 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let size = value
  let unit = 0
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024
    unit += 1
  }
  return `${size >= 10 || unit === 0 ? size.toFixed(0) : size.toFixed(1)} ${units[unit]}`
}

function formatPullPercent(value?: number | null): string {
  return typeof value === 'number' ? `${Math.round(value)}%` : '-'
}

function recordPullProgress(event: ImagePullProgressEvent) {
  latestPullEvent.value = event
  if (!event.id) return
  // 同一层 id 的进度直接覆盖，避免追加重复进度行。
  pullLayers.value = {
    ...pullLayers.value,
    [event.id]: event,
  }
}

function toggleImageDetail(imageId: string) {
  if (expandedImageId.value === imageId) {
    closeImageDetail()
    return
  }
  if (imageCollapseTimer) clearTimeout(imageCollapseTimer)
  // 先渲染再展开，CSS 高度过渡才能测量到真实内容。
  renderedImageId.value = imageId
  expandedImageId.value = imageId
  activeImageTab.value = 'summary'
}

function closeImageDetail() {
  expandedImageId.value = null
  if (imageCollapseTimer) clearTimeout(imageCollapseTimer)
  imageCollapseTimer = setTimeout(() => {
    renderedImageId.value = null
  }, 340)
}

function openImportWizard() {
  importForm.value = {
    source: 'pull',
    image: '',
    file: null,
    retag: false,
    repository: '',
    tag: 'latest',
  }
  importStep.value = 'source'
  latestPullEvent.value = null
  pullLayers.value = {}
  importWizardOpen.value = true
}

function closeImportWizard() {
  if (importSubmitting.value) return
  importWizardOpen.value = false
}

async function handleSubmitImportWizard() {
  if (!canSubmitImport.value) return
  importSubmitting.value = true
  notice.value = null
  try {
    if (importForm.value.source === 'pull') {
      await handlePullImage(importForm.value.image.trim())
    } else if (importForm.value.file) {
      notice.value = await importImage(importForm.value.file)
      if (notice.value.ok) {
        await loadImages()
      }
    }

    if (notice.value?.ok && importForm.value.retag) {
      const source = importForm.value.source === 'pull'
        ? importForm.value.image.trim()
        : importedImageSource(notice.value)
      if (!source) {
        notice.value = {
          ok: false,
          message: '镜像已导入，但没有找到可用于重新打标签的镜像 ID。',
          data: notice.value.data,
          error: null,
          timestamp: new Date().toISOString(),
        }
        return
      }
      notice.value = await tagImage({
        source,
        repository: importForm.value.repository.trim(),
        tag: importForm.value.tag.trim() || 'latest',
      })
      if (notice.value.ok) await loadImages()
    }

    if (notice.value?.ok) {
      importWizardOpen.value = false
    }
  } catch (err) {
    notice.value = { ok: false, message: '镜像导入请求失败。', data: {}, error: String(err), timestamp: new Date().toISOString() }
  } finally {
    importSubmitting.value = false
  }
}

async function handlePullImage(imageName: string) {
  if (!imageName) return
  pullingImage.value = true
  latestPullEvent.value = {
    type: 'start',
    image: imageName,
    message: `准备拉取 ${imageName}`,
  }
  pullLayers.value = {}
  try {
    // 进度流结束后，pullImageWithProgress 会解析成 OperationResponse。
    notice.value = await pullImageWithProgress(imageName, recordPullProgress)
    if (notice.value.ok) {
      await loadImages()
    }
  } catch (err) {
    notice.value = { ok: false, message: '镜像拉取请求失败。', data: {}, error: String(err), timestamp: new Date().toISOString() }
    latestPullEvent.value = {
      type: 'error',
      image: imageName,
      message: '镜像拉取请求失败。',
      error: String(err),
    }
  } finally {
    pullingImage.value = false
  }
}

function importedImageSource(response: OperationResponse): string {
  const images = response.data.images
  if (Array.isArray(images) && images.length) {
    const first = images[0]
    if (first && typeof first === 'object') {
      const record = first as { id?: unknown; tags?: unknown }
      if (Array.isArray(record.tags) && typeof record.tags[0] === 'string') return record.tags[0]
      if (typeof record.id === 'string') return record.id
    }
  }
  return ''
}

async function handleRemoveImage(image: ImageSummary) {
  const target = imageReference(image)
  // 被容器引用的镜像需要 force=true，最终删除确认前先单独询问。
  const force = image.containers > 0
    ? await requestConfirm({
        title: '强制删除镜像',
        message: `镜像 ${target} 正被 ${image.containers} 个容器引用。是否强制删除？`,
        confirmText: '强制删除',
        intent: 'danger',
        icon: 'warning',
      })
    : false
  if (image.containers > 0 && !force) return
  const confirmed = await requestConfirm({
    title: '删除镜像',
    message: `确认删除镜像 ${target}？`,
    confirmText: '删除',
    intent: 'danger',
    icon: 'delete',
  })
  if (!confirmed) return

  busyImage.value = image.id
  notice.value = null
  try {
    notice.value = await removeImage({ image: target, force, approve: true })
    await loadImages()
  } catch (err) {
    notice.value = { ok: false, message: '镜像删除请求失败。', data: {}, error: String(err), timestamp: new Date().toISOString() }
  } finally {
    busyImage.value = null
  }
}

async function handleBatchRemoveImages() {
  const targets = selectedImages.value
  if (!targets.length) return

  const forceRequired = targets.filter((image) => image.containers > 0)
  let force = false
  if (forceRequired.length) {
    force = await requestConfirm({
      title: '批量强制删除镜像',
      message: `${forceRequired.length} 个镜像正被容器引用。是否对这些镜像使用强制删除？`,
      confirmText: '允许强制删除',
      intent: 'danger',
      icon: 'warning',
    })
    if (!force) return
  }

  const confirmed = await requestConfirm({
    title: '批量删除镜像',
    message: `确认删除选中的 ${targets.length} 个镜像？`,
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
      (image) => removeImage({ image: imageReference(image), force: image.containers > 0 ? force : false, approve: true }),
      imageReference,
    )
    notice.value = batchNotice('镜像', '删除', outcome)
    imageSelection.clear()
    await loadImages()
  } finally {
    batchBusy.value = false
  }
}

async function handleTagImage(image: ImageSummary) {
  if (!canSubmitImageTag(image)) return
  const form = tagFormFor(image)
  taggingImage.value = image.id
  notice.value = null
  try {
    notice.value = await tagImage({
      source: imageReference(image),
      repository: form.repository,
      tag: form.tag || 'latest',
    })
    if (notice.value.ok) {
      form.repository = ''
      form.tag = 'latest'
      await loadImages()
    }
  } catch (err) {
    notice.value = { ok: false, message: '添加镜像标签请求失败。', data: {}, error: String(err), timestamp: new Date().toISOString() }
  } finally {
    taggingImage.value = null
  }
}

async function handleUntagImage(image: ImageSummary, tag: string) {
  if (!canDeleteImageTag(image)) return
  const confirmed = await requestConfirm({
    title: '删除镜像标签',
    message: `确认删除镜像标签 ${tag}？`,
    confirmText: '删除标签',
    intent: 'danger',
    icon: 'label_off',
  })
  if (!confirmed) return
  busyTag.value = tag
  notice.value = null
  try {
    notice.value = await untagImage({ image: tag })
    await loadImages()
  } catch (err) {
    notice.value = { ok: false, message: '删除镜像标签请求失败。', data: {}, error: String(err), timestamp: new Date().toISOString() }
  } finally {
    busyTag.value = null
  }
}

async function handleImportFileChange(event: Event) {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) return
  importForm.value.file = file
  target.value = ''
}

async function handlePruneImages() {
  const scope = pruneDanglingOnly.value ? '悬空镜像' : '所有未使用镜像'
  const confirmed = await requestConfirm({
    title: '清理镜像',
    message: `确认清理${scope}？`,
    confirmText: '清理',
    intent: 'danger',
    icon: 'delete_sweep',
  })
  if (!confirmed) return
  pruning.value = true
  notice.value = null
  try {
    notice.value = await pruneImages({ dangling_only: pruneDanglingOnly.value, approve: true })
    await loadImages()
  } catch (err) {
    notice.value = { ok: false, message: '镜像清理请求失败。', data: {}, error: String(err), timestamp: new Date().toISOString() }
  } finally {
    pruning.value = false
  }
}

async function loadImages() {
  loading.value = true
  try {
    response.value = await listImages()
    imageSelection.sync((response.value.images ?? []).map((image) => image.id))
  } catch (err) {
    console.error('Failed to load images:', err)
  } finally {
    loading.value = false
  }
}

onMounted(loadImages)
</script>

<style scoped>
.spinning {
  animation: spin 0.9s linear infinite;
}

.header-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: flex-end;
}

.image-workbench {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 18px;
  margin-bottom: 18px;
}

.cleanup-panel,
.image-list-panel {
  padding: 18px;
}

.panel-heading {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  align-items: flex-start;
  margin-bottom: 16px;
}

.panel-heading h2 {
  margin: 0;
  color: var(--md-sys-color-on-surface);
  font-size: 20px;
}

.panel-heading > .material-symbol {
  color: var(--md-sys-color-primary);
  font-size: 24px;
}

.file-input {
  display: none;
}

.pull-progress-panel {
  display: grid;
  gap: 10px;
  min-width: 0;
  margin-top: 14px;
  padding: 14px;
  border: 1px solid var(--md-sys-color-outline-variant);
  border-radius: 18px;
  background: var(--md-sys-color-surface-container-lowest);
}

.pull-progress-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  min-width: 0;
}

.pull-progress-head div {
  display: flex;
  gap: 8px;
  align-items: center;
  min-width: 0;
}

.pull-progress-head strong {
  min-width: 0;
  overflow: hidden;
  color: var(--md-sys-color-on-surface);
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pull-progress-head .material-symbol {
  color: var(--md-sys-color-primary);
  font-size: 18px;
}

.pull-percent {
  color: var(--md-sys-color-primary);
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 800;
}

.pull-track {
  position: relative;
  overflow: hidden;
  height: 8px;
  border-radius: 999px;
  background: var(--md-sys-color-surface-container-high);
}

.pull-track span {
  position: absolute;
  inset: 0 auto 0 0;
  border-radius: inherit;
  background: linear-gradient(90deg, var(--md-sys-color-primary), color-mix(in srgb, var(--md-sys-color-primary) 62%, #22c55e));
  transition: width 0.24s var(--ease-standard);
}

.pull-track.indeterminate span {
  width: 38%;
  animation: pull-indeterminate 1.15s ease-in-out infinite;
}

.pull-layer-list {
  display: grid;
  gap: 6px;
}

.pull-layer-row {
  display: grid;
  grid-template-columns: minmax(74px, 0.7fr) minmax(0, 1fr) 48px;
  gap: 8px;
  align-items: center;
  min-height: 30px;
  padding: 0 8px;
  border-radius: 12px;
  background: var(--md-sys-color-surface-container-low);
  color: var(--md-sys-color-on-surface-variant);
  font-size: 12px;
}

.pull-layer-row span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pull-layer-row strong {
  color: var(--md-sys-color-on-surface);
  font-family: var(--font-mono);
  font-size: 12px;
  text-align: right;
}

.pull-error {
  margin: 0;
  color: var(--md-sys-color-error);
  font-size: 12px;
  font-weight: 700;
  overflow-wrap: anywhere;
}

.toggle-row {
  display: grid;
  grid-template-columns: 20px 1fr;
  gap: 12px;
  align-items: start;
  margin-bottom: 16px;
  color: var(--md-sys-color-on-surface);
  cursor: pointer;
}

.toggle-row input {
  width: 18px;
  height: 18px;
  margin-top: 2px;
  accent-color: var(--md-sys-color-primary);
}

.toggle-row strong,
.toggle-row small {
  display: block;
}

.toggle-row small {
  margin-top: 4px;
  color: var(--md-sys-color-on-surface-variant);
  font-size: 12px;
  line-height: 1.45;
}

.tag-chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}

.tag-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  max-width: 100%;
  min-height: 30px;
  padding: 0 9px;
  border-radius: 15px;
  background: var(--md-sys-color-primary-container);
  color: var(--md-sys-color-on-primary-container);
  cursor: pointer;
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 800;
  overflow-wrap: anywhere;
}

.tag-chip:disabled {
  opacity: 0.48;
  cursor: not-allowed;
}

.tag-chip.locked {
  background: var(--md-sys-color-surface-container-high);
  color: var(--md-sys-color-on-surface-variant);
}

.tag-chip .material-symbol {
  font-size: 15px;
}

.tag-manager {
  display: grid;
  gap: 10px;
}

.tag-guard {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  width: fit-content;
  max-width: 100%;
  margin: 0;
  padding: 7px 10px;
  border-radius: 16px;
  background: var(--md-sys-color-surface-container-high);
  color: var(--md-sys-color-on-surface-variant);
  font-size: 12px;
  font-weight: 700;
  line-height: 1.4;
}

.tag-guard .material-symbol {
  flex: 0 0 auto;
  color: var(--md-sys-color-primary);
  font-size: 16px;
}

.inline-tag-form {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 150px auto;
  gap: 10px;
  align-items: end;
  margin-top: 4px;
  padding-top: 10px;
  border-top: 1px solid var(--md-sys-color-outline-variant);
}

.list-summary {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
  color: var(--md-sys-color-on-surface-variant);
  font-size: 13px;
  font-weight: 700;
}

.image-table {
  display: grid;
}

.image-groups {
  display: grid;
  gap: 18px;
}

.image-group {
  display: grid;
  gap: 8px;
}

.group-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 18px;
  background: var(--md-sys-color-surface-container-low);
}

.group-heading h2 {
  margin: 0;
  color: var(--md-sys-color-on-surface);
  font-size: 16px;
  font-weight: 800;
}

.group-heading span {
  color: var(--md-sys-color-on-surface-variant);
  font-size: 12px;
  font-weight: 800;
}

.group-heading > .material-symbol {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border-radius: 13px;
  background: var(--md-sys-color-primary-container);
  color: var(--md-sys-color-primary);
  font-size: 20px;
}

.table-head,
.table-row-main {
  display: grid;
  grid-template-columns: 30px minmax(180px, 1.2fr) minmax(130px, 0.7fr) 96px minmax(150px, 0.8fr) 120px minmax(96px, auto);
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

.image-row {
  border-bottom: 1px solid var(--md-sys-color-outline-variant);
  font-size: 14px;
}

.image-row.expanded {
  border-radius: 16px;
  background: var(--md-sys-color-surface-container-low);
  border-color: color-mix(in srgb, var(--md-sys-color-primary) 30%, var(--md-sys-color-outline-variant));
  box-shadow: var(--md-elevation-1);
}

.image-row.untagged {
  background: color-mix(in srgb, var(--state-warning-container) 20%, transparent);
}

.image-row:last-child {
  border-bottom: none;
}

.table-row-main {
  min-height: 68px;
  padding: 12px;
}

.tag-stack strong,
.tag-stack small {
  display: block;
}

.tag-stack strong {
  overflow-wrap: anywhere;
}

.tag-stack small {
  margin-top: 4px;
  color: var(--text-faint);
  font-size: 12px;
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

.inline-detail {
  margin: 0 12px 12px;
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

.label-list {
  display: grid;
  gap: 8px;
}

.label-row {
  display: grid;
  grid-template-columns: minmax(160px, 0.7fr) minmax(0, 1fr);
  gap: 10px;
  padding: 10px 12px;
  border-radius: 14px;
  background: var(--md-sys-color-surface-container-low);
}

.label-row span,
.label-row strong {
  min-width: 0;
  color: var(--md-sys-color-on-surface-variant);
  font-family: var(--font-mono);
  font-size: 12px;
  overflow-wrap: anywhere;
}

.label-row strong {
  color: var(--md-sys-color-on-surface);
}

.empty-state.compact {
  padding: 24px;
}

.image-import-backdrop {
  position: fixed;
  inset: 0;
  z-index: 80;
  display: grid;
  place-items: center;
  padding: 28px;
  background: color-mix(in srgb, #101418 42%, transparent);
  backdrop-filter: blur(10px);
}

.image-import-dialog {
  display: grid;
  grid-template-rows: auto auto minmax(0, 1fr) auto;
  width: min(820px, 100%);
  max-height: min(760px, calc(100vh - 56px));
  overflow: hidden;
  border: 1px solid var(--md-sys-color-outline-variant);
  border-radius: 28px;
  background: var(--md-sys-color-surface);
  box-shadow: var(--md-elevation-3);
}

.wizard-header,
.wizard-footer {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 18px 20px;
}

.wizard-header {
  justify-content: space-between;
  border-bottom: 1px solid var(--md-sys-color-outline-variant);
}

.wizard-header h2 {
  margin: 0;
  color: var(--md-sys-color-on-surface);
  font-size: 24px;
  line-height: 1.2;
  font-weight: 800;
}

.wizard-steps {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 14px 20px;
  border-bottom: 1px solid var(--md-sys-color-outline-variant);
  background: var(--md-sys-color-surface-container-lowest);
}

.step-pill {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  min-height: 36px;
  padding: 0 12px;
  border-radius: 18px;
  background: var(--md-sys-color-surface-container);
  color: var(--md-sys-color-on-surface-variant);
  cursor: pointer;
  font-size: 12px;
  font-weight: 800;
  transition: background-color 0.18s ease, color 0.18s ease, transform 0.18s ease;
}

.step-pill.active,
.step-pill.done {
  background: var(--md-sys-color-primary-container);
  color: var(--md-sys-color-on-primary-container);
}

.step-pill:active:not(:disabled) {
  transform: scale(0.97);
}

.step-pill:disabled {
  opacity: 0.42;
  cursor: not-allowed;
}

.step-pill .material-symbol {
  font-size: 17px;
}

.image-import-body {
  min-height: 0;
  overflow: auto;
  padding: 20px;
}

.wizard-page {
  display: grid;
  gap: 16px;
}

.source-choice-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.source-choice {
  display: grid;
  gap: 8px;
  min-height: 150px;
  padding: 18px;
  border: 1px solid var(--md-sys-color-outline-variant);
  border-radius: 22px;
  background: var(--md-sys-color-surface-container-low);
  color: var(--md-sys-color-on-surface);
  cursor: pointer;
  text-align: left;
  transition: border-color 0.18s ease, background-color 0.18s ease, box-shadow 0.18s ease, transform 0.18s ease;
}

.source-choice:hover,
.source-choice.selected {
  border-color: color-mix(in srgb, var(--md-sys-color-primary) 42%, var(--md-sys-color-outline-variant));
  background: var(--md-sys-color-primary-container);
  box-shadow: var(--md-elevation-1);
}

.source-choice:active {
  transform: scale(0.985);
}

.source-choice .material-symbol {
  color: var(--md-sys-color-primary);
  font-size: 28px;
}

.source-choice strong {
  font-size: 16px;
  font-weight: 800;
}

.source-choice small {
  color: var(--md-sys-color-on-surface-variant);
  line-height: 1.5;
}

.field-row {
  display: grid;
  gap: 7px;
  min-width: 0;
}

.field-row.wide {
  grid-column: 1 / -1;
}

.field-row span {
  color: var(--md-sys-color-on-surface-variant);
  font-size: 12px;
  font-weight: 800;
}

.upload-drop {
  display: grid;
  place-items: center;
  gap: 12px;
  min-height: 180px;
  padding: 24px;
  border: 1px dashed color-mix(in srgb, var(--md-sys-color-primary) 45%, var(--md-sys-color-outline-variant));
  border-radius: 22px;
  background: var(--md-sys-color-surface-container-low);
  text-align: center;
}

.upload-drop strong {
  max-width: 100%;
  color: var(--md-sys-color-on-surface);
  font-family: var(--font-mono);
  font-size: 12px;
  overflow-wrap: anywhere;
}

.switch-row {
  display: grid;
  grid-template-columns: 20px 1fr;
  gap: 12px;
  align-items: start;
  color: var(--md-sys-color-on-surface);
  cursor: pointer;
}

.switch-row input {
  width: 18px;
  height: 18px;
  margin-top: 2px;
  accent-color: var(--md-sys-color-primary);
}

.switch-row strong,
.switch-row small {
  display: block;
}

.switch-row small {
  margin-top: 4px;
  color: var(--md-sys-color-on-surface-variant);
  font-size: 12px;
  line-height: 1.45;
}

.retag-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 160px;
  gap: 12px;
}

.wizard-footer {
  justify-content: flex-end;
  border-top: 1px solid var(--md-sys-color-outline-variant);
  background: var(--md-sys-color-surface-container-lowest);
}

.wizard-fade-enter-active,
.wizard-fade-leave-active {
  transition: opacity 0.2s ease;
}

.wizard-fade-enter-active .image-import-dialog,
.wizard-fade-leave-active .image-import-dialog {
  transition: opacity 0.22s ease, transform 0.26s var(--ease-standard);
}

.wizard-fade-enter-from,
.wizard-fade-leave-to {
  opacity: 0;
}

.wizard-fade-enter-from .image-import-dialog,
.wizard-fade-leave-to .image-import-dialog {
  opacity: 0;
  transform: translateY(12px) scale(0.985);
}

@media (max-width: 1180px) {
  .image-workbench {
    grid-template-columns: 1fr;
  }

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

@media (max-width: 760px) {
  .inline-tag-form,
  .detail-grid,
  .label-row,
  .source-choice-grid,
  .retag-grid {
    grid-template-columns: 1fr;
  }

  .header-actions {
    justify-content: flex-start;
  }

  .image-import-backdrop {
    padding: 14px;
  }

  .wizard-footer {
    align-items: stretch;
    flex-direction: column-reverse;
  }

  .wizard-footer > button {
    width: 100%;
  }
}

@keyframes pull-indeterminate {
  0% {
    transform: translateX(-115%);
  }

  55% {
    transform: translateX(75%);
  }

  100% {
    transform: translateX(240%);
  }
}
</style>
