<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  NButton,
  NDescriptions,
  NDescriptionsItem,
  NEmpty,
  NModal,
  NSpace,
  NSpin,
  NTag,
  useDialog,
  useMessage,
} from 'naive-ui'
import { extractError } from '../../api/error'
import {
  PLOT_IMPORTANCE_LABELS,
  PLOT_IMPORTANCE_TYPES,
  type PlotEvent,
} from '../../api/plotEvent'
import { usePlotEventStore } from '../../stores/plotEvent'

const props = defineProps<{
  show: boolean
  novelId: string
  event?: PlotEvent | null
}>()
const emit = defineEmits<{
  'update:show': [v: boolean]
  edit: []
  deleted: []
  'open-character': [characterId: string]
  'open-chapter': [chapterId: string]
}>()

const store = usePlotEventStore()
const message = useMessage()
const dialog = useDialog()

const current = ref<PlotEvent | null>(null)
const loading = ref(false)

const detail = computed(() => current.value || props.event || null)

async function init() {
  if (!props.event) return
  current.value = props.event
  loading.value = true
  try {
    current.value = await store.fetchOne(props.event.id)
  } catch {
    // 拉取失败时回退到列表里的快照
  } finally {
    loading.value = false
  }
}

watch(
  () => [props.show, props.event?.id] as const,
  ([show]) => {
    if (show) init()
  },
  { immediate: true },
)

function close() {
  emit('update:show', false)
}

function confirmDelete() {
  const event = detail.value
  if (!event) return
  dialog.warning({
    title: '删除剧情事件',
    content: `确定删除「${event.title}」吗？参与人物关联会被清理，人物档案与章节不会受影响。`,
    positiveText: '确认删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await store.remove(event.id)
        message.success('事件已删除')
        emit('deleted')
        close()
      } catch (error) {
        message.error(extractError(error, '删除事件失败'))
      }
    },
  })
}
</script>

<template>
  <n-modal
    :show="show"
    preset="card"
    title="剧情事件详情"
    :style="{ width: 'min(680px, calc(100vw - 16px))' }"
    :bordered="false"
    @update:show="(v: boolean) => { if (!v) close() }"
  >
    <n-spin :show="loading">
      <template v-if="detail">
        <n-descriptions bordered :column="1" size="small" label-placement="left">
          <n-descriptions-item label="事件标题">{{ detail.title }}</n-descriptions-item>
          <n-descriptions-item label="事件类型">
            <n-tag v-if="detail.event_type" size="tiny" :bordered="false">
              {{ detail.event_type }}
            </n-tag>
            <span v-else class="muted">未填写</span>
          </n-descriptions-item>
          <n-descriptions-item label="重要程度">
            <n-tag size="tiny" :bordered="false" :type="PLOT_IMPORTANCE_TYPES[detail.importance]">
              {{ PLOT_IMPORTANCE_LABELS[detail.importance] }}
            </n-tag>
          </n-descriptions-item>
          <n-descriptions-item label="故事发生时间">
            <span v-if="detail.story_time">{{ detail.story_time }}</span>
            <span v-else class="muted">未填写（系统记录时间不算故事时间）</span>
          </n-descriptions-item>
          <n-descriptions-item label="发生地点">
            <span v-if="detail.location_name">{{ detail.location_name }}</span>
            <span v-else class="muted">未填写</span>
          </n-descriptions-item>
          <n-descriptions-item label="关联章节">
            <span v-if="detail.chapter_id">
              <n-button size="tiny" quaternary type="primary" @click="emit('open-chapter', detail.chapter_id as string)">
                第 {{ detail.chapter_number }} 章 {{ detail.chapter_title }}
              </n-button>
            </span>
            <span v-else class="muted">未关联章节</span>
          </n-descriptions-item>
          <n-descriptions-item label="事件描述">
            <div class="detail-desc">{{ detail.description || '暂无描述' }}</div>
          </n-descriptions-item>
        </n-descriptions>

        <div class="section-title">参与人物（{{ detail.participants.length }}）</div>
        <n-empty v-if="!detail.participants.length" description="没有关联参与人物" size="small" />
        <div v-else class="participant-list">
          <div v-for="p in detail.participants" :key="p.id" class="participant-item">
            <button class="char-link" @click="emit('open-character', p.character_id)">
              {{ p.character_name }}
            </button>
            <n-tag v-if="p.participant_role" size="tiny" :bordered="false" type="info">
              {{ p.participant_role }}
            </n-tag>
            <span v-if="p.description" class="participant-desc">{{ p.description }}</span>
          </div>
        </div>
      </template>
      <n-empty v-else description="未选择事件" />
    </n-spin>

    <template #footer>
      <n-space justify="space-between">
        <n-button size="small" type="error" quaternary @click="confirmDelete">删除事件</n-button>
        <n-space>
          <n-button size="small" @click="close">关闭</n-button>
          <n-button size="small" type="primary" @click="emit('edit')">编辑</n-button>
        </n-space>
      </n-space>
    </template>
  </n-modal>
</template>

<style scoped>
.muted {
  font-size: 12px;
  color: var(--sf-text-tertiary, #999);
}
.detail-desc {
  white-space: pre-wrap;
  line-height: 1.7;
}
.section-title {
  margin: 16px 0 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--sf-text-secondary, #666);
}
.participant-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.participant-item {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.char-link {
  border: none;
  background: none;
  padding: 0;
  font-size: 14px;
  color: #2080f0;
  cursor: pointer;
}
.char-link:hover {
  text-decoration: underline;
}
.participant-desc {
  font-size: 12px;
  color: var(--sf-text-tertiary, #888);
}
</style>
