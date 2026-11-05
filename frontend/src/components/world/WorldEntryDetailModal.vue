<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  NButton,
  NDescriptions,
  NDescriptionsItem,
  NEmpty,
  NModal,
  NSpin,
  NTag,
  useDialog,
  useMessage,
} from 'naive-ui'
import { extractError } from '../../api/error'
import type { WorldEntry, WorldEntryRelation, WorldEntryRelations, WorldRelation } from '../../api/world'
import { useWorldStore } from '../../stores/world'
import { formatDateTime } from '../../utils/format'
import WorldRelationModal from './WorldRelationModal.vue'

const props = withDefaults(
  defineProps<{ show: boolean; entry: WorldEntry | null; entryActions?: boolean }>(),
  { entryActions: true },
)

const emit = defineEmits<{
  'update:show': [value: boolean]
  edit: []
  remove: []
  'open-entry': [entryId: string]
  'relations-changed': []
}>()

const store = useWorldStore()
const dialog = useDialog()
const message = useMessage()

const relations = ref<WorldEntryRelations | null>(null)
const relationsLoading = ref(false)
const relationsError = ref('')
const showRelationModal = ref(false)
const editingRelation = ref<WorldRelation | null>(null)

const allRelations = computed<WorldEntryRelation[]>(() => {
  if (!relations.value) return []
  return [...relations.value.outgoing, ...relations.value.incoming]
})

function otherEndpoint(relation: WorldEntryRelation) {
  return relation.direction === 'outgoing' ? relation.target : relation.source
}

async function loadRelations() {
  if (!props.entry) return
  relationsLoading.value = true
  relationsError.value = ''
  try {
    relations.value = await store.fetchEntryRelations(props.entry.id)
  } catch (error) {
    relationsError.value = extractError(error, '加载关联关系失败')
  } finally {
    relationsLoading.value = false
  }
}

watch(
  () => [props.show, props.entry?.id] as const,
  ([show]) => {
    if (show) loadRelations()
    else showRelationModal.value = false
  },
)

function openCreateRelation() {
  if (!props.entry) return
  editingRelation.value = null
  showRelationModal.value = true
}

function editRelation(relation: WorldRelation) {
  editingRelation.value = relation
  showRelationModal.value = true
}

function onRelationSaved() {
  loadRelations()
  emit('relations-changed')
}

function confirmRemoveRelation(relation: WorldEntryRelation) {
  const other = otherEndpoint(relation)
  dialog.warning({
    title: '删除关系',
    content: `确定删除「${relation.source.name} ${relation.relation_type} ${relation.target.name}」吗？两端的世界观设定不会被删除。`,
    positiveText: '确认删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await store.removeRelation(relation.id)
        await loadRelations()
        emit('relations-changed')
        message.success(`已删除与《${other.name}》的关系`)
      } catch (error) {
        message.error(extractError(error, '删除关系失败'))
      }
    },
  })
}
</script>

