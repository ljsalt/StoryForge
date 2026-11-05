<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  NButton,
  NEmpty,
  NInput,
  NResult,
  NSelect,
  NSpin,
  NTabPane,
  NTabs,
  NTag,
  useDialog,
  useMessage,
} from 'naive-ui'
import { getNovel } from '../api/novels'
import { extractError } from '../api/error'
import { DEFAULT_RELATION_TYPES, type WorldRelation } from '../api/world'
import { useWorldStore } from '../stores/world'
import { formatDateTime } from '../utils/format'
import WorldRelationGraph from '../components/world/WorldRelationGraph.vue'
import WorldRelationModal from '../components/world/WorldRelationModal.vue'
import WorldRelationDetailModal from '../components/world/WorldRelationDetailModal.vue'
import WorldEntryDetailModal from '../components/world/WorldEntryDetailModal.vue'

const route = useRoute()
const router = useRouter()
const store = useWorldStore()
const dialog = useDialog()
const message = useMessage()

const novelTitle = ref('')
const loadingNovel = ref(false)
const pageError = ref('')
const activeTab = ref<'list' | 'graph'>('list')
const graphCategoryId = ref('')

const showRelationModal = ref(false)
const editingRelation = ref<WorldRelation | null>(null)
const showRelationDetail = ref(false)
const relationDetail = ref<WorldRelation | null>(null)
const showEntryDetail = ref(false)

let searchTimer: ReturnType<typeof setTimeout> | undefined

const currentNovelId = computed(() => String(route.params.id))
const worldPath = computed(() => `/novels/${currentNovelId.value}/world`)
const hasRelationFilters = computed(() =>
  Boolean(store.relationTypeFilter || store.relationSearch.trim()),
)

const typeFilterOptions = computed(() => {
  const types = new Set(DEFAULT_RELATION_TYPES)
  for (const item of store.relationTypeOptions) types.add(item)
  return Array.from(types).map((item) => ({ label: item, value: item }))
})

const categoryFilterOptions = computed(() =>
  store.categories.map((item) => ({ label: item.name, value: item.id })),
)

const graphEntries = computed(() =>
  graphCategoryId.value
    ? store.allEntries.filter((entry) => entry.category_id === graphCategoryId.value)
    : store.allEntries,
)

async function load(novelId: string) {
  loadingNovel.value = true
  pageError.value = ''
  try {
    const { data } = await getNovel(novelId)
    novelTitle.value = data.title
    await store.load(novelId)
  } catch (error) {
    pageError.value = extractError(error, '小说不存在或已被删除')
  } finally {
    loadingNovel.value = false
  }
}

watch(
  () => store.relationSearch,
  () => {
    if (searchTimer) clearTimeout(searchTimer)
    searchTimer = setTimeout(() => {
      store.fetchRelations().catch(() => message.error('搜索关系失败，请检查后端服务'))
    }, 300)
  },
)

async function changeTypeFilter(value: string | null) {
  try {
    await store.setRelationTypeFilter(value ?? '')
  } catch {
    message.error('筛选关系失败')
  }
}

async function clearFilters() {
  store.clearRelationFilters()
  try {
    await store.fetchRelations()
  } catch {
    message.error('加载关系失败')
  }
}

function openCreateRelation() {
  if (!store.allEntries.length) {
    message.warning('请先创建世界观设定，再建立关系')
    return
  }
  editingRelation.value = null
  showRelationModal.value = true
}

function openEditRelation(relation: WorldRelation) {
  editingRelation.value = relation
  showRelationDetail.value = false
  showRelationModal.value = true
}

function openRelationDetail(relation: WorldRelation) {
  relationDetail.value = relation
  showRelationDetail.value = true
}

function confirmRemoveRelation(relation: WorldRelation) {
  dialog.warning({
    title: '删除关系',
    content: `确定删除「${relation.source.name} ${relation.relation_type} ${relation.target.name}」吗？两端的世界观设定不会被删除。`,
    positiveText: '确认删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await store.removeRelation(relation.id)
        showRelationDetail.value = false
        message.success('关系已删除')
      } catch (error) {
        message.error(extractError(error, '删除关系失败'))
      }
    },
  })
}

