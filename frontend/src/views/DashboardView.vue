<template>
  <section class="page-shell dashboard-view">
    <header class="page-header">
      <div>
        <p class="eyebrow">运行总览</p>
        <h1 class="page-title">总览面板</h1>
        <p class="page-subtitle">查看 Docker 容器、Compose 项目和容器资源趋势。</p>
      </div>
      <button class="toolbar-button" type="button" @click="loadOverview" :disabled="loading">
        <span class="material-symbol" :class="{ spinning: loading }">{{ loading ? 'progress_activity' : 'refresh' }}</span>
        {{ loading ? '刷新中' : '刷新' }}
      </button>
    </header>

    <div v-if="overview?.error" class="error-banner">
      Docker 连接异常：{{ overview.error }}
    </div>

    <div class="dashboard-grid">
      <MotionSurface class="container-panel">
        <div class="panel-header">
          <div class="panel-title-row">
            <span class="panel-icon material-symbol">deployed_code</span>
            <div>
              <p class="eyebrow">容器状态</p>
              <h2>运行分布</h2>
            </div>
          </div>
          <span class="sync-time">{{ overview ? formatTime(overview.timestamp) : '等待同步' }}</span>
        </div>

        <div class="state-grid">
          <div class="state-cell">
            <span>全部容器</span>
            <strong>{{ overview?.containers_total ?? '--' }}</strong>
          </div>
          <div class="state-cell running">
            <span>运行中</span>
            <strong>{{ overview?.running_containers ?? '--' }}</strong>
          </div>
          <div class="state-cell stopped">
            <span>非运行</span>
            <strong>{{ overview?.stopped_containers ?? '--' }}</strong>
          </div>
          <div class="state-cell compose">
            <span>Compose 项目</span>
            <strong>{{ overview?.compose_projects ?? '--' }}</strong>
          </div>
        </div>
      </MotionSurface>

      <MotionSurface class="resource-panel" :expanded="cpuDetailsOpen" :delay="45">
        <div class="panel-header">
          <div class="panel-title-row">
            <span class="panel-icon material-symbol">speed</span>
            <div>
              <p class="eyebrow">CPU 占用</p>
              <h2>容器 CPU 负载</h2>
            </div>
          </div>
        </div>

        <div class="kuma-summary">
          <div class="kuma-summary-head">
            <span class="percentage-tag" :class="usageLevel(totalCpuGaugePercent)">{{ formatPercent(totalCpuPercent) }}</span>
            <div class="kuma-summary-name">
              <span class="material-symbol">monitoring</span>
              <span>容器 CPU 总占用</span>
            </div>
          </div>
          <div class="kuma-bars-container">
            <div class="kuma-bars">
              <div v-for="bar in totalBars" :key="`cpu-bar-${bar}`" class="kuma-bar-bg" :title="formatPercent(totalCpuPercent)">
                <div
                  class="kuma-bar-fill"
                  :style="{
                    height: getBarHeight(totalCpuGaugePercent, bar, totalBars),
                    backgroundColor: getBarColor(totalCpuGaugePercent),
                    transitionDelay: `${bar * 0.015}s`,
                  }"
                ></div>
              </div>
            </div>
            <div class="kuma-bars-label">
              <span>0%</span>
              <span>100%</span>
            </div>
          </div>
        </div>

        <div class="line-chart-block">
          <div class="chart-title">
            <span>各容器 CPU 趋势</span>
            <span class="chart-scale-label">0 - {{ formatPercent(animatedCpuScale) }}</span>
          </div>
          <div v-if="cpuSeries.length" class="chart-shell">
            <div class="chart-plot" @mouseleave="clearChartTooltip">
              <svg class="line-chart" viewBox="0 0 100 72" preserveAspectRatio="none" role="img">
                <path class="chart-grid-line" d="M 0 18 H 100" />
                <path class="chart-grid-line" d="M 0 36 H 100" />
                <path class="chart-grid-line" d="M 0 54 H 100" />
                <g v-for="item in cpuSeries" :key="`cpu-points-${item.id}-${chartDrawKey}`" class="chart-points">
                  <circle
                    v-for="point in chartPoints(item.values, animatedCpuScale, chartSlideProgress)"
                    :key="`cpu-point-${item.id}-${point.index}`"
                    class="chart-hit-area"
                    :cx="point.x"
                    :cy="point.y"
                    r="3.8"
                    fill="transparent"
                    tabindex="0"
                    @mouseenter="showChartTooltip('cpu', point)"
                    @focus="showChartTooltip('cpu', point)"
                    @blur="clearChartTooltip"
                  />
                </g>
                <polyline
                  v-for="item in cpuSeries"
                  :key="`cpu-line-${item.id}-${chartDrawKey}`"
                  class="chart-line"
                  :class="{ 'is-ready': chartLineReady }"
                  :points="linePoints(item.values, animatedCpuScale, chartSlideProgress)"
                  fill="none"
                  :stroke="item.color"
                  stroke-width="2.6"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                />
              </svg>
              <div v-if="chartTooltip && chartTooltip.metric === 'cpu'" class="chart-tooltip" :style="chartTooltipStyle">
                <div class="chart-tooltip-head">
                  <strong>CPU 采样</strong>
                  <span>{{ formatTime(chartTooltip.timestamp) }}</span>
                </div>
                <div class="chart-tooltip-list">
                  <div v-for="row in chartTooltip.rows" :key="`cpu-tip-${row.id}`" class="chart-tooltip-row">
                    <i :style="{ backgroundColor: row.color }"></i>
                    <span>{{ row.name }}</span>
                    <strong>{{ row.valueLabel }}</strong>
                  </div>
                </div>
              </div>
            </div>
            <div class="chart-legend">
              <span v-for="item in cpuSeries" :key="`cpu-legend-${item.id}`" class="legend-item" :title="item.name">
                <i :style="{ backgroundColor: item.color }"></i>
                <span>{{ item.name }}</span>
                <strong>{{ formatPercent(item.latest) }}</strong>
              </span>
            </div>
          </div>
          <div v-else class="empty-state compact-empty">等待 CPU 采样</div>
        </div>

        <div class="resource-details">
          <button class="details-toggle" :class="{ active: cpuDetailsOpen }" type="button" @click="cpuDetailsOpen = !cpuDetailsOpen">
            <span>CPU 排序明细</span>
            <small v-if="cpuRows.length > 3">共 {{ cpuRows.length }} 个</small>
            <span class="material-symbol">{{ cpuDetailsOpen ? 'expand_less' : 'expand_more' }}</span>
          </button>
          <Transition
            name="resource-expand"
            @before-enter="beforeExpand"
            @enter="enterExpand"
            @after-enter="afterExpand"
            @before-leave="beforeCollapse"
            @leave="leaveCollapse"
          >
            <div v-if="cpuDetailsOpen" class="resource-list limited-resource-list">
              <article v-for="row in cpuRows" :key="`cpu-detail-${row.id}`" class="resource-row">
                <div class="resource-topline">
                  <span class="resource-name" :title="row.name">{{ row.name }}</span>
                  <strong>{{ formatPercent(row.cpu_percent) }}</strong>
                </div>
                <div class="bar-track" aria-hidden="true">
                  <span class="bar-fill cpu" :style="{ width: `${clampPercent(row.cpu_percent)}%` }"></span>
                </div>
                <div class="resource-meta">
                  <span>{{ statusLabel(row.status) }}</span>
                  <span v-if="row.error" class="resource-error">{{ row.error }}</span>
                  <span v-else>{{ shortImage(row.image) }}</span>
                </div>
              </article>
              <div v-if="!cpuRows.length" class="empty-state compact-empty">暂无容器资源数据</div>
            </div>
          </Transition>
        </div>
      </MotionSurface>

      <MotionSurface class="resource-panel" :expanded="memoryDetailsOpen" :delay="90">
        <div class="panel-header">
          <div class="panel-title-row">
            <span class="panel-icon material-symbol">memory</span>
            <div>
              <p class="eyebrow">内存占用</p>
              <h2>容器工作集</h2>
            </div>
          </div>
        </div>

        <div class="kuma-summary">
          <div class="kuma-summary-head">
            <span class="percentage-tag" :class="usageLevel(totalMemoryPercent)">{{ formatPercent(totalMemoryPercent) }}</span>
            <div class="kuma-summary-name">
              <span class="material-symbol">monitoring</span>
              <span>容器内存总占用</span>
            </div>
          </div>
          <div class="kuma-bars-container">
            <div class="kuma-bars">
              <div v-for="bar in totalBars" :key="`memory-bar-${bar}`" class="kuma-bar-bg" :title="formatPercent(totalMemoryPercent)">
                <div
                  class="kuma-bar-fill"
                  :style="{
                    height: getBarHeight(totalMemoryPercent, bar, totalBars),
                    backgroundColor: getBarColor(totalMemoryPercent),
                    transitionDelay: `${bar * 0.015}s`,
                  }"
                ></div>
              </div>
            </div>
            <div class="kuma-bars-label">
              <span>{{ formatMemory(totalMemoryUsage, totalMemoryLimit) }}</span>
              <span>100%</span>
            </div>
          </div>
        </div>

        <div class="line-chart-block">
          <div class="chart-title">
            <span>各容器内存趋势</span>
            <span class="chart-scale-label">0 - {{ formatPercent(animatedMemoryScale) }}</span>
          </div>
          <div v-if="memorySeries.length" class="chart-shell">
            <div class="chart-plot" @mouseleave="clearChartTooltip">
              <svg class="line-chart" viewBox="0 0 100 72" preserveAspectRatio="none" role="img">
                <path class="chart-grid-line" d="M 0 18 H 100" />
                <path class="chart-grid-line" d="M 0 36 H 100" />
                <path class="chart-grid-line" d="M 0 54 H 100" />
                <g v-for="item in memorySeries" :key="`memory-points-${item.id}-${chartDrawKey}`" class="chart-points">
                  <circle
                    v-for="point in chartPoints(item.values, animatedMemoryScale, chartSlideProgress)"
                    :key="`memory-point-${item.id}-${point.index}`"
                    class="chart-hit-area"
                    :cx="point.x"
                    :cy="point.y"
                    r="3.8"
                    fill="transparent"
                    tabindex="0"
                    @mouseenter="showChartTooltip('memory', point)"
                    @focus="showChartTooltip('memory', point)"
                    @blur="clearChartTooltip"
                  />
                </g>
                <polyline
                  v-for="item in memorySeries"
                  :key="`memory-line-${item.id}-${chartDrawKey}`"
                  class="chart-line"
                  :class="{ 'is-ready': chartLineReady }"
                  :points="linePoints(item.values, animatedMemoryScale, chartSlideProgress)"
                  fill="none"
                  :stroke="item.color"
                  stroke-width="2.6"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                />
              </svg>
              <div v-if="chartTooltip && chartTooltip.metric === 'memory'" class="chart-tooltip" :style="chartTooltipStyle">
                <div class="chart-tooltip-head">
                  <strong>内存采样</strong>
                  <span>{{ formatTime(chartTooltip.timestamp) }}</span>
                </div>
                <div class="chart-tooltip-list">
                  <div v-for="row in chartTooltip.rows" :key="`memory-tip-${row.id}`" class="chart-tooltip-row">
                    <i :style="{ backgroundColor: row.color }"></i>
                    <span>{{ row.name }}</span>
                    <strong>{{ row.valueLabel }}</strong>
                  </div>
                </div>
              </div>
            </div>
            <div class="chart-legend">
              <span v-for="item in memorySeries" :key="`memory-legend-${item.id}`" class="legend-item" :title="item.name">
                <i :style="{ backgroundColor: item.color }"></i>
                <span>{{ item.name }}</span>
                <strong>{{ formatPercent(item.latest) }}</strong>
              </span>
            </div>
          </div>
          <div v-else class="empty-state compact-empty">等待内存采样</div>
        </div>

        <div class="resource-details">
          <button class="details-toggle" :class="{ active: memoryDetailsOpen }" type="button" @click="memoryDetailsOpen = !memoryDetailsOpen">
            <span>内存排序明细</span>
            <small v-if="memoryRows.length > 3">共 {{ memoryRows.length }} 个</small>
            <span class="material-symbol">{{ memoryDetailsOpen ? 'expand_less' : 'expand_more' }}</span>
          </button>
          <Transition
            name="resource-expand"
            @before-enter="beforeExpand"
            @enter="enterExpand"
            @after-enter="afterExpand"
            @before-leave="beforeCollapse"
            @leave="leaveCollapse"
          >
            <div v-if="memoryDetailsOpen" class="resource-list limited-resource-list">
              <article v-for="row in memoryRows" :key="`memory-detail-${row.id}`" class="resource-row">
                <div class="resource-topline">
                  <span class="resource-name" :title="row.name">{{ row.name }}</span>
                  <strong>{{ formatPercent(row.memory_percent) }}</strong>
                </div>
                <div class="bar-track" aria-hidden="true">
                  <span class="bar-fill memory" :style="{ width: `${clampPercent(row.memory_percent)}%` }"></span>
                </div>
                <div class="resource-meta">
                  <span>{{ formatMemory(row.memory_usage, row.memory_limit) }}</span>
                  <span>{{ statusLabel(row.status) }}</span>
                </div>
              </article>
              <div v-if="!memoryRows.length" class="empty-state compact-empty">暂无容器资源数据</div>
            </div>
          </Transition>
        </div>
      </MotionSurface>

      <MotionSurface class="storage-panel" :delay="135">
        <div class="panel-header">
          <div class="panel-title-row">
            <span class="panel-icon material-symbol">donut_large</span>
            <div>
              <p class="eyebrow">存储占用</p>
              <h2>容器大小分布</h2>
            </div>
          </div>
          <span class="storage-mode">{{ storageModeLabel }}</span>
        </div>

        <div class="storage-layout" ref="storageHoverArea" @mouseleave="clearStorageHover">
          <div class="storage-chart-area">
            <div class="storage-pie-wrap" :class="{ empty: !storageSlices.length }">
              <svg class="storage-pie" viewBox="0 0 200 200" role="img" aria-label="容器存储占用圆饼图">
                <circle class="storage-track" cx="100" cy="100" r="70" pathLength="100" />
                <circle
                  v-for="slice in storageSlices"
                  :key="`storage-slice-${slice.id}`"
                  class="storage-slice"
                  :class="{ active: hoveredStorageSlice?.id === slice.id }"
                  cx="100"
                  cy="100"
                  r="70"
                  pathLength="100"
                  :stroke="slice.color"
                  :stroke-dasharray="storageSliceDashArray(slice)"
                  :stroke-dashoffset="slice.dashOffset"
                  tabindex="0"
                  @mouseenter="setStorageHover(slice, $event)"
                  @focus="hoveredStorageSlice = slice"
                  @blur="clearStorageHover"
                >
                  <title>{{ storageSliceTitle(slice) }}</title>
                </circle>
              </svg>
              <div class="storage-pie-center">
                <span>总占用</span>
                <strong>{{ storageTotalParts.value }}</strong>
                <small>{{ storageTotalParts.unit }}</small>
              </div>
            </div>
          </div>

          <div class="storage-list">
            <article
              v-for="slice in storageSlices"
              :key="`storage-${slice.id}`"
              class="storage-name-row"
              :class="{ active: hoveredStorageSlice?.id === slice.id }"
              @mouseenter="setStorageHover(slice, $event)"
              @mouseleave="clearStorageHover"
            >
              <span class="storage-color" :style="{ backgroundColor: slice.color }"></span>
              <span :title="slice.name">{{ slice.name }}</span>
            </article>
            <div v-if="!storageSlices.length" class="empty-state compact-empty">暂无容器大小数据</div>
          </div>

          <Transition name="storage-tooltip">
            <div v-if="hoveredStorageSlice" class="storage-detail-popover" :style="storagePopoverStyle">
              <div class="storage-detail-head">
                <span class="storage-color" :style="{ backgroundColor: hoveredStorageSlice.color }"></span>
                <strong>{{ hoveredStorageSlice.name }}</strong>
              </div>
              <dl>
                <div>
                  <dt>占用</dt>
                  <dd>{{ formatBytes(hoveredStorageSlice.chartSize) }}</dd>
                </div>
                <div>
                  <dt>比例</dt>
                  <dd>{{ formatPercent(hoveredStorageSlice.percent) }}</dd>
                </div>
                <div>
                  <dt>状态</dt>
                  <dd>{{ statusLabel(hoveredStorageSlice.status) }}</dd>
                </div>
                <div>
                  <dt>镜像</dt>
                  <dd>{{ shortImage(hoveredStorageSlice.image) }}</dd>
                </div>
                <div v-if="hoveredStorageSlice.virtualSize !== hoveredStorageSlice.chartSize">
                  <dt>虚拟大小</dt>
                  <dd>{{ formatBytes(hoveredStorageSlice.virtualSize) }}</dd>
                </div>
              </dl>
            </div>
          </Transition>
        </div>
      </MotionSurface>
    </div>

  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { getOverview } from '../api'
