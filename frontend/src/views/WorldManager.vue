<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  NButton,
  NCard,
  NEmpty,
  NGrid,
  NGridItem,
  NInput,
  NResult,
  NSpin,
  useDialog,
  useMessage,
} from 'naive-ui'
import { getNovel } from '../api/novels'
import { extractError } from '../api/error'
import type { WorldEntry } from '../api/world'
import { useWorldStore } from '../stores/world'
import WorldEntryCard from '../components/world/WorldEntryCard.vue'
import WorldEntryFormModal from '../components/world/WorldEntryFormModal.vue'
import WorldEntryDetailModal from '../components/world/WorldEntryDetailModal.vue'
import WorldCategoryManager from '../components/world/WorldCategoryManager.vue'

const route = useRoute()
const router = useRouter()
const store = useWorldStore()
const dialog = useDialog()
const message = useMessage()

const novelTitle = ref('')
const loadingNovel = ref(false)
const pageError = ref('')
const showForm = ref(false)
const showDetail = ref(false)
const showCategories = ref(false)
const editingEntry = ref<WorldEntry | null>(null)
let searchTimer: ReturnType<typeof setTimeout> | undefined

const currentNovelId = computed(() => String(route.params.id))

const activeCategoryName = computed(() => {
  if (!store.categoryFilter) return '全部设定'
  return store.categories.find((item) => item.id === store.categoryFilter)?.name ?? '设定'
})

const hasFilters = computed(() => Boolean(store.search.trim() || store.categoryFilter))

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
  () => store.search,
  () => {
    if (searchTimer) clearTimeout(searchTimer)
    searchTimer = setTimeout(() => {
      store.fetchEntries().catch(() => message.error('搜索失败，请检查后端服务'))
    }, 300)
  },
)

async function selectCategory(categoryId: string) {
  try {
    await store.selectCategory(categoryId)
  } catch {
    message.error('加载分类下的设定失败')
  }
}

function clearFilters() {
  store.clearFilters()
  store.fetchEntries().catch(() => message.error('加载失败'))
}

function openCreate() {
  if (!store.categories.length) {
    message.warning('请先在「分类管理」中创建至少一个分类')
    return
  }
  editingEntry.value = null
  showForm.value = true
}

function openEdit(entry: WorldEntry) {
  editingEntry.value = entry
  showDetail.value = false
  showForm.value = true
}

async function openDetail(entry: WorldEntry) {
  try {
    await store.openEntry(entry.id)
    showDetail.value = true
  } catch (error) {
    message.error(extractError(error, '读取设定详情失败'))
  }
}

async function openRelatedEntry(entryId: string) {
  try {
    await store.openEntry(entryId)
    showDetail.value = true
  } catch (error) {
    message.error(extractError(error, '读取关联设定失败'))
  }
}

function goRelations() {
  router.push(`/novels/${currentNovelId.value}/world/relations`)
}

function confirmRemove(entry: WorldEntry) {
  dialog.warning({
    title: '删除世界观设定',
    content: `确定删除《${entry.name}》吗？若存在子设定，需要先移动或删除子设定。此操作不可恢复。`,
    positiveText: '确认删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await store.removeEntry(entry.id)
        showDetail.value = false
        message.success('设定已删除')
      } catch (error) {
        message.error(extractError(error, '删除失败'))
      }
    },
  })
}

function onSaved() {
  message.success('世界观数据已更新')
}

