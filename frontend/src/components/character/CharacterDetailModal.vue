<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  NButton,
  NCard,
  NDescriptions,
  NDescriptionsItem,
  NEmpty,
  NGrid,
  NGridItem,
  NSpin,
  NTabPane,
  NTabs,
  NTag,
  NText,
  useDialog,
  useMessage,
} from 'naive-ui'
import { useRouter } from 'vue-router'
import { extractError } from '../../api/error'
import type { Character, CharacterSecret } from '../../api/character'
import {
  listCharacterPlotEvents,
  PLOT_IMPORTANCE_LABELS,
  PLOT_IMPORTANCE_TYPES,
  type PlotEvent,
} from '../../api/plotEvent'
import { DEFAULT_LIFE_STATUSES, DEFAULT_REVEAL_STATUSES, DEFAULT_SECRECY_LEVELS } from '../../api/character'
import type { CharacterRelation } from '../../api/characterRelation'
import { useCharacterStore } from '../../stores/character'
import { useCharacterRelationStore } from '../../stores/characterRelation'
import CharacterStateModal from './CharacterStateModal.vue'
import CharacterSecretModal from './CharacterSecretModal.vue'
import CharacterRelationModal from './CharacterRelationModal.vue'
import CharacterRelationDetailModal from './CharacterRelationDetailModal.vue'
import PlotEventDetailModal from '../plot/PlotEventDetailModal.vue'

const props = defineProps<{ show: boolean; character: Character | null }>()
const emit = defineEmits<{
  'update:show': [value: boolean]
  edit: []
  remove: []
  'state-changed': []
  'secrets-changed': []
}>()

const store = useCharacterStore()
const relStore = useCharacterRelationStore()
const dialog = useDialog()
const message = useMessage()

const loadingSecrets = ref(false)
const secrets = ref<CharacterSecret[]>([])
const showStateModal = ref(false)
const showSecretModal = ref(false)
const editingSecret = ref<CharacterSecret | null>(null)
const expandedSecrets = ref<Record<string, boolean>>({})
const loadingRelations = ref(false)
const router = useRouter()
const plotEvents = ref<PlotEvent[]>([])
const loadingPlotEvents = ref(false)
const showPlotEventDetail = ref(false)
const viewingPlotEvent = ref<PlotEvent | null>(null)
const showRelModal = ref(false)
const showRelDetail = ref(false)
const editingRel = ref<import('../../api/characterRelation').CharacterRelation | null>(null)
const viewingRel = ref<import('../../api/characterRelation').CharacterRelation | null>(null)

const lifeLabelMap: Record<string, string> = {
  alive: '存活', dead: '已陨落', unknown: '状态不明',
}
const secrecyLabelMap = Object.fromEntries(DEFAULT_SECRECY_LEVELS.map((i) => [i.value, i.label]))
const revealLabelMap = Object.fromEntries(DEFAULT_REVEAL_STATUSES.map((i) => [i.value, i.label]))
const lifeTypeMap: Record<string, 'success' | 'error' | 'warning'> = {
  alive: 'success', dead: 'error', unknown: 'warning',
}

async function loadSecrets() {
  if (!props.character) return
  loadingSecrets.value = true
  try {
    await store.fetchSecrets(props.character.id)
    secrets.value = store.secrets
  } catch (error) {
    message.error(extractError(error, '加载秘密失败'))
  } finally {
    loadingSecrets.value = false
  }
}

async function loadPlotEvents() {
  if (!props.character) return
  loadingPlotEvents.value = true
  try {
    const { data } = await listCharacterPlotEvents(props.character.novel_id, props.character.id)
    plotEvents.value = data
  } catch (error) {
    message.error(extractError(error, '加载人物剧情事件失败'))
  } finally {
    loadingPlotEvents.value = false
  }
}

function roleIn(event: PlotEvent): string {
  return (
    event.participants.find((p) => p.character_id === props.character?.id)?.participant_role || ''
  )
}

function openPlotEvent(event: PlotEvent) {
  viewingPlotEvent.value = event
  showPlotEventDetail.value = true
}

function openEventChapter(chapterId: string) {
  if (!props.character) return
  router.push({ path: `/novels/${props.character.novel_id}/chapters`, query: { open: chapterId } })
}

async function loadRelations() {
  if (!props.character) return
  loadingRelations.value = true
  try {
    await relStore.fetchCharacterRelations(props.character.id)
  } catch (error) {
    message.error(extractError(error, '加载人物关系失败'))
  } finally {
    loadingRelations.value = false
  }
}

