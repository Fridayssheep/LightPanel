<template>
  <Teleport to="body">
    <Transition name="wizard-fade">
      <div v-if="open" class="wizard-backdrop" role="presentation" @click.self="handleClose">
        <section class="wizard-dialog" role="dialog" aria-modal="true" aria-labelledby="create-container-title">
          <header class="wizard-header">
            <div>
              <p class="eyebrow">Create container</p>
              <h2 id="create-container-title">创建容器</h2>
            </div>
            <button class="icon-button" type="button" title="关闭" :disabled="submitting" @click="handleClose">
              <span class="material-symbol">close</span>
            </button>
          </header>

          <div class="wizard-steps" aria-label="创建流程">
            <button
              v-for="item in steps"
              :key="item.key"
              class="step-pill"
              :class="{ active: step === item.key, done: stepOrder(item.key) < stepOrder(step) }"
              type="button"
              :disabled="item.key === 'advanced' && !canGoAdvanced"
              @click="step = item.key"
            >
              <span class="material-symbol">{{ item.icon }}</span>
              {{ item.label }}
            </button>
          </div>

          <NoticeBanner v-if="localNotice" :ok="localNotice.ok" :message="localNotice.message" />

          <form class="wizard-body" @submit.prevent="handleSubmit">
            <Transition name="panel-rise" mode="out-in">
              <section v-if="step === 'basic'" key="basic" class="wizard-page">
                <div class="section-heading">
                  <span class="material-symbol">deployed_code</span>
                  <div>
                    <strong>基础信息</strong>
                    <small>配置容器的名称与基本信息</small>
                  </div>
                </div>

                <div class="form-grid">
                  <label class="field-row wide">
                    <span>镜像</span>
                    <input
                      v-model.trim="form.image"
                      class="themed-input"
                      list="container-image-options"
                      placeholder="选择已有镜像或输入 nginx:latest"
                      autocomplete="off"
                      required
                    />
                    <datalist id="container-image-options">
                      <option v-for="image in imageOptions" :key="image" :value="image"></option>
                    </datalist>
                  </label>
                  <label class="field-row">
                    <span>容器名称</span>
                    <input v-model.trim="form.name" class="themed-input" placeholder="留空自动生成" autocomplete="off" />
                  </label>
                  <label class="field-row">
                    <span>重启策略</span>
                    <select v-model="form.restart_policy" class="themed-input">
                      <option v-for="policy in restartPolicies" :key="policy.value" :value="policy.value">
                        {{ policy.label }}
                      </option>
                    </select>
                  </label>
                  <label class="field-row">
                    <span>网络模式</span>
                    <select v-model="form.networkMode" class="themed-input">
                      <option value="bridge">bridge</option>
                      <option value="host">host</option>
                      <option value="custom">自定义网络</option>
                    </select>
                  </label>
                  <label v-if="form.networkMode === 'custom'" class="field-row">
                    <span>网络名称</span>
                    <input v-model.trim="form.customNetwork" class="themed-input" placeholder="例如 app-net" autocomplete="off" />
                  </label>
                  <label class="field-row wide">
                    <span>启动命令</span>
                    <textarea v-model.trim="form.command" class="themed-textarea" rows="3" placeholder="留空使用镜像默认命令"></textarea>
                  </label>
                </div>

                <div class="option-strip">
                  <label class="switch-row">
                    <input v-model="form.start" type="checkbox" />
                    <span>
                      <strong>创建后启动</strong>
                      <small>创建完成后立即启动容器</small>
                    </span>
                  </label>
                  <label class="switch-row">
                    <input v-model="form.pull_if_missing" type="checkbox" />
                    <span>
                      <strong>缺失时拉取镜像</strong>
                      <small>本地没有镜像时自动拉取</small>
                    </span>
                  </label>
                </div>

                <div class="image-state">
                  <span class="material-symbol" :class="{ spinning: loadingImages }">
                    {{ loadingImages ? 'progress_activity' : 'inventory_2' }}
                  </span>
                  <span>{{ loadingImages ? '正在读取本地镜像' : `${imageOptions.length} 个本地镜像可选` }}</span>
                  <button class="text-action" type="button" :disabled="loadingImages" @click="loadImages">
                    刷新
                  </button>
                </div>
              </section>

              <section v-else key="advanced" class="wizard-page">
                <div class="advanced-layout">
                  <aside class="advanced-summary">
                    <span class="material-symbol">fact_check</span>
                    <strong>{{ form.image || '未选择镜像' }}</strong>
                    <small>{{ networkLabel }}</small>
                    <small>{{ resourceSummary }}</small>
                    <small>{{ capabilitySummary }}</small>
                  </aside>

                  <div class="advanced-content">
                    <section v-if="!isHostNetwork" class="form-section">
                      <div class="section-title action-title">
                        <div>
                          <span class="material-symbol">lan</span>
                          <strong>端口映射</strong>
                        </div>
                        <button class="small-action" type="button" @click="addPortBinding">
                          <span class="material-symbol">add</span>
                          添加
                        </button>
                      </div>
                      <div v-if="!form.ports.length" class="empty-inline">没有端口映射</div>
                      <div v-else class="dynamic-list">
                        <div v-for="(port, index) in form.ports" :key="`port-${index}`" class="dynamic-row ports-row">
                          <input v-model.trim="port.host_ip" class="themed-input" placeholder="0.0.0.0" autocomplete="off" />
                          <input v-model.trim="port.host_port" class="themed-input" placeholder="宿主端口" autocomplete="off" />
                          <input v-model.trim="port.container_port" class="themed-input" placeholder="容器端口" autocomplete="off" />
                          <select v-model="port.protocol" class="themed-input">
                            <option value="tcp">tcp</option>
                            <option value="udp">udp</option>
                            <option value="tcp/udp">tcp/udp</option>
                          </select>
                          <button class="icon-action danger" type="button" title="删除" @click="removePortBinding(index)">
                            <span class="material-symbol">close</span>
                          </button>
                        </div>
                      </div>
                    </section>

                    <section v-else class="host-network-note">
                      <span class="material-symbol">settings_ethernet</span>
                      <div>
                        <strong>host 网络无需配置端口映射</strong>
                      </div>
                    </section>

                    <section class="form-section">
                      <div class="section-title action-title">
                        <div>
                          <span class="material-symbol">folder_managed</span>
                          <strong>存储映射</strong>
                        </div>
                        <button class="small-action" type="button" @click="addVolumeMount">
                          <span class="material-symbol">add</span>
                          添加
                        </button>
                      </div>
                      <div v-if="!form.volumes.length" class="empty-inline">没有目录或文件映射</div>
                      <div v-else class="dynamic-list">
                        <div v-for="(mount, index) in form.volumes" :key="`volume-${index}`" class="dynamic-row volume-row">
                          <input v-model.trim="mount.host_path" class="themed-input" placeholder="宿主路径或文件" autocomplete="off" />
                          <input v-model.trim="mount.container_path" class="themed-input" placeholder="容器路径或文件" autocomplete="off" />
                          <select v-model="mount.mode" class="themed-input">
                            <option value="rw">读写</option>
                            <option value="ro">只读</option>
                          </select>
                          <button class="icon-action danger" type="button" title="删除" @click="removeVolumeMount(index)">
                            <span class="material-symbol">close</span>
                          </button>
                        </div>
                      </div>
                    </section>

                    <section class="form-section">
                      <div class="section-title action-title">
                        <div>
                          <span class="material-symbol">key</span>
                          <strong>环境变量</strong>
                        </div>
                        <button class="small-action" type="button" @click="addEnvVar">
                          <span class="material-symbol">add</span>
                          添加
                        </button>
                      </div>
                      <div v-if="!form.env.length" class="empty-inline">没有环境变量</div>
                      <div v-else class="dynamic-list">
                        <div v-for="(item, index) in form.env" :key="`env-${index}`" class="dynamic-row env-row">
                          <input v-model.trim="item.key" class="themed-input" placeholder="KEY" autocomplete="off" />
                          <input v-model="item.value" class="themed-input" placeholder="value" autocomplete="off" />
                          <button class="icon-action danger" type="button" title="删除" @click="removeEnvVar(index)">
                            <span class="material-symbol">close</span>
                          </button>
                        </div>
                      </div>
                    </section>

                    <section class="form-section">
                      <div class="section-title resource-title">
                        <div class="resource-title-left">
                          <span class="material-symbol">speed</span>
                          <strong>资源限制</strong>
                        </div>
                        <label class="resource-enable">
                          <span>启用</span>
                          <input v-model="form.resource_limits_enabled" type="checkbox" aria-label="启用资源限制" />
                        </label>
                      </div>
                      <Transition name="panel-rise">
                        <div v-if="form.resource_limits_enabled" class="resource-simple">
                          <label class="resource-row">
                            <span>CPU 优先级</span>
                            <div class="priority-segment" role="radiogroup" aria-label="CPU 优先级">
                              <label
                                v-for="option in cpuPriorityOptions"
                                :key="option.value"
                                class="priority-option"
                                :class="{ selected: form.cpu_priority === option.value }"
                              >
                                <input v-model="form.cpu_priority" type="radio" :value="option.value" />
                                {{ option.label }}
                              </label>
                            </div>
                          </label>
                          <label class="resource-row">
                            <span>内存限制</span>
                            <input
                              v-model.trim="form.memory_limit_mb"
                              class="resource-slider"
                              type="range"
                              min="4"
                              :max="memoryLimitMaxMb"
                              step="64"
                            />
                            <span class="memory-input-wrap">
                              <input
                                v-model.trim="form.memory_limit_mb"
                                class="resource-number"
                                type="number"
                                min="4"
                                :max="memoryLimitMaxMb"
                                step="1"
                              />
                              <b>MB</b>
                            </span>
                            <small class="resource-limit-caption">上限 {{ memoryLimitMaxLabel }}</small>
                          </label>
                        </div>
                      </Transition>
                    </section>

                    <section class="form-section">
                      <div class="section-title">
                        <span class="material-symbol">admin_panel_settings</span>
                        <strong>权限能力</strong>
                      </div>
                      <div class="permission-grid">
                        <label
                          v-for="mode in permissionModes"
                          :key="mode.value"
                          class="choice-card"
                          :class="{ selected: form.permissionMode === mode.value, danger: mode.value === 'privileged' }"
                        >
                          <input v-model="form.permissionMode" type="radio" :value="mode.value" />
                          <span class="material-symbol">{{ mode.icon }}</span>
                          <strong>{{ mode.label }}</strong>
                          <small>{{ mode.description }}</small>
                        </label>
                      </div>

                      <Transition name="panel-rise">
                        <div v-if="form.permissionMode === 'capabilities'" class="capability-panel">
                          <section
                            v-for="group in capabilityGroups"
                            :key="group.title"
                            class="capability-group"
                            :class="{ elevated: group.elevated }"
                          >
                            <div class="capability-group-head">
                              <strong>{{ group.title }}</strong>
                              <small>{{ group.description }}</small>
                            </div>
                            <div class="capability-grid">
                              <label
                                v-for="capability in group.items"
                                :key="capability.value"
                                class="capability-chip"
                                :class="{ selected: form.cap_add.includes(capability.value) }"
                                :title="capability.description"
                              >
                                <input v-model="form.cap_add" type="checkbox" :value="capability.value" />
                                <strong>{{ capability.value }}</strong>
                                <small>{{ capability.label }}</small>
                              </label>
                            </div>
                          </section>
                        </div>
                      </Transition>
                    </section>
                  </div>
                </div>
              </section>
            </Transition>
          </form>

          <footer class="wizard-footer">
            <button class="secondary-button" type="button" :disabled="submitting" @click="handleClose">
              取消
            </button>
            <button v-if="step === 'advanced'" class="secondary-button" type="button" :disabled="submitting" @click="step = 'basic'">
              <span class="material-symbol">arrow_back</span>
              上一步
            </button>
            <button v-if="step === 'basic'" class="primary-button" type="button" :disabled="!canGoAdvanced" @click="step = 'advanced'">
              下一步
              <span class="material-symbol">arrow_forward</span>
            </button>
            <button v-else class="primary-button" type="button" :disabled="!canSubmit" @click="handleSubmit">
              <span class="material-symbol" :class="{ spinning: submitting }">
                {{ submitting ? 'progress_activity' : 'add_circle' }}
              </span>
              {{ submitting ? '创建中' : '创建容器' }}
            </button>
          </footer>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { createContainer, getOverview, listImages } from '../api'
