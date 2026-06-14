<template>
  <Teleport to="body">
    <Transition name="panel-rise">
      <div v-if="report" class="report-modal" @click.self="$emit('close')">
        <div class="report-panel" role="dialog" aria-modal="true" :aria-label="report.title">
          <div class="report-header">
            <h2>{{ report.title }}</h2>
            <button class="btn-close" type="button" title="关闭报告" @click="$emit('close')">
              <span class="material-symbol">close</span>
            </button>
          </div>
          <div class="report-body">
            <div class="report-section">
              <div class="section-label">严重程度</div>
              <div class="severity-badge" :class="report.severity">
                {{ severityLabel(report.severity) }}
              </div>
            </div>
            <div class="report-section">
              <div class="section-label">故障现象</div>
              <div class="section-text">{{ report.symptom }}</div>
            </div>
            <div class="report-section">
              <div class="section-label">已检查项</div>
              <ul class="section-list">
                <li v-for="item in report.checked_items" :key="item">{{ item }}</li>
              </ul>
            </div>
            <div class="report-section">
              <div class="section-label">主要发现</div>
              <ul class="section-list">
                <li v-for="item in report.findings" :key="item">{{ item }}</li>
              </ul>
            </div>
            <div class="report-section">
              <div class="section-label">根因分析</div>
              <div class="section-text">{{ report.root_cause }}</div>
            </div>
            <div class="report-section">
              <div class="section-label">处理建议</div>
              <ul class="section-list">
                <li v-for="item in report.recommendations" :key="item">{{ item }}</li>
              </ul>
            </div>
            <div class="report-section">
              <div class="section-label">最终状态</div>
              <div class="section-text">{{ report.final_status }}</div>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import type { DiagnosisReport } from '../api/types'

defineProps<{
  report: DiagnosisReport | null
}>()

defineEmits<{
  close: []
}>()

function severityLabel(severity: DiagnosisReport['severity']): string {
  const labels: Record<DiagnosisReport['severity'], string> = {
    info: '信息',
    low: '低',
    medium: '中',
    high: '高',
  }
  return labels[severity]
}
</script>

<style scoped>
.report-modal {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
  background: rgba(32, 33, 36, 0.42);
}

.report-panel {
  display: flex;
  flex-direction: column;
  width: 100%;
  max-width: 800px;
  max-height: 90vh;
  overflow: hidden;
  border-radius: 28px;
  background: var(--md-sys-color-surface);
  box-shadow: var(--shadow-float);
}

.report-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 24px 32px;
  border-bottom: 1px solid var(--md-sys-color-outline-variant);
}

.report-header h2 {
  min-width: 0;
  margin: 0;
  color: var(--md-sys-color-on-surface);
  font-size: 20px;
  overflow-wrap: anywhere;
}

.btn-close {
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  width: 32px;
  height: 32px;
  border-radius: 16px;
  background: var(--md-sys-color-surface-container);
  color: var(--md-sys-color-on-surface-variant);
  cursor: pointer;
  transition: background-color 0.18s ease, transform 0.18s ease;
}

.btn-close:hover {
  background: var(--md-sys-color-surface-container-high);
}

.btn-close:active {
  transform: scale(0.94);
}

.btn-close .material-symbol {
  font-size: 18px;
}

.report-body {
  display: flex;
  flex-direction: column;
  gap: 24px;
  overflow-y: auto;
  padding: 24px 32px;
}

.report-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.section-label {
  color: var(--md-sys-color-on-surface-variant);
  font-size: 13px;
  font-weight: 700;
  text-transform: uppercase;
}

.section-text,
.section-list li {
  color: var(--md-sys-color-on-surface);
  font-size: 15px;
  line-height: 1.7;
}

.section-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin: 0;
  padding-left: 20px;
}

.severity-badge {
  display: inline-block;
  width: fit-content;
  padding: 6px 14px;
  border-radius: 999px;
  font-size: 14px;
  font-weight: 700;
}

.severity-badge.info {
  background: rgba(44, 108, 157, 0.14);
  color: #214f72;
}

.severity-badge.low {
  background: rgba(31, 157, 112, 0.14);
  color: #0f6f4d;
}

.severity-badge.medium {
  background: rgba(201, 131, 24, 0.16);
  color: #7a4d0c;
}

.severity-badge.high {
  background: rgba(200, 66, 50, 0.14);
  color: #8f2e24;
}
</style>