watch(
  () => [props.show, props.character?.id] as const,
  ([show]) => {
    if (show && props.character) {
      expandedSecrets.value = {}
      loadSecrets()
      loadRelations()
      loadPlotEvents()
    }
  },
)

function toggleSecret(id: string) {
  expandedSecrets.value[id] = !expandedSecrets.value[id]
}

function openNewSecret() {
  editingSecret.value = null
  showSecretModal.value = true
}

function openEditSecret(secret: CharacterSecret) {
  editingSecret.value = secret
  showSecretModal.value = true
}

function confirmRemoveSecret(secret: CharacterSecret) {
  if (!props.character) return
  dialog.warning({
    title: '删除秘密',
    content: `确定删除秘密《${secret.title}》吗？`,
    positiveText: '确认删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      if (!props.character) return
      try {
        await store.removeSecret(props.character.id, secret.id)
        secrets.value = store.secrets
        emit('secrets-changed')
        message.success('秘密已删除')
      } catch (error) {
        message.error(extractError(error, '删除秘密失败'))
      }
    },
  })
}

function onSecretSaved() {
  secrets.value = store.secrets
  emit('secrets-changed')
}

// 人物关系辅助
const outgoingRelations = computed(() => relStore.characterRelations?.outgoing ?? [])
const incomingRelations = computed(() => relStore.characterRelations?.incoming ?? [])

function openNewRelation() {
  editingRel.value = null
  showRelModal.value = true
}

function openEditRelation(rel: CharacterRelation) {
  editingRel.value = rel
  showRelModal.value = true
  showRelDetail.value = false
}

function openRelationDetail(rel: CharacterRelation) {
  viewingRel.value = rel
  showRelDetail.value = true
}

async function onRelationSaved() {
  showRelModal.value = false
  editingRel.value = null
  await loadRelations()
}

async function onRelationDetailReload() {
  if (viewingRel.value) {
    viewingRel.value = relStore.getCachedRelation(viewingRel.value.id) ?? viewingRel.value
    await loadRelations()
  }
}

function onRelationDetailEdit() {
  if (viewingRel.value) openEditRelation(viewingRel.value)
}

// 点击关系详情中的对方人物，把当前详情弹窗切换到对方人物
// （父组件把 store.currentCharacter 作为 prop 传入，store 更新后本组件自动刷新）
async function openRelatedCharacter(id: string) {
  if (!id || id === props.character?.id) return
  try {
    await store.openCharacter(id)
  } catch (error) {
    message.error(extractError(error, '打开人物详情失败'))
  }
}
</script>