import type {
  ContainerCreateRequest,
  ContainerEnvVar,
  ContainerPortBinding,
  ContainerVolumeMount,
  ImageSummary,
  OperationResponse,
  RestartPolicyName,
} from '../api/types'
import NoticeBanner from './NoticeBanner.vue'

type WizardStep = 'basic' | 'advanced'
type NetworkMode = 'bridge' | 'host' | 'custom'
type PermissionMode = 'default' | 'capabilities' | 'privileged'
type CpuPriority = 'low' | 'medium' | 'high'

interface CapabilityOption {
  value: string
  label: string
  description: string
}

interface CapabilityGroup {
  title: string
  description: string
  elevated?: boolean
  items: CapabilityOption[]
}

interface ContainerCreateForm {
  image: string
  name: string
  command: string
  networkMode: NetworkMode
  customNetwork: string
  restart_policy: RestartPolicyName
  permissionMode: PermissionMode
  cap_add: string[]
  resource_limits_enabled: boolean
  cpu_priority: CpuPriority
  memory_limit_mb: string
  pull_if_missing: boolean
  start: boolean
  env: ContainerEnvVar[]
  ports: ContainerPortBinding[]
  volumes: ContainerVolumeMount[]
}

const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  close: []
  created: [response: OperationResponse]
  notice: [response: OperationResponse]
}>()

