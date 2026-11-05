<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
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
} from 'naive-ui'
import { getNovel } from '../api/novels'
import { extractError } from '../api/error'
import type { Character } from '../api/character'
import { DEFAULT_CHARACTER_ROLES } from '../api/character'
import { useCharacterStore } from '../stores/character'
import { useCharacterRelationStore } from '../stores/characterRelation'
import CharacterCard from '../components/character/CharacterCard.vue'
import CharacterFormModal from '../components/character/CharacterFormModal.vue'
import CharacterDetailModal from '../components/character/CharacterDetailModal.vue'

const route = useRoute()
const router = useRouter()
const store = useCharacterStore()
const relStore = useCharacterRelationStore()
const dialog = useDialog()
const message = useMessage()

const novelTitle = ref('')
const loadingNovel = ref(false)
const pageError = ref('')
const showForm = ref(false)
const showDetail = ref(false)
const editingCharacter = ref<Character | null>(null)
let searchTimer: ReturnType<typeof setTimeout> | undefined

const currentNovelId = computed(() => String(route.params.id))

const roleOptions = computed(() =>
  ['', ...DEFAULT_CHARACTER_ROLES].map((r) => ({ label: r ? r : '全部定位', value: r })),
)

async function load(novelId: string) {
  loadingNovel.value = true
  pageError.value = ''
  try {
    const { data } = await getNovel(novelId)
    novelTitle.value = data.title
    await store.load(novelId)
    // 人物关系加载失败不应影响人物档案主功能（新建/编辑/详情等），
    // 此时关系数显示为 0，人物关系页面会单独展示错误详情。
    try {
      await relStore.load(novelId)
    } catch {
      /* 忽略关系加载错误 */
    }
  } catch (error) {
    pageError.value = extractError(error, '小说不存在或已被删除')
  } finally {
    loadingNovel.value = false
  }
}

watch(
  () => [store.search, store.roleFilter, store.tagFilter, store.sort] as const,
  () => {
    if (searchTimer) clearTimeout(searchTimer)
    searchTimer = setTimeout(() => store.fetchCharacters().catch(() => {}), 300)
  },
)

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

function openCreate() {
  editingCharacter.value = null
  showForm.value = true
}

function openEdit(character: Character) {
  editingCharacter.value = character
  showDetail.value = false
  showForm.value = true
}

async function openDetail(characterId: string) {
  try {
    await store.openCharacter(characterId)
    showDetail.value = true
  } catch (error) {
    message.error(extractError(error, '读取人物详情失败'))
  }
}

async function confirmRemove(character: Character) {
  dialog.warning({
    title: '删除人物',
    content: `确定删除《${character.name}》吗？相关的当前状态和秘密会一并清理。此操作不可恢复。`,
    positiveText: '确认删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await store.remove(character.id)
        showDetail.value = false
        message.success('人物已删除')
      } catch (error) {
        message.error(extractError(error, '删除失败'))
      }
    },
  })
}

function clearFilters() {
  store.clearFilters()
}

function onDetailEdit() {
  if (store.currentCharacter) openEdit(store.currentCharacter)
}

function onDetailRemove() {
  if (store.currentCharacter) confirmRemove(store.currentCharacter)
}

async function onStateChanged() {
  if (store.currentCharacter) {
    await store.openCharacter(store.currentCharacter.id)
  }
}

async function onSecretsChanged() {
  if (store.currentCharacter) {
    await store.openCharacter(store.currentCharacter.id)
  }
}

async function onDetailSaved() {
  if (store.currentCharacter) {
    await store.openCharacter(store.currentCharacter.id)
  }
}
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
              <h2 class="page-title">人物档案</h2>
              <div class="page-sub">
                《{{ novelTitle }}》 · 共 {{ store.totalCharacters }} 位人物 ·
                {{ relStore.totalRelations }} 条人物关系
              </div>
            </div>
          </div>
          <div class="header-actions">
            <n-button size="small" @click="router.push(`/novels/${currentNovelId}/world`)">
              世界观管理
            </n-button>
            <n-button size="small" @click="router.push(`/novels/${currentNovelId}/character-relations`)">
              人物关系
            </n-button>
            <n-button size="small" type="primary" @click="openCreate">
              + 新建人物
            </n-button>
          </div>
        </div>

        <div class="toolbar">
          <n-input
            v-model:value="store.search"
            clearable
            placeholder="搜索姓名、身份、背景或别名"
            class="search-input"
          />
          <n-select
            v-model:value="store.roleFilter"
            :options="roleOptions"
            class="filter-select"
          />
          <n-select
            v-model:value="store.sort"
            :options="[
              { label: '按排序优先 · 再按更新', value: '' },
              { label: '按姓名排序', value: 'name' },
              { label: '按创建时间倒序', value: 'created_desc' },
              { label: '按更新时间倒序', value: 'updated_desc' },
            ]"
            class="filter-select"
          />
          <n-button v-if="store.search || store.roleFilter || store.tagFilter || store.sort" size="small" @click="clearFilters">
            清空筛选
          </n-button>
        </div>

        <n-spin :show="store.loading">
          <div v-if="store.characters.length" class="char-grid">
            <n-grid :x-gap="12" :y-gap="12" cols="1 s:2 m:3" responsive="screen">
              <n-grid-item v-for="c in store.characters" :key="c.id">
                <CharacterCard
                  :character="c"
                  @open="openDetail(c.id)"
                  @edit="openEdit(c as unknown as Character)"
                  @remove="confirmRemove(c as unknown as Character)"
                />
              </n-grid-item>
            </n-grid>
          </div>

          <n-empty
            v-else
            class="empty-block"
            :description="store.search || store.roleFilter ? '没有符合条件的人物' : '还没有人物档案'"
            size="large"
          >
            <template #extra>
              <n-button v-if="store.search || store.roleFilter" size="small" @click="clearFilters">
                清空筛选
              </n-button>
              <n-button v-else size="small" type="primary" @click="openCreate">
                创建第一位人物
              </n-button>
            </template>
          </n-empty>
        </n-spin>

        <CharacterFormModal
          v-model:show="showForm"
          :character="editingCharacter"
          @saved="onDetailSaved"
        />

        <CharacterDetailModal
          v-model:show="showDetail"
          :character="store.currentCharacter"
          @edit="onDetailEdit"
          @remove="onDetailRemove"
          @state-changed="onStateChanged"
          @secrets-changed="onSecretsChanged"
        />
      </template>
    </n-spin>
  </div>
</template>

<style scoped>
.page { max-width: 1200px; margin: 0 auto; }

.page-header {
  display: flex; align-items: flex-end; justify-content: space-between;
  gap: 12px; flex-wrap: wrap; margin-bottom: 16px;
}
.header-left { display: flex; flex-direction: column; gap: 4px; }
.page-title { margin: 0; font-size: 22px; color: #fff; }
.page-sub { margin-top: 4px; font-size: 13px; color: rgba(255,255,255,0.45); }
.header-actions { display: flex; gap: 8px; flex-wrap: wrap; }

.toolbar {
  display: flex; gap: 12px; align-items: center; flex-wrap: wrap;
  margin-bottom: 16px;
}
.search-input { flex: 1; min-width: 200px; }
.filter-select { width: 180px; }

.char-grid { margin-top: 4px; }
.empty-block { padding: 40px 0; }
</style>
