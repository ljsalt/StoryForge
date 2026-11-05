<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  NAlert,
  NButton,
  NCollapse,
  NCollapseItem,
  NEmpty,
  NForm,
  NFormItem,
  NGrid,
  NGridItem,
  NInput,
  NInputNumber,
  NSelect,
  NSpin,
  NTag,
  useMessage,
} from 'naive-ui'
import { extractError } from '../../api/error'
import {
  previewContext,
  AI_TASK_TYPE_OPTIONS,
  POV_LABELS,
  type ContextPov,
  type ContextPreview,
  type AiTaskType,
} from '../../api/ai'
import { useNovelStore } from '../../stores/novels'
import { useChapterStore } from '../../stores/chapter'
import { useCharacterStore } from '../../stores/character'

const novelStore = useNovelStore()
const chapterStore = useChapterStore()
const characterStore = useCharacterStore()
const message = useMessage()

const novelId = ref<string | null>(null)
const taskType = ref<AiTaskType>('writer')
const pov = ref<ContextPov>('author')
const tokenBudget = ref<number | null>(6000)
const chapterId = ref<string | null>(null)
const characterIds = ref<string[]>([])
const requirement = ref('')

const loading = ref(false)
const preview = ref<ContextPreview | null>(null)

const novelOptions = computed(() =>
  novelStore.novels.map((n) => ({ label: n.title, value: n.id })),
)
const chapterOptions = computed(() =>
  chapterStore.chapters.map((c) => ({
    label: `第 ${c.chapter_number} 章 ${c.title}`,
    value: c.id,
  })),
)
const characterOptions = computed(() =>
  characterStore.characters.map((c) => ({ label: c.name, value: c.id })),
)
const povOptions = computed(() =>
  (Object.keys(POV_LABELS) as ContextPov[]).map((v) => ({ label: POV_LABELS[v], value: v })),
)

watch(novelId, async (value) => {
  chapterId.value = null
  characterIds.value = []
  preview.value = null
  if (!value) return
  try {
    await Promise.all([
      chapterStore.novelId === value ? Promise.resolve() : chapterStore.load(value),
      characterStore.novelId === value ? Promise.resolve() : characterStore.load(value),
    ])
  } catch {
    // 关联数据加载失败不阻塞预览
  }
})