const steps: Array<{ key: WizardStep; label: string; icon: string }> = [
  { key: 'basic', label: '基础信息', icon: 'looks_one' },
  { key: 'advanced', label: '高级设置', icon: 'looks_two' },
]

const restartPolicies: Array<{ value: RestartPolicyName; label: string }> = [
  { value: 'unless-stopped', label: 'unless-stopped' },
  { value: 'always', label: 'always' },
  { value: 'on-failure', label: 'on-failure' },
  { value: 'no', label: 'no' },
]

const cpuPriorityOptions: Array<{ value: CpuPriority; label: string; shares: number }> = [
  { value: 'low', label: '低', shares: 512 },
  { value: 'medium', label: '中', shares: 1024 },
  { value: 'high', label: '高', shares: 2048 },
]

const DEFAULT_MEMORY_LIMIT_MB = 1024
const MIN_MEMORY_LIMIT_MB = 4

const permissionModes: Array<{ value: PermissionMode; label: string; icon: string; description: string }> = [
  { value: 'default', label: '默认权限', icon: 'verified_user', description: '使用 Docker 默认 capability' },
  { value: 'capabilities', label: '单独添加权限', icon: 'rule_settings', description: '按需选择 Docker 支持的 Linux capability。' },
  { value: 'privileged', label: '完整特权', icon: 'warning', description: '给予容器完整特权' },
]