<template>
  <n-modal
    :show="show"
    preset="card"
    title="设定详情"
    :style="{ width: '760px', maxWidth: 'calc(100vw - 24px)' }"
    :bordered="false"
    @update:show="emit('update:show', $event)"
  >
    <n-empty v-if="!entry" description="暂无设定内容" />

    <div v-else class="detail-body">
      <div class="title-row">
        <h2 class="entry-title">{{ entry.name }}</h2>
        <n-tag size="small" round type="info" :bordered="false">
          {{ entry.category_name }}
        </n-tag>
      </div>

      <div v-if="entry.tags.length" class="tag-row">
        <n-tag v-for="tag in entry.tags" :key="tag" size="small" round :bordered="false">
          {{ tag }}
        </n-tag>
      </div>

      <section v-if="entry.summary" class="block">
        <div class="block-title">简介</div>
        <p class="text">{{ entry.summary }}</p>
      </section>

      <section class="block">
        <div class="block-title">详细描述</div>
        <p class="text pre">{{ entry.content || '暂无详细描述' }}</p>
      </section>

      <section class="block">
        <div class="block-title">自定义属性</div>
        <n-descriptions
          v-if="Object.keys(entry.attributes).length"
          :column="1"
          label-placement="left"
          bordered
          size="small"
        >
          <n-descriptions-item
            v-for="(value, key) in entry.attributes"
            :key="key"
            :label="String(key)"
          >
            {{ value === null || value === '' ? '—' : value }}
          </n-descriptions-item>
        </n-descriptions>
        <span v-else class="muted">暂无自定义属性</span>
      </section>

      <section class="block relation-block">
        <div class="relation-header">
          <div class="block-title">
            关联关系
            <span v-if="relations" class="count">
              （{{ allRelations.length }} 条）
            </span>
          </div>
          <n-button size="tiny" type="primary" ghost @click="openCreateRelation">
            新建关系
          </n-button>
        </div>

        <n-spin :show="relationsLoading">
          <div v-if="relationsError" class="relation-error">{{ relationsError }}</div>

          <div v-else-if="allRelations.length" class="relation-list">
            <div
              v-for="relation in allRelations"
              :key="relation.id"
              class="relation-row"
              :class="relation.direction"
            >
              <span class="dir-arrow" :title="relation.direction === 'outgoing' ? '当前条目为起点' : '当前条目为终点'">
                {{ relation.direction === 'outgoing' ? '→' : '←' }}
              </span>
              <div class="relation-main">
                <div class="relation-line">
                  <n-tag size="tiny" round :bordered="false" type="success">
                    {{ relation.relation_type }}
                  </n-tag>
                  <button
                    type="button"
                    class="endpoint"
                    @click="emit('open-entry', otherEndpoint(relation).id)"
                  >
                    {{ otherEndpoint(relation).name }}
                  </button>
                  <span class="endpoint-cat">{{ otherEndpoint(relation).category_name }}</span>
                  <span class="direction-text">
                    {{ relation.direction === 'outgoing' ? '当前设定为起点' : '当前设定为终点' }}
                  </span>
                </div>
                <div v-if="relation.description" class="relation-desc">
                  {{ relation.description }}
                </div>
              </div>
              <div class="relation-actions">
                <n-button size="tiny" quaternary @click="editRelation(relation)">编辑</n-button>
                <n-button
                  size="tiny"
                  quaternary
                  type="error"
                  @click="confirmRemoveRelation(relation)"
                >
                  删除
                </n-button>
              </div>
            </div>
          </div>

          <div v-else-if="!relationsLoading" class="relation-empty">
            <span class="muted">该设定还没有关联关系。</span>
            <n-button size="tiny" @click="openCreateRelation">创建第一条关系</n-button>
          </div>
        </n-spin>
      </section>

      <n-descriptions :column="1" label-placement="left" size="small" class="info">
        <n-descriptions-item label="父级条目">
          {{ entry.parent_name || '无' }}
        </n-descriptions-item>
        <n-descriptions-item label="排序">{{ entry.sort_order }}</n-descriptions-item>
        <n-descriptions-item label="创建时间">
          {{ formatDateTime(entry.created_at) }}
        </n-descriptions-item>
        <n-descriptions-item label="更新时间">
          {{ formatDateTime(entry.updated_at) }}
        </n-descriptions-item>
      </n-descriptions>
    </div>

    <template #footer>
      <div v-if="entry" class="footer">
        <n-button
          v-if="entryActions"
          size="small"
          type="error"
          ghost
          @click="emit('remove')"
        >
          删除设定
        </n-button>
        <div class="right">
          <n-button size="small" @click="emit('update:show', false)">关闭</n-button>
          <n-button
            v-if="entryActions"
            size="small"
            type="primary"
            @click="emit('edit')"
          >
            编辑设定
          </n-button>
        </div>
      </div>
    </template>

    <WorldRelationModal
      v-model:show="showRelationModal"
      :relation="editingRelation"
      :default-source-id="entry?.id"
      @saved="onRelationSaved"
    />
  </n-modal>
</template>

<style scoped>
.title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.entry-title {
  margin: 0;
  font-size: 20px;
  color: #fff;
  word-break: break-word;
}

.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
}

.block {
  margin-top: 18px;
}

.block-title {
  margin-bottom: 6px;
  font-size: 13px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.75);
}

.count {
  font-weight: 400;
  color: rgba(255, 255, 255, 0.4);
}

.text {
  margin: 0;
  font-size: 13px;
  line-height: 1.8;
  color: rgba(255, 255, 255, 0.7);
  word-break: break-word;
}

.pre {
  white-space: pre-wrap;
}

.muted {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.4);
}

.info {
  margin-top: 18px;
}

.footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.right {
  display: flex;
  gap: 8px;
}

.relation-block {
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.03);
  padding: 12px;
}

.relation-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}

.relation-header .block-title {
  margin-bottom: 0;
}

.relation-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.relation-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.04);
}

.dir-arrow {
  flex: none;
  width: 18px;
  text-align: center;
  font-size: 15px;
  line-height: 22px;
  color: #7ea2ff;
}

.relation-row.incoming .dir-arrow {
  color: #ffa94d;
}

.relation-main {
  flex: 1;
  min-width: 0;
}

.relation-line {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.endpoint {
  padding: 0;
  border: none;
  background: transparent;
  color: #8fb4ff;
  font-size: 13px;
  cursor: pointer;
}

.endpoint:hover {
  text-decoration: underline;
}

.endpoint-cat {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.4);
}

.direction-text {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.35);
}

.relation-desc {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.7;
  color: rgba(255, 255, 255, 0.6);
  white-space: pre-wrap;
  word-break: break-word;
}

.relation-actions {
  flex: none;
  display: flex;
  gap: 2px;
}

.relation-empty {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  padding: 8px 0;
}

.relation-error {
  font-size: 12px;
  color: #ff7875;
  padding: 8px 0;
}

@media (max-width: 767px) {
  .relation-row {
    flex-wrap: wrap;
  }

  .relation-actions {
    width: 100%;
    justify-content: flex-end;
  }
}
</style>