import type { ContainerResourceUsage, OverviewResponse } from '../api/types'
import MotionSurface from '../components/MotionSurface.vue'

interface ResourceSample {
  timestamp: string
  resources: ContainerResourceUsage[]
}

interface ChartSeries {
  id: string
  name: string
  color: string
  values: number[]
  latest: number
}

interface ChartPoint {
  index: number
  sampleIndex: number
  x: number
  y: number
  latest: boolean
}

interface ChartTooltipRow {
  id: string
  name: string
  color: string
  value: number
  valueLabel: string
}

interface ChartTooltip {
  metric: 'cpu' | 'memory'
  sampleIndex: number
  timestamp: string
  rows: ChartTooltipRow[]
  x: number
  y: number
}

interface StorageSlice {
  id: string
  name: string
  image?: string | null
  status: string
  storageSize: number
  virtualSize: number
  chartSize: number
  percent: number
  offset: number
  dashOffset: number
  color: string
}

const overview = ref<OverviewResponse | null>(null)
const loading = ref(false)
const resourceHistory = ref<ResourceSample[]>([])
const storageHoverArea = ref<HTMLElement | null>(null)
const cpuDetailsOpen = ref(false)
const memoryDetailsOpen = ref(false)
const hoveredStorageSlice = ref<StorageSlice | null>(null)
const storagePopoverPosition = ref<{ x: number; y: number } | null>(null)
const animatedCpuScale = ref(100)
const animatedMemoryScale = ref(100)
const chartSlideProgress = ref(1)
const chartDrawKey = ref(0)
const chartLineReady = ref(false)
const chartTooltip = ref<ChartTooltip | null>(null)