const capabilityGroups: CapabilityGroup[] = [
  {
    title: 'Docker 默认能力',
    description: '大多数应用不需要修改这些默认能力。',
    items: [
      { value: 'AUDIT_WRITE', label: '写审计日志', description: '向内核审计日志写入记录。' },
      { value: 'CHOWN', label: '修改所有者', description: '修改文件 UID/GID。' },
      { value: 'DAC_OVERRIDE', label: '绕过文件权限', description: '绕过普通文件读写执行权限检查。' },
      { value: 'FOWNER', label: '绕过属主检查', description: '绕过需要文件属主匹配的权限检查。' },
      { value: 'FSETID', label: '保留 setid 位', description: '修改文件时不清除 setuid/setgid 位。' },
      { value: 'KILL', label: '发送信号', description: '绕过发送进程信号的权限检查。' },
      { value: 'MKNOD', label: '创建设备文件', description: '允许使用 mknod 创建特殊文件。' },
      { value: 'NET_BIND_SERVICE', label: '绑定低位端口', description: '绑定 1024 以下的特权端口。' },
      { value: 'NET_RAW', label: '原始套接字', description: '使用 RAW 和 PACKET socket。' },
      { value: 'SETFCAP', label: '设置文件能力', description: '设置文件 capability。' },
      { value: 'SETGID', label: '修改 GID', description: '修改进程 GID 和附加组。' },
      { value: 'SETPCAP', label: '修改 capability', description: '修改进程 capability 集。' },
      { value: 'SETUID', label: '修改 UID', description: '修改进程 UID。' },
      { value: 'SYS_CHROOT', label: 'chroot', description: '使用 chroot 修改根目录。' },
    ],
  },
  {
    title: '额外授予能力',
    description: 'Docker 默认不授予；选择以扩大容器对应权限。',
    elevated: true,
    items: [
      { value: 'AUDIT_CONTROL', label: '管理审计', description: '启停内核审计、修改审计规则和状态。' },
      { value: 'AUDIT_READ', label: '读取审计日志', description: '通过 netlink 读取审计日志。' },
      { value: 'BLOCK_SUSPEND', label: '阻止休眠', description: '阻止系统进入 suspend。' },
      { value: 'BPF', label: 'BPF 操作', description: '创建 BPF map、加载 BPF 类型信息等。' },
      { value: 'CHECKPOINT_RESTORE', label: '检查点恢复', description: '执行 checkpoint/restore 相关操作。' },
      { value: 'DAC_READ_SEARCH', label: '绕过读/搜索权限', description: '绕过文件读取和目录搜索权限检查。' },
      { value: 'IPC_LOCK', label: '锁定内存', description: '允许 mlock、mlockall、共享内存锁定。' },
      { value: 'IPC_OWNER', label: 'IPC 属主绕过', description: '绕过 System V IPC 对象权限检查。' },
      { value: 'LEASE', label: '文件租约', description: '在任意文件上建立 lease。' },
      { value: 'LINUX_IMMUTABLE', label: '不可变标志', description: '设置 append-only 和 immutable inode 标志。' },
      { value: 'MAC_ADMIN', label: 'MAC 管理', description: '管理强制访问控制配置或状态。' },
      { value: 'MAC_OVERRIDE', label: '绕过 MAC', description: '覆盖强制访问控制策略。' },
      { value: 'NET_ADMIN', label: '网络管理', description: '执行网络接口、路由、防火墙等管理操作。' },
      { value: 'NET_BROADCAST', label: '网络广播', description: '发送广播并监听多播。' },
      { value: 'PERFMON', label: '性能观测', description: '使用 perf_events 等性能观测能力。' },
      { value: 'SYS_ADMIN', label: '系统管理', description: '范围很大的系统管理能力，高风险。' },
      { value: 'SYS_BOOT', label: '重启系统', description: '使用 reboot、kexec 等启动相关调用。' },
      { value: 'SYS_MODULE', label: '内核模块', description: '加载或卸载内核模块。' },
      { value: 'SYS_NICE', label: '调度优先级', description: '修改 nice 值和调度策略。' },
      { value: 'SYS_PACCT', label: '进程记账', description: '启停进程 accounting。' },
      { value: 'SYS_PTRACE', label: '进程跟踪', description: '使用 ptrace 跟踪任意进程。' },
      { value: 'SYS_RAWIO', label: '原始 I/O', description: '执行 I/O 端口操作。' },
      { value: 'SYS_RESOURCE', label: '资源限制', description: '覆盖资源限制。' },
      { value: 'SYS_TIME', label: '系统时间', description: '设置系统时钟和硬件时钟。' },
      { value: 'SYS_TTY_CONFIG', label: 'TTY 配置', description: '执行虚拟终端相关特权操作。' },
      { value: 'SYSLOG', label: '系统日志', description: '执行特权 syslog 操作。' },
      { value: 'WAKE_ALARM', label: '唤醒闹钟', description: '设置可唤醒系统的 alarm。' },
    ],
  },
]

const step = ref<WizardStep>('basic')
const images = ref<ImageSummary[]>([])
const loadingImages = ref(false)
const submitting = ref(false)
const localNotice = ref<OperationResponse | null>(null)
const hostMemoryTotal = ref<number | null>(null)
const form = reactive<ContainerCreateForm>(createEmptyForm())

const imageOptions = computed(() => {
  const values = images.value.flatMap((image) => image.tags.length ? image.tags : [image.id])
  return Array.from(new Set(values)).sort((a, b) => a.localeCompare(b))
})
const isHostNetwork = computed(() => form.networkMode === 'host')
const canGoAdvanced = computed(() => Boolean(form.image.trim()) && (form.networkMode !== 'custom' || Boolean(form.customNetwork.trim())))
const canSubmit = computed(() => canGoAdvanced.value && !submitting.value)
const networkLabel = computed(() => {
  if (form.networkMode === 'custom') return `网络：${form.customNetwork || '自定义'}`
  return `网络：${form.networkMode}`
})
const capabilitySummary = computed(() => {
  if (form.permissionMode === 'privileged') return '权限：完整特权'
  if (form.permissionMode === 'capabilities') return form.cap_add.length ? `权限：${form.cap_add.join(', ')}` : '权限：待选择 capability'
  return '权限：默认'
})
const cpuPriorityLabel = computed(() => cpuPriorityOptions.find((option) => option.value === form.cpu_priority)?.label ?? '中')
const resourceSummary = computed(() => {
  if (!form.resource_limits_enabled) return '资源：不限制'
  return `资源：CPU ${cpuPriorityLabel.value} / 内存 ${form.memory_limit_mb || '未设置'} MB`
})
const memoryLimitMaxMb = computed(() => {
  if (hostMemoryTotal.value && hostMemoryTotal.value > 0) {
    // 使用 Docker 报告的宿主内存，避免滑块上限脱离真实机器。
    return Math.max(MIN_MEMORY_LIMIT_MB, Math.floor(hostMemoryTotal.value / 1024 / 1024))
  }
  const current = Number.parseInt(form.memory_limit_mb, 10)
  return Math.max(DEFAULT_MEMORY_LIMIT_MB, Number.isFinite(current) ? current : DEFAULT_MEMORY_LIMIT_MB)
})
const memoryLimitMaxLabel = computed(() => `${memoryLimitMaxMb.value.toLocaleString()} MB`)