<template>
  <n-modal
    :show="show"
    preset="card"
    title="人物详情"
    :style="{ width: '820px', maxWidth: 'calc(100vw - 24px)' }"
    :bordered="false"
    @update:show="emit('update:show', $event)"
  >
    <template v-if="character">
      <div class="header">
        <div class="avatar" :style="{ background: character.avatar_color || '#3b5bdb' }">
          {{ character.name.charAt(0) }}
        </div>
        <div class="header-info">
          <div class="name-row">
            <h3 class="char-name">{{ character.name }}</h3>
            <n-tag v-if="character.role" size="small" round :bordered="false" type="info">
              {{ character.role }}
            </n-tag>
            <n-tag
              size="small" round :bordered="false"
              :type="lifeTypeMap[character.state?.life_status || 'alive'] ?? 'default'"
            >
              {{ lifeLabelMap[character.state?.life_status || 'alive'] }}
            </n-tag>
          </div>
          <div v-if="character.aliases.length" class="aliases">别名：{{ character.aliases.join('、') }}</div>
        </div>
        <div class="header-actions">
          <n-button size="small" @click="$emit('edit')">编辑档案</n-button>
          <n-button size="small" type="error" @click="$emit('remove')">删除</n-button>
        </div>
      </div>

      <n-tabs animated>
        <n-tab-pane name="archive" tab="基础档案">
          <n-descriptions :column="2" label-placement="left" bordered size="small">
            <n-descriptions-item label="性别">{{ character.gender || '-' }}</n-descriptions-item>
            <n-descriptions-item label="年龄">{{ character.age || '-' }}</n-descriptions-item>
            <n-descriptions-item label="种族">{{ character.race || '-' }}</n-descriptions-item>
            <n-descriptions-item label="身份">{{ character.identity || '-' }}</n-descriptions-item>
            <n-descriptions-item label="所属势力" :span="2">{{ character.affiliation || '-' }}</n-descriptions-item>
            <n-descriptions-item label="修为">{{ character.cultivation || '-' }}</n-descriptions-item>
            <n-descriptions-item label="排序">{{ character.sort_order }}</n-descriptions-item>
          </n-descriptions>
          <div v-if="character.tags.length" class="section">
            <div class="section-title">标签</div>
            <div class="tag-row">
              <n-tag v-for="tag in character.tags" :key="tag" size="small" round :bordered="false">{{ tag }}</n-tag>
            </div>
          </div>
          <div v-if="Object.keys(character.attributes).length" class="section">
            <div class="section-title">自定义属性</div>
            <n-descriptions :column="2" label-placement="left" bordered size="small">
              <n-descriptions-item
                v-for="(val, key) in character.attributes"
                :key="key"
                :label="key"
              >{{ String(val) }}</n-descriptions-item>
            </n-descriptions>
          </div>
        </n-tab-pane>

        <n-tab-pane name="appearance" tab="外貌与性格">
          <div class="block">
            <div class="section-title">外貌描述</div>
            <p class="text-block">{{ character.appearance || '暂无记录' }}</p>
          </div>
          <div class="block">
            <div class="section-title">性格描述</div>
            <p class="text-block">{{ character.personality || '暂无记录' }}</p>
          </div>
        </n-tab-pane>

        <n-tab-pane name="background" tab="背景与能力">
          <div class="block">
            <div class="section-title">人物背景</div>
            <p class="text-block">{{ character.background || '暂无记录' }}</p>
          </div>
          <div class="block">
            <div class="section-title">能力与天赋</div>
            <p class="text-block">{{ character.abilities || '暂无记录' }}</p>
          </div>
        </n-tab-pane>

        <n-tab-pane name="state" tab="当前状态">
          <template v-if="character.state">
            <div class="section-head">
              <div class="hint">以下为人物在当前剧情时间点的即时状态，可随时更新。</div>
              <n-button size="small" type="primary" ghost @click="showStateModal = true">
                编辑当前状态
              </n-button>
            </div>
            <n-descriptions :column="2" label-placement="left" bordered size="small">
              <n-descriptions-item label="生死状态">
                {{ lifeLabelMap[character.state.life_status] || character.state.life_status }}
              </n-descriptions-item>
              <n-descriptions-item label="当前位置">{{ character.state.current_location || '-' }}</n-descriptions-item>
              <n-descriptions-item label="当前阵营">{{ character.state.current_faction || '-' }}</n-descriptions-item>
              <n-descriptions-item label="当前修为">{{ character.state.current_cultivation || '-' }}</n-descriptions-item>
              <n-descriptions-item label="伤势与健康">{{ character.state.health_status || '-' }}</n-descriptions-item>
              <n-descriptions-item label="情绪状态">{{ character.state.emotional_state || '-' }}</n-descriptions-item>
              <n-descriptions-item label="当前目标" :span="2">{{ character.state.current_goal || '-' }}</n-descriptions-item>
              <n-descriptions-item label="其他状态" :span="2">{{ character.state.current_status || '-' }}</n-descriptions-item>
            </n-descriptions>
            <div v-if="Object.keys(character.state.attributes).length" class="section">
              <div class="section-title">状态自定义属性</div>
              <n-descriptions :column="2" label-placement="left" bordered size="small">
                <n-descriptions-item
                  v-for="(val, key) in character.state.attributes"
                  :key="key"
                  :label="key"
                >{{ String(val) }}</n-descriptions-item>
              </n-descriptions>
            </div>
          </template>
          <n-empty v-else description="暂无当前状态" />
        </n-tab-pane>

        <n-tab-pane name="secrets" tab="人物秘密">
          <div class="section-head">
            <div class="hint">秘密信息独立管理，默认折叠显示内容，避免在卡片或列表中出现。</div>
            <n-button size="small" type="primary" ghost @click="openNewSecret">
              + 新建秘密
            </n-button>
          </div>
          <n-spin :show="loadingSecrets">
            <n-empty v-if="!secrets.length" description="还没有秘密记录" class="empty-mini">
              <template #extra>
                <n-button size="small" type="primary" @click="openNewSecret">创建第一条秘密</n-button>
              </template>
            </n-empty>
            <div v-else class="secret-list">
              <div v-for="secret in secrets" :key="secret.id" class="secret-item">
                <div class="secret-head">
                  <div class="secret-title" @click="toggleSecret(secret.id)">
                    {{ expandedSecrets[secret.id] ? '▾' : '▸' }} {{ secret.title }}
                  </div>
                  <div class="secret-tags">
                    <n-tag size="tiny" round :bordered="false" type="warning">
                      {{ secrecyLabelMap[secret.secrecy_level] || secret.secrecy_level }}
                    </n-tag>
                    <n-tag size="tiny" round :bordered="false">
                      {{ revealLabelMap[secret.reveal_status] || secret.reveal_status }}
                    </n-tag>
                  </div>
                  <div class="secret-actions">
                    <n-button size="tiny" quaternary @click="openEditSecret(secret)">编辑</n-button>
                    <n-button size="tiny" quaternary type="error" @click="confirmRemoveSecret(secret)">删除</n-button>
                  </div>
                </div>
                <div v-if="expandedSecrets[secret.id]" class="secret-body">
                  <p class="secret-content">{{ secret.content || '（无内容）' }}</p>
                  <p v-if="secret.notes" class="secret-notes">备注：{{ secret.notes }}</p>
                </div>
              </div>
            </div>
          </n-spin>
        </n-tab-pane>

        <n-tab-pane name="plot-events" tab="剧情事件">
          <div class="section-head">
            <div class="hint">
              该人物参与的全部剧情事件（故事事实）。点击事件可查看详情、关联章节与其他参与者。
            </div>
          </div>
          <n-spin :show="loadingPlotEvents">
            <n-empty
              v-if="!plotEvents.length"
              description="该人物还没有参与剧情事件"
              class="empty-mini"
            />
            <div v-else class="plot-event-list">
              <div
                v-for="event in plotEvents"
                :key="event.id"
                class="plot-event-item"
                @click="openPlotEvent(event)"
              >
                <div class="plot-event-head">
                  <span class="plot-event-title">{{ event.title }}</span>
                  <n-tag
                    size="tiny"
                    round
                    :bordered="false"
                    :type="PLOT_IMPORTANCE_TYPES[event.importance]"
                  >
                    {{ PLOT_IMPORTANCE_LABELS[event.importance] }}
                  </n-tag>
                  <n-tag v-if="roleIn(event)" size="tiny" round :bordered="false" type="info">
                    {{ roleIn(event) }}
                  </n-tag>
                </div>
                <div class="plot-event-meta">
                  <span v-if="event.chapter_title">
                    第 {{ event.chapter_number }} 章 · {{ event.chapter_title }}
                  </span>
                  <span v-else>未关联章节</span>
                  <span v-if="event.story_time">故事时间：{{ event.story_time }}</span>
                </div>
              </div>
            </div>
          </n-spin>
        </n-tab-pane>

        <n-tab-pane name="relations" tab="人物关系">
          <div class="section-head">
            <div class="hint">
              展示 {{ character?.name }} 作为发起方和目标方的全部当前关系，点击行可查看关系详情与演变历史。
            </div>
            <n-button size="small" type="primary" ghost @click="openNewRelation">
              + 新建关系
            </n-button>
          </div>
          <n-spin :show="loadingRelations">
            <n-empty
              v-if="!outgoingRelations.length && !incomingRelations.length"
              description="还没有与该人物相关的关系"
              class="empty-mini"
            />
            <template v-else>
              <div v-if="outgoingRelations.length" class="section-title-sm">
                → 主动发起的关系（{{ outgoingRelations.length }}）
              </div>
              <div class="rel-list">
                <div
                  v-for="item in outgoingRelations"
                  :key="item.relation.id"
                  class="rel-item"
                  :class="{ ended: item.relation.status === 'ended' }"
                  @click="openRelationDetail(item.relation)"
                >
                  <span class="rel-dir">→</span>
                  <span class="rel-name">{{ item.relation.target_name }}</span>
                  <n-tag size="tiny" round :bordered="false">{{ item.relation.relation_type }}</n-tag>
                  <n-tag
                    size="tiny"
                    round
                    :bordered="false"
                    :type="item.relation.status === 'ended' ? 'warning' : 'success'"
                  >{{ item.relation.status === 'ended' ? '已结束' : '有效' }}</n-tag>
                </div>
              </div>

              <div v-if="incomingRelations.length" class="section-title-sm">
                ← 指向该人物的关系（{{ incomingRelations.length }}）
              </div>
              <div class="rel-list">
                <div
                  v-for="item in incomingRelations"
                  :key="item.relation.id"
                  class="rel-item"
                  :class="{ ended: item.relation.status === 'ended' }"
                  @click="openRelationDetail(item.relation)"
                >
                  <span class="rel-dir">←</span>
                  <span class="rel-name">{{ item.relation.source_name }}</span>
                  <n-tag size="tiny" round :bordered="false">{{ item.relation.relation_type }}</n-tag>
                  <n-tag
                    size="tiny"
                    round
                    :bordered="false"
                    :type="item.relation.status === 'ended' ? 'warning' : 'success'"
                  >{{ item.relation.status === 'ended' ? '已结束' : '有效' }}</n-tag>
                </div>
              </div>
            </template>
          </n-spin>
        </n-tab-pane>
      </n-tabs>
    </template>
    <n-empty v-else description="暂无可显示的人物" />

    <CharacterStateModal
      v-model:show="showStateModal"
      :character-id="character?.id || ''"
      :state="character?.state"
      @saved="$emit('state-changed')"
    />
    <CharacterSecretModal
      v-model:show="showSecretModal"
      :character-id="character?.id || ''"
      :secret="editingSecret"
      @saved="onSecretSaved"
    />
    <CharacterRelationModal
      v-model:show="showRelModal"
      :relation="editingRel"
      :default-source-id="character?.id"
      @saved="onRelationSaved"
    />
    <PlotEventDetailModal
      v-model:show="showPlotEventDetail"
      :novel-id="character?.novel_id || ''"
      :event="viewingPlotEvent"
      @open-chapter="openEventChapter"
    />
    <CharacterRelationDetailModal
      v-model:show="showRelDetail"
      :relation="viewingRel"
      @edit="onRelationDetailEdit"
      @reload="onRelationDetailReload"
      @open-source="openRelatedCharacter"
      @open-target="openRelatedCharacter"
    />
  </n-modal>
