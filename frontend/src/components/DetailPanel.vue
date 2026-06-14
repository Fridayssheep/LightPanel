<!--
  DetailPanel — 可展开详情面板的统一外壳。
  用于 ContainersView、ComposeView 等处展示日志/编辑器等内联详情。
  提供 topbar(tabs + close) + 内容 pane + loading/error 状态。
  切换 tab 时内容高度平滑过渡，兄弟元素不会瞬移。
-->
<template>
  <div class="detail-panel" role="region" :aria-label="ariaLabel">
    <!-- 顶部工具栏：tabs + 关闭按钮 -->
    <div class="detail-topbar">
      <div class="detail-tabs" role="tablist" :aria-label="tabsLabel">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          class="detail-tab"
          :class="{ active: modelValue === tab.key }"
          type="button"
          :disabled="tab.disabled"
          :title="tab.title"
          @click="$emit('update:modelValue', tab.key)"
        >
          <span class="material-symbol">{{ tab.icon }}</span>
          {{ tab.label }}
        </button>
      </div>
      <button class="icon-button" type="button" title="收起" @click="$emit('close')">
        <span class="material-symbol">close</span>
      </button>
    </div>

    <!-- 内容区域：高度变化时平滑过渡 -->
    <div ref="paneRef" class="detail-pane">
      <Transition
        name="tab-fade"
        mode="out-in"
        @before-leave="lockHeight"
        @enter="animateHeight"
        @after-enter="unlockHeight"
      >
        <div v-if="loading" key="loading" class="inline-loading">
          <span class="material-symbol spinning">progress_activity</span>
          {{ loadingText }}
        </div>
        <div v-else-if="error" key="error" class="error-banner inline">
          {{ error }}
        </div>
        <div v-else :key="modelValue" class="pane-content">
          <slot />
        </div>
      </Transition>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * @prop tabs       — tab 配置列表 [{key, label, icon, disabled?, title?}]
 * @prop modelValue — 当前激活的 tab key (v-model)
 * @prop loading    — 是否显示加载状态
 * @prop error      — 错误信息（truthy 时显示 error-banner）
 * @prop loadingText — 加载提示文字
 * @prop ariaLabel  — 面板的 aria-label
 * @prop tabsLabel  — tablist 的 aria-label
 * @emits update:modelValue — tab 切换
 * @emits close — 关闭面板
 */
import { ref, nextTick } from 'vue'
import type { TabItem } from './types'

withDefaults(defineProps<{
  tabs: TabItem[]
  modelValue: string
  loading?: boolean
  error?: string | null
  loadingText?: string
  ariaLabel?: string
  tabsLabel?: string
}>(), {
  loading: false,
  error: null,
  loadingText: '加载中',
  ariaLabel: '详情面板',
  tabsLabel: '详情标签页',
})

defineEmits<{
  'update:modelValue': [value: string]
  close: []
}>()

const paneRef = ref<HTMLElement>()

/** 离开前：锁定当前高度，防止内容消失后高度塌缩 */
function lockHeight() {
  const el = paneRef.value
  if (!el) return
  el.style.height = `${el.offsetHeight}px`
}

/** 新内容进入时：计算新高度并过渡 */
function animateHeight() {
  const el = paneRef.value
  if (!el) return
  nextTick(() => {
    const lockedHeight = el.style.height
    // 临时 auto 测量真实高度
    el.style.height = 'auto'
    const newHeight = el.offsetHeight
    // 回到锁定高度，强制 reflow，再过渡到新高度
    el.style.height = lockedHeight
    void el.offsetHeight // force reflow
    el.style.height = `${newHeight}px`
  })
}

/** 进入完毕：解锁高度回 auto（后续内容变化不受限） */
function unlockHeight() {
  const el = paneRef.value
  if (!el) return
  el.style.height = ''
}
</script>

<style scoped>
.detail-panel {
  display: grid;
  gap: 14px;
  padding: 14px;
  border: 1px solid var(--md-sys-color-outline-variant);
  border-radius: 20px;
  background: var(--md-sys-color-surface);
  box-shadow: 0 12px 30px color-mix(in srgb, var(--md-sys-color-primary) 8%, transparent);
}

.detail-pane {
  min-height: 80px;
  overflow: hidden;
  transition: height 0.3s var(--ease-standard, cubic-bezier(0.2, 0, 0, 1));
}

/* Tab 切换淡入淡出 */
.tab-fade-enter-active,
.tab-fade-leave-active {
  transition: opacity 0.18s ease;
}

.tab-fade-enter-from,
.tab-fade-leave-to {
  opacity: 0;
}

.detail-topbar {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}

.detail-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.detail-tab {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  min-height: 34px;
  padding: 0 12px;
  border-radius: 17px;
  background: var(--md-sys-color-surface-container-low);
  color: var(--md-sys-color-on-surface-variant);
  cursor: pointer;
  font-size: 12px;
  font-weight: 800;
  transition: background-color 0.18s ease, color 0.18s ease, transform 0.18s ease;
}

.detail-tab:hover:not(:disabled),
.detail-tab.active {
  background: var(--md-sys-color-primary-container);
  color: var(--md-sys-color-on-primary-container);
}

.detail-tab:active:not(:disabled) {
  transform: scale(0.97);
}

.detail-tab:disabled {
  opacity: 0.38;
  cursor: not-allowed;
}

.detail-tab .material-symbol {
  font-size: 17px;
}

.inline-loading {
  display: inline-flex;
  gap: 8px;
  align-items: center;
  min-height: 42px;
  color: var(--md-sys-color-on-surface-variant);
  font-size: 13px;
  font-weight: 700;
}

.inline-loading .material-symbol {
  font-size: 18px;
}

.error-banner.inline {
  margin-bottom: 0;
}
</style>