function createEmptyForm(): ContainerCreateForm {
  return {
    image: '',
    name: '',
    command: '',
    networkMode: 'bridge',
    customNetwork: '',
    restart_policy: 'unless-stopped',
    permissionMode: 'default',
    cap_add: [],
    resource_limits_enabled: false,
    cpu_priority: 'medium',
    memory_limit_mb: '',
    pull_if_missing: true,
    start: true,
    env: [],
    ports: [],
    volumes: [],
  }
}

function resetForm() {
  Object.assign(form, createEmptyForm())
  step.value = 'basic'
  localNotice.value = null
}

function stepOrder(value: WizardStep): number {
  return steps.findIndex((item) => item.key === value)
}

function optionalText(value: string): string | null {
  const trimmed = value.trim()
  return trimmed ? trimmed : null
}

function optionalInteger(value: string): number | null {
  const trimmed = value.trim()
  if (!trimmed) return null
  const parsed = Number(trimmed)
  return Number.isFinite(parsed) ? Math.trunc(parsed) : null
}

function cpuPriorityValue(): number {
  // 处理器权重 cpu_shares 是相对值，不是绝对 CPU 配额。
  return cpuPriorityOptions.find((option) => option.value === form.cpu_priority)?.shares ?? 1024
}

function clampMemoryLimit(value: number | null): number | null {
  if (value === null) return null
  return Math.min(Math.max(value, MIN_MEMORY_LIMIT_MB), memoryLimitMaxMb.value)
}

function ensureMemoryLimitDefault() {
  if (!form.resource_limits_enabled) return
  // 启用限制时填入合理默认值，并把旧值夹到当前宿主机上限内。
  const current = optionalInteger(form.memory_limit_mb)
  const next = clampMemoryLimit(current ?? DEFAULT_MEMORY_LIMIT_MB)
  form.memory_limit_mb = next === null ? '' : String(next)
}

function resolveNetwork(): string | null {
  if (form.networkMode === 'custom') return optionalText(form.customNetwork)
  return form.networkMode
}

function buildPayload(): ContainerCreateRequest {
  const ports = isHostNetwork.value
    ? []
    : form.ports
      .map((item) => ({
        container_port: item.container_port.trim(),
        host_port: item.host_port?.trim() || null,
        protocol: item.protocol,
        host_ip: item.host_ip.trim() || '0.0.0.0',
      }))
      .filter((item) => item.container_port)

  return {
    image: form.image.trim(),
    name: optionalText(form.name),
    command: optionalText(form.command),
    env: form.env
      .map((item) => ({ key: item.key.trim(), value: item.value }))
      .filter((item) => item.key),
    ports,
    volumes: form.volumes
      .map((item) => ({
        host_path: item.host_path.trim(),
        container_path: item.container_path.trim(),
        mode: item.mode,
      }))
      .filter((item) => item.host_path && item.container_path),
    restart_policy: form.restart_policy,
    network: resolveNetwork(),
    // 界面上让 privileged 和 cap_add 互斥，避免权限请求含义不清。
    privileged: form.permissionMode === 'privileged',
    cap_add: form.permissionMode === 'capabilities' ? [...form.cap_add] : [],
    resource_limits_enabled: form.resource_limits_enabled,
    cpu_priority: form.resource_limits_enabled ? cpuPriorityValue() : null,
    memory_limit_mb: form.resource_limits_enabled ? clampMemoryLimit(optionalInteger(form.memory_limit_mb)) : null,
    pull_if_missing: form.pull_if_missing,
    start: form.start,
  }
}

function addPortBinding() {
  form.ports.push({
    host_ip: '0.0.0.0',
    host_port: '',
    container_port: '',
    protocol: 'tcp',
  })
}

function removePortBinding(index: number) {
  form.ports.splice(index, 1)
}

function addEnvVar() {
  form.env.push({ key: '', value: '' })
}

function removeEnvVar(index: number) {
  form.env.splice(index, 1)
}

function addVolumeMount() {
  form.volumes.push({ host_path: '', container_path: '', mode: 'rw' })
}

function removeVolumeMount(index: number) {
  form.volumes.splice(index, 1)
}

function handleClose() {
  // 创建请求进行中时禁止关闭弹窗。
  if (submitting.value) return
  emit('close')
}

async function handleSubmit() {
  if (!canSubmit.value) {
    step.value = 'basic'
    return
  }
  submitting.value = true
  localNotice.value = null
  try {
    const response = await createContainer(buildPayload())
    if (response.ok) {
      emit('created', response)
      resetForm()
      emit('close')
    } else {
      localNotice.value = response
      emit('notice', response)
    }
  } catch (err) {
    localNotice.value = { ok: false, message: '容器创建请求失败。', data: {}, error: String(err), timestamp: new Date().toISOString() }
    emit('notice', localNotice.value)
  } finally {
    submitting.value = false
  }
}

