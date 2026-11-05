<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  NButton,
  NCard,
  NDescriptions,
  NDescriptionsItem,
  NEmpty,
  NInput,
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
import { useCharacterStore } from '../stores/character'
import { useCharacterRelationStore } from '../stores/characterRelation'
import type { CharacterRelation } from '../api/characterRelation'
import { DEFAULT_CHAR_RELATION_STATUSES } from '../api/characterRelation'
import CharacterRelationModal from '../components/character/CharacterRelationModal.vue'
import CharacterRelationDetailModal from '../components/character/CharacterRelationDetailModal.vue'
import CharacterRelationGraph from '../components/character/CharacterRelationGraph.vue'
import CharacterDetailModal from '../components/character/CharacterDetailModal.vue'

const route = useRoute()
const router = useRouter()
const charStore = useCharacterStore()
const relStore = useCharacterRelationStore()
const dialog = useDialog()
const message = useMessage()

const novelTitle = ref('')
const pageError = ref('')
const loadingNovel = ref(false)

const showModal = ref(false)
const showDetail = ref(false)
const editingRelation = ref<CharacterRelation | null>(null)
const tab = ref<'list' | 'graph'>('list')

const currentNovelId = computed(() => String(route.params.id))
const statusOptions = DEFAULT_CHAR_RELATION_STATUSES

async function load(novelId: string) {
  loadingNovel.value = true
  pageError.value = ''
  try {
    const { data } = await getNovel(novelId)
    novelTitle.value = data.title
    if (charStore.novelId !== novelId) await charStore.load(novelId)
    await relStore.load(novelId)
  } catch (error) {
    pageError.value = extractError(error, '小说不存在')
  } finally {
    loadingNovel.value = false
  }
}

function clearFilters() {
  relStore.search = ''
  relStore.typeFilter = ''
  relStore.statusFilter = ''
}

function goNew() {
  editingRelation.value = null
  showModal.value = true
}

function openDetail(relation: CharacterRelation) {
  editingRelation.value = relation
  showDetail.value = true
}

function openEdit() {
  if (!editingRelation.value) return
  showDetail.value = false
  showModal.value = true
}

function onDetailReload() {
  if (!editingRelation.value) return
  editingRelation.value = relStore.getCachedRelation(editingRelation.value.id) ?? editingRelation.value
}

// 点击关系详情中的两端人物名，直接打开对方人物详情弹窗
const showCharDetail = ref(false)

async function openCharacterDetail(id: string) {
  if (!id) return
  try {
    await charStore.openCharacter(id)
    showCharDetail.value = true
  } catch (error) {
    message.error(extractError(error, '打开人物详情失败'))
  }
}

function confirmEnd(r: CharacterRelation) {
  dialog.warning({
    title: '结束关系',
    content: `确定结束「${r.source_name} → ${r.target_name}」的 ${r.relation_type} 关系吗？历史会保留。`,
    positiveText: '确认结束',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await relStore.end(r.id)
        message.success('关系已结束')
        if (editingRelation.value?.id === r.id) {
          editingRelation.value = relStore.getCachedRelation(r.id) || editingRelation.value
        }
      } catch (error) {
        message.error(relStore.error || extractError(error, '结束失败'))
      }
    },
  })
}

async function doRestore(r: CharacterRelation) {
  try {
    await relStore.restore(r.id)
    message.success('关系已恢复')
    if (editingRelation.value?.id === r.id) {
      editingRelation.value = relStore.getCachedRelation(r.id) || editingRelation.value
    }
  } catch (error) {
    message.error(relStore.error || extractError(error, '恢复失败'))
  }
}

onMounted(() => load(currentNovelId.value))
watch(
  () => route.params.id,
  (id) => {
    if (id) load(String(id))
  },
)

