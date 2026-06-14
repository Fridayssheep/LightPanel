<template>
  <div class="app-layout">
    <aside class="navigation-drawer">
      <RouterLink to="/" class="brand">
        <span class="brand-mark">OA</span>
        <span>
          <span class="brand-title">Ops Agent</span>
          <span class="brand-subtitle">Docker Operations</span>
        </span>
      </RouterLink>

      <nav class="nav" aria-label="Primary">
        <RouterLink v-for="item in navItems" :key="item.to" :to="item.to" class="nav-item">
          <span class="nav-icon material-symbol">{{ item.icon }}</span>
          <span>{{ item.label }}</span>
        </RouterLink>
      </nav>

      <section class="theme-panel" :class="{ expanded: themePanelOpen }" aria-label="Theme color">
        <button
          class="theme-trigger"
          type="button"
          :aria-expanded="themePanelOpen"
          @click="themePanelOpen = !themePanelOpen"
        >
          <span class="theme-preview" :style="{ backgroundColor: themeColor }"></span>
          <span class="theme-trigger-text">主题色</span>
          <span class="material-symbol theme-chevron">{{ themePanelOpen ? 'expand_more' : 'chevron_right' }}</span>
        </button>

        <Transition name="theme-panel-reveal">
          <div v-if="themePanelOpen" class="theme-body">
            <div class="theme-panel-title">
              <span>当前颜色</span>
              <span class="theme-value">{{ themeColor.toUpperCase() }}</span>
            </div>
            <div class="theme-swatches">
          <button
            v-for="color in themePresets"
            :key="color"
            class="theme-swatch"
            :class="{ active: themeColor === color }"
            :style="{ backgroundColor: color }"
            type="button"
            :aria-label="`使用主题色 ${color}`"
            @click="setThemeColor(color)"
          ></button>
          <label class="theme-picker" title="自定义主题色">
            <span class="material-symbol">palette</span>
            <input :value="themeColor" type="color" @input="handleThemeInput" />
          </label>
            </div>
          </div>
        </Transition>
      </section>
    </aside>

    <div class="app-frame">
      <main class="main-content">
        <RouterView v-slot="{ Component, route }">
          <Transition name="route-surface" mode="out-in">
            <component :is="Component" :key="route.fullPath" />
          </Transition>
        </RouterView>
      </main>
    </div>
    <ConfirmDialog />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import ConfirmDialog from './components/ConfirmDialog.vue'

const THEME_STORAGE_KEY = 'ops-agent-theme-color'
const DEFAULT_THEME = '#1a73e8'

const navItems = [
  { to: '/', label: '总览面板', icon: 'dashboard' },
  { to: '/containers', label: '容器查看', icon: 'deployed_code' },
  { to: '/images', label: '镜像管理', icon: 'inventory_2' },
  { to: '/networks', label: '网络管理', icon: 'hub' },
  { to: '/volumes', label: '卷管理', icon: 'database' },
  { to: '/compose', label: 'Compose', icon: 'account_tree' },
  { to: '/chat', label: '对话诊断', icon: 'forum' },
  { to: '/history', label: '历史记录', icon: 'history' },
  { to: '/settings', label: '设置', icon: 'settings' },
]

const themePresets = ['#1a73e8', '#0b8043', '#d93025', '#9334e6', '#f9ab00']
const themeColor = ref(DEFAULT_THEME)
const themePanelOpen = ref(false)

function hexToRgb(hex: string): { r: number; g: number; b: number } {
  const normalized = hex.replace('#', '')
  const value = normalized.length === 3
    ? normalized.split('').map(char => char + char).join('')
    : normalized
  return {
    r: parseInt(value.slice(0, 2), 16),
    g: parseInt(value.slice(2, 4), 16),
    b: parseInt(value.slice(4, 6), 16),
  }
}

function mixChannel(channel: number, target: number, amount: number): number {
  return Math.round(channel + (target - channel) * amount)
}

function rgbToHex(r: number, g: number, b: number): string {
  return `#${[r, g, b].map(value => value.toString(16).padStart(2, '0')).join('')}`
}

function mixColor(hex: string, target: '#ffffff' | '#000000', amount: number): string {
  const { r, g, b } = hexToRgb(hex)
  const targetValue = target === '#ffffff' ? 255 : 0
  return rgbToHex(
    mixChannel(r, targetValue, amount),
    mixChannel(g, targetValue, amount),
    mixChannel(b, targetValue, amount),
  )
}