const totalBars = 40
const maxHistorySamples = 24
const refreshIntervalMs = 8000
const chartLeftPadding = 5
const chartRightPadding = 5
const chartTopPadding = 6
const chartBottomPadding = 6
let refreshTimer: ReturnType<typeof window.setInterval> | null = null
let chartSlideAnimation = 0
let chartLineReadyFrame = 0

// 这里使用 CSS 变量，让每条曲线都跟随当前主题色。
const seriesColors = [
  'var(--md-sys-color-primary)',
  'var(--state-info)',
  'var(--state-success)',
  'var(--state-warning)',
  'var(--md-sys-color-error)',
  'var(--md-sys-color-tertiary, #7b61ff)',
  '#00897b',
  '#5f6368',
]

const resourceRows = computed(() => overview.value?.container_resources ?? [])
const cpuRows = computed(() => sortResources(resourceRows.value, 'cpu_percent'))
const memoryRows = computed(() => sortResources(resourceRows.value, 'memory_percent'))
const totalCpuPercent = computed(() => roundValue(resourceRows.value.reduce((sum, row) => sum + safeNumber(row.cpu_percent), 0)))
const totalCpuGaugePercent = computed(() => clampPercent(totalCpuPercent.value))
const totalMemoryUsage = computed(() => resourceRows.value.reduce((sum, row) => sum + safeNumber(row.memory_usage), 0))
const totalMemoryLimit = computed(() => {
  const limits = resourceRows.value.map((row) => row.memory_limit || 0).filter((value) => value > 0)
  return limits.length ? Math.max(...limits) : null
})
const totalMemoryPercent = computed(() => {
  if (totalMemoryLimit.value) return roundValue((totalMemoryUsage.value / totalMemoryLimit.value) * 100)
  return roundValue(resourceRows.value.reduce((sum, row) => sum + safeNumber(row.memory_percent), 0))
})
const cpuSeries = computed(() => buildSeries('cpu_percent', cpuRows.value))
const memorySeries = computed(() => buildSeries('memory_percent', memoryRows.value))
const cpuScaleTarget = computed(() => niceScaleMax(cpuSeries.value))
const memoryScaleTarget = computed(() => niceScaleMax(memorySeries.value))
const storageRows = computed(() =>
  [...resourceRows.value]
    .map((row) => ({
      ...row,
      storage_size: safeNumber(row.storage_size),
      storage_virtual_size: safeNumber(row.storage_virtual_size),
    }))
    .filter((row) => row.storage_size > 0 || row.storage_virtual_size > 0)
    .sort((first, second) => {
      const byWritableSize = second.storage_size - first.storage_size
      if (byWritableSize !== 0) return byWritableSize
      const byVirtualSize = second.storage_virtual_size - first.storage_virtual_size
      if (byVirtualSize !== 0) return byVirtualSize
      return first.name.localeCompare(second.name, 'zh-CN')
    }),
)
const totalStorageSize = computed(() => storageRows.value.reduce((sum, row) => sum + row.storage_size, 0))
const totalVirtualStorageSize = computed(() => storageRows.value.reduce((sum, row) => sum + row.storage_virtual_size, 0))
const storageUsesVirtualSize = computed(() => totalStorageSize.value <= 0 && totalVirtualStorageSize.value > 0)
const storageChartTotal = computed(() => (storageUsesVirtualSize.value ? totalVirtualStorageSize.value : totalStorageSize.value))
const storageModeLabel = computed(() => (storageUsesVirtualSize.value ? '按虚拟大小展示' : '按可写层展示'))
const storageTotalParts = computed(() => formatBytesParts(storageChartTotal.value))
const storagePopoverStyle = computed(() => {
  if (!storagePopoverPosition.value) return {}
  return {
    left: `${storagePopoverPosition.value.x}px`,
    top: `${storagePopoverPosition.value.y}px`,
    transform: 'none',
  }
})
const chartTooltipStyle = computed(() => {
  if (!chartTooltip.value) return {}
  const x = Math.min(Math.max(chartTooltip.value.x, 6), 94)
  const y = Math.min(Math.max((chartTooltip.value.y / 72) * 100, 12), 88)
  const transform = x > 68 ? 'translate(calc(-100% - 12px), -50%)' : 'translate(12px, -50%)'
  return {
    left: `${x}%`,
    top: `${y}%`,
    transform,
  }
})
const storageSlices = computed<StorageSlice[]>(() => {
  const total = storageChartTotal.value
  if (total <= 0) return []

  let offset = 0
  return storageRows.value.map((row, index) => {
    const chartSize = storageUsesVirtualSize.value ? row.storage_virtual_size : row.storage_size
    const percent = (chartSize / total) * 100
    const slice = {
      id: row.id,
      name: row.name,
      image: row.image,
      status: row.status,
      storageSize: row.storage_size,
      virtualSize: row.storage_virtual_size,
      chartSize,
      percent,
      offset,
      dashOffset: -offset,
      color: seriesColors[index % seriesColors.length],
    }
    offset += percent
    return slice
  })
})

