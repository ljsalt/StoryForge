<script setup lang="ts">
import { computed, ref } from 'vue'
import {
  NButton,
  NCollapse,
  NCollapseItem,
  NInput,
  NInputNumber,
  NSelect,
  NSwitch,
} from 'naive-ui'
import type { ChapterSummary } from '../../api/chapter'
import type { ModelItem } from '../../api/models'
import {
  CONTEXT_MODE_HINTS,
  CONTEXT_MODE_LABELS,
  type ContextMode,
  type QuickWritingMeta,
  type QuickWritingSessionCreate,
  type WritingPreset,
} from '../../api/quickWriting'

const props = defineProps<{
  presets: WritingPreset[]
  models: ModelItem[]
  meta: QuickWritingMeta | null
  chapters?: ChapterSummary[]
  submitting?: boolean
}>()

const emit = defineEmits<{
  (event: 'create', payload: QuickWritingSessionCreate): void
  (event: 'manage-presets'): void
}>()

const title = ref('')
const requirement = ref('')
const presetId = ref('__none__')
const modelId = ref('__default__')
const chapterId = ref('__new__')
const targetWordCount = ref(1500)
const segmentWords = ref(700)
const contextMode = ref<ContextMode>('auto')
const autoContinuity = ref(false)
const autoMemory = ref(false)
const remindMemory = ref(true)

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

const chapterOptions = computed(() => [
  { label: '另存为新章节', value: '__new__' },
  ...(props.chapters || []).map((chapter) => ({
    label: `第 ${chapter.chapter_number} 章 · ${chapter.title}`,
    value: chapter.id,
  })),
])

function submit() {
  emit('create', {
    title: title.value.trim(),
    user_requirement: requirement.value.trim(),
    preset_id: presetId.value === '__none__' ? null : presetId.value,
    model_id: modelId.value === '__default__' ? null : modelId.value,
    chapter_id: chapterId.value === '__new__' ? null : chapterId.value,
    target_word_count: targetWordCount.value,
    segment_words: segmentWords.value,
    context_mode: contextMode.value,
    auto_continuity: autoContinuity.value,
    auto_memory: autoMemory.value,
    remind_memory: remindMemory.value,
  })
}
</script>

<template>
  <div class="panel">
    <div class="panel-head">
      <div>
        <div class="panel-title">开始快速写作</div>
        <div class="panel-hint">
          不需要创建剧情计划。直接写你想写的内容，生成正文后再阅读、修改、保存。
        </div>
      </div>
      <n-button size="tiny" @click="emit('manage-presets')">管理预设</n-button>
    </div>

    <n-input v-model:value="title" size="small" placeholder="章节标题（可选，保存时使用）" />
    <n-input
      v-model:value="requirement"
      type="textarea"
      class="requirement"
      :autosize="{ minRows: 5, maxRows: 12 }"
      placeholder="想写什么就写什么，例如：继续上一章，描写主角与对手在雨夜的冲突，重点写环境与心理活动。"
    />

    <n-collapse class="advanced">
      <n-collapse-item title="写作配置（预设 / 模型 / 上下文）" name="config">
        <div class="field-grid">
          <div class="field">
            <label>写作预设</label>
            <n-select v-model:value="presetId" size="small" :options="presetOptions" />
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
            <label>关联章节</label>
            <n-select v-model:value="chapterId" size="small" :options="chapterOptions" />
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
        <div class="switch-hint">
          默认不自动修改正式记忆。开关只影响保存后的提醒，快速写作不会等待记忆审核。
        </div>
      </n-collapse-item>
    </n-collapse>

    <div class="panel-actions">
      <n-button type="primary" block :loading="submitting" @click="submit">
        进入快速写作
      </n-button>
    </div>
  </div>
</template>

<style scoped>
.panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
}
.panel-title {
  font-size: 18px;
  font-weight: 600;
  color: #fff;
}
.panel-hint,
.context-hint,
.switch-hint {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.48);
  line-height: 1.6;
  margin-top: 4px;
  word-break: break-word;
}
.requirement :deep(textarea) {
  font-size: 15px;
  line-height: 1.8;
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
.switch-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.72);
  margin-top: 8px;
}
.advanced {
  margin-top: 4px;
}
@media (max-width: 640px) {
  .field-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