function readableOn(hex: string): string {
  const { r, g, b } = hexToRgb(hex)
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
  return luminance > 0.58 ? '#1f1f1f' : '#ffffff'
}

function applyThemeColor(color: string) {
  themeColor.value = color
  const root = document.documentElement
  // 从用户选择的主色推导一组精简的 Material 风格颜色变量。
  root.style.setProperty('--md-sys-color-primary', color)
  root.style.setProperty('--md-sys-color-on-primary', readableOn(color))
  root.style.setProperty('--md-sys-color-primary-container', mixColor(color, '#ffffff', 0.84))
  root.style.setProperty('--md-sys-color-on-primary-container', mixColor(color, '#000000', 0.52))
  root.style.setProperty('--md-sys-color-secondary-container', mixColor(color, '#ffffff', 0.9))
  root.style.setProperty('--md-sys-color-outline-primary', mixColor(color, '#000000', 0.18))
  localStorage.setItem(THEME_STORAGE_KEY, color)
}

function setThemeColor(color: string) {
  applyThemeColor(color)
}

function handleThemeInput(event: Event) {
  const target = event.target as HTMLInputElement
  applyThemeColor(target.value)
}

onMounted(() => {
  const savedColor = localStorage.getItem(THEME_STORAGE_KEY)
  // 先应用已保存主题色，保证首屏按用户主题渲染。
  applyThemeColor(savedColor || DEFAULT_THEME)
})
</script>

<style scoped>
.app-layout {
  display: grid;
  grid-template-columns: 276px minmax(0, 1fr);
  height: 100vh;
  overflow: hidden;
  background: var(--md-sys-color-background);
}

.navigation-drawer {
  position: sticky;
  top: 0;
  display: flex;
  flex-direction: column;
  gap: 18px;
  height: 100vh;
  padding: 20px 16px;
  background: var(--md-sys-color-surface-container-low);
  border-right: 1px solid var(--md-sys-color-outline-variant);
}

.brand {
  display: grid;
  grid-template-columns: 48px 1fr;
  align-items: center;
  gap: 12px;
  min-height: 56px;
  padding: 4px;
  color: var(--md-sys-color-on-surface);
  text-decoration: none;
}

.brand-mark {
  display: grid;
  place-items: center;
  width: 48px;
  height: 48px;
  border-radius: 16px;
  background: var(--md-sys-color-primary);
  color: var(--md-sys-color-on-primary);
  font-weight: 800;
  letter-spacing: 0;
  box-shadow: var(--md-elevation-1);
}

.brand-title,
.brand-subtitle {
  display: block;
}

.brand-title {
  font-size: 18px;
  font-weight: 700;
}

.brand-subtitle {
  margin-top: 2px;
  color: var(--md-sys-color-on-surface-variant);
  font-size: 12px;
}

.nav {
  display: grid;
  gap: 4px;
}

.nav-item {
  position: relative;
  overflow: hidden;
  display: grid;
  grid-template-columns: 28px 1fr;
  align-items: center;
  gap: 12px;
  min-height: 48px;
  padding: 0 16px;
  border-radius: 24px;
  color: var(--md-sys-color-on-surface-variant);
  text-decoration: none;
  font-size: 14px;
  font-weight: 600;
  transition: background-color 0.18s ease, color 0.18s ease, transform 0.18s ease;
}

.nav-item:hover {
  background: var(--md-sys-color-surface-container-high);
  color: var(--md-sys-color-on-surface);
}

.nav-item:active {
  transform: scale(0.985);
}

.nav-item::after {
  content: '';
  position: absolute;
  inset: 0;
  background: var(--md-sys-color-primary);
  opacity: 0;
  transition: opacity 0.18s ease;
}

.nav-item:active::after {
  opacity: 0.1;
}

.nav-item.router-link-active {
  background: var(--md-sys-color-secondary-container);
  color: var(--md-sys-color-on-primary-container);
}

.nav-icon {
  font-size: 22px;
}

.theme-panel {
  margin-top: auto;
  display: grid;
  gap: 8px;
  min-width: 0;
  padding: 8px;
  border-radius: 20px;
  background: var(--md-sys-color-surface-container);
  border: 1px solid var(--md-sys-color-outline-variant);
  transition: box-shadow 0.2s ease, background-color 0.2s ease;
}

