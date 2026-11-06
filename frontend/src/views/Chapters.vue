<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  NButton,
  NCard,
  NEmpty,
  NInput,
  NSelect,
  NSpin,
  NTag,
  useDialog,
  useMessage,
} from 'naive-ui'
import { getNovel } from '../api/novels'
import { extractError } from '../api/error'
import {
  CHAPTER_STATUS_LABELS,
  CHAPTER_STATUS_OPTIONS,
  CHAPTER_STATUS_TYPES,
  type ChapterSummary,
} from '../api/chapter'
import { useChapterStore } from '../stores/chapter'
import ChapterEditor from '../components/chapter/ChapterEditor.vue'

const route = useRoute()
const router = useRouter()
const store = useChapterStore()
const message = useMessage()
const dialog = useDialog()

const novelTitle = ref('')
const loadingNovel = ref(false)
const pageError = ref('')

const showEditor = ref(false)
const editingChapterId = ref<string | null>(null)

const currentNovelId = computed(() => String(route.params.id))

const volumeOptions = computed(() => [
  { label: '全部卷', value: 'all' },
  ...store.volumes.map((v) => ({ label: `第 ${v} 卷`, value: String(v) })),
])

const volumeSelectValue = computed({
  get: () => (store.volumeFilter === null ? 'all' : String(store.volumeFilter)),
  set: (value: string | null) => {
    store.volumeFilter = value === 'all' ? null : Number(value)
    store.fetchChapters()
  },
})

const groups = computed(() => {
  const map = new Map<number | null, ChapterSummary[]>()
  for (const chapter of store.chapters) {
    const key = chapter.volume_number
    if (!map.has(key)) map.set(key, [])
    map.get(key)!.push(chapter)
  }
  return Array.from(map.entries()).map(([volume, items]) => ({
    volume,
    label: volume === null ? '未分卷' : `第 ${volume} 卷`,
    items,
  }))
})

async function load(novelId: string) {
  loadingNovel.value = true
  pageError.value = ''
  try {
    const { data } = await getNovel(novelId)
    novelTitle.value = data.title
    await store.load(novelId)
    // 支持从剧情事件详情跳转到指定章节
    const openId = route.query.open
    if (typeof openId === 'string' && openId) {
      editingChapterId.value = openId
      showEditor.value = true
    }
  } catch (error) {
    pageError.value = extractError(error, '小说不存在或已被删除')
  } finally {
    loadingNovel.value = false
  }
}

function openCreate() {
  editingChapterId.value = null
  showEditor.value = true
}

function openEdit(chapter: ChapterSummary) {
  editingChapterId.value = chapter.id
  showEditor.value = true
}

async function onSaved() {
  // Editor 内部已完成保存，这里只需切换到最新数据
  await store.fetchChapters()
}

function confirmDelete(chapter: ChapterSummary) {
  dialog.warning({
    title: '删除章节',
    content: `确定删除「第 ${chapter.chapter_number} 章 ${chapter.title}」吗？关联的剧情事件会保留，但会解除与本章的关联。`,
    positiveText: '确认删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await store.remove(chapter.id)
        message.success('章节已删除')
      } catch (error) {
        message.error(extractError(error, '删除章节失败'))
      }
    },
  })
}

async function move(chapter: ChapterSummary, direction: -1 | 1) {
  try {
    await store.move(chapter.id, direction)
    message.success('章节顺序已调整')
  } catch (error) {
    message.error(extractError(error, '调整顺序失败'))
  }
}

onMounted(() => load(currentNovelId.value))
watch(
  () => route.params.id,
  (id) => {
    if (id) load(String(id))
  },
)
</script>