let cpuScaleAnimation = 0
let memoryScaleAnimation = 0

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function sortResources(rows: ContainerResourceUsage[], key: 'cpu_percent' | 'memory_percent'): ContainerResourceUsage[] {
  return [...rows].sort((first, second) => {
    const byValue = second[key] - first[key]
    if (byValue !== 0) return byValue
    if (first.status === 'running' && second.status !== 'running') return -1
    if (first.status !== 'running' && second.status === 'running') return 1
    return first.name.localeCompare(second.name, 'zh-CN')
  })
}

function buildSeries(key: 'cpu_percent' | 'memory_percent', sortedRows: ContainerResourceUsage[]): ChartSeries[] {
  // 保留排序后的容器顺序用于图例；缺失采样用 0 补齐。
  return sortedRows.map((row, index) => ({
    id: row.id,
    name: row.name,
    color: seriesColors[index % seriesColors.length],
    latest: safeNumber(row[key]),
    values: resourceHistory.value.map((sample) => {
      const match = sample.resources.find((item) => item.id === row.id)
      return match ? safeNumber(match[key]) : 0
    }),
  }))
}

function linePoints(values: number[], scaleMax: number, slideProgress = 1): string {
  return chartPoints(values, scaleMax, slideProgress)
    .map((point) => `${point.x.toFixed(2)},${point.y.toFixed(2)}`)
    .join(' ')
}

function chartPoints(values: number[], scaleMax: number, slideProgress = 1): ChartPoint[] {
  const originalCount = values.length
  const padded = originalCount > 1 ? values : [values[0] ?? 0, values[0] ?? 0]
  const visibleValues = padded.slice(-maxHistorySamples)
  const scale = Math.max(scaleMax, 1)
  const usableWidth = 100 - chartLeftPadding - chartRightPadding
  const slotWidth = usableWidth / Math.max(maxHistorySamples - 1, 1)
  const visibleCount = visibleValues.length
  const startIndex = Math.max(originalCount - visibleCount, 0)
  const latestIndex = visibleValues.length - 1
  const startOffset = chartLeftPadding + (maxHistorySamples - visibleCount) * slotWidth

  return visibleValues
    .map((value, index) => {
      const sampleIndex = Math.min(startIndex + index, Math.max(originalCount - 1, 0))
      const baseX = startOffset + index * slotWidth
      const x = baseX + slotWidth * (1 - slideProgress)
      const safeValue = Math.min(Math.max(safeNumber(value), 0), scale)
      const y = 72 - chartBottomPadding - (safeValue / scale) * (72 - chartTopPadding - chartBottomPadding)
      return {
        index,
        sampleIndex,
        x,
        y,
        latest: index === latestIndex,
      }
    })
    .filter((point) => point.x >= chartLeftPadding - slotWidth && point.x <= 100 - chartRightPadding + slotWidth)
}

function showChartTooltip(metric: 'cpu' | 'memory', point: ChartPoint) {
  const sample = resourceHistory.value[point.sampleIndex]
  if (!sample) return

  const key = metric === 'cpu' ? 'cpu_percent' : 'memory_percent'
  const sortedRows = sortResources(sample.resources, key)
  chartTooltip.value = {
    metric,
    sampleIndex: point.sampleIndex,
    timestamp: sample.timestamp,
    x: point.x,
    y: point.y,
    rows: sortedRows.map((row, index) => ({
      id: row.id,
      name: row.name,
      color: seriesColors[index % seriesColors.length],
      value: safeNumber(row[key]),
      valueLabel: formatPercent(row[key]),
    })),
  }
}

function clearChartTooltip() {
  chartTooltip.value = null
}

