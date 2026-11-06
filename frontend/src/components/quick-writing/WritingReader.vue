<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  NAlert,
  NButton,
  NButtonGroup,
  NInput,
  NTag,
} from 'naive-ui'
import { countWords } from '../../api/chapter'
import type { QuickWritingSession } from '../../api/quickWriting'

const props = defineProps<{
  session: QuickWritingSession
  saving?: boolean
}>()

const emit = defineEmits<{
  (event: 'save-content', content: string): void
  (event: 'view', seq: number | null): void
}>()

const editing = ref(false)
const draft = ref('')
const viewSeq = ref<number | null>(null)

watch(
  () => props.session.id,
  () => {
    editing.value = false
    viewSeq.value = null
    draft.value = props.session.content
  },
  { immediate: true },
)

watch(
  () => props.session.content,
  (content) => {
    if (!editing.value) draft.value = content
  },
)

const segments = computed(() => props.session.segments || [])

const currentIndex = computed(() =>
  segments.value.findIndex((segment) => segment.seq === viewSeq.value),
)

const currentSegment = computed(() =>
  currentIndex.value >= 0 ? segments.value[currentIndex.value] : null,
)

const displayContent = computed(() => {
  if (viewSeq.value === null) return props.session.content
  const segment = currentSegment.value
  if (!segment) return ''
  if (segment.status === 'failed') {
    return `【第 ${segment.seq} 段生成失败】${segment.error_message || '模型调用失败'}`
  }
  return segment.content
})

const displayWordCount = computed(() =>
  editing.value ? countWords(draft.value) : countWords(displayContent.value),
)

const hasContent = computed(() => props.session.content.trim().length > 0)
const dirty = computed(() => draft.value !== props.session.content)

function startEdit() {
  draft.value = props.session.content
  editing.value = true
  viewSeq.value = null
}

function cancelEdit() {
  editing.value = false
  draft.value = props.session.content
}

function saveEdit() {
  emit('save-content', draft.value)
}

function showAll() {
  viewSeq.value = null
  emit('view', null)
}

function prevSegment() {
  if (viewSeq.value === null) {
    const last = segments.value[segments.value.length - 1]
    if (last) {
      viewSeq.value = last.seq
      emit('view', last.seq)
    }
    return
  }
  if (currentIndex.value > 0) {
    viewSeq.value = segments.value[currentIndex.value - 1].seq
    emit('view', viewSeq.value)
  }
}

function nextSegment() {
  if (viewSeq.value === null) {
    const first = segments.value[0]
    if (first) {
      viewSeq.value = first.seq
      emit('view', first.seq)
    }
    return
  }
  if (currentIndex.value >= 0 && currentIndex.value < segments.value.length - 1) {
    viewSeq.value = segments.value[currentIndex.value + 1].seq
    emit('view', viewSeq.value)
  }
}
</script>

<template>
  <div class="reader">
    <div class="reader-head">
      <div class="reader-title-row">
        <span class="reader-title">{{ session.title || '未命名章节' }}</span>
        <n-tag v-if="session.edited" size="tiny" type="warning">手工编辑</n-tag>
        <n-tag v-if="session.model_id" size="tiny" type="info">
          {{ session.model_label || '指定模型' }}
        </n-tag>
      </div>
      <div class="reader-meta">
        <span>{{ displayWordCount }} 字</span>
        <span v-if="session.target_word_count">目标 {{ session.target_word_count }}</span>
        <span v-if="viewSeq !== null" class="muted">第 {{ viewSeq }} 段</span>
        <span v-else class="muted">全文</span>
      </div>
    </div>

    <div class="reader-toolbar">
      <n-button-group size="small">
        <n-button :disabled="editing" @click="prevSegment">上一段</n-button>
        <n-button :disabled="editing || viewSeq === null" @click="showAll">全文</n-button>
        <n-button :disabled="editing" @click="nextSegment">下一段</n-button>
      </n-button-group>
      <div class="reader-actions">
        <template v-if="!editing">
          <n-button size="small" :disabled="!hasContent" @click="startEdit">编辑正文</n-button>
        </template>
        <template v-else>
          <n-button size="small" @click="cancelEdit">取消</n-button>
          <n-button
            size="small"
            type="primary"
            :loading="saving"
            :disabled="!dirty"
            @click="saveEdit"
          >
            保存草稿
          </n-button>
        </template>
      </div>
      <span class="save-state">
        <template v-if="editing && dirty">有未保存修改</template>
        <template v-else-if="saving">保存中…</template>
        <template v-else>草稿已保存</template>
      </span>
    </div>

    <n-alert
      v-if="session.error_message"
      type="error"
      :bordered="false"
      class="reader-error"
    >
      上次生成失败（{{ session.error_code || '未知错误' }}）：{{ session.error_message }}
      已完成内容仍然保留，可直接重试或继续生成。
    </n-alert>

    <n-input
      v-if="editing"
      v-model:value="draft"
      type="textarea"
      class="article-editor"
      placeholder="正文为空，可以直接开始写，或先点击生成"
      :autosize="{ minRows: 14, maxRows: 40 }"
    />
    <div v-else class="article">
      <template v-if="displayContent">{{ displayContent }}</template>
      <div v-else class="article-empty">
        还没有正文。可以在上方输入写作要求，然后点击「生成正文」。
      </div>
    </div>
  </div>
</template>

<style scoped>
.reader {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 0;
}
.reader-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
}
.reader-title-row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  min-width: 0;
}
.reader-title {
  font-size: 17px;
  font-weight: 600;
  color: #fff;
  word-break: break-word;
}
.reader-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
  flex-wrap: wrap;
}
.muted {
  color: rgba(255, 255, 255, 0.35);
}
.reader-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  padding: 8px 0;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}
.reader-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}
.save-state {
  margin-left: auto;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.4);
}
.reader-error {
  margin-top: 2px;
}
.article {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  word-break: break-word;
  font-size: 16px;
  line-height: 2;
  color: rgba(255, 255, 255, 0.88);
  padding: 18px 4px 32px;
  max-width: 76ch;
  width: 100%;
  margin: 0 auto;
  min-height: 240px;
}
.article-empty {
  color: rgba(255, 255, 255, 0.35);
  font-size: 14px;
  text-align: center;
  padding: 48px 0;
}
.article-editor :deep(textarea) {
  font-size: 16px;
  line-height: 2;
  overflow-wrap: anywhere;
}
@media (max-width: 640px) {
  .article {
    font-size: 15px;
    line-height: 1.9;
    padding: 8px 0 24px;
  }
  .save-state {
    margin-left: 0;
    width: 100%;
  }
}
</style>
