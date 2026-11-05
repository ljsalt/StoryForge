<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  NButton,
  NDescriptions,
  NDescriptionsItem,
  NEmpty,
  NModal,
  NSelect,
  NSpin,
  NTag,
  useMessage,
} from 'naive-ui'
import { extractError } from '../../api/error'
import { formatDateTime } from '../../utils/format'
import {
  getAiTask,
  listAiTasks,
  AI_STATUS_LABELS,
  AI_STATUS_TYPES,
  AI_TASK_TYPE_LABELS,
  AI_TASK_TYPE_OPTIONS,
  type AiTask,
  type AiTaskStatus,
  type AiTaskType,
} from '../../api/ai'
import { useNovelStore } from '../../stores/novels'

const props = defineProps<{ novelId: string | null }>()
const emit = defineEmits<{ 'update:novelId': [value: string | null] }>()

const novelStore = useNovelStore()
const message = useMessage()

const tasks = ref<AiTask[]>([])
const loading = ref(false)
const statusFilter = ref<AiTaskStatus | null>(null)
const typeFilter = ref<AiTaskType | null>(null)

const showDetail = ref(false)
const detail = ref<AiTask | null>(null)

const novelOptions = computed(() =>
  novelStore.novels.map((n) => ({ label: n.title, value: n.id })),
)
const statusOptions = computed(() => [
  { label: '全部状态', value: '' },
  ...Object.entries(AI_STATUS_LABELS).map(([value, label]) => ({ label, value })),
])
const typeOptions = computed(() => [
  { label: '全部类型', value: '' },
  ...AI_TASK_TYPE_OPTIONS,
])

async function load() {
  if (!props.novelId) {
    tasks.value = []
    return
  }
  loading.value = true
  try {
    const { data } = await listAiTasks(props.novelId, {
      ...(statusFilter.value ? { status: statusFilter.value } : {}),
      ...(typeFilter.value ? { task_type: typeFilter.value } : {}),
      limit: 100,
    })
    tasks.value = data
  } catch (error) {
    message.error(extractError(error, '加载任务记录失败'))
  } finally {
    loading.value = false
  }
}

watch(() => [props.novelId, statusFilter.value, typeFilter.value], load, { immediate: true })

async function openDetail(task: AiTask) {
  if (!props.novelId) return
  try {
    const { data } = await getAiTask(props.novelId, task.id)
    detail.value = data
    showDetail.value = true
  } catch (error) {
    message.error(extractError(error, '加载任务详情失败'))
  }
}

function taskLabel(taskType: string): string {
  return AI_TASK_TYPE_LABELS[taskType as AiTaskType] || taskType
}

function tokenText(task: AiTask): string {
  const parts: string[] = []
  if (task.input_tokens != null) parts.push(`入 ${task.input_tokens}`)
  if (task.output_tokens != null) parts.push(`出 ${task.output_tokens}`)
  if (!parts.length && task.estimated_tokens != null) parts.push(`估算 ${task.estimated_tokens}`)
  return parts.join(' / ')
}
</script>