async function openEntry(entryId: string) {
  try {
    await store.openEntry(entryId)
    showEntryDetail.value = true
  } catch (error) {
    message.error(extractError(error, '读取设定详情失败'))
  }
}

function onRelationSaved() {
  message.success('关系已更新')
}

onMounted(() => load(currentNovelId.value))
watch(
  () => route.params.id,
  (id) => {
    if (id) {
      showRelationModal.value = false
      showRelationDetail.value = false
      showEntryDetail.value = false
      load(String(id))
    }
  },
)
</script>

<template>
  <div class="page">
    <n-spin :show="loadingNovel">
      <n-result
        v-if="pageError"
        status="404"
        title="无法打开该小说的世界观关系"
        :description="pageError"
      >
        <template #footer>
          <n-button size="small" @click="router.push('/novels')">返回小说列表</n-button>
        </template>
      </n-result>

      <template v-else>
        <div class="page-header">
          <div class="header-left">
            <n-button size="small" quaternary @click="router.push(worldPath)">
              ← 返回世界观
            </n-button>
            <div>
              <h2 class="page-title">世界观关系</h2>
              <div class="page-sub">《{{ novelTitle }}》 · 关系的方向与两端都属于当前小说</div>
            </div>
          </div>
          <div class="header-actions">
            <n-button size="small" type="primary" @click="openCreateRelation">
              新建关系
            </n-button>
          </div>
        </div>

        <div class="stat-strip">
          <div class="stat">
            <span class="stat-value">{{ store.stats?.total_relations ?? 0 }}</span>
            <span class="stat-label">关系总数</span>
          </div>
          <div class="stat">
            <span class="stat-value">{{ store.stats?.relation_type_count ?? 0 }}</span>
            <span class="stat-label">关系类型</span>
          </div>
          <div class="stat">
            <span class="stat-value">{{ store.stats?.related_entry_count ?? 0 }}</span>
            <span class="stat-label">关联条目</span>
          </div>
          <div class="stat">
            <span class="stat-value">{{ store.allEntries.length }}</span>
            <span class="stat-label">条目总数</span>
          </div>
        </div>

        <n-tabs v-model:value="activeTab" type="line" animated>
          <n-tab-pane name="list" tab="关系列表">
            <div class="toolbar">
              <n-select
                :value="store.relationTypeFilter"
                :options="typeFilterOptions"
                clearable
                filterable
                placeholder="按关系类型筛选"
                class="type-select"
                @update:value="changeTypeFilter"
              />
              <n-input
                v-model:value="store.relationSearch"
                clearable
                placeholder="搜索关系描述"
                class="search-input"
              />
              <n-button v-if="hasRelationFilters" size="small" @click="clearFilters">
                清空筛选
              </n-button>
            </div>

            <n-spin :show="store.relationsLoading">
              <div v-if="store.relations.length" class="relation-list">
                <div v-for="relation in store.relations" :key="relation.id" class="relation-item">
                  <div class="line-main">
                    <button
                      type="button"
                      class="endpoint"
                      @click="openEntry(relation.source_entry_id)"
                    >
                      {{ relation.source.name }}
                    </button>
                    <n-tag size="small" round type="success" :bordered="false">
                      {{ relation.relation_type }}
                    </n-tag>
                    <span class="arrow">→</span>
                    <button
                      type="button"
                      class="endpoint"
                      @click="openEntry(relation.target_entry_id)"
                    >
                      {{ relation.target.name }}
                    </button>
                    <span class="cat-note">
                      {{ relation.source.category_name }} → {{ relation.target.category_name }}
                    </span>
                  </div>
                  <div class="line-desc">
                    {{ relation.description || '暂无关系描述' }}
                  </div>
                  <div class="line-foot">
                    <span class="time">更新于 {{ formatDateTime(relation.updated_at) }}</span>
                    <div class="actions">
                      <n-button size="tiny" quaternary @click="openEditRelation(relation)">
                        编辑
                      </n-button>
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
              </div>

              <n-empty
                v-else
                class="empty-block"
                :description="hasRelationFilters ? '没有符合筛选条件的关系' : '还没有建立任何世界观关系'"
                size="large"
              >
                <template #extra>
                  <n-button v-if="hasRelationFilters" size="small" @click="clearFilters">
                    清空筛选
                  </n-button>
                  <n-button v-else size="small" type="primary" @click="openCreateRelation">
                    创建第一条关系
                  </n-button>
                </template>
              </n-empty>
            </n-spin>
          </n-tab-pane>

          <n-tab-pane name="graph" tab="关系网络">
            <div class="toolbar">
              <n-select
                v-model:value="graphCategoryId"
                :options="categoryFilterOptions"
                clearable
                placeholder="按分类筛选节点"
                class="type-select"
              />
              <n-select
                :value="store.relationTypeFilter"
                :options="typeFilterOptions"
                clearable
                filterable
                placeholder="按关系类型筛选连线"
                class="type-select"
                @update:value="changeTypeFilter"
              />
              <span class="graph-note">
                当前展示 {{ graphEntries.length }} 个节点 / {{ store.relations.length }} 条关系
              </span>
            </div>

            <WorldRelationGraph
              :entries="graphEntries"
              :relations="store.relations"
              @open-entry="openEntry"
              @open-relation="openRelationDetail"
            />

            <div v-if="!store.relations.length" class="graph-guide">
              <span>还没有关系连线。</span>
              <n-button size="small" type="primary" @click="openCreateRelation">
                创建关系
              </n-button>
            </div>
          </n-tab-pane>
        </n-tabs>

        <WorldRelationModal
          v-model:show="showRelationModal"
          :relation="editingRelation"
          @saved="onRelationSaved"
        />

        <WorldRelationDetailModal
          v-model:show="showRelationDetail"
          :relation="relationDetail"
          @edit="relationDetail && openEditRelation(relationDetail)"
          @remove="relationDetail && confirmRemoveRelation(relationDetail)"
        />

        <WorldEntryDetailModal
          v-model:show="showEntryDetail"
          :entry="store.currentEntry"
          :entry-actions="false"
          @open-entry="openEntry"
          @relations-changed="store.fetchRelations()"
        />
      </template>
    </n-spin>
  </div>