<template>
  <div class="page">
    <n-spin :show="loadingNovel">
      <template v-if="pageError">
        <n-empty :description="pageError">
          <template #extra>
            <n-button size="small" @click="router.push('/novels')">返回小说列表</n-button>
          </template>
        </n-empty>
      </template>

      <template v-else>
        <div class="page-header">
          <div class="header-left">
            <n-button size="small" quaternary @click="router.push(`/novels/${currentNovelId}`)">
              ← 返回小说详情
            </n-button>
            <div>
              <h2 class="page-title">章节管理</h2>
              <div class="page-sub">
                《{{ novelTitle }}》 · 共 {{ store.stats.chapter_count }} 章 ·
                已完成 {{ store.stats.completed_chapter_count }} 章 ·
                {{ store.stats.total_word_count }} 字
              </div>
            </div>
          </div>
          <div class="header-actions">
            <n-button size="small" type="primary" @click="openCreate">+ 新建章节</n-button>
          </div>
        </div>

        <div class="toolbar">
          <n-input
            v-model:value="store.search"
            clearable
            placeholder="搜索章节标题 / 摘要"
            class="search"
            @update:value="store.fetchChapters()"
          />
          <n-select
            v-model:value="store.statusFilter"
            clearable
            :options="CHAPTER_STATUS_OPTIONS"
            placeholder="按状态筛选"
            class="filter"
            @update:value="store.fetchChapters()"
          />
          <n-select
            v-model:value="volumeSelectValue"
            :options="volumeOptions"
            placeholder="按卷查看"
            class="filter"
          />
        </div>

        <div v-if="!store.chapters.length && !store.loading" class="empty-state">
          <n-empty description="还没有章节。新建第一章，开始搭建小说的叙事结构。" />
        </div>

        <n-spin v-else :show="store.loading">
          <div v-for="group in groups" :key="String(group.volume)" class="volume-group">
            <div class="volume-title">{{ group.label }}（{{ group.items.length }} 章）</div>
            <n-card
              v-for="chapter in group.items"
              :key="chapter.id"
              size="small"
              hoverable
              class="chapter-row"
              @click="openEdit(chapter)"
            >
              <div class="chapter-main">
                <div class="chapter-head">
                  <span class="chapter-number">第 {{ chapter.chapter_number }} 章</span>
                  <span class="chapter-title">{{ chapter.title }}</span>
                  <n-tag size="tiny" :bordered="false" :type="CHAPTER_STATUS_TYPES[chapter.status]">
                    {{ CHAPTER_STATUS_LABELS[chapter.status] }}
                  </n-tag>
                </div>
                <div class="chapter-meta">
                  <span>{{ chapter.word_count }} 字</span>
                  <span>更新于 {{ chapter.updated_at.slice(0, 16).replace('T', ' ') }}</span>
                </div>
                <div v-if="chapter.summary" class="chapter-summary">{{ chapter.summary }}</div>
              </div>
              <div class="chapter-actions" @click.stop>
                <n-button size="tiny" quaternary @click="move(chapter, -1)">上移</n-button>
                <n-button size="tiny" quaternary @click="move(chapter, 1)">下移</n-button>
                <n-button
                  size="tiny"
                  quaternary
                  @click="router.push(`/novels/${currentNovelId}/chapters/${chapter.id}/continuity`)"
                >
                  连续性
                </n-button>
                <n-button size="tiny" quaternary type="primary" @click="openEdit(chapter)">编辑</n-button>
                <n-button size="tiny" quaternary type="error" @click="confirmDelete(chapter)">删除</n-button>
              </div>
            </n-card>
          </div>
        </n-spin>

        <div v-if="store.error" class="page-error">
          <n-tag type="error" :bordered="false">{{ store.error }}</n-tag>
        </div>
      </template>
    </n-spin>

    <ChapterEditor
      v-model:show="showEditor"
      :novel-id="currentNovelId"
      :chapter-id="editingChapterId"
      @saved="onSaved"
    />
  </div>
</template>

<style scoped>
.page {
  max-width: 1080px;
  margin: 0 auto;
  padding: 16px;
}
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}
.header-left {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}
.page-title {
  margin: 0;
  font-size: 20px;
}
.page-sub {
  margin-top: 4px;
  font-size: 12px;
  color: var(--sf-text-tertiary, #888);
}
.toolbar {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}
.search {
  flex: 1 1 240px;
}
.filter {
  width: 160px;
}
.empty-state {
  padding: 48px 0;
}
.volume-group {
  margin-bottom: 20px;
}
.volume-title {
  margin: 8px 0;
  font-size: 13px;
  font-weight: 600;
  color: var(--sf-text-secondary, #666);
}
.chapter-row {
  margin-bottom: 8px;
  cursor: pointer;
}
.chapter-row :deep(.n-card__content) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.chapter-main {
  min-width: 0;
}
.chapter-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.chapter-number {
  font-size: 12px;
  color: var(--sf-text-tertiary, #888);
}
.chapter-title {
  font-size: 15px;
  font-weight: 600;
  word-break: break-word;
}
.chapter-meta {
  display: flex;
  gap: 12px;
  margin-top: 4px;
  font-size: 12px;
  color: var(--sf-text-tertiary, #888);
  flex-wrap: wrap;
}
.chapter-summary {
  margin-top: 4px;
  font-size: 12px;
  color: var(--sf-text-secondary, #666);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.chapter-actions {
  display: flex;
  gap: 2px;
  flex-shrink: 0;
}
.page-error {
  margin-top: 16px;
}
@media (max-width: 640px) {
  .page {
    padding: 12px;
  }
  .chapter-row :deep(.n-card__content) {
    flex-direction: column;
    align-items: stretch;
  }
  .chapter-actions {
    justify-content: flex-end;
    flex-wrap: wrap;
  }
  .chapter-summary {
    white-space: normal;
  }
}
</style>