<template>
  <div class="panel">
    <div class="toolbar">
      <n-select
        :value="novelId"
        :options="novelOptions"
        filterable
        clearable
        placeholder="选择小说"
        class="novel-select"
        @update:value="(v: string | null) => emit('update:novelId', v)"
      />
      <n-select
        :value="statusFilter"
        :options="statusOptions"
        class="filter"
        :disabled="!novelId"
        @update:value="(v: string) => { statusFilter = (v || null) as AiTaskStatus | null }"
      />
      <n-select
        :value="typeFilter"
        :options="typeOptions"
        class="filter"
        :disabled="!novelId"
        @update:value="(v: string) => { typeFilter = (v || null) as AiTaskType | null }"
      />
      <n-button size="small" :disabled="!novelId" @click="load">刷新</n-button>
    </div>

    <n-spin :show="loading">
      <n-empty v-if="!novelId" description="请先选择小说" />
      <n-empty v-else-if="!tasks.length" description="暂无任务记录" />
      <div v-else class="list">
        <button v-for="task in tasks" :key="task.id" class="item" @click="openDetail(task)">
          <div class="item-head">
            <n-tag size="small" round :bordered="false" :type="AI_STATUS_TYPES[task.status]">
              {{ AI_STATUS_LABELS[task.status] }}
            </n-tag>
            <n-tag size="small" round :bordered="false" type="info">{{ taskLabel(task.task_type) }}</n-tag>
            <span class="model">{{ task.model_identifier || '（未记录模型）' }}</span>
            <n-tag v-if="task.truncated" size="small" round :bordered="false" type="warning">截断</n-tag>
          </div>
          <div class="item-summary">{{ task.output_summary || task.input_summary || '（无摘要）' }}</div>
          <div class="item-meta">
            <span v-if="task.error_code" class="error">错误：{{ task.error_code }}</span>
            <span v-if="tokenText(task)">{{ tokenText(task) }}</span>
            <span v-if="task.latency_ms != null">{{ task.latency_ms }} ms</span>
            <span>{{ formatDateTime(task.created_at) }}</span>
          </div>
        </button>
      </div>
    </n-spin>

    <n-modal
      :show="showDetail"
      preset="card"
      title="AI 任务详情"
      :style="{ width: '640px', maxWidth: 'calc(100vw - 24px)' }"
      :bordered="false"
      @update:show="showDetail = $event"
    >
      <template v-if="detail">
        <n-descriptions :column="2" label-placement="left" bordered size="small">
          <n-descriptions-item label="状态">
            <n-tag size="small" round :bordered="false" :type="AI_STATUS_TYPES[detail.status]">
              {{ AI_STATUS_LABELS[detail.status] }}
            </n-tag>
          </n-descriptions-item>
          <n-descriptions-item label="任务类型">{{ taskLabel(detail.task_type) }}</n-descriptions-item>
          <n-descriptions-item label="模型">{{ detail.model_identifier || '-' }}</n-descriptions-item>
          <n-descriptions-item label="耗时">{{ detail.latency_ms != null ? `${detail.latency_ms} ms` : '-' }}</n-descriptions-item>
          <n-descriptions-item label="输入 tokens">{{ detail.input_tokens ?? '-' }}</n-descriptions-item>
          <n-descriptions-item label="输出 tokens">{{ detail.output_tokens ?? '-' }}</n-descriptions-item>
          <n-descriptions-item label="估算 tokens">{{ detail.estimated_tokens ?? '-' }}</n-descriptions-item>
          <n-descriptions-item label="是否截断">{{ detail.truncated ? '是' : '否' }}</n-descriptions-item>
          <n-descriptions-item label="输入摘要" :span="2">{{ detail.input_summary || '（无）' }}</n-descriptions-item>
          <n-descriptions-item label="输出摘要" :span="2">{{ detail.output_summary || '（无）' }}</n-descriptions-item>
          <n-descriptions-item v-if="detail.error_code" label="错误码">{{ detail.error_code }}</n-descriptions-item>
          <n-descriptions-item v-if="detail.error_message" label="错误信息">{{ detail.error_message }}</n-descriptions-item>
          <n-descriptions-item v-if="detail.prompt_template_id" label="模板">
            {{ detail.prompt_template_id }}<template v-if="detail.template_version">（v{{ detail.template_version }}）</template>
          </n-descriptions-item>
          <n-descriptions-item label="开始时间">{{ detail.started_at ? formatDateTime(detail.started_at) : '-' }}</n-descriptions-item>
          <n-descriptions-item label="完成时间">{{ detail.completed_at ? formatDateTime(detail.completed_at) : '-' }}</n-descriptions-item>
        </n-descriptions>
        <div class="note">任务记录仅用于审计与排错，不保存完整提示词与完整正文。</div>
      </template>
    </n-modal>
  </div>
</template>

<style scoped>
.panel { padding-top: 4px; }
.toolbar { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
.novel-select { width: 200px; }
.filter { width: 140px; }
.list { display: flex; flex-direction: column; gap: 6px; }
.item {
  display: block; width: 100%; text-align: left; cursor: pointer;
  background: rgba(255, 255, 255, 0.04); border: none; border-radius: 6px;
  padding: 10px 12px; transition: background 0.15s;
}
.item:hover { background: rgba(255, 255, 255, 0.08); }
.item-head { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.model { font-size: 12px; color: rgba(255, 255, 255, 0.7); }
.item-summary {
  font-size: 12px; color: rgba(255, 255, 255, 0.6); margin-top: 4px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.item-meta { display: flex; gap: 12px; flex-wrap: wrap; font-size: 12px; color: rgba(255, 255, 255, 0.4); margin-top: 4px; }
.error { color: #f0a0a0; }
.note { margin-top: 10px; font-size: 12px; color: rgba(255, 255, 255, 0.4); }
</style>
