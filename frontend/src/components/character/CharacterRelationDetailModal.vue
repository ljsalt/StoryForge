<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  NButton,
  NDescriptions,
  NDescriptionsItem,
  NEmpty,
  NSpin,
  NTag,
  NTimeline,
  NTimelineItem,
  useDialog,
  useMessage,
} from 'naive-ui'
import { formatDateTime } from '../../utils/format'
import { useCharacterRelationStore } from '../../stores/characterRelation'
import type { CharacterRelation, CharacterRelationEvent } from '../../api/characterRelation'

const props = defineProps<{ show: boolean; relation: CharacterRelation | null }>()
const emit = defineEmits<{
  'update:show': [value: boolean]
  edit: []
  reload: []
  'open-source': [id: string]
  'open-target': [id: string]
}>()

const store = useCharacterRelationStore()
const dialog = useDialog()
const message = useMessage()

const loading = ref(false)
const events = ref<CharacterRelationEvent[]>([])

async function loadEvents() {
  if (!props.relation) return
  loading.value = true
  try {
    events.value = await store.fetchEvents(props.relation.id)
  } catch (error) {
    message.error(store.error || '加载历史失败')
  } finally {
    loading.value = false
  }
}

watch(
  () => [props.show, props.relation?.id] as const,
  ([show]) => {
    if (show && props.relation) loadEvents()
  },
)

const statusTag = computed(() =>
  props.relation?.status === 'ended'
    ? { label: '已结束', type: 'warning' as const }
    : { label: '有效', type: 'success' as const },
)

const eventLabelMap: Record<string, { label: string; type: 'success' | 'info' | 'warning' | 'error' }> = {
  created: { label: '建立', type: 'success' },
  updated: { label: '修改', type: 'info' },
  ended: { label: '结束', type: 'error' },
  restored: { label: '恢复', type: 'success' },
}

function confirmEnd() {
  if (!props.relation) return
  dialog.warning({
    title: '结束人物关系',
    content: `确定结束「${props.relation.source_name} → ${props.relation.target_name}」的 ${props.relation.relation_type} 关系吗？历史记录会保留。`,
    positiveText: '确认结束',
    negativeText: '取消',
    onPositiveClick: async () => {
      if (!props.relation) return
      try {
        await store.end(props.relation.id)
        message.success('关系已结束')
        loadEvents()
        emit('reload')
      } catch (error) {
        message.error(store.error || '结束失败')
      }
    },
  })
}

async function doRestore() {
  if (!props.relation) return
  try {
    await store.restore(props.relation.id)
    message.success('关系已恢复')
    loadEvents()
    emit('reload')
  } catch (error) {
    message.error(store.error || '恢复失败')
  }
}
</script>