.theme-panel.expanded {
  background: var(--md-sys-color-surface);
  box-shadow: var(--md-elevation-1);
}

.theme-trigger {
  display: grid;
  grid-template-columns: 32px minmax(0, 1fr) 24px;
  align-items: center;
  gap: 10px;
  min-height: 42px;
  width: 100%;
  padding: 0 8px;
  border-radius: 18px;
  background: transparent;
  color: var(--md-sys-color-on-surface);
  cursor: pointer;
  text-align: left;
}

.theme-trigger:hover {
  background: var(--md-sys-color-surface-container-low);
}

.theme-preview {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  box-shadow: inset 0 0 0 2px rgba(255, 255, 255, 0.72), 0 0 0 1px rgba(60, 64, 67, 0.24);
}

.theme-trigger-text {
  min-width: 0;
  overflow: hidden;
  font-size: 13px;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.theme-chevron {
  color: var(--md-sys-color-on-surface-variant);
  font-size: 22px;
}

.theme-body {
  display: grid;
  gap: 12px;
  min-width: 0;
  padding: 6px 6px 8px;
}

.theme-panel-title {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px;
  min-width: 0;
  color: var(--md-sys-color-on-surface-variant);
  font-size: 12px;
  font-weight: 700;
}

.theme-value {
  max-width: 74px;
  overflow: hidden;
  font-family: var(--font-mono);
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.theme-swatches {
  display: grid;
  grid-template-columns: repeat(6, 28px);
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  min-width: 0;
}

.theme-swatch,
.theme-picker {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: 2px solid transparent;
  box-shadow: inset 0 0 0 1px rgba(0, 0, 0, 0.12);
  cursor: pointer;
}

.theme-swatch.active {
  border-color: var(--md-sys-color-on-surface);
}

.theme-picker {
  position: relative;
  display: grid;
  place-items: center;
  background: var(--md-sys-color-surface);
  color: var(--md-sys-color-primary);
  overflow: hidden;
}

.theme-picker input {
  position: absolute;
  inset: 0;
  opacity: 0;
  cursor: pointer;
}

.app-frame {
  display: grid;
  grid-template-rows: minmax(0, 1fr);
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

.icon-button {
  width: 40px;
  height: 40px;
}

.spinning {
  animation: spin 0.8s linear infinite;
}

.main-content {
  position: relative;
  min-width: 0;
  overflow: auto;
}

.route-surface-enter-active,
.route-surface-leave-active {
  transition: opacity 0.2s ease, transform 0.22s var(--ease-standard), filter 0.22s ease;
}

.route-surface-enter-from {
  opacity: 0;
  filter: blur(3px);
  transform: translateY(10px) scale(0.992);
}

.route-surface-leave-to {
  opacity: 0;
  filter: blur(2px);
  transform: translateY(-6px) scale(0.996);
}

.theme-panel-reveal-enter-active,
.theme-panel-reveal-leave-active {
  transform-origin: bottom center;
  transition: opacity 0.18s ease, transform 0.2s var(--ease-standard), max-height 0.22s ease;
  overflow: hidden;
}

.theme-panel-reveal-enter-from,
.theme-panel-reveal-leave-to {
  max-height: 0;
  opacity: 0;
  transform: translateY(6px) scale(0.98);
}

.theme-panel-reveal-enter-to,
.theme-panel-reveal-leave-from {
  max-height: 128px;
  opacity: 1;
  transform: translateY(0) scale(1);
}

@media (max-width: 900px) {
  .app-layout {
    grid-template-columns: 1fr;
  }

  .navigation-drawer {
    position: sticky;
    z-index: 20;
    flex-direction: row;
    align-items: center;
    height: auto;
    padding: 10px 12px;
    overflow-x: auto;
  }

  .brand {
    grid-template-columns: 40px auto;
    min-width: max-content;
  }

  .brand-mark {
    width: 40px;
    height: 40px;
    border-radius: 14px;
  }

  .brand-subtitle,
  .theme-panel {
    display: none;
  }

  .nav {
    display: flex;
    min-width: max-content;
  }

  .nav-item {
    grid-template-columns: 24px auto;
    min-height: 42px;
    padding: 0 14px;
  }

  .app-frame {
    min-height: 0;
  }
}
</style>