async function run() {
  if (!novelId.value) {
    message.warning('请先选择小说')
    return
  }
  loading.value = true
  try {
    const { data } = await previewContext({
      novel_id: novelId.value,
      task_type: taskType.value,
      chapter_id: chapterId.value,
      character_ids: characterIds.value.length ? characterIds.value : null,
      token_budget: tokenBudget.value,
      pov: pov.value,
      user_requirement: requirement.value,
    })
    preview.value = data
  } catch (error) {
    message.error(extractError(error, '上下文组装失败'))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="panel">
    <n-form label-placement="top" size="small">
      <n-grid :x-gap="12" cols="1 s:2" responsive="screen">
        <n-grid-item>
          <n-form-item label="选择小说" required>
            <n-select v-model:value="novelId" :options="novelOptions" filterable placeholder="选择小说" />
          </n-form-item>
        </n-grid-item>
        <n-grid-item>
          <n-form-item label="任务类型">
            <n-select v-model:value="taskType" :options="AI_TASK_TYPE_OPTIONS" />
          </n-form-item>
        </n-grid-item>
        <n-grid-item>
          <n-form-item label="叙事视角（秘密隔离）">
            <n-select v-model:value="pov" :options="povOptions" />
          </n-form-item>
        </n-grid-item>
        <n-grid-item>
          <n-form-item label="Token 预算（估算值）">
            <n-input-number v-model:value="tokenBudget" :min="200" :max="200000" class="full" />
          </n-form-item>
        </n-grid-item>
        <n-grid-item>
          <n-form-item label="关联章节（可选）">
            <n-select
              v-model:value="chapterId"
              :options="chapterOptions"
              clearable
              filterable
              placeholder="不选则不含当前章节信息"
            />
          </n-form-item>
        </n-grid-item>
        <n-grid-item>
          <n-form-item label="涉及人物（可选，默认全部）">
            <n-select
              v-model:value="characterIds"
              :options="characterOptions"
              multiple
              clearable
              filterable
              placeholder="不选则按默认人物集合"
            />
          </n-form-item>
        </n-grid-item>
      </n-grid>
      <n-form-item label="本次创作要求（可选）">
        <n-input
          v-model:value="requirement"
          type="textarea"
          :autosize="{ minRows: 2, maxRows: 4 }"
          placeholder="例如：写下一章的开场，承接上一章结尾"
        />
      </n-form-item>
      <n-button type="primary" :loading="loading" @click="run">组装上下文预览</n-button>
      <span class="hint">预览只读取数据库，不会发起任何模型调用</span>
    </n-form>

    <n-spin :show="loading">
      <div v-if="preview" class="result">
        <div class="stats-row">
          <n-tag size="small" round :bordered="false" type="info">
            估算 {{ preview.estimated_tokens }} / 预算 {{ preview.token_budget }} tokens
          </n-tag>
          <n-tag size="small" round :bordered="false">{{ preview.sections.length }} 个分区</n-tag>
          <n-tag v-if="preview.omitted_sections.length" size="small" round :bordered="false" type="warning">
            省略 {{ preview.omitted_sections.length }} 个分区
          </n-tag>
        </div>

        <n-alert v-if="preview.warnings.length" type="warning" :bordered="false" class="warn-block">
          <div v-for="(w, i) in preview.warnings" :key="i" class="warn-line">{{ w }}</div>
        </n-alert>

        <n-alert
          v-if="pov !== 'author'"
          type="info"
          :bordered="false"
          class="warn-block"
        >
          当前为{{ pov === 'narrative' ? '叙事' : '角色' }}视角：人物秘密不会被注入上下文。
        </n-alert>

        <div v-if="preview.omitted_sections.length" class="omitted">
          <div class="block-title">被省略的内容</div>
          <div v-for="item in preview.omitted_sections" :key="item.key" class="omitted-item">
            「{{ item.title }}」因预算不足被省略（{{ item.dropped_items ?? 0 }} 条）
          </div>
        </div>

        <n-collapse class="sections">
          <n-collapse-item
            v-for="section in preview.sections"
            :key="section.key"
            :name="section.key"
          >
            <template #header>
              <div class="section-head">
                <span>{{ section.title }}</span>
                <span class="section-meta">≈{{ section.tokens }} tokens · {{ section.item_count }} 条</span>
              </div>
            </template>
            <pre class="content-pre">{{ section.content }}</pre>
          </n-collapse-item>
        </n-collapse>

        <n-collapse class="sections">
          <n-collapse-item title="完整组装文本（发送给模型前会加入提示词）" name="full">
            <pre class="content-pre full-pre">{{ preview.context_text }}</pre>
          </n-collapse-item>
        </n-collapse>
      </div>
      <n-empty v-else-if="!loading" description="选择参数后点击「组装上下文预览」" class="empty" />
    </n-spin>
  </div>
</template>

<style scoped>
.panel { padding-top: 4px; }
.full { width: 100%; }
.hint { font-size: 12px; color: rgba(255, 255, 255, 0.4); margin-left: 10px; }
.result { margin-top: 16px; border-top: 1px solid rgba(255, 255, 255, 0.08); padding-top: 12px; }
.stats-row { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 8px; }
.warn-block { margin: 8px 0; }
.warn-line { font-size: 12px; }
.block-title { font-size: 13px; font-weight: 600; color: #fff; margin: 10px 0 6px; }
.omitted { margin: 8px 0; }
.omitted-item { font-size: 12px; color: rgba(255, 255, 255, 0.55); padding: 2px 0; }
.sections { margin-top: 10px; }
.section-head { display: flex; align-items: baseline; gap: 10px; }
.section-meta { font-size: 12px; color: rgba(255, 255, 255, 0.45); }
.content-pre {
  margin: 0; padding: 10px 12px; background: rgba(255, 255, 255, 0.05);
  border-radius: 6px; font-size: 12px; line-height: 1.7; color: rgba(255, 255, 255, 0.8);
  white-space: pre-wrap; word-break: break-word; max-height: 320px; overflow: auto;
}
.full-pre { max-height: 480px; }
.empty { padding: 40px 0; }
</style>