function runChartSlideAnimation() {
  if (chartSlideAnimation) window.cancelAnimationFrame(chartSlideAnimation)

  const startTime = performance.now()
  const duration = 680
  const tick = (now: number) => {
    const progress = Math.min((now - startTime) / duration, 1)
    chartSlideProgress.value = 1 - Math.pow(1 - progress, 3)
    if (progress < 1) {
      chartSlideAnimation = window.requestAnimationFrame(tick)
      return
    }
    chartSlideProgress.value = 1
    chartSlideAnimation = 0
  }

  chartSlideAnimation = window.requestAnimationFrame(tick)
}

async function animateChartRefresh(shouldSlide: boolean, hasChartData: boolean) {
  if (chartSlideAnimation) window.cancelAnimationFrame(chartSlideAnimation)
  if (chartLineReadyFrame) window.cancelAnimationFrame(chartLineReadyFrame)
  chartSlideAnimation = 0
  chartLineReadyFrame = 0
  chartTooltip.value = null
  chartLineReady.value = false
  chartSlideProgress.value = shouldSlide ? 0 : 1
  chartDrawKey.value += 1

  await nextTick()

  if (!hasChartData) {
    chartLineReady.value = true
    return
  }

  chartLineReadyFrame = window.requestAnimationFrame(() => {
    chartLineReady.value = true
    chartLineReadyFrame = 0
    if (shouldSlide) runChartSlideAnimation()
  })
}

function niceScaleMax(series: ChartSeries[]): number {
  const maxValue = Math.max(0, ...series.flatMap((item) => item.values), ...series.map((item) => item.latest))
  // 把图表比例尺吸附到易读档位，避免指标微小变化导致坐标轴抖动。
  if (maxValue <= 1) return 1
  if (maxValue <= 5) return 5
  if (maxValue <= 10) return 10
  if (maxValue <= 25) return 25
  if (maxValue <= 50) return 50
  if (maxValue <= 100) return 100
  return Math.ceil(maxValue / 50) * 50
}

function animateScaleValue(target: number, current: typeof animatedCpuScale, frame: 'cpu' | 'memory') {
  const start = current.value
  const end = Math.max(target, 1)
  const startTime = performance.now()
  const duration = 380
  const previousFrame = frame === 'cpu' ? cpuScaleAnimation : memoryScaleAnimation
  if (previousFrame) window.cancelAnimationFrame(previousFrame)

  const tick = (now: number) => {
    const progress = Math.min((now - startTime) / duration, 1)
    const eased = 1 - Math.pow(1 - progress, 3)
    current.value = roundValue(start + (end - start) * eased)
    if (progress < 1) {
      const nextFrame = window.requestAnimationFrame(tick)
      if (frame === 'cpu') cpuScaleAnimation = nextFrame
      else memoryScaleAnimation = nextFrame
      return
    }
    current.value = end
    if (frame === 'cpu') cpuScaleAnimation = 0
    else memoryScaleAnimation = 0
  }

  const nextFrame = window.requestAnimationFrame(tick)
  if (frame === 'cpu') cpuScaleAnimation = nextFrame
  else memoryScaleAnimation = nextFrame
}

function beforeExpand(element: Element) {
  const target = element as HTMLElement
  target.style.height = '0'
  target.style.opacity = '0'
  target.style.transform = 'scaleY(0.96)'
  target.style.transformOrigin = 'top'
  target.style.overflow = 'hidden'
}

function enterExpand(element: Element, done: () => void) {
  const target = element as HTMLElement
  const height = target.scrollHeight
  // 设置过渡目标前强制布局，确保高度动画从 0 开始。
  target.offsetHeight
  target.style.transition = 'height 0.28s var(--ease-standard), opacity 0.22s ease, transform 0.28s var(--ease-standard)'
  target.style.height = `${height}px`
  target.style.opacity = '1'
  target.style.transform = 'scaleY(1)'
  window.setTimeout(done, 300)
}

function afterExpand(element: Element) {
  const target = element as HTMLElement
  target.style.height = 'auto'
  target.style.overflow = ''
  target.style.transition = ''
  target.style.transform = ''
  target.style.opacity = ''
}

function beforeCollapse(element: Element) {
  const target = element as HTMLElement
  target.style.height = `${target.scrollHeight}px`
  target.style.opacity = '1'
  target.style.transform = 'scaleY(1)'
  target.style.transformOrigin = 'top'
  target.style.overflow = 'hidden'
}

function leaveCollapse(element: Element, done: () => void) {
  const target = element as HTMLElement
  // 固定当前高度后强制布局，确保收起动画能过渡到 0。
  target.offsetHeight
  target.style.transition = 'height 0.24s var(--ease-standard), opacity 0.2s ease, transform 0.24s var(--ease-standard)'
  target.style.height = '0'
  target.style.opacity = '0'
  target.style.transform = 'scaleY(0.96)'
  window.setTimeout(done, 260)
}

function getBarHeight(percent: number, index: number, total: number): string {
  const step = 100 / total
  const minForBar = (index - 1) * step
  const maxForBar = index * step
  const value = clampPercent(percent)
  if (value >= maxForBar) return '100%'
  if (value <= minForBar) return '0%'
  return `${((value - minForBar) / step) * 100}%`
}

function getBarColor(value: number): string {
  if (value <= 0) return 'var(--md-sys-color-outline-variant)'
  if (value < 60) return 'var(--state-success)'
  if (value < 85) return 'var(--state-warning)'
  return 'var(--md-sys-color-error)'
}

function usageLevel(value: number): string {
  if (value < 60) return 'success'
  if (value < 85) return 'warning'
  return 'danger'
}

function formatPercent(value: number): string {
  if (!Number.isFinite(value)) return '0.00%'
  return `${Math.max(value, 0).toFixed(2)}%`
}

function formatMemory(usage: number, limit?: number | null): string {
  const used = formatBytes(usage)
  return limit ? `${used} / ${formatBytes(limit)}` : used
}

function formatBytesParts(value: number): { value: string; unit: string } {
  if (!Number.isFinite(value) || value <= 0) return { value: '0', unit: 'B' }
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let size = value
  let index = 0
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024
    index += 1
  }

  const fractionDigits = index === 0 || size >= 100 ? 0 : 1
  return {
    value: size.toFixed(fractionDigits),
    unit: units[index],
  }
}

function formatBytes(value: number): string {
  if (!Number.isFinite(value) || value <= 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let size = value
  let index = 0
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024
    index += 1
  }
  return `${size.toFixed(index === 0 ? 0 : 1)} ${units[index]}`
}

function storageSliceDashArray(slice: StorageSlice): string {
  const percent = clampPercent(slice.percent)
  return `${percent} ${Math.max(100 - percent, 0)}`
}

function storageSliceTitle(slice: StorageSlice): string {
  return `${slice.name}：${formatBytes(slice.chartSize)}，${formatPercent(slice.percent)}`
}