const typeOptions = computed(() => {
  const types = new Set<string>()
  for (const r of relStore.relations) if (r.relation_type) types.add(r.relation_type)
  return Array.from(types).map((t) => ({ label: t, value: t }))
})
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
              <h2 class="page-title">人物关系</h2>
              <div class="page-sub">
                《{{ novelTitle }}》 · {{ relStore.activeRelations.length }} 条有效 ·
                {{ relStore.endedRelations.length }} 条已结束
              </div>
            </div>
          </div>
          <div class="header-actions">
            <n-button size="small" type="primary" @click="goNew">+ 建立关系</n-button>
          </div>
        </div>

        <div v-if="!relStore.relations.length" class="empty-state">
          <n-empty
            description="还没有任何人物关系。建立关系后可以在下方列表查看，或切换到关系网络视图。"
          >
            <template #extra>
              <n-button size="small" type="primary" @click="goNew">建立第一条关系</n-button>
            </template>
          </n-empty>
        </div>

        <template v-else>
          <div class="toolbar">
            <n-input
              v-model:value="relStore.search"
              clearable
              placeholder="搜索人物姓名 / 关系类型 / 描述"
              class="search"
              @update:value="relStore.fetchRelations()"
            />
            <n-select
              v-model:value="relStore.typeFilter"
              clearable
              :options="typeOptions"
              placeholder="按类型筛选"
              class="filter"
              @update:value="relStore.fetchRelations()"
            />
            <n-select
              v-model:value="relStore.statusFilter"
              clearable
              :options="statusOptions"
              placeholder="按状态筛选"
              class="filter"
              @update:value="relStore.fetchRelations()"
            />
            <n-button
              v-if="relStore.search || relStore.typeFilter || relStore.statusFilter"
              size="small"
              @click="clearFilters"
            >
              清空筛选
            </n-button>
          </div>

          <NTabs v-model:value="tab" animated>
            <NTabPane name="list" tab="关系列表">
              <n-spin :show="relStore.loading">
                <div v-if="relStore.relations.length" class="rel-list">
                  <n-card
                    v-for="r in relStore.relations"
                    :key="r.id"
                    class="rel-row"
                    size="small"
                    hoverable
                    @click="openDetail(r)"
                  >
                    <div class="rel-main">
                      <div class="rel-flow">
                        <button class="char-btn" @click.stop="router.push(`/novels/${currentNovelId}/characters`)">
                          {{ r.source_name }}
                        </button>
                        <span class="arrow">→</span>
                        <span class="type-tag">{{ r.relation_type }}</span>
                        <span class="arrow">→</span>
                        <button class="char-btn" @click.stop="router.push(`/novels/${currentNovelId}/characters`)">
                          {{ r.target_name }}
                        </button>
                      </div>
                      <div class="rel-meta">
                        <n-tag
                          size="tiny"
                          round
                          :bordered="false"
                          :type="r.status === 'active' ? 'success' : 'warning'"
                        >
                          {{ r.status === 'active' ? '有效' : '已结束' }}
                        </n-tag>
                        <span v-if="r.strength !== null" class="strength">强度 {{ r.strength }}</span>
                        <span class="time">更新于 {{ r.updated_at.slice(0, 16).replace('T', ' ') }}</span>
                      </div>
                      <div v-if="r.description" class="rel-desc">{{ r.description }}</div>
                    </div>
                    <div class="rel-actions" @click.stop>
                      <n-button size="tiny" quaternary type="primary" @click="openDetail(r)">详情</n-button>
                      <n-button
                        v-if="r.status === 'active'"
                        size="tiny"
                        quaternary
                        type="warning"
                        @click="confirmEnd(r)"
                      >
                        结束
                      </n-button>
                      <n-button
                        v-else
                        size="tiny"
                        quaternary
                        @click="doRestore(r)"
                      >
                        恢复
                      </n-button>
                    </div>
                  </n-card>
                </div>
                <n-empty v-else description="没有符合条件的关系" />
              </n-spin>
            </NTabPane>

            <NTabPane name="graph" tab="关系网络">
              <CharacterRelationGraph
                :relations="relStore.relations"
                @open-edge="(id) => { const r = relStore.getCachedRelation(id); if (r) openDetail(r); }"
                @open-node="(id) => router.push(`/novels/${currentNovelId}/characters`)"
              />
              <div class="graph-hint">
                点击连线查看关系详情和历史事件；点击节点会跳到人物管理页（本阶段图谱暂不直接打开人物详情）。
              </div>
            </NTabPane>
          </NTabs>
        </template>

        <CharacterRelationModal
          v-model:show="showModal"
          :relation="editingRelation"
          @saved="relStore.fetchRelations()"
        />
        <CharacterRelationDetailModal
          v-model:show="showDetail"
          :relation="editingRelation"
          @edit="openEdit"
          @reload="onDetailReload"
          @open-source="openCharacterDetail"
          @open-target="openCharacterDetail"
        />
        <CharacterDetailModal
          v-model:show="showCharDetail"
          :character="charStore.currentCharacter"
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

.empty-state { padding: 40px 0; }

.toolbar {
  display: flex; gap: 10px; align-items: center; flex-wrap: wrap;
  margin-bottom: 12px;
}
.search { flex: 1; min-width: 220px; }
.filter { width: 160px; }

.rel-list { display: flex; flex-direction: column; gap: 10px; }

.rel-row {
  display: flex; align-items: center; justify-content: space-between;
  gap: 12px;
}
.rel-main { flex: 1; min-width: 0; }
.rel-flow {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  font-size: 15px; color: #fff;
}
.char-btn {
  background: transparent; border: none; padding: 2px 6px;
  color: #5b8ff9; cursor: pointer; font-size: 14px; border-radius: 4px;
}
.char-btn:hover { background: rgba(91,143,249,0.12); }
.arrow { color: rgba(255,255,255,0.4); }
.type-tag {
  background: rgba(91,143,249,0.18); color: #a5bfff;
  padding: 1px 8px; border-radius: 10px; font-size: 12px;
}

.rel-meta {
  display: flex; gap: 10px; align-items: center; flex-wrap: wrap;
  margin-top: 4px;
}
.strength { font-size: 12px; color: rgba(255,255,255,0.55); }
.time { font-size: 12px; color: rgba(255,255,255,0.4); }
.rel-desc {
  font-size: 13px; color: rgba(255,255,255,0.65);
  margin-top: 6px;
  white-space: pre-wrap; word-break: break-word;
}

.rel-actions { display: flex; gap: 2px; flex-shrink: 0; }

.graph-hint {
  margin-top: 12px; font-size: 12px; color: rgba(255,255,255,0.4);
  text-align: center;
}
</style>