async function loadImages() {
  loadingImages.value = true
  try {
    const response = await listImages()
    images.value = response.images
  } catch (err) {
    localNotice.value = { ok: false, message: '读取本地镜像失败。', data: {}, error: String(err), timestamp: new Date().toISOString() }
  } finally {
    loadingImages.value = false
  }
}

async function loadHostOverview() {
  try {
    const response = await getOverview()
    hostMemoryTotal.value = response.host_memory_total ?? null
    ensureMemoryLimitDefault()
  } catch {
    hostMemoryTotal.value = null
  }
}

watch(() => props.open, (value) => {
  if (value) {
    // 每次打开都重置表单，避免上一次失败输入带入新的创建流程。
    resetForm()
    void loadImages()
    void loadHostOverview()
  }
})

watch(() => form.networkMode, (value) => {
  if (value === 'host') {
    // 主机网络模式会忽略端口映射，切换过去时直接清空端口配置。
    form.ports = []
  }
})

watch(() => form.permissionMode, (value) => {
  if (value !== 'capabilities') {
    // 只有显式选择 capability 模式时才提交 cap_add。
    form.cap_add = []
  }
})

watch(() => form.resource_limits_enabled, (value) => {
  if (value) ensureMemoryLimitDefault()
})

watch(hostMemoryTotal, () => {
  ensureMemoryLimitDefault()
})

onMounted(() => {
  if (props.open) {
    void loadImages()
    void loadHostOverview()
  }
})
</script>

<style scoped>
.wizard-backdrop {
  position: fixed;
  inset: 0;
  z-index: 80;
  display: grid;
  place-items: center;
  padding: 28px;
  background: color-mix(in srgb, #0f1720 44%, transparent);
  backdrop-filter: blur(8px);
}

.wizard-dialog {
  display: grid;
  grid-template-rows: auto auto auto 1fr auto;
  width: min(1040px, 100%);
  max-height: min(860px, calc(100vh - 56px));
  overflow: hidden;
  border: 1px solid var(--md-sys-color-outline-variant);
  border-radius: 28px;
  background: var(--md-sys-color-surface);
  box-shadow: var(--md-elevation-3);
}

.wizard-header,
.wizard-footer {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 18px 20px;
}

.wizard-header {
  justify-content: space-between;
  border-bottom: 1px solid var(--md-sys-color-outline-variant);
}

.wizard-header h2 {
  margin: 0;
  color: var(--md-sys-color-on-surface);
  font-size: 24px;
}

.wizard-steps {
  display: flex;
  gap: 10px;
  padding: 14px 20px;
  border-bottom: 1px solid var(--md-sys-color-outline-variant);
  background: var(--md-sys-color-surface-container-lowest);
}

.step-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 38px;
  padding: 0 14px;
  border-radius: 19px;
  background: var(--md-sys-color-surface-container);
  color: var(--md-sys-color-on-surface-variant);
  cursor: pointer;
  font-size: 13px;
  font-weight: 800;
  transition: background-color 0.18s ease, color 0.18s ease, transform 0.18s ease;
}

.step-pill.active,
.step-pill.done {
  background: var(--md-sys-color-primary-container);
  color: var(--md-sys-color-on-primary-container);
}

.step-pill:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.step-pill:active:not(:disabled) {
  transform: scale(0.98);
}

.wizard-body {
  min-height: 0;
  overflow: auto;
  padding: 20px;
}

.wizard-page {
  display: grid;
  gap: 18px;
}

.section-heading,
.section-title {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  color: var(--md-sys-color-on-surface);
}

.section-heading .material-symbol,
.section-title .material-symbol {
  color: var(--md-sys-color-primary);
  font-size: 20px;
}

.section-heading strong,
.section-heading small,
.section-title strong {
  display: block;
}

