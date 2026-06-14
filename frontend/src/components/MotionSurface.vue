<template>
  <component
    :is="as"
    ref="rootElement"
    class="surface motion-surface"
    :class="{
      'is-interactive': interactive,
      'is-expanded': expanded,
      'motion-disabled': disabledMotion,
    }"
    :style="styleVars"
  >
    <slot />
  </component>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

const props = withDefaults(defineProps<{
  as?: string
  interactive?: boolean
  expanded?: boolean
  delay?: number | string
  disabledMotion?: boolean
}>(), {
  as: 'section',
  interactive: true,
  expanded: false,
  delay: 0,
  disabledMotion: false,
})

const rootElement = ref<HTMLElement | null>(null)

const normalizedDelay = computed(() => {
  // 同时支持数字毫秒延迟和显式 CSS 延迟字符串。
  if (typeof props.delay === 'number') return `${props.delay}ms`
  return props.delay || '0ms'
})

const styleVars = computed(() => ({
  '--motion-delay': normalizedDelay.value,
}) as Record<string, string>)

defineExpose({ rootElement })
</script>
