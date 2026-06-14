<template>
  <Teleport to="body">
    <Transition name="confirm-dialog-fade">
      <div v-if="confirmDialogState.open" class="confirm-backdrop" role="presentation" @click.self="handleCancel">
        <section
          ref="dialogElement"
          class="confirm-dialog"
          :class="confirmDialogState.intent"
          role="alertdialog"
          aria-modal="true"
          aria-labelledby="confirm-dialog-title"
          aria-describedby="confirm-dialog-message"
          tabindex="-1"
          @keydown.esc.prevent="handleCancel"
        >
          <div class="confirm-icon">
            <span class="material-symbol">{{ confirmDialogState.icon }}</span>
          </div>

          <div class="confirm-content">
            <h2 id="confirm-dialog-title">{{ confirmDialogState.title }}</h2>
            <p id="confirm-dialog-message">{{ confirmDialogState.message }}</p>
            <p v-if="confirmDialogState.detail" class="confirm-detail">{{ confirmDialogState.detail }}</p>
          </div>

          <footer class="confirm-actions">
            <button class="secondary-button" type="button" @click="handleCancel">
              {{ confirmDialogState.cancelText }}
            </button>
            <button
              ref="confirmButton"
              class="confirm-primary"
              :class="confirmDialogState.intent"
              type="button"
              @click="handleConfirm"
            >
              {{ confirmDialogState.confirmText }}
            </button>
          </footer>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import { confirmDialogState, resolveConfirmDialog } from '../utils/confirmDialog'

const dialogElement = ref<HTMLElement | null>(null)
const confirmButton = ref<HTMLButtonElement | null>(null)

watch(
  () => confirmDialogState.open,
  async (open) => {
    if (!open) return
    await nextTick()
    confirmButton.value?.focus()
  },
)

function handleCancel() {
  resolveConfirmDialog(false)
}

function handleConfirm() {
  resolveConfirmDialog(true)
}
</script>

<style scoped>
.confirm-backdrop {
  position: fixed;
  inset: 0;
  z-index: 120;
  display: grid;
  place-items: center;
  padding: 24px;
  background: color-mix(in srgb, #101418 44%, transparent);
  backdrop-filter: blur(10px);
}

.confirm-dialog {
  display: grid;
  grid-template-columns: 48px minmax(0, 1fr);
  gap: 16px;
  width: min(460px, 100%);
  padding: 22px;
  border: 1px solid color-mix(in srgb, var(--md-sys-color-primary) 24%, var(--md-sys-color-outline-variant));
  border-radius: 28px;
  background: var(--md-sys-color-surface);
  box-shadow: var(--md-elevation-3);
  outline: none;
}

.confirm-dialog.danger {
  border-color: color-mix(in srgb, var(--md-sys-color-error) 34%, var(--md-sys-color-outline-variant));
}

.confirm-icon {
  display: grid;
  place-items: center;
  width: 48px;
  height: 48px;
  border-radius: 18px;
  background: var(--md-sys-color-primary-container);
  color: var(--md-sys-color-primary);
}

.confirm-dialog.danger .confirm-icon {
  background: var(--md-sys-color-error-container);
  color: var(--md-sys-color-error);
}

.confirm-icon .material-symbol {
  font-size: 24px;
}

.confirm-content {
  min-width: 0;
}

.confirm-content h2 {
  margin: 1px 0 8px;
  color: var(--md-sys-color-on-surface);
  font-size: 20px;
  line-height: 1.25;
  font-weight: 800;
}

.confirm-content p {
  margin: 0;
  color: var(--md-sys-color-on-surface-variant);
  font-size: 14px;
  line-height: 1.6;
  white-space: pre-line;
  overflow-wrap: anywhere;
}

.confirm-detail {
  margin-top: 10px !important;
  padding: 10px 12px;
  border-radius: 14px;
  background: var(--md-sys-color-surface-container-low);
  font-family: var(--font-mono);
  font-size: 12px !important;
}

.confirm-actions {
  grid-column: 1 / -1;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding-top: 6px;
}

.confirm-primary {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 40px;
  padding: 0 20px;
  border-radius: 20px;
  background: var(--md-sys-color-primary);
  color: var(--md-sys-color-on-primary);
  font-weight: 800;
  cursor: pointer;
  transition: box-shadow 0.18s ease, transform 0.18s ease, background-color 0.18s ease;
}

.confirm-primary.danger {
  background: var(--md-sys-color-error);
  color: #fff;
}

.confirm-primary:hover {
  box-shadow: var(--md-elevation-1);
}

.confirm-primary:active {
  transform: scale(0.98);
}

.confirm-dialog-fade-enter-active,
.confirm-dialog-fade-leave-active {
  transition: opacity 0.2s ease;
}

.confirm-dialog-fade-enter-active .confirm-dialog,
.confirm-dialog-fade-leave-active .confirm-dialog {
  transition: opacity 0.22s ease, transform 0.26s var(--ease-standard);
}

.confirm-dialog-fade-enter-from,
.confirm-dialog-fade-leave-to {
  opacity: 0;
}

.confirm-dialog-fade-enter-from .confirm-dialog,
.confirm-dialog-fade-leave-to .confirm-dialog {
  opacity: 0;
  transform: translateY(12px) scale(0.985);
}

@media (max-width: 560px) {
  .confirm-dialog {
    grid-template-columns: 1fr;
  }

  .confirm-actions {
    flex-direction: column-reverse;
  }

  .confirm-actions > button {
    width: 100%;
  }
}
</style>