<template>
  <n-modal
    :show="show"
    preset="card"
    :title="relation ? `${relation.source_name} → ${relation.target_name}` : '关系详情'"
    :style="{ width: '640px', maxWidth: 'calc(100vw - 24px)' }"
    :bordered="false"
    @update:show="emit('update:show', $event)"
  >
    <template v-if="relation">
      <div class="head">
        <div class="type-row">
          <n-tag size="small" round :bordered="false">{{ relation.relation_type }}</n-tag>
          <n-tag size="small" round :bordered="false" :type="statusTag.type">{{ statusTag.label }}</n-tag>
        </div>
        <div class="names">
          <button class="name-btn" @click="emit('open-source', relation.source_character_id)">
            {{ relation.source_name }}
          </button>
          <span class="arrow">→</span>
          <button class="name-btn" @click="emit('open-target', relation.target_character_id)">
            {{ relation.target_name }}
          </button>
        </div>
      </div>

      <n-descriptions :column="2" label-placement="left" bordered size="small">
        <n-descriptions-item label="关系描述" :span="2">
          {{ relation.description || '（无）' }}
        </n-descriptions-item>
        <n-descriptions-item label="关系强度">
          {{ relation.strength === null ? '（未设置）' : relation.strength }}
        </n-descriptions-item>
        <n-descriptions-item label="开始时间">
          {{ relation.start_time || '（未记录）' }}
        </n-descriptions-item>
        <n-descriptions-item label="结束时间">
          {{ relation.end_time || '（未结束）' }}
        </n-descriptions-item>
        <n-descriptions-item label="最近更新">
          {{ formatDateTime(relation.updated_at) }}
        </n-descriptions-item>
        <n-descriptions-item v-if="Object.keys(relation.attributes).length" label="自定义属性" :span="2">
          <div class="attr-grid">
            <div v-for="(v, k) in relation.attributes" :key="k" class="attr-item">
              <span class="attr-k">{{ k }}:</span>
              <span class="attr-v">{{ String(v) }}</span>
            </div>
          </div>
        </n-descriptions-item>
      </n-descriptions>

      <div class="section">
        <div class="section-title">关系变化历史</div>
        <n-spin :show="loading">
          <n-empty v-if="!events.length" description="还没有事件记录" />
          <n-timeline v-else>
            <n-timeline-item
              v-for="ev in events"
              :key="ev.id"
              :type="eventLabelMap[ev.event_type]?.type ?? 'info'"
              :title="(eventLabelMap[ev.event_type]?.label ?? ev.event_type) + ' · ' + (ev.title || relation.relation_type)"
            >
              <div class="ev-meta">
                {{ formatDateTime(ev.created_at) }}
                <span v-if="ev.story_time" class="story-time"> · 小说时间 {{ ev.story_time }}</span>
                <span v-if="ev.chapter_title" class="story-time">
                  · 关联章节 第 {{ ev.chapter_number }} 章 {{ ev.chapter_title }}
                </span>
              </div>
              <div v-if="ev.description" class="ev-desc">{{ ev.description }}</div>
              <div v-if="ev.event_type !== 'created'" class="ev-diff">
                <div v-if="JSON.stringify(ev.previous_data) !== '{}' && JSON.stringify(ev.new_data) !== '{}'">
                  从
                  <code>{{ JSON.stringify(ev.previous_data) }}</code>
                  变为
                  <code>{{ JSON.stringify(ev.new_data) }}</code>
                </div>
              </div>
            </n-timeline-item>
          </n-timeline>
        </n-spin>
      </div>
    </template>
    <n-empty v-else description="没有可显示的关系" />

    <template #footer>
      <div class="footer">
        <n-button size="small" quaternary :type="relation?.status === 'active' ? 'error' : undefined" @click="relation?.status === 'active' ? confirmEnd() : doRestore()">
          {{ relation?.status === 'active' ? '结束关系' : '恢复关系' }}
        </n-button>
        <n-button size="small" @click="emit('edit')">编辑</n-button>
        <n-button size="small" type="primary" @click="emit('update:show', false)">关闭</n-button>
      </div>
    </template>
  </n-modal>
</template>

<style scoped>
.head { margin-bottom: 12px; }
.type-row { display: flex; gap: 6px; margin-bottom: 6px; }
.names { display: flex; align-items: center; gap: 8px; font-size: 16px; }
.name-btn {
  background: transparent; border: none; padding: 4px 8px; color: #5b8ff9;
  cursor: pointer; border-radius: 4px; font-size: 14px;
}
.name-btn:hover { background: rgba(91,143,249,0.12); }
.arrow { color: rgba(255,255,255,0.4); }
.attr-grid { display: flex; flex-wrap: wrap; gap: 4px 12px; }
.attr-item { font-size: 12px; }
.attr-k { color: rgba(255,255,255,0.6); }
.attr-v { color: rgba(255,255,255,0.9); }

.section { margin-top: 16px; }
.section-title { font-size: 14px; font-weight: 600; color: #fff; margin-bottom: 8px; }
.ev-meta { font-size: 12px; color: rgba(255,255,255,0.45); }
.story-time { color: rgba(255,255,255,0.35); }
.ev-desc { font-size: 13px; color: rgba(255,255,255,0.75); margin-top: 4px; }
.ev-diff { font-size: 12px; color: rgba(255,255,255,0.55); margin-top: 4px; word-break: break-all; }
.ev-diff code { background: rgba(255,255,255,0.06); padding: 1px 4px; border-radius: 3px; }

.footer { display: flex; gap: 8px; justify-content: flex-end; flex-wrap: wrap; }
</style>
