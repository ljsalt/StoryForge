<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  NButton,
  NCard,
  NCheckbox,
  NCheckboxGroup,
  NCollapse,
  NCollapseItem,
  NInput,
  NInputNumber,
  NSelect,
  NSwitch,
  NTag,
} from 'naive-ui'
import type { ModelItem } from '../../api/models'
import {
  CONTEXT_MODE_HINTS,
  CONTEXT_MODE_LABELS,
  SESSION_STATUS_LABELS,
  SESSION_STATUS_TYPES,
  type ContextMode,
  type QuickWritingMeta,
  type QuickWritingSession,
  type QuickWritingSessionUpdate,
  type WritingPreset,
} from '../../api/quickWriting'

const props = defineProps<{
  session: QuickWritingSession
  presets: WritingPreset[]
  models: ModelItem[]
  meta: QuickWritingMeta | null
  saving?: boolean
}>()

const emit = defineEmits<{
  (event: 'save', payload: QuickWritingSessionUpdate): void
  (event: 'manage-presets'): void
  (event: 'preview-context'): void
}>()

const title = ref('')
const presetId = ref('__none__')
const modelId = ref('__default__')
const targetWordCount = ref(1500)
const segmentWords = ref(700)
const contextMode = ref<ContextMode>('auto')
const sections = ref<string[]>([])
const includeRecentChapter = ref(false)
const autoContinuity = ref(false)
const autoMemory = ref(false)
const remindMemory = ref(true)

function sync() {
  const session = props.session
  title.value = session.title
  presetId.value = session.preset_id || '__none__'
  modelId.value = session.model_id || '__default__'
  targetWordCount.value = session.target_word_count
  segmentWords.value = session.segment_words
  contextMode.value = session.context_mode
  const options = session.context_options || {}
  sections.value = Array.isArray(options.sections) ? (options.sections as string[]) : []
  includeRecentChapter.value = Boolean(options.include_recent_chapter)
  autoContinuity.value = session.auto_continuity
  autoMemory.value = session.auto_memory
  remindMemory.value = session.remind_memory
}

watch(() => props.session, sync, { immediate: true })

const presetOptions = computed(() => [
  { label: '不使用预设（内置写作提示）', value: '__none__' },
  ...props.presets
    .filter((preset) => preset.is_active)
    .map((preset) => ({
      label: preset.is_default ? `${preset.name}（全局默认）` : preset.name,
      value: preset.id,
    })),
])

const modelOptions = computed(() => [
  { label: '使用任务默认模型（正文作者）', value: '__default__' },
  ...props.models
    .filter((model) => model.enabled)
    .map((model) => ({
      label: `${model.name} · ${model.provider_name}`,
      value: model.id,
    })),
])

const sectionOptions = computed(() =>
  (props.meta?.section_keys || Object.keys(props.meta?.section_labels || {})).map((key) => ({
    label: props.meta?.section_labels?.[key] || key,
    value: key,
  })),
)

const currentModelLabel = computed(
  () => props.session.model_id
    ? props.session.model_label
    : '正文作者任务默认模型',
)

function save() {
  const payload: QuickWritingSessionUpdate = {
    title: title.value.trim(),
    preset_id: presetId.value === '__none__' ? null : presetId.value,
    model_id: modelId.value === '__default__' ? null : modelId.value,
    target_word_count: targetWordCount.value,
    segment_words: segmentWords.value,
    context_mode: contextMode.value,
    context_options: {
      sections: sections.value,
      include_recent_chapter: includeRecentChapter.value,
    },
    auto_continuity: autoContinuity.value,
    auto_memory: autoMemory.value,
    remind_memory: remindMemory.value,
  }
  emit('save', payload)
}
</script>

