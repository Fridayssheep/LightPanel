<template>
  <div v-if="totalCount > 0" class="batch-toolbar" :class="{ active: selectedCount > 0 }">
    <label class="batch-select control-item">
      <input
        ref="selectAllInput"
        type="checkbox"
        :checked="allSelected"
        :aria-checked="selectedCount > 0 && !allSelected ? 'mixed' : allSelected ? 'true' : 'false'"
        :disabled="disabled"
        title="切换全选"
        @change="$emit('toggleAll')"
      />
      <span>
        <strong>{{ selectedCount > 0 ? `已选 ${selectedCount} 项` : '批量选择' }}</strong>
        <small>{{ totalCount }} 项可选</small>
      </span>
    </label>

    <div class="batch-actions">
      <slot />
    </div>

    <button class="batch-clear" type="button" :disabled="disabled || selectedCount === 0" @click="$emit('clear')">
      <span class="material-symbol">close</span>
      清空
    </button>
  </div>
</template>

<script setup lang="ts">
import { ref, watchEffect } from 'vue'

const props = defineProps<{
  selectedCount: number
  totalCount: number
  allSelected: boolean
  disabled?: boolean
}>()

defineEmits<{
  toggleAll: []
  clear: []
}>()

const selectAllInput = ref<HTMLInputElement | null>(null)

watchEffect(() => {
  if (!selectAllInput.value) return
  selectAllInput.value.indeterminate = props.selectedCount > 0 && !props.allSelected
})
</script>

<style scoped>
.batch-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
  padding: 10px 12px;
  border: 1px solid var(--md-sys-color-outline-variant);
  border-radius: 18px;
  background: var(--md-sys-color-surface-container-low);
  color: var(--md-sys-color-on-surface-variant);
}

.batch-toolbar.active {
  border-color: color-mix(in srgb, var(--md-sys-color-primary) 42%, var(--md-sys-color-outline-variant));
  background: color-mix(in srgb, var(--md-sys-color-primary-container) 62%, var(--md-sys-color-surface));
}

.batch-select {
  min-width: 160px;
}

.batch-select span {
  display: grid;
  gap: 2px;
}

.batch-select strong {
  color: var(--md-sys-color-on-surface);
  font-size: 13px;
}

.batch-select small {
  font-size: 11px;
}

.batch-actions {
  display: flex;
  flex: 1;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.batch-clear {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 34px;
  padding: 0 12px;
  border-radius: 17px;
  color: var(--md-sys-color-on-surface-variant);
  cursor: pointer;
  font-size: 12px;
  font-weight: 800;
}

.batch-clear:hover:not(:disabled) {
  background: var(--md-sys-color-surface-container-high);
}

.batch-clear:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.batch-clear .material-symbol {
  font-size: 16px;
}
</style>
