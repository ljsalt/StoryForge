<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  NButton,
  NDivider,
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
  NModal,
  NSelect,
  NSpace,
  NSpin,
  NTag,
  useDialog,
  useMessage,
} from 'naive-ui'
import { extractError } from '../../api/error'
import {
  CHAPTER_STATUS_OPTIONS,
  countWords,
  createChapter,
  getChapter,
  listChapterPlotEvents,
  listChapterRelationEvents,
  updateChapter,
  type Chapter,
  type ChapterRelationEvent,
  type ChapterStatus,
} from '../../api/chapter'
import {
  PLOT_IMPORTANCE_LABELS,
  PLOT_IMPORTANCE_TYPES,
  type PlotEvent,
} from '../../api/plotEvent'

const props = defineProps<{
  show: boolean
  novelId: string
  chapterId: string | null
  defaultVolume?: number | null
}>()
const emit = defineEmits<{ 'update:show': [v: boolean]; saved: [chapter: Chapter] }>()

const message = useMessage()
const dialog = useDialog()
const router = useRouter()

const loading = ref(false)
const saving = ref(false)
const loadError = ref('')
const chapterEvents = ref<PlotEvent[]>([])
const relationEvents = ref<ChapterRelationEvent[]>([])
const loadingRelated = ref(false)

const RELATION_EVENT_LABELS: Record<string, string> = {
  created: '建立关系',
  updated: '关系变化',
  ended: '关系结束',
  restored: '关系恢复',
}

const form = reactive({
  title: '',
  summary: '',
  content: '',
  status: 'planned' as ChapterStatus,
  volumeNumber: null as number | null,
})

const snapshot = ref('')
const liveWordCount = computed(() => countWords(form.content))
const dirty = computed(() => snapshot.value !== '' && snapshotString() !== snapshot.value)

function snapshotString(): string {
  return JSON.stringify({
    title: form.title,
    summary: form.summary,
    content: form.content,
    status: form.status,
    volumeNumber: form.volumeNumber,
  })
}

function applyChapter(chapter: Chapter) {
  form.title = chapter.title
  form.summary = chapter.summary
  form.content = chapter.content
  form.status = chapter.status
  form.volumeNumber = chapter.volume_number
  snapshot.value = snapshotString()
}

async function loadRelated(chapterId: string) {
  loadingRelated.value = true
  try {
    const [plotRes, relationRes] = await Promise.all([
      listChapterPlotEvents(props.novelId, chapterId),
      listChapterRelationEvents(props.novelId, chapterId),
    ])
    chapterEvents.value = plotRes.data
    relationEvents.value = relationRes.data
  } catch {
    chapterEvents.value = []
    relationEvents.value = []
  } finally {
    loadingRelated.value = false
  }
}

async function init() {
  loadError.value = ''
  snapshot.value = ''
  chapterEvents.value = []
  relationEvents.value = []
  if (props.chapterId) {
    loading.value = true
    try {
      const { data } = await getChapter(props.novelId, props.chapterId)
      applyChapter(data)
      await loadRelated(props.chapterId)
    } catch (error) {
      loadError.value = extractError(error, '加载章节内容失败')
    } finally {
      loading.value = false
    }
  } else {
    form.title = ''
    form.summary = ''
    form.content = ''
    form.status = 'planned'
    form.volumeNumber = props.defaultVolume ?? null
    snapshot.value = snapshotString()
  }
}

watch(
  () => [props.show, props.chapterId, props.novelId] as const,
  ([show]) => {
    if (show) init()
  },
  { immediate: true },
)

function close() {
  emit('update:show', false)
}

function attemptClose() {
  if (saving.value) return
  if (!dirty.value) {
    close()
    return
  }
  dialog.warning({
    title: '放弃未保存的修改？',
    content: '当前章节内容尚未保存，关闭后本次修改会丢失。',
    positiveText: '放弃修改',
    negativeText: '继续编辑',
    onPositiveClick: () => close(),
  })
}

async function submit() {
  if (!form.title.trim()) {
    message.error('章节标题不能为空')
    return
  }
  saving.value = true
  try {
    const payload = {
      title: form.title.trim(),
      summary: form.summary,
      content: form.content,
      status: form.status,
      volume_number: form.volumeNumber,
    }
    const { data } = props.chapterId
      ? await updateChapter(props.novelId, props.chapterId, payload)
      : await createChapter(props.novelId, payload)
    applyChapter(data)
    message.success(`已保存，共 ${data.word_count} 字`)
    emit('saved', data)
    close()
  } catch (error) {
    // 保存失败时保持弹窗与正文，不静默丢失内容
    message.error(extractError(error, '保存章节失败，内容仍保留在编辑框中'))
  } finally {
    saving.value = false
  }
}

function onBeforeUnload(event: BeforeUnloadEvent) {
  if (!props.show || !dirty.value) return
  event.preventDefault()
  event.returnValue = ''
}

onMounted(() => window.addEventListener('beforeunload', onBeforeUnload))
onUnmounted(() => window.removeEventListener('beforeunload', onBeforeUnload))
</script>