<template>
  <n-card size="small" class="settings-card" :bordered="false">
    <template #header>
      <div class="settings-head">
        <span class="settings-title">写作设置</span>
        <div class="settings-head-side">
          <n-tag size="small" :type="SESSION_STATUS_TYPES[session.status]">
            {{ SESSION_STATUS_LABELS[session.status] }}
          </n-tag>
          <n-button size="tiny" @click="emit('manage-presets')">管理预设</n-button>
        </div>
      </div>
    </template>

    <div class="current-model">
      当前模型：<strong>{{ currentModelLabel }}</strong>
      <span class="model-hint">（API Key 只在后端使用，前端不接触）</span>
    </div>

    <n-collapse>
      <n-collapse-item title="生成配置（点击展开）" name="config">
        <div class="field-grid">
          <div class="field">
            <label>章节标题</label>
            <n-input v-model:value="title" size="small" placeholder="保存章节时使用" />
          </div>
          <div class="field">
            <label>写作预设</label>
            <n-select
              v-model:value="presetId"
              size="small"
              :options="presetOptions"
              filterable
            />
          </div>
          <div class="field">
            <label>模型</label>
            <n-select v-model:value="modelId" size="small" :options="modelOptions" />
          </div>
          <div class="field">
            <label>上下文注入</label>
            <n-select
              v-model:value="contextMode"
              size="small"
              :options="(Object.keys(CONTEXT_MODE_LABELS) as ContextMode[]).map((mode) => ({
                label: CONTEXT_MODE_LABELS[mode],
                value: mode,
              }))"
            />
          </div>
          <div class="field">
            <label>目标字数</label>
            <n-input-number
              v-model:value="targetWordCount"
              size="small"
              :min="200"
              :max="20000"
              :step="100"
            />
          </div>
          <div class="field">
            <label>每段字数</label>
            <n-input-number
              v-model:value="segmentWords"
              size="small"
              :min="200"
              :max="4000"
              :step="100"
            />
          </div>
        </div>

        <div class="context-hint">{{ CONTEXT_MODE_HINTS[contextMode] }}</div>

        <div v-if="contextMode === 'custom'" class="custom-context">
          <n-checkbox-group v-model:value="sections">
            <n-checkbox v-for="item in sectionOptions" :key="item.value" :value="item.value">
              {{ item.label }}
            </n-checkbox>
          </n-checkbox-group>
          <div class="switch-row">
            <span>同时注入最近章节正文</span>
            <n-switch v-model:value="includeRecentChapter" size="small" />
          </div>
          <n-button size="tiny" quaternary @click="emit('preview-context')">
            预览本次上下文
          </n-button>
        </div>

        <div class="switch-list">
          <div class="switch-row">
            <span>自动提取剧情记忆</span>
            <n-switch v-model:value="autoMemory" size="small" />
          </div>
          <div class="switch-row">
            <span>保存后提醒审核记忆</span>
            <n-switch v-model:value="remindMemory" size="small" />
          </div>
          <div class="switch-row">
            <span>自动连续性检查</span>
            <n-switch v-model:value="autoContinuity" size="small" />
          </div>
        </div>
        <div class="switch-hint">
          默认不自动修改正式记忆；开关仅决定保存后是否提醒你手动执行检查与提取。
        </div>

        <div class="settings-actions">
          <n-button size="small" type="primary" :loading="saving" @click="save">
            保存设置
          </n-button>
        </div>
      </n-collapse-item>
    </n-collapse>
  </n-card>
</template>

<style scoped>
.settings-card {
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.08);
}
.settings-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
}
.settings-title {
  font-size: 15px;
  font-weight: 600;
  color: #fff;
}
.settings-head-side {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.current-model {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
  margin-bottom: 8px;
  word-break: break-word;
}
.current-model strong {
  color: #63e2b7;
}
.model-hint {
  color: rgba(255, 255, 255, 0.35);
}
.field-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}
.field label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.45);
}
.context-hint,
.switch-hint {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.45);
  margin-top: 8px;
  line-height: 1.6;
  word-break: break-word;
}
.custom-context {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.03);
}
.switch-list {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.switch-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.72);
}
.settings-actions {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}
:deep(.n-checkbox) {
  margin-bottom: 6px;
}
@media (max-width: 640px) {
  .field-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
