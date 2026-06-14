<template>
  <div class="notice-banner" :class="{ error: !ok }" role="status">
    <span class="material-symbol">{{ ok ? 'check_circle' : 'error' }}</span>
    <div class="notice-content">
      <span>{{ message }}</span>
      <pre v-if="detail" class="notice-detail">{{ detail }}</pre>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  ok: boolean
  message: string
  detail?: string
}>()
</script>

<style scoped>
.notice-banner {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  margin-bottom: 16px;
  padding: 12px 14px;
  border-radius: 16px;
  background: var(--state-success-container);
  color: var(--state-success);
  font-size: 13px;
  font-weight: 700;
  animation: banner-in 0.22s var(--ease-standard) both;
}

.notice-banner.error {
  background: var(--md-sys-color-error-container);
  color: var(--md-sys-color-error);
}

.notice-banner .material-symbol {
  flex: 0 0 auto;
  font-size: 18px;
}

.notice-content {
  display: grid;
  gap: 8px;
  min-width: 0;
  flex: 1;
}

.notice-detail {
  max-height: 220px;
  margin: 0;
  padding: 10px 12px;
  overflow: auto;
  border-radius: 12px;
  background: color-mix(in srgb, var(--md-sys-color-error) 10%, var(--md-sys-color-surface));
  color: var(--md-sys-color-error);
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 600;
  line-height: 1.5;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

@keyframes banner-in {
  from {
    opacity: 0;
    transform: translateY(-6px) scale(0.99);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}
</style>
