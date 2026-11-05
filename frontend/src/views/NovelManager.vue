<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  NButton,
  NEmpty,
  NGrid,
  NGridItem,
  NInput,
  NSelect,
  NSpin,
  useDialog,
  useMessage,
  type SelectOption,
} from 'naive-ui'
import { NOVEL_STATUS_OPTIONS, type Novel } from '../api/novels'
import { extractError } from '../api/error'
import { useNovelStore } from '../stores/novels'
import NovelCard from '../components/novels/NovelCard.vue'
import NovelFormModal from '../components/novels/NovelFormModal.vue'

const store = useNovelStore()
const router = useRouter()
const route = useRoute()
const dialog = useDialog()
const message = useMessage()

const showForm = ref(false)
const editingNovel = ref<Novel | null>(null)
let searchTimer: ReturnType<typeof setTimeout> | undefined

const statusOptions: SelectOption[] = [
  { label: '全部状态', value: '' },
  ...NOVEL_STATUS_OPTIONS,
]

watch(
  () => store.search,
  () => {
    if (searchTimer) clearTimeout(searchTimer)
    searchTimer = setTimeout(() => {
      store.fetchList().catch(() => message.error('搜索失败，请检查后端服务'))
    }, 300)
  },
)

watch(
  () => store.statusFilter,
  () => {
    store.fetchList().catch(() => message.error('筛选失败，请检查后端服务'))
  },
)

function openCreate() {
  editingNovel.value = null
  showForm.value = true
}

function openEdit(novel: Novel) {
  editingNovel.value = novel
  showForm.value = true
}

function openNovel(novel: Novel) {
  router.push(`/novels/${novel.id}`)
}

async function setDefault(novel: Novel) {
  try {
    await store.setDefault(novel.id)
    message.success(`已将《${novel.title}》设为默认项目`)
  } catch (error) {
    message.error(extractError(error))
  }
}

function confirmDelete(novel: Novel) {
  dialog.warning({
    title: '删除小说项目',
    content: `确定删除《${novel.title}》吗？该小说将被永久移除，此操作不可恢复。`,
    positiveText: '确认删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await store.removeNovel(novel.id)
        message.success('小说项目已删除')
      } catch (error) {
        message.error(extractError(error))
      }
    },
  })
}

function clearFilters() {
  store.clearFilters()
  store.fetchList().catch(() => message.error('加载失败'))
}

onMounted(async () => {
  try {
    await store.load()
  } catch {
    message.error('加载小说列表失败，请确认后端服务已启动')
  }
  if (route.query.create === '1') {
    openCreate()
    router.replace({ path: '/novels', query: {} })
  }
})
</script>

<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h2 class="page-title">小说项目</h2>
        <div class="page-sub">
          共 {{ store.count }} 部小说
          <span v-if="store.defaultNovel"> · 默认项目《{{ store.defaultNovel.title }}》</span>
        </div>
      </div>
      <n-button type="primary" size="small" @click="openCreate">新建小说</n-button>
    </div>

    <div class="toolbar">
      <n-input
        v-model:value="store.search"
        clearable
        placeholder="按小说标题搜索"
        class="search-input"
      />
      <n-select
        v-model:value="store.statusFilter"
        :options="statusOptions"
        class="status-select"
      />
    </div>

    <n-spin :show="store.loading">
      <div v-if="store.novels.length" class="grid-wrap">
        <n-grid :x-gap="16" :y-gap="16" cols="1 s:2 l:3" responsive="screen">
          <n-grid-item v-for="novel in store.novels" :key="novel.id">
            <NovelCard
              :novel="novel"
              @open="openNovel(novel)"
              @edit="openEdit(novel)"
              @remove="confirmDelete(novel)"
              @set-default="setDefault(novel)"
            />
          </n-grid-item>
        </n-grid>
      </div>

      <n-empty
        v-else
        class="empty-block"
        :description="store.search || store.statusFilter ? '没有符合条件的小说' : '还没有小说项目'"
        size="large"
      >
        <template #extra>
          <n-button v-if="store.search || store.statusFilter" size="small" @click="clearFilters">
            清空筛选
          </n-button>
          <n-button v-else type="primary" size="small" @click="openCreate">
            创建第一部小说
          </n-button>
        </template>
      </n-empty>
    </n-spin>

    <NovelFormModal v-model:show="showForm" :novel="editingNovel" />
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
  margin-bottom: 16px;
  flex-wrap: wrap;
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

.toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.search-input {
  width: 280px;
}

.status-select {
  width: 160px;
}

.empty-block {
  padding: 48px 0;
}

@media (max-width: 767px) {
  .search-input,
  .status-select {
    width: 100%;
  }
}
</style>