.section-heading small {
  margin-top: 4px;
  color: var(--md-sys-color-on-surface-variant);
  font-size: 12px;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.field-row {
  display: grid;
  gap: 7px;
  min-width: 0;
}

.field-row.wide {
  grid-column: 1 / -1;
}

.field-row span {
  color: var(--md-sys-color-on-surface-variant);
  font-size: 12px;
  font-weight: 800;
}

.option-strip {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.switch-row {
  display: grid;
  grid-template-columns: 20px 1fr;
  gap: 10px;
  align-items: start;
  min-width: 0;
  padding: 12px;
  border: 1px solid var(--md-sys-color-outline-variant);
  border-radius: 16px;
  background: var(--md-sys-color-surface-container-low);
  cursor: pointer;
}

.switch-row input {
  width: 18px;
  height: 18px;
  margin: 2px 0 0;
  accent-color: var(--md-sys-color-primary);
}

.switch-row strong,
.switch-row small {
  display: block;
}

.switch-row strong {
  color: var(--md-sys-color-on-surface);
  font-size: 13px;
}

.switch-row small {
  margin-top: 4px;
  color: var(--md-sys-color-on-surface-variant);
  font-size: 12px;
  line-height: 1.45;
}

.image-state {
  display: flex;
  gap: 10px;
  align-items: center;
  min-height: 40px;
  padding: 0 12px;
  border-radius: 16px;
  background: var(--md-sys-color-surface-container-low);
  color: var(--md-sys-color-on-surface-variant);
  font-size: 13px;
  font-weight: 700;
}

.image-state .material-symbol {
  color: var(--md-sys-color-primary);
  font-size: 18px;
}

.text-action {
  margin-left: auto;
  background: transparent;
  color: var(--md-sys-color-primary);
  cursor: pointer;
  font-size: 13px;
  font-weight: 800;
}

.advanced-layout {
  display: grid;
  grid-template-columns: minmax(210px, 0.32fr) minmax(0, 1fr);
  gap: 18px;
}

.advanced-summary {
  display: grid;
  align-content: start;
  gap: 8px;
  min-width: 0;
  padding: 16px;
  border-radius: 20px;
  background: var(--md-sys-color-surface-container-low);
}

.advanced-summary .material-symbol {
  color: var(--md-sys-color-primary);
  font-size: 24px;
}

.advanced-summary strong,
.advanced-summary small {
  min-width: 0;
  overflow-wrap: anywhere;
}

.advanced-summary small {
  color: var(--md-sys-color-on-surface-variant);
  font-size: 12px;
}

.advanced-content,
.form-section {
  display: grid;
  gap: 12px;
}

.form-section {
  padding: 14px;
  border: 1px solid var(--md-sys-color-outline-variant);
  border-radius: 20px;
  background: var(--md-sys-color-surface-container-lowest);
}

.action-title {
  justify-content: space-between;
}

.action-title > div {
  display: inline-flex;
  gap: 9px;
  align-items: center;
}

.small-action,
.secondary-button,
.primary-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 40px;
  border-radius: 20px;
  font-weight: 700;
  cursor: pointer;
  transition: background-color 0.18s ease, box-shadow 0.18s ease, transform 0.18s ease;
}

.small-action {
  min-height: 34px;
  padding: 0 12px;
  border-radius: 17px;
  background: var(--md-sys-color-surface-container);
  color: var(--md-sys-color-on-surface-variant);
  font-size: 12px;
}

.secondary-button {
  padding: 0 18px;
  background: var(--md-sys-color-surface-container);
  color: var(--md-sys-color-on-surface-variant);
}

.primary-button {
  padding: 0 22px;
  background: var(--md-sys-color-primary);
  color: var(--md-sys-color-on-primary);
}

.small-action:hover:not(:disabled),
.secondary-button:hover:not(:disabled) {
  background: var(--md-sys-color-primary-container);
  color: var(--md-sys-color-on-primary-container);
  box-shadow: var(--md-elevation-1);
}

.primary-button:hover:not(:disabled) {
  box-shadow: var(--md-elevation-1);
}

.small-action:active:not(:disabled),
.secondary-button:active:not(:disabled),
.primary-button:active:not(:disabled) {
  transform: scale(0.98);
}

.small-action:disabled,
.secondary-button:disabled,
.primary-button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.dynamic-list {
  display: grid;
  gap: 8px;
}

.dynamic-row {
  display: grid;
  gap: 8px;
  align-items: center;
}

.ports-row {
  grid-template-columns: minmax(120px, 0.8fr) minmax(110px, 0.7fr) minmax(120px, 0.7fr) 96px 34px;
}

.env-row {
  grid-template-columns: minmax(160px, 0.45fr) minmax(0, 1fr) 34px;
}

.volume-row {
  grid-template-columns: minmax(180px, 1fr) minmax(180px, 1fr) 96px 34px;
}

.resource-title {
  align-items: center;
  justify-content: space-between;
}

.resource-title-left {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.resource-enable {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  gap: 9px;
  min-width: 0;
  margin-left: auto;
  color: var(--md-sys-color-on-surface-variant);
  cursor: pointer;
  font-size: 13px;
  font-weight: 800;
}

.resource-enable input {
  width: 20px;
  height: 20px;
  margin: 0;
  accent-color: var(--md-sys-color-primary);
}

.resource-simple {
  display: grid;
  gap: 14px;
  padding-top: 4px;
}

.resource-row {
  display: grid;
  grid-template-columns: 120px minmax(0, 1fr) minmax(112px, auto);
  gap: 14px;
  align-items: center;
}

.resource-row > span:first-child {
  color: var(--md-sys-color-on-surface-variant);
  font-size: 14px;
  font-weight: 800;
}

.priority-segment {
  display: grid;
  grid-column: 2 / -1;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 6px;
  min-width: 0;
  padding: 4px;
  border: 1px solid var(--md-sys-color-outline-variant);
  border-radius: 14px;
  background: var(--md-sys-color-surface-container-low);
}

.priority-option {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 36px;
  border-radius: 10px;
  color: var(--md-sys-color-on-surface-variant);
  cursor: pointer;
  font-size: 13px;
  font-weight: 800;
  transition: background-color 0.18s ease, color 0.18s ease, box-shadow 0.18s ease, transform 0.18s ease;
}

.priority-option input {
  position: absolute;
  opacity: 0;
  pointer-events: none;
}

.priority-option.selected {
  background: var(--md-sys-color-primary);
  color: var(--md-sys-color-on-primary);
  box-shadow: var(--md-elevation-1);
}

.priority-option:active {
  transform: scale(0.98);
}

.resource-slider {
  width: 100%;
  min-width: 0;
  accent-color: var(--md-sys-color-primary);
}

.resource-number {
  width: 112px;
  min-height: 44px;
  padding: 0 12px;
  border: 1px solid var(--md-sys-color-outline-variant);
  border-radius: 12px;
  background: var(--md-sys-color-surface);
  color: var(--md-sys-color-on-surface);
  font: 700 14px var(--font-mono);
}

.memory-input-wrap {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  justify-self: end;
}

.memory-input-wrap b {
  color: var(--md-sys-color-on-surface-variant);
  font-size: 13px;
}

.resource-limit-caption {
  grid-column: 2 / -1;
  color: var(--md-sys-color-on-surface-variant);
  font-size: 12px;
  font-weight: 700;
}

.empty-inline,
.host-network-note {
  min-height: 42px;
  padding: 12px 14px;
  border: 1px dashed var(--md-sys-color-outline-variant);
  border-radius: 16px;
  background: var(--md-sys-color-surface-container-lowest);
  color: var(--md-sys-color-on-surface-variant);
  font-size: 13px;
  font-weight: 700;
}

.host-network-note {
  display: grid;
  grid-template-columns: 24px 1fr;
  gap: 10px;
  border-style: solid;
  background: var(--state-info-container);
  color: var(--state-info);
}

.host-network-note strong,
.host-network-note small {
  display: block;
}

.host-network-note small {
  margin-top: 4px;
  color: var(--md-sys-color-on-surface-variant);
  font-size: 12px;
}

.icon-action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 17px;
  background: var(--md-sys-color-surface-container);
  color: var(--md-sys-color-on-surface-variant);
  cursor: pointer;
  transition: background-color 0.18s ease, color 0.18s ease, transform 0.18s ease;
}

.icon-action.danger:hover:not(:disabled) {
  background: var(--md-sys-color-error-container);
  color: var(--md-sys-color-error);
}

.icon-action .material-symbol {
  font-size: 18px;
}

.permission-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.choice-card {
  display: grid;
  gap: 7px;
  min-width: 0;
  padding: 12px;
  border: 1px solid var(--md-sys-color-outline-variant);
  border-radius: 18px;
  background: var(--md-sys-color-surface);
  cursor: pointer;
  transition: background-color 0.18s ease, border-color 0.18s ease, transform 0.18s ease;
}

.choice-card input,
.capability-chip input {
  position: absolute;
  opacity: 0;
  pointer-events: none;
}

.choice-card .material-symbol {
  color: var(--md-sys-color-primary);
  font-size: 22px;
}

.choice-card strong,
.choice-card small {
  display: block;
}

.choice-card small {
  color: var(--md-sys-color-on-surface-variant);
  font-size: 12px;
  line-height: 1.45;
}

.choice-card.selected {
  border-color: color-mix(in srgb, var(--md-sys-color-primary) 56%, var(--md-sys-color-outline-variant));
  background: var(--md-sys-color-primary-container);
}

.choice-card.danger.selected {
  border-color: color-mix(in srgb, var(--md-sys-color-error) 56%, var(--md-sys-color-outline-variant));
  background: var(--md-sys-color-error-container);
}

.capability-panel {
  display: grid;
  gap: 12px;
}

.capability-group {
  display: grid;
  gap: 10px;
  padding: 12px;
  border: 1px solid var(--md-sys-color-outline-variant);
  border-radius: 18px;
  background: var(--md-sys-color-surface-container-lowest);
}

.capability-group.elevated {
  border-color: color-mix(in srgb, var(--md-sys-color-error) 24%, var(--md-sys-color-outline-variant));
}

.capability-group-head {
  display: grid;
  gap: 4px;
}

.capability-group-head strong {
  color: var(--md-sys-color-on-surface);
  font-size: 13px;
}

.capability-group-head small {
  color: var(--md-sys-color-on-surface-variant);
  font-size: 12px;
  line-height: 1.45;
}

.capability-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}