onMounted(() => load(currentNovelId.value))
watch(
  () => route.params.id,
  (id) => {
    if (id) {
      showForm.value = false
      showDetail.value = false
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
        title="无法打开该小说的世界观"
        :description="pageError"
      >
        <template #footer>
          <n-button size="small" @click="router.push('/novels')">返回小说列表</n-button>
        </template>
      </n-result>

      <template v-else>
        <div class="page-header">
          <div class="header-left">
            <n-button
              size="small"
              quaternary
              @click="router.push(`/novels/${currentNovelId}`)"
            >
              ← 返回小说详情
            </n-button>
            <div>
              <h2 class="page-title">世界观设定</h2>
              <div class="page-sub">
                《{{ novelTitle }}》 · 共 {{ store.totalEntries }} 条设定 ·
                {{ store.categories.length }} 个分类 ·
                {{ store.totalRelations }} 条关系
              </div>
            </div>
          </div>
          <div class="header-actions">
            <n-button size="small" @click="goRelations">关系管理</n-button>
            <n-button size="small" @click="showCategories = true">分类管理</n-button>
            <n-button size="small" type="primary" @click="openCreate">新建设定</n-button>
          </div>
        </div>

        <div v-if="!store.totalRelations" class="relation-tip">
          <span class="relation-tip-text">
            还没有世界观关系。关系可以描述条目之间的管辖、联盟、贸易等关联，让世界观形成可查询的网络。
          </span>
          <n-button size="small" type="primary" ghost @click="goRelations">
            去创建关系
          </n-button>
        </div>

        <div class="world-layout">
          <aside class="category-panel">
            <div class="panel-title">分类导航</div>
            <div class="category-nav">
              <button
                type="button"
                class="cat-item"
                :class="{ active: !store.categoryFilter }"
                @click="selectCategory('')"
              >
                <span class="cat-name">全部设定</span>
                <span class="cat-count">{{ store.totalEntries }}</span>
              </button>
              <button
                v-for="category in store.categories"
                :key="category.id"
                type="button"
                class="cat-item"
                :class="{ active: store.categoryFilter === category.id }"
                @click="selectCategory(category.id)"
              >
                <span class="cat-name">{{ category.name }}</span>
                <span class="cat-count">{{ category.entry_count }}</span>
              </button>
            </div>
          </aside>

          <section class="content-panel">
            <div class="toolbar">
              <n-input
                v-model:value="store.search"
                clearable
                placeholder="搜索设定名称、简介或详细描述"
                class="search-input"
              />
              <span class="current-cat">当前：{{ activeCategoryName }}</span>
            </div>

            <n-spin :show="store.loading">
              <div v-if="store.entries.length" class="entry-grid">
                <n-grid :x-gap="12" :y-gap="12" cols="1 s:2" responsive="screen">
                  <n-grid-item v-for="entry in store.entries" :key="entry.id">
                    <WorldEntryCard
                      :entry="entry"
                      @open="openDetail(entry)"
                      @edit="openEdit(entry)"
                      @remove="confirmRemove(entry)"
                    />
                  </n-grid-item>
                </n-grid>
              </div>

              <n-empty
                v-else
                class="empty-block"
                :description="hasFilters ? '没有符合条件的设定' : '还没有世界观设定'"
                size="large"
              >
                <template #extra>
                  <n-button v-if="hasFilters" size="small" @click="clearFilters">
                    清空筛选
                  </n-button>
                  <n-button v-else size="small" type="primary" @click="openCreate">
                    创建第一条设定
                  </n-button>
                </template>
              </n-empty>
            </n-spin>
          </section>
        </div>

        <WorldEntryFormModal
          v-model:show="showForm"
          :categories="store.categories"
          :entries="store.entries"
          :entry="editingEntry"
          :default-category-id="store.categoryFilter"
          @saved="onSaved"
        />

        <WorldEntryDetailModal
          v-model:show="showDetail"
          :entry="store.currentEntry"
          @edit="store.currentEntry && openEdit(store.currentEntry)"
          @remove="store.currentEntry && confirmRemove(store.currentEntry)"
          @open-entry="openRelatedEntry"
        />

        <WorldCategoryManager v-model:show="showCategories" @changed="onSaved" />
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

.relation-tip {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 12px;
  padding: 10px 14px;
  border-radius: 8px;
  background: rgba(64, 128, 255, 0.1);
  border: 1px solid rgba(64, 128, 255, 0.22);
}

.relation-tip-text {
  flex: 1;
  min-width: 200px;
  font-size: 13px;
  line-height: 1.7;
  color: rgba(255, 255, 255, 0.6);
}

.world-layout {
  display: flex;
  gap: 16px;
  align-items: flex-start;
}

.category-panel {
  width: 220px;
  flex: none;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.03);
  padding: 12px;
}

.panel-title {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.4);
  margin-bottom: 8px;
}

.category-nav {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.cat-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 10px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: rgba(255, 255, 255, 0.7);
  font-size: 13px;
  cursor: pointer;
  text-align: left;
  white-space: nowrap;
}

.cat-item:hover {
  background: rgba(255, 255, 255, 0.06);
}

.cat-item.active {
  background: rgba(64, 128, 255, 0.18);
  color: #fff;
}

.cat-name {
  overflow: hidden;
  text-overflow: ellipsis;
}

.cat-count {
  flex: none;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.45);
}

.content-panel {
  flex: 1;
  min-width: 0;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.search-input {
  width: 320px;
}

.current-cat {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.45);
}

.empty-block {
  padding: 48px 0;
}

@media (max-width: 767px) {
  .world-layout {
    flex-direction: column;
  }

  .category-panel {
    width: 100%;
    box-sizing: border-box;
    padding: 10px;
  }

  .category-nav {
    flex-direction: row;
    overflow-x: auto;
    padding-bottom: 4px;
  }

  .cat-item {
    flex: none;
  }

  .content-panel {
    width: 100%;
  }

  .search-input {
    width: 100%;
  }
}
</style>