</template>

<style scoped>
.header {
  display: flex;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 16px;
}
.avatar {
  width: 56px; height: 56px; border-radius: 12px;
  color: #fff; font-size: 26px; font-weight: 600;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.header-info { flex: 1; min-width: 0; }
.name-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.char-name { margin: 0; font-size: 20px; color: #fff; }
.aliases { margin-top: 2px; font-size: 12px; color: rgba(255,255,255,0.5); }
.header-actions { display: flex; gap: 8px; flex-shrink: 0; }

.section { margin-top: 16px; }
.section-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; margin-bottom: 10px; }
.section-title { font-size: 14px; font-weight: 600; color: #fff; margin-bottom: 8px; }
.hint { font-size: 12px; color: rgba(255,255,255,0.45); line-height: 1.6; }

.tag-row { display: flex; flex-wrap: wrap; gap: 6px; }
.block { margin-top: 16px; }
.text-block { white-space: pre-wrap; line-height: 1.8; color: rgba(255,255,255,0.75); }

.empty-mini { padding: 16px 0; }

.secret-list { display: flex; flex-direction: column; gap: 12px; margin-top: 8px; }
.secret-item {
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 8px;
  padding: 12px;
  background: rgba(255,255,255,0.03);
}
.secret-head { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.secret-title { font-weight: 600; color: #fff; cursor: pointer; flex: 1; min-width: 0; }
.secret-tags { display: flex; gap: 6px; }
.secret-actions { display: flex; gap: 2px; }
.secret-body { margin-top: 10px; padding-top: 10px; border-top: 1px dashed rgba(255,255,255,0.1); }
.secret-content { white-space: pre-wrap; color: rgba(255,255,255,0.75); margin: 0; }
.secret-notes { margin-top: 8px; font-size: 12px; color: rgba(255,255,255,0.5); }

.section-title-sm { margin: 14px 0 6px; font-size: 13px; font-weight: 600; color: rgba(255,255,255,0.8); }
.rel-list { display: flex; flex-direction: column; gap: 6px; margin-bottom: 4px; }
.rel-item {
  display: flex; gap: 8px; align-items: center;
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 6px; padding: 8px 12px;
  background: rgba(255,255,255,0.03);
  cursor: pointer; transition: background 0.15s;
}
.rel-item:hover { background: rgba(255,255,255,0.06); }
.rel-item.ended { opacity: 0.6; }
.rel-dir { width: 18px; text-align: center; color: rgba(255,255,255,0.5); font-weight: 600; }
.rel-name { flex: 1; font-weight: 500; color: #fff; }
.plot-event-list { display: flex; flex-direction: column; gap: 6px; }
.plot-event-item {
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 6px; padding: 8px 12px;
  background: rgba(255,255,255,0.03);
  cursor: pointer; transition: background 0.15s;
}
.plot-event-item:hover { background: rgba(255,255,255,0.06); }
.plot-event-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.plot-event-title { font-weight: 500; color: #fff; }
.plot-event-meta {
  display: flex; gap: 12px; flex-wrap: wrap;
  margin-top: 4px; font-size: 12px; color: rgba(255,255,255,0.45);
}
</style>
