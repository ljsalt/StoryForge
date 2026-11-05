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
  NTabPane,
  NTabs,
  NTag,
  useMessage,
} from 'naive-ui'
import { getNovel } from '../api/novels'
import { extractError } from '../api/error'
import {
  PLOT_IMPORTANCE_LABELS,
  PLOT_IMPORTANCE_OPTIONS,
  PLOT_IMPORTANCE_TYPES,
  type PlotEvent,
  type PlotImportance,
} from '../api/plotEvent'
import { useChapterStore } from '../stores/chapter'
import { useCharacterStore } from '../stores/character'
import { usePlotEventStore } from '../stores/plotEvent'
import PlotEventModal from '../components/plot/PlotEventModal.vue'
import PlotEventDetailModal from '../components/plot/PlotEventDetailModal.vue'
import PlotTimeline from '../components/plot/PlotTimeline.vue'
import CharacterDetailModal from '../components/character/CharacterDetailModal.vue'

const route = useRoute()
const router = useRouter()
const plotStore = usePlotEventStore()
const charStore = useCharacterStore()
const chapterStore = useChapterStore()
const message = useMessage()

const novelTitle = ref('')
const loadingNovel = ref(false)
const pageError = ref('')
const tab = ref<'list' | 'timeline'>('list')

const showEventModal = ref(false)
const showDetail = ref(false)
const selectedEvent = ref<PlotEvent | null>(null)
const editingEvent = ref<PlotEvent | null>(null)
const showCharDetail = ref(false)

const currentNovelId = computed(() => String(route.params.id))

const characterOptions = computed(() =>
  charStore.characters.map((c) => ({ label: c.name, value: c.id })),
)
const chapterOptions = computed(() =>
  chapterStore.chapters.map((c) => ({
    label: `第 ${c.chapter_number} 章 ${c.title}`,
    value: c.id,
  })),
)

async function load(novelId: string) {
  loadingNovel.value = true
  pageError.value = ''
  try {
    const { data } = await getNovel(novelId)
    novelTitle.value = data.title
    await Promise.all([
      plotStore.load(novelId),
      charStore.load(novelId),
      chapterStore.load(novelId),
    ])
  } catch (error) {
    pageError.value = extractError(error, '小说不存在或已被删除')
  } finally {
    loadingNovel.value = false
  }
}

function refresh() {
  plotStore.fetchEvents()
  if (tab.value === 'timeline') plotStore.fetchTimeline()
}

function openCreate() {
  editingEvent.value = null
  showEventModal.value = true
}

function openDetail(event: PlotEvent) {
  selectedEvent.value = event
  showDetail.value = true
}

function onDetailEdit() {
  editingEvent.value = selectedEvent.value
  showDetail.value = false
  showEventModal.value = true
}

function onSaved() {
  selectedEvent.value = null
  refresh()
}

async function openCharacter(id: string) {
  showDetail.value = false
  try {
    await charStore.openCharacter(id)
    showCharDetail.value = true
  } catch (error) {
    message.error(extractError(error, '打开人物详情失败'))
  }
}

function openChapter(chapterId: string) {
  router.push({ path: `/novels/${currentNovelId.value}/chapters`, query: { open: chapterId } })
}

watch(tab, (value) => {
  if (value === 'timeline') plotStore.fetchTimeline()
})
watch(
  () => [plotStore.search, plotStore.chapterFilter, plotStore.characterFilter, plotStore.typeFilter, plotStore.importanceFilter] as const,
  () => refresh(),
)
watch(
  () => route.params.id,
  (id) => {
    if (id) load(String(id))
  },
)

