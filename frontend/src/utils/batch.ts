import { computed, shallowRef } from 'vue'
import type { OperationResponse } from '../api/types'

export interface BatchFailure {
  label: string
  message: string
}

export interface BatchOutcome {
  total: number
  succeeded: number
  failed: number
  failures: BatchFailure[]
}

export function useBatchSelection<T extends string>() {
  const selected = shallowRef<Set<T>>(new Set())
  const selectedCount = computed(() => selected.value.size)

  function setSelected(next: Iterable<T>) {
    selected.value = new Set(next)
  }

  function isSelected(key: T): boolean {
    return selected.value.has(key)
  }

  function toggle(key: T, checked?: boolean) {
    const next = new Set(selected.value)
    const shouldSelect = checked ?? !next.has(key)
    if (shouldSelect) {
      next.add(key)
    } else {
      next.delete(key)
    }
    selected.value = next
  }

  function clear() {
    selected.value = new Set()
  }

  function sync(validKeys: Iterable<T>) {
    const valid = new Set(validKeys)
    selected.value = new Set([...selected.value].filter((key) => valid.has(key)))
  }

  function areAllSelected(keys: readonly T[]): boolean {
    return keys.length > 0 && keys.every((key) => selected.value.has(key))
  }

  function toggleAll(keys: readonly T[]) {
    if (areAllSelected(keys)) {
      selected.value = new Set([...selected.value].filter((key) => !keys.includes(key)))
      return
    }
    selected.value = new Set([...selected.value, ...keys])
  }

  return {
    selected,
    selectedCount,
    isSelected,
    toggle,
    clear,
    sync,
    areAllSelected,
    toggleAll,
    setSelected,
  }
}

export async function runBatchOperation<T>(
  items: readonly T[],
  execute: (item: T) => Promise<OperationResponse>,
  label: (item: T) => string,
): Promise<BatchOutcome> {
  const failures: BatchFailure[] = []
  let succeeded = 0

  for (const item of items) {
    try {
      const result = await execute(item)
      if (result.ok) {
        succeeded += 1
      } else {
        failures.push({ label: label(item), message: result.error || result.message || '操作失败' })
      }
    } catch (error) {
      failures.push({ label: label(item), message: String(error) })
    }
  }

  return {
    total: items.length,
    succeeded,
    failed: failures.length,
    failures,
  }
}

export function batchNotice(subject: string, action: string, outcome: BatchOutcome): OperationResponse {
  const ok = outcome.failed === 0
  const message = ok
    ? `${subject}批量${action}完成：${outcome.succeeded}/${outcome.total} 成功。`
    : `${subject}批量${action}完成：${outcome.succeeded}/${outcome.total} 成功，${outcome.failed} 项失败。`
  return {
    ok,
    message,
    data: {
      total: outcome.total,
      succeeded: outcome.succeeded,
      failed: outcome.failed,
      failures: outcome.failures,
    },
    error: ok ? null : outcome.failures.map((item) => `${item.label}: ${item.message}`).join('\n'),
    timestamp: new Date().toISOString(),
  }
}
