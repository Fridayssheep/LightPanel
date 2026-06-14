import { reactive } from 'vue'

export type ConfirmIntent = 'default' | 'danger' | 'warning'

export interface ConfirmDialogOptions {
  title?: string
  message: string
  detail?: string
  confirmText?: string
  cancelText?: string
  intent?: ConfirmIntent
  icon?: string
}

export interface ConfirmDialogState {
  open: boolean
  title: string
  message: string
  detail: string
  confirmText: string
  cancelText: string
  intent: ConfirmIntent
  icon: string
}

export const confirmDialogState = reactive<ConfirmDialogState>({
  open: false,
  title: '确认操作',
  message: '',
  detail: '',
  confirmText: '确认',
  cancelText: '取消',
  intent: 'default',
  icon: 'help',
})

let activeResolver: ((confirmed: boolean) => void) | null = null

function defaultIcon(intent: ConfirmIntent): string {
  if (intent === 'danger') return 'warning'
  if (intent === 'warning') return 'priority_high'
  return 'help'
}

function normalizeOptions(input: string | ConfirmDialogOptions): ConfirmDialogState {
  const options = typeof input === 'string' ? { message: input } : input
  const intent = options.intent ?? 'default'
  return {
    open: true,
    title: options.title ?? (intent === 'danger' ? '确认危险操作' : '确认操作'),
    message: options.message,
    detail: options.detail ?? '',
    confirmText: options.confirmText ?? '确认',
    cancelText: options.cancelText ?? '取消',
    intent,
    icon: options.icon ?? defaultIcon(intent),
  }
}

export function requestConfirm(input: string | ConfirmDialogOptions): Promise<boolean> {
  if (activeResolver) {
    activeResolver(false)
    activeResolver = null
  }
  Object.assign(confirmDialogState, normalizeOptions(input))
  return new Promise((resolve) => {
    activeResolver = resolve
  })
}

export function resolveConfirmDialog(confirmed: boolean) {
  if (!confirmDialogState.open && !activeResolver) return
  confirmDialogState.open = false
  if (activeResolver) {
    activeResolver(confirmed)
    activeResolver = null
  }
}