function setStorageHover(slice: StorageSlice, event: MouseEvent | FocusEvent) {
  const previousId = hoveredStorageSlice.value?.id
  hoveredStorageSlice.value = slice
  if (event instanceof MouseEvent && (storagePopoverPosition.value === null || previousId !== slice.id)) {
    updateStoragePopoverPosition(event)
  }
}

function clearStorageHover() {
  hoveredStorageSlice.value = null
  storagePopoverPosition.value = null
}

function updateStoragePopoverPosition(event: MouseEvent) {
  const area = storageHoverArea.value
  if (!area) return

  const rect = area.getBoundingClientRect()
  const popoverWidth = 280
  const popoverHeight = 184
  const gap = 14
  const rawX = event.clientX - rect.left + gap
  const rawY = event.clientY - rect.top + gap
  const maxX = Math.max(rect.width - popoverWidth - 8, 8)
  const maxY = Math.max(rect.height - popoverHeight - 8, 8)

  storagePopoverPosition.value = {
    x: Math.min(Math.max(rawX, 8), maxX),
    y: Math.min(Math.max(rawY, 8), maxY),
  }
}

function shortImage(image?: string | null): string {
  if (!image) return '无镜像信息'
  return image.length > 42 ? `${image.slice(0, 39)}...` : image
}

function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    running: '运行中',
    exited: '已停止',
    created: '已创建',
    paused: '已暂停',
    restarting: '重启中',
  }
  return labels[status] ?? status
}

function safeNumber(value: number | null | undefined): number {
  return Number.isFinite(value) ? Number(value) : 0
}

function roundValue(value: number): number {
  return Math.round(value * 100) / 100
}

function clampPercent(value: number): number {
  return Math.min(Math.max(safeNumber(value), 0), 100)
}

async function recordResourceHistory(response: OverviewResponse) {
  const hadSamples = resourceHistory.value.length > 0
  // 只保留滑动窗口内的采样，避免长时间打开总览页造成数据无限增长。
  resourceHistory.value = [
    ...resourceHistory.value,
    { timestamp: response.timestamp, resources: response.container_resources },
  ].slice(-maxHistorySamples)
  await animateChartRefresh(hadSamples, response.container_resources.length > 0)
}

async function loadOverview() {
  if (loading.value) return
  loading.value = true
  try {
    const nextOverview = await getOverview()
    overview.value = nextOverview
    await recordResourceHistory(nextOverview)
  } catch (err) {
    console.error('Failed to load overview:', err)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadOverview()
  refreshTimer = window.setInterval(loadOverview, refreshIntervalMs)
})

onBeforeUnmount(() => {
  if (cpuScaleAnimation) window.cancelAnimationFrame(cpuScaleAnimation)
  if (memoryScaleAnimation) window.cancelAnimationFrame(memoryScaleAnimation)
  if (chartSlideAnimation) window.cancelAnimationFrame(chartSlideAnimation)
  if (chartLineReadyFrame) window.cancelAnimationFrame(chartLineReadyFrame)
  if (refreshTimer) {
    window.clearInterval(refreshTimer)
    refreshTimer = null
  }
})

watch(cpuScaleTarget, (target) => animateScaleValue(target, animatedCpuScale, 'cpu'), { immediate: true })
watch(memoryScaleTarget, (target) => animateScaleValue(target, animatedMemoryScale, 'memory'), { immediate: true })
</script>

<style scoped>
.toolbar-button {
  display: flex;
  align-items: center;
  gap: 8px;
}

.toolbar-button .material-symbol {
  font-size: 18px;
}

.spinning {
  animation: spin 0.9s linear infinite;
}

.error-banner {
  margin-bottom: 18px;
}

.dashboard-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
  align-items: stretch;
}

.container-panel,
.resource-panel,
.storage-panel {
  padding: 20px;
}

.container-panel {
  grid-column: 1 / -1;
}

.resource-panel {
  display: grid;
  align-content: start;
  gap: 16px;
}

.storage-panel {
  display: grid;
  grid-column: 1 / -1;
  gap: 16px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 16px;
}

.resource-panel .panel-header {
  margin-bottom: 0;
}

.panel-title-row {
  display: grid;
  grid-template-columns: 42px minmax(0, 1fr);
  gap: 12px;
  align-items: center;
  min-width: 0;
}

.panel-icon {
  display: grid;
  place-items: center;
  width: 42px;
  height: 42px;
  border-radius: 21px;
  background: var(--md-sys-color-secondary-container);
  color: var(--md-sys-color-on-primary-container);
  font-size: 21px;
}

.panel-header h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
}

.sync-time {
  color: var(--md-sys-color-on-surface-variant);
  font-family: var(--font-mono);
  font-size: 12px;
  white-space: nowrap;
}

.state-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.state-cell {
  display: grid;
  min-height: 98px;
  align-content: space-between;
  padding: 14px;
  border: 1px solid var(--md-sys-color-outline-variant);
  border-radius: 18px;
  background: var(--md-sys-color-surface-container-low);
}

.state-cell span {
  color: var(--md-sys-color-on-surface-variant);
  font-size: 12px;
  font-weight: 700;
}

.state-cell strong {
  color: var(--md-sys-color-on-surface);
  font-size: 34px;
  line-height: 1;
}

.state-cell.running strong {
  color: var(--state-success);
}

.state-cell.stopped strong {
  color: var(--md-sys-color-error);
}

.state-cell.compose strong {
  color: var(--md-sys-color-primary);
}

.docker-state {
  display: flex;
  align-items: center;
  gap: 9px;
  margin-top: 14px;
  min-height: 42px;
  padding: 0 12px;
  border-radius: 14px;
  background: var(--state-success-container);
  color: var(--state-success);
  font-size: 13px;
  font-weight: 700;
}

.docker-state.error {
  background: var(--md-sys-color-error-container);
  color: var(--md-sys-color-error);
}

.kuma-summary {
  display: grid;
  gap: 12px;
}