</template>

<style scoped>
.page {
  max-width: 1200px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}

.header-left {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.page-title {
  margin: 0;
  font-size: 22px;
  color: #fff;
}

.page-sub {
  margin-top: 4px;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.45);
}

.header-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.stat-strip {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.stat {
  flex: 1 1 140px;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 10px 14px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.04);
}

.stat-value {
  font-size: 20px;
  font-weight: 600;
  color: #fff;
}

.stat-label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.45);
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.type-select {
  width: 190px;
}

.search-input {
  width: 260px;
}

.graph-note {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.4);
}

.relation-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.relation-item {
  padding: 12px 14px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.04);
}

.line-main {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  min-width: 0;
}

.endpoint {
  padding: 0;
  border: none;
  background: transparent;
  color: #8fb4ff;
  font-size: 14px;
  cursor: pointer;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.endpoint:hover {
  text-decoration: underline;
}

.arrow {
  color: #7ea2ff;
}

.cat-note {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.35);
}

.line-desc {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.7;
  color: rgba(255, 255, 255, 0.6);
  white-space: pre-wrap;
  word-break: break-word;
}

.line-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 8px;
}

.time {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.35);
}

.actions {
  display: flex;
  gap: 2px;
}

.empty-block {
  padding: 40px 0;
}

.graph-guide {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 12px;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.5);
}

@media (max-width: 767px) {
  .page-header {
    align-items: flex-start;
  }

  .stat {
    flex: 1 1 45%;
  }

  .type-select,
  .search-input {
    width: 100%;
  }

  .relation-item {
    padding: 10px 12px;
  }
}
</style>
