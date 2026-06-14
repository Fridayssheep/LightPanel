<template>
  <pre
    ref="rootElement"
    class="highlighted-code"
    :class="`highlighted-code--${resolvedMode}`"
    v-html="highlightedHtml"
  ></pre>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { highlightCodeToHtml, normalizeHighlightMode } from '../utils/highlight'

const props = withDefaults(defineProps<{
  content?: string | null
  mode?: string
  emptyText?: string
}>(), {
  content: '',
  mode: 'plain',
  emptyText: '暂无内容',
})

const rootElement = ref<HTMLElement | null>(null)
const resolvedMode = computed(() => normalizeHighlightMode(props.mode))
// 高亮函数会先转义原始内容再插入 token span，因此 v-html 的风险受控。
const highlightedHtml = computed(() => highlightCodeToHtml(props.content || props.emptyText, resolvedMode.value))

defineExpose({ rootElement })
</script>