.kuma-summary-head {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.percentage-tag {
  display: inline-flex;
  justify-content: center;
  align-items: center;
  min-width: 72px;
  min-height: 30px;
  padding: 0 10px;
  border-radius: 999px;
  color: #fff;
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 800;
}

.percentage-tag.success {
  background: var(--state-success);
}

.percentage-tag.warning {
  background: var(--state-warning);
}

.percentage-tag.danger {
  background: var(--md-sys-color-error);
}

.kuma-summary-name {
  display: flex;
  align-items: center;
  gap: 7px;
  min-width: 0;
  color: var(--md-sys-color-on-surface);
  font-size: 14px;
  font-weight: 800;
}

.kuma-summary-name .material-symbol {
  color: var(--md-sys-color-primary);
  font-size: 18px;
}

.kuma-bars-container {
  display: grid;
  gap: 8px;
  width: 100%;
  min-width: 0;
}

.kuma-bars {
  display: flex;
  gap: 4px;
  width: 100%;
  height: 36px;
}

.kuma-bar-bg {
  display: flex;
  flex: 1;
  align-items: flex-end;
  min-width: 3px;
  overflow: hidden;
  border-radius: 5px;
  background: var(--md-sys-color-surface-container-high);
}

.kuma-bar-fill {
  width: 100%;
  border-radius: inherit;
  transition: height 0.6s cubic-bezier(0.34, 1.56, 0.64, 1), background-color 0.6s ease;
}

.kuma-bar-bg:hover .kuma-bar-fill {
  filter: brightness(0.86);
}

.kuma-bars-label {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  color: var(--md-sys-color-on-surface-variant);
  font-family: var(--font-mono);
  font-size: 11px;
  line-height: 1.4;
}

.line-chart-block {
  display: grid;
  gap: 10px;
  min-width: 0;
  padding-top: 2px;
}

.chart-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: var(--md-sys-color-on-surface-variant);
  font-size: 12px;
  font-weight: 800;
}

.chart-scale-label {
  color: var(--md-sys-color-primary);
  font-family: var(--font-mono);
  font-size: 11px;
  white-space: nowrap;
}

.chart-shell {
  display: grid;
  gap: 10px;
  min-width: 0;
}

.chart-plot {
  position: relative;
  min-width: 0;
}

.line-chart {
  width: 100%;
  height: 260px;
  overflow: visible;
  border-radius: 16px;
  background:
    linear-gradient(180deg, color-mix(in srgb, var(--md-sys-color-primary) 7%, transparent), transparent),
    var(--md-sys-color-surface-container-low);
  border: 1px solid var(--md-sys-color-outline-variant);
}

.chart-grid-line {
  stroke: var(--md-sys-color-outline-variant);
  stroke-dasharray: 2 4;
  stroke-width: 0.6;
  vector-effect: non-scaling-stroke;
}

