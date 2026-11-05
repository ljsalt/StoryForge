<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useMessage } from 'naive-ui'
import {
  NAlert,
  NButton,
  NCard,
  NSelect,
  NTag,
  type SelectOption,
} from 'naive-ui'
import {
  TASK_DESCRIPTIONS,
  TASK_LABELS,
  saveModelSettings,
  type TaskKey,
} from '../../api/models'
import { extractError } from '../../api/error'
import { useModelStore } from '../../stores/models'

const store = useModelStore()
const message = useMessage()

const TASKS: TaskKey[] = ['planner', 'writer', 'editor', 'assistant']

const form = reactive<Record<TaskKey, string | null>>({
  planner: null,
  writer: null,
  editor: null,
  assistant: null,
})
const defaultModelId = ref<string | null>(null)
const saving = ref(false)

watch(
  () => store.settings,
  (settings) => {
    for (const task of TASKS) {
      const found = settings.tasks.find((item) => item.task === task)
      form[task] = found?.model_id ?? null
    }
    defaultModelId.value = settings.default_model_id
  },
  { deep: true, immediate: true },
)

const modelOptions = computed<SelectOption[]>(() =>
  store.models.map((item) => ({
    label: `${item.provider_name} / ${item.name}（${item.model_id}）${item.enabled ? '' : ' · 已停用'}`,
    value: item.id,
  })),
)

async function save() {
  saving.value = true
  try {
    await saveModelSettings({
      tasks: {
        planner: form.planner,
        writer: form.writer,
        editor: form.editor,
        assistant: form.assistant,
      },
      default_model_id: defaultModelId.value,
    })
    message.success('任务模型分配已保存')
    await store.refreshProviders()
  } catch (error) {
    message.error(extractError(error))
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <n-card>
    <div class="header">
      <div class="hint">为不同创作任务指定模型；未指定或模型停用时自动使用全局默认模型。</div>
      <n-button type="primary" size="small" :loading="saving" @click="save">
        保存分配
      </n-button>
    </div>

    <n-alert v-if="!store.models.length" type="warning" :bordered="false" class="tip">
      还没有可用模型，请先在「模型管理」标签页添加模型。
    </n-alert>

    <div class="task-list">
      <div v-for="task in TASKS" :key="task" class="task-row">
        <div class="task-info">
          <div class="task-title">
            {{ TASK_LABELS[task] }}
            <n-tag v-if="!form[task]" size="tiny" round class="fallback-tag">
              回退默认
            </n-tag>
          </div>
          <div class="task-desc">{{ TASK_DESCRIPTIONS[task] }}</div>
        </div>
        <n-select
          v-model:value="form[task]"
          :options="modelOptions"
          clearable
          placeholder="未指定（使用全局默认模型）"
          class="task-select"
        />
      </div>
    </div>

    <div class="default-block">
      <div class="task-info">
        <div class="task-title">全局默认模型</div>
        <div class="task-desc">所有未单独分配任务的模型请求都会使用该模型</div>
      </div>
      <n-select
        v-model:value="defaultModelId"
        :options="modelOptions"
        clearable
        placeholder="未设置全局默认模型"
        class="task-select"
      />
    </div>
  </n-card>
</template>

<style scoped>
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.hint {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.55);
}

.tip {
  margin-bottom: 12px;
  font-size: 12px;
}

.task-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.task-row,
.default-block {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.07);
}

.default-block {
  border-bottom: none;
  border-top: 1px solid rgba(255, 255, 255, 0.12);
  margin-top: 4px;
}

.task-title {
  font-size: 14px;
  font-weight: 600;
  color: #fff;
  display: flex;
  align-items: center;
  gap: 8px;
}

.fallback-tag {
  font-weight: 400;
}

.task-desc {
  margin-top: 4px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.45);
}

.task-select {
  width: min(360px, 55vw);
  flex-shrink: 0;
}

@media (max-width: 767px) {
  .task-row,
  .default-block {
    flex-direction: column;
    align-items: stretch;
    gap: 8px;
  }

  .task-select {
    width: 100%;
  }
}
</style>