.capability-chip {
  display: grid;
  gap: 3px;
  min-height: 58px;
  padding: 10px;
  border: 1px solid var(--md-sys-color-outline-variant);
  border-radius: 16px;
  background: var(--md-sys-color-surface);
  cursor: pointer;
}

.capability-chip.selected {
  border-color: color-mix(in srgb, var(--md-sys-color-primary) 56%, var(--md-sys-color-outline-variant));
  background: var(--md-sys-color-primary-container);
}

.capability-chip strong {
  font-family: var(--font-mono);
  font-size: 12px;
}

.capability-chip small {
  color: var(--md-sys-color-on-surface-variant);
  font-size: 11px;
}

.wizard-footer {
  justify-content: flex-end;
  border-top: 1px solid var(--md-sys-color-outline-variant);
  background: var(--md-sys-color-surface-container-lowest);
}

.spinning {
  animation: spin 0.9s linear infinite;
}

.wizard-fade-enter-active,
.wizard-fade-leave-active {
  transition: opacity 0.2s ease;
}

.wizard-fade-enter-active .wizard-dialog,
.wizard-fade-leave-active .wizard-dialog {
  transition: opacity 0.22s ease, transform 0.26s var(--ease-standard);
}

.wizard-fade-enter-from,
.wizard-fade-leave-to {
  opacity: 0;
}

.wizard-fade-enter-from .wizard-dialog,
.wizard-fade-leave-to .wizard-dialog {
  opacity: 0;
  transform: translateY(12px) scale(0.985);
}

@media (max-width: 900px) {
  .wizard-backdrop {
    padding: 14px;
  }

  .advanced-layout,
  .form-grid,
  .option-strip,
  .permission-grid,
  .capability-grid {
    grid-template-columns: 1fr;
  }

  .ports-row,
  .env-row,
  .volume-row,
  .resource-row {
    grid-template-columns: 1fr;
  }

  .priority-segment,
  .resource-limit-caption {
    grid-column: 1;
  }

  .memory-input-wrap {
    justify-self: stretch;
  }

  .memory-input-wrap .resource-number,
  .resource-number {
    width: 100%;
  }

  .dynamic-row .icon-action {
    justify-self: start;
  }

  .wizard-footer {
    flex-wrap: wrap;
  }
}
</style>