.chart-line {
  opacity: 0;
  vector-effect: non-scaling-stroke;
  pointer-events: none;
  filter: drop-shadow(0 2px 3px color-mix(in srgb, var(--md-sys-color-shadow, #000) 15%, transparent));
}

.chart-line.is-ready {
  animation: chart-line-fade 0.32s var(--ease-standard) both;
}

.chart-hit-area {
  cursor: pointer;
  outline: none;
  pointer-events: all;
}

.chart-tooltip {
  position: absolute;
  z-index: 4;
  display: grid;
  gap: 10px;
  width: min(280px, calc(100% - 24px));
  max-height: 230px;
  padding: 12px;
  border: 1px solid color-mix(in srgb, var(--md-sys-color-primary) 26%, var(--md-sys-color-outline-variant));
  border-radius: 18px;
  background: color-mix(in srgb, var(--md-sys-color-surface) 94%, transparent);
  box-shadow: var(--md-elevation-2);
  pointer-events: none;
}

.chart-tooltip-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: baseline;
}

.chart-tooltip-head strong {
  color: var(--md-sys-color-on-surface);
  font-size: 13px;
}

.chart-tooltip-head span {
  color: var(--md-sys-color-on-surface-variant);
  font-family: var(--font-mono);
  font-size: 11px;
  white-space: nowrap;
}

.chart-tooltip-list {
  display: grid;
  gap: 7px;
  max-height: 168px;
  overflow-y: auto;
  padding-right: 4px;
}

.chart-tooltip-row {
  display: grid;
  grid-template-columns: 9px minmax(0, 1fr) auto;
  gap: 8px;
  align-items: center;
  min-width: 0;
  font-size: 12px;
  font-weight: 700;
}

.chart-tooltip-row i {
  width: 9px;
  height: 9px;
  border-radius: 50%;
}

.chart-tooltip-row span {
  min-width: 0;
  overflow: hidden;
  color: var(--md-sys-color-on-surface-variant);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chart-tooltip-row strong {
  color: var(--md-sys-color-on-surface);
  font-family: var(--font-mono);
  font-size: 11px;
}

.chart-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  min-width: 0;
}

.legend-item {
  display: inline-grid;
  grid-template-columns: 8px minmax(0, 1fr) auto;
  align-items: center;
  gap: 6px;
  max-width: 100%;
  min-height: 26px;
  padding: 0 8px;
  border-radius: 13px;
  background: var(--md-sys-color-surface-container-low);
  color: var(--md-sys-color-on-surface-variant);
  font-size: 11px;
  font-weight: 700;
}

.legend-item i {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.legend-item span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.legend-item strong {
  color: var(--md-sys-color-on-surface);
  font-family: var(--font-mono);
  font-weight: 800;
}

.resource-details {
  display: grid;
  gap: 12px;
}

.details-toggle {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 12px;
  width: 100%;
  min-height: 42px;
  padding: 0 12px;
  border-radius: 14px;
  background: var(--md-sys-color-surface-container-low);
  color: var(--md-sys-color-on-surface);
  cursor: pointer;
  font-size: 13px;
  font-weight: 800;
  transition: background-color 0.18s ease, color 0.18s ease, transform 0.18s ease;
}

.details-toggle:hover {
  background: var(--md-sys-color-surface-container);
}

.details-toggle:active {
  transform: scale(0.99);
}

.details-toggle.active {
  background: var(--md-sys-color-secondary-container);
  color: var(--md-sys-color-on-primary-container);
}

.details-toggle .material-symbol {
  color: var(--md-sys-color-on-surface-variant);
  font-size: 20px;
  transition: color 0.18s ease, transform 0.24s var(--ease-standard);
}

.details-toggle.active .material-symbol {
  color: var(--md-sys-color-on-primary-container);
  transform: rotate(180deg);
}

.details-toggle small {
  color: var(--md-sys-color-on-surface-variant);
  font-size: 11px;
  font-weight: 800;
  white-space: nowrap;
}

.resource-list {
  display: grid;
  gap: 14px;
  will-change: height, opacity, transform;
}

.limited-resource-list {
  max-height: 242px;
  overflow-y: auto;
  padding-right: 6px;
  overscroll-behavior: contain;
}

.resource-row {
  display: grid;
  gap: 8px;
  min-width: 0;
  padding-top: 12px;
  border-top: 1px solid var(--md-sys-color-outline-variant);
}

.resource-row:first-child {
  padding-top: 0;
  border-top: none;
}

.resource-topline,
.resource-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-width: 0;
}

.resource-name {
  min-width: 0;
  overflow: hidden;
  color: var(--md-sys-color-on-surface);
  font-size: 13px;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.resource-topline strong {
  color: var(--md-sys-color-primary);
  font-family: var(--font-mono);
  font-size: 13px;
  white-space: nowrap;
}

.bar-track {
  overflow: hidden;
  width: 100%;
  height: 10px;
  border-radius: 999px;
  background: var(--md-sys-color-surface-container-high);
}

.bar-fill {
  display: block;
  height: 100%;
  min-width: 2px;
  border-radius: inherit;
  transition: width 0.28s ease;
}

.bar-fill.cpu {
  background: var(--md-sys-color-primary);
}

.bar-fill.memory {
  background: var(--state-info);
}

.bar-fill.storage {
  transition: width 0.32s var(--ease-standard), background-color 0.2s ease;
}

.resource-meta {
  color: var(--md-sys-color-on-surface-variant);
  font-size: 12px;
  line-height: 1.4;
}

.resource-meta span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.resource-error {
  color: var(--md-sys-color-error);
}

.storage-mode {
  display: inline-flex;
  align-items: center;
  min-height: 30px;
  padding: 0 10px;
  border-radius: 999px;
  background: var(--md-sys-color-secondary-container);
  color: var(--md-sys-color-on-primary-container);
  font-size: 12px;
  font-weight: 800;
  white-space: nowrap;
}

.storage-layout {
  position: relative;
  display: grid;
  grid-template-columns: minmax(280px, 0.82fr) minmax(220px, 1fr);
  gap: 28px;
  align-items: center;
}

.storage-chart-area {
  position: relative;
  display: grid;
  place-items: center;
  min-width: 0;
}

.storage-pie-wrap {
  position: relative;
  display: grid;
  place-items: center;
  width: min(280px, 72vw);
  aspect-ratio: 1;
  transition: transform 0.24s var(--ease-standard);
}

.storage-pie-wrap:not(.empty):hover {
  transform: scale(1.01);
}

.storage-pie-wrap.empty {
  opacity: 0.72;
}

.storage-pie {
  width: 100%;
  height: 100%;
  overflow: visible;
  transform: rotate(-90deg);
}

.storage-track,
.storage-slice {
  fill: none;
  stroke-width: 44;
}

.storage-track {
  stroke: var(--md-sys-color-surface-container-high);
}

.storage-slice {
  cursor: pointer;
  transition: opacity 0.18s ease, stroke-width 0.2s var(--ease-standard), filter 0.2s ease;
}

.storage-slice:hover,
.storage-slice:focus,
.storage-slice.active {
  opacity: 0.92;
  outline: none;
  stroke-width: 50;
  filter: drop-shadow(0 4px 8px color-mix(in srgb, var(--md-sys-color-shadow, #000) 18%, transparent));
}

.storage-pie-center {
  position: absolute;
  inset: 50%;
  transform: translate(-50%, -50%);
  display: grid;
  grid-template-rows: auto minmax(0, auto) auto;
  place-items: center;
  width: 42%;
  min-width: 96px;
  max-width: 124px;
  aspect-ratio: 1;
  padding: 10px;
  border-radius: 50%;
  background: var(--md-sys-color-surface);
  box-shadow: var(--md-elevation-1);
  text-align: center;
  pointer-events: none;
}

.storage-pie-center span {
  color: var(--md-sys-color-on-surface-variant);
  font-size: 11px;
  font-weight: 800;
}

.storage-pie-center strong {
  max-width: 100%;
  overflow: hidden;
  color: var(--md-sys-color-on-surface);
  font-family: var(--font-mono);
  font-size: clamp(18px, 2.3vw, 26px);
  line-height: 1.1;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.storage-pie-center small {
  color: var(--md-sys-color-on-surface-variant);
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 800;
}

.storage-detail-popover {
  position: absolute;
  top: 50%;
  left: 50%;
  z-index: 3;
  width: min(280px, 92vw);
  min-width: 220px;
  padding: 14px;
  border: 1px solid color-mix(in srgb, var(--md-sys-color-primary) 22%, var(--md-sys-color-outline-variant));
  border-radius: 18px;
  background: color-mix(in srgb, var(--md-sys-color-surface) 92%, transparent);
  box-shadow: var(--md-elevation-3);
  backdrop-filter: blur(14px);
  transform: translate(-50%, -50%);
  pointer-events: none;
}

.storage-detail-head {
  display: grid;
  grid-template-columns: 10px minmax(0, 1fr);
  gap: 10px;
  align-items: center;
  margin-bottom: 10px;
}

.storage-detail-head strong {
  min-width: 0;
  overflow: hidden;
  color: var(--md-sys-color-on-surface);
  font-size: 14px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.storage-detail-popover dl {
  display: grid;
  gap: 8px;
  margin: 0;
}

.storage-detail-popover dl div {
  display: grid;
  grid-template-columns: 64px minmax(0, 1fr);
  gap: 10px;
}

.storage-detail-popover dt,
.storage-detail-popover dd {
  min-width: 0;
  margin: 0;
  overflow: hidden;
  font-size: 12px;
  line-height: 1.45;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.storage-detail-popover dt {
  color: var(--md-sys-color-on-surface-variant);
  font-weight: 700;
}

.storage-detail-popover dd {
  color: var(--md-sys-color-on-surface);
  font-weight: 800;
  text-align: right;
}

.storage-list {
  display: grid;
  align-content: start;
  gap: 8px;
  min-width: 0;
}

.storage-name-row {
  display: grid;
  grid-template-columns: 10px minmax(0, 1fr);
  align-items: center;
  gap: 10px;
  min-width: 0;
  min-height: 36px;
  padding: 0 10px;
  border-radius: 18px;
  color: var(--md-sys-color-on-surface);
  cursor: default;
  font-size: 13px;
  font-weight: 800;
  transition: background-color 0.18s ease, color 0.18s ease;
}

.storage-name-row:hover,
.storage-name-row.active {
  background: var(--md-sys-color-secondary-container);
  color: var(--md-sys-color-on-primary-container);
}

.storage-color {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.storage-name-row > span:last-child {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.storage-tooltip-enter-active,
.storage-tooltip-leave-active {
  transition: opacity 0.16s ease, transform 0.18s var(--ease-standard);
}

.storage-tooltip-enter-from,
.storage-tooltip-leave-to {
  opacity: 0;
  transform: translateY(6px) scale(0.98);
}

.compact-empty {
  min-height: 84px;
}

@keyframes chart-line-fade {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

@media (max-width: 1080px) {
  .state-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .storage-layout {
    grid-template-columns: 1fr;
    justify-items: stretch;
  }

}

@media (max-width: 720px) {
  .dashboard-grid {
    grid-template-columns: 1fr;
  }

  .panel-header,
  .resource-topline,
  .resource-meta,
  .kuma-summary-head {
    align-items: flex-start;
    flex-direction: column;
  }

  .sync-time {
    white-space: normal;
  }

  .kuma-bars {
    gap: 2px;
  }

  .line-chart {
    height: 118px;
  }

  .storage-pie-wrap {
    width: min(240px, 74vw);
  }

  .storage-detail-popover {
    position: static;
    width: 100%;
    margin-top: 12px;
    transform: none;
    pointer-events: auto;
  }
}
</style>