<template>
  <n-modal
    :show="show"
    preset="card"
    :title="chapterId ? '编辑章节' : '新建章节'"
    :style="{ width: 'min(920px, calc(100vw - 16px))' }"
    :mask-closable="false"
    :close-on-esc="false"
    :bordered="false"
    @update:show="(v: boolean) => { if (!v) attemptClose() }"
  >
    <n-spin :show="loading">
      <div v-if="loadError" class="editor-error">
        <n-tag type="error" :bordered="false">{{ loadError }}</n-tag>
      </div>
      <n-form v-else label-placement="top" :show-feedback="false">
        <n-form-item label="章节标题（必填）">
          <n-input v-model:value="form.title" maxlength="200" placeholder="例如：第一章 初入宗门" />
        </n-form-item>
        <div class="editor-grid">
          <n-form-item label="章节状态">
            <n-select v-model:value="form.status" :options="CHAPTER_STATUS_OPTIONS" />
          </n-form-item>
          <n-form-item label="所属卷（可空）">
            <n-input-number
              v-model:value="form.volumeNumber"
              :min="1"
              clearable
              placeholder="留空表示不分卷"
            />
          </n-form-item>
          <n-form-item label="字数（后端保存时重新计算）">
            <div class="word-count">
              <n-tag :bordered="false" type="info">{{ liveWordCount }} 字</n-tag>
            </div>
          </n-form-item>
        </div>
        <n-form-item label="章节摘要（可空）">
          <n-input v-model:value="form.summary" maxlength="5000" placeholder="一句话概括本章剧情" />
        </n-form-item>
        <n-form-item label="章节正文">
          <n-input
            v-model:value="form.content"
            type="textarea"
            :autosize="{ minRows: 12, maxRows: 40 }"
            placeholder="支持长篇中文正文，可直接粘贴或输入 Markdown / 纯文本"
            class="content-input"
          />
        </n-form-item>
      </n-form>
    </n-spin>

    <div v-if="chapterId" class="related-block">
      <n-divider style="margin: 12px 0">本章关联数据</n-divider>
      <n-spin :show="loadingRelated">
        <div class="related-grid">
          <div>
            <div class="related-title">剧情事件（故事事实）</div>
            <div v-if="!chapterEvents.length" class="related-empty">本章暂无关联剧情事件</div>
            <div v-for="event in chapterEvents" :key="event.id" class="related-item">
              <div class="related-item-head">
                <span class="related-item-title">{{ event.title }}</span>
                <n-tag
                  size="tiny"
                  :bordered="false"
                  :type="PLOT_IMPORTANCE_TYPES[event.importance]"
                >
                  {{ PLOT_IMPORTANCE_LABELS[event.importance] }}
                </n-tag>
              </div>
              <div class="related-meta">
                <span v-if="event.story_time">故事时间：{{ event.story_time }}</span>
                <span v-if="event.location_name">{{ event.location_name }}</span>
                <span v-if="event.participants.length">
                  {{ event.participants.map((p) => p.character_name).join('、') }}
                </span>
              </div>
            </div>
          </div>
          <div>
            <div class="related-title">人物关系变化</div>
            <div v-if="!relationEvents.length" class="related-empty">
              本章暂无关联的人物关系变化记录
            </div>
            <div v-for="event in relationEvents" :key="event.id" class="related-item">
              <div class="related-item-head">
                <span class="related-item-title">
                  {{ event.source_name }} → {{ event.target_name }}
                </span>
                <n-tag size="tiny" :bordered="false" type="info">
                  {{ RELATION_EVENT_LABELS[event.event_type] || event.event_type }}
                </n-tag>
              </div>
              <div class="related-meta">{{ event.title }}</div>
            </div>
          </div>
        </div>
      </n-spin>
    </div>

    <template #footer>
      <n-space justify="space-between" align="center">
        <span class="editor-hint">正文可以为空；字数由后端根据正文重新计算。</span>
        <n-space>
          <n-button
            v-if="chapterId"
            size="small"
            quaternary
            @click="router.push(`/novels/${novelId}/chapters/${chapterId}/continuity`)"
          >
            连续性与记忆
          </n-button>
          <n-button size="small" :disabled="saving" @click="attemptClose">取消</n-button>
          <n-button size="small" type="primary" :loading="saving" :disabled="loading" @click="submit">
            {{ chapterId ? '保存修改' : '创建章节' }}
          </n-button>
        </n-space>
      </n-space>
    </template>
  </n-modal>
</template>

<style scoped>
.editor-error {
  padding: 24px 0;
  text-align: center;
}
.editor-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}
.word-count {
  display: flex;
  align-items: center;
  height: 34px;
}
.content-input :deep(textarea) {
  line-height: 1.8;
  font-size: 14px;
}
.editor-hint {
  font-size: 12px;
  color: var(--sf-text-tertiary, #999);
}
.related-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}
.related-title {
  margin-bottom: 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--sf-text-secondary, #666);
}
.related-empty {
  font-size: 12px;
  color: var(--sf-text-tertiary, #999);
}
.related-item {
  border: 1px solid var(--sf-border, #eee);
  border-radius: 6px;
  padding: 6px 8px;
  margin-bottom: 6px;
}
.related-item-head {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.related-item-title {
  font-size: 13px;
  font-weight: 500;
}
.related-meta {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 2px;
  font-size: 12px;
  color: var(--sf-text-tertiary, #888);
}
@media (max-width: 640px) {
  .related-grid,
  .editor-grid {
    grid-template-columns: 1fr;
  }
}
</style>