onMounted(() => load(currentNovelId.value))
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
              <h2 class="page-title">剧情事件</h2>
              <div class="page-sub">
                《{{ novelTitle }}》 · {{ plotStore.totalEvents }} 个事件 ·
                {{ plotStore.timeline.timed.length }} 个有故事时间
              </div>
            </div>
          </div>
          <div class="header-actions">
            <n-button size="small" type="primary" @click="openCreate">+ 新建事件</n-button>
          </div>
        </div>

        <div class="toolbar">
          <n-input
            v-model:value="plotStore.search"
            clearable
            placeholder="搜索标题 / 描述 / 类型"
            class="search"
          />
          <n-select
            v-model:value="plotStore.chapterFilter"
            :options="chapterOptions"
            clearable
            filterable
            placeholder="按章节筛选"
            class="filter"
          />
          <n-select
            v-model:value="plotStore.characterFilter"
            :options="characterOptions"
            clearable
            filterable
            placeholder="按人物筛选"
            class="filter"
          />
          <n-input
            v-model:value="plotStore.typeFilter"
            clearable
            placeholder="事件类型"
            class="filter small"
          />
          <n-select
            v-model:value="plotStore.importanceFilter"
            :options="PLOT_IMPORTANCE_OPTIONS"
            clearable
            placeholder="重要程度"
            class="filter small"
          />
          <n-button
            v-if="plotStore.search || plotStore.chapterFilter || plotStore.characterFilter || plotStore.typeFilter || plotStore.importanceFilter"
            size="small"
            @click="plotStore.clearFilters(); refresh()"
          >
            清空筛选
          </n-button>
        </div>

        <NTabs v-model:value="tab" animated>
          <NTabPane name="list" tab="事件列表">
            <n-spin :show="plotStore.loading">
              <div v-if="plotStore.events.length" class="event-list">
                <n-card
                  v-for="event in plotStore.events"
                  :key="event.id"
                  size="small"
                  hoverable
                  class="event-row"
                  @click="openDetail(event)"
                >
                  <div class="event-main">
                    <div class="event-head">
                      <span class="event-title">{{ event.title }}</span>
                      <n-tag size="tiny" :bordered="false" :type="PLOT_IMPORTANCE_TYPES[event.importance]">
                        {{ PLOT_IMPORTANCE_LABELS[event.importance] }}
                      </n-tag>
                      <n-tag v-if="event.event_type" size="tiny" :bordered="false">
                        {{ event.event_type }}
                      </n-tag>
                    </div>
                    <div class="event-meta">
                      <span v-if="event.chapter_title">第 {{ event.chapter_number }} 章 · {{ event.chapter_title }}</span>
                      <span v-else>未关联章节</span>
                      <span v-if="event.story_time">故事时间：{{ event.story_time }}</span>
                      <span v-if="event.location_name">地点：{{ event.location_name }}</span>
                    </div>
                    <div v-if="event.participants.length" class="event-participants">
                      参与：{{ event.participants.map((p) => p.character_name).join('、') }}
                    </div>
                  </div>
                  <div class="event-actions" @click.stop>
                    <n-button size="tiny" quaternary type="primary" @click="openDetail(event)">详情</n-button>
                  </div>
                </n-card>
              </div>
              <n-empty v-else description="没有符合条件的剧情事件" />
            </n-spin>
          </NTabPane>

          <NTabPane name="timeline" tab="剧情时间线">
            <PlotTimeline
              :timed="plotStore.timeline.timed"
              :untimed="plotStore.timeline.untimed"
              :loading="plotStore.loading"
              @open="openDetail"
            />
          </NTabPane>
        </NTabs>

        <div v-if="plotStore.error" class="page-error">
          <n-tag type="error" :bordered="false">{{ plotStore.error }}</n-tag>
        </div>
      </template>
    </n-spin>

    <PlotEventModal
      v-model:show="showEventModal"
      :novel-id="currentNovelId"
      :event="editingEvent"
      @saved="onSaved"
    />
    <PlotEventDetailModal
      v-model:show="showDetail"
      :novel-id="currentNovelId"
      :event="selectedEvent"
      @edit="onDetailEdit"
      @deleted="onSaved"
      @open-character="openCharacter"
      @open-chapter="openChapter"
    />
    <CharacterDetailModal v-model:show="showCharDetail" :character="charStore.currentCharacter" />
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
  flex: 1 1 220px;
}
.filter {
  width: 160px;
}
.filter.small {
  width: 130px;
}
.event-row {
  margin-bottom: 8px;
  cursor: pointer;
}
.event-row :deep(.n-card__content) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.event-main {
  min-width: 0;
}
.event-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.event-title {
  font-size: 15px;
  font-weight: 600;
  word-break: break-word;
}
.event-meta {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 4px;
  font-size: 12px;
  color: var(--sf-text-tertiary, #888);
}
.event-participants {
  margin-top: 4px;
  font-size: 12px;
  color: var(--sf-text-secondary, #666);
}
.event-actions {
  flex-shrink: 0;
}
.page-error {
  margin-top: 16px;
}
@media (max-width: 640px) {
  .page {
    padding: 12px;
  }
  .filter,
  .filter.small {
    width: calc(50% - 4px);
  }
}
</style>
