<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { NButton, NCard, NEmpty, NSpin, NTag, useDialog, useMessage } from 'naive-ui'
import {
  BATCH_STATUS_LABELS,
  BATCH_STATUS_TYPES,
  acceptMemoryProposal,
  applyMemoryBatch,
  createMemoryBatch,
  getMemoryBatch,
  listMemoryBatches,
  rejectMemoryProposal,
  reviewMemoryBatch,
  updateMemoryProposal,
  type MemoryBatch,
  type MemoryProposal,
} from '../../api/continuity'
import { extractError } from '../../api/error'
import MemoryProposalCard from './MemoryProposalCard.vue'
import MemoryProposalEditModal from './MemoryProposalEditModal.vue'

const props = defineProps<{ novelId: string; chapterId: string }>()
const message = useMessage()
const dialog = useDialog()

const batches = ref<MemoryBatch[]>([])
const activeBatch = ref<MemoryBatch | null>(null)
const loading = ref(false)
const extracting = ref(false)
const acting = ref(false)
const applying = ref(false)

const editing = ref(false)
const editingProposal = ref<MemoryProposal | null>(null)

const proposals = computed(() => activeBatch.value?.proposals ?? [])
const pendingCount = computed(
  () => proposals.value.filter((p) => ['pending', 'conflict'].includes(p.status)).length,
)
const acceptedCount = computed(
  () => proposals.value.filter((p) => ['accepted', 'modified'].includes(p.status)).length,
)
const canApply = computed(
  () =>
    activeBatch.value &&
    ['approved', 'partially_approved'].includes(activeBatch.value.status) &&
    acceptedCount.value > 0,
)
const skipped = computed(() => activeBatch.value?.report?.skipped ?? [])

async function loadBatches(keepActive = true) {
  loading.value = true
  try {
    batches.value = (await listMemoryBatches(props.novelId, props.chapterId)).data
    if (!batches.value.length) {
      activeBatch.value = null
      return
    }
    const currentId = keepActive ? activeBatch.value?.id : null
    const target = batches.value.find((b) => b.id === currentId) ?? batches.value[0]
    activeBatch.value = (await getMemoryBatch(props.novelId, target.id)).data
  } catch (error) {
    message.error(extractError(error, '加载记忆提案失败'))
  } finally {
    loading.value = false
  }
}

async function selectBatch(batch: MemoryBatch) {
  if (activeBatch.value?.id === batch.id) return
  try {
    activeBatch.value = (await getMemoryBatch(props.novelId, batch.id)).data
  } catch (error) {
    message.error(extractError(error, '加载批次详情失败'))
  }
}

async function extract() {
  if (extracting.value) return
  extracting.value = true
  try {
    const batch = (
      await createMemoryBatch(props.novelId, props.chapterId, {
        check_id: undefined,
      })
    ).data
    message.success(`提取完成：${batch.proposals?.length ?? 0} 条提案待审核`)
    await loadBatches(false)
    activeBatch.value = batch
  } catch (error) {
    message.error(extractError(error, '剧情变化提取失败'))
  } finally {
    extracting.value = false
  }
}

async function refreshActive() {
  if (!activeBatch.value) return
  try {
    activeBatch.value = (await getMemoryBatch(props.novelId, activeBatch.value.id)).data
    const summary = batches.value.find((b) => b.id === activeBatch.value?.id)
    if (summary && activeBatch.value) {
      summary.status = activeBatch.value.status
      summary.reviewed_at = activeBatch.value.reviewed_at
      summary.applied_at = activeBatch.value.applied_at
    }
  } catch (error) {
    message.error(extractError(error, '刷新批次失败'))
  }
}

async function onAccept(proposal: MemoryProposal) {
  acting.value = true
  try {
    await acceptMemoryProposal(props.novelId, proposal.id)
    await refreshActive()
  } catch (error) {
    message.error(extractError(error, '接受提案失败'))
    await refreshActive() // 失败时保留服务端真实状态
  } finally {
    acting.value = false
  }
}

async function onReject(proposal: MemoryProposal) {
  acting.value = true
  try {
    await rejectMemoryProposal(props.novelId, proposal.id)
    await refreshActive()
  } catch (error) {
    message.error(extractError(error, '拒绝提案失败'))
    await refreshActive()
  } finally {
    acting.value = false
  }
}

async function onReset(proposal: MemoryProposal) {
  acting.value = true
  try {
    await reviewMemoryBatch(props.novelId, proposal.batch_id, [
      { id: proposal.id, action: 'reset' },
    ])
    await refreshActive()
  } catch (error) {
    message.error(extractError(error, '退回失败'))
    await refreshActive()
  } finally {
    acting.value = false
  }
}

function onEdit(proposal: MemoryProposal) {
  editingProposal.value = proposal
  editing.value = true
}

async function onSaveEdit(payload: { final_json: Record<string, unknown>; user_note: string }) {
  if (!editingProposal.value) return
  acting.value = true
  try {
    await updateMemoryProposal(props.novelId, editingProposal.value.id, payload)
    editing.value = false
    message.success('提案已修改并标记为已修改')
    await refreshActive()
  } catch (error) {
    message.error(extractError(error, '修改提案失败'))
  } finally {
    acting.value = false
  }
}

function acceptAll() {
  const items = proposals.value
    .filter((p) => ['pending', 'conflict'].includes(p.status) && p.apply_supported)
    .map((p) => ({ id: p.id, action: 'accept' as const }))
  if (!items.length) {
    message.info('没有可接受的提案')
    return
  }
  acting.value = true
  reviewMemoryBatch(props.novelId, activeBatch.value!.id, items)
    .then(async () => {
      message.success(`已批量接受 ${items.length} 条提案`)
      await refreshActive()
    })
    .catch(async (error) => {
      message.error(extractError(error, '批量审核失败'))
      await refreshActive()
    })
    .finally(() => {
      acting.value = false
    })
}

function apply() {
  if (!activeBatch.value || applying.value) return
  dialog.warning({
    title: '提交记忆更新',
    content: `将把 ${acceptedCount.value} 条已接受提案在单个事务中写入正式数据；任何一条失败都会整体回滚。确定提交吗？`,
    positiveText: '确认提交',
    negativeText: '取消',
    onPositiveClick: async () => {
      applying.value = true
      try {
        const result = (await applyMemoryBatch(props.novelId, activeBatch.value!.id)).data
        message.success(`已应用 ${result.applied.length} 条提案`)
        await refreshActive()
      } catch (error) {
        message.error(extractError(error, '提交失败，已整体回滚'))
        await refreshActive() // 冲突提案状态从数据库恢复
      } finally {
        applying.value = false
      }
    },
  })
}

function formatTime(value: string | null) {
  return value ? value.slice(0, 16).replace('T', ' ') : '—'
}

onMounted(() => loadBatches(false))
</script>

<template>
  <n-card size="small" class="panel">
    <div class="panel-head">
      <div class="panel-title">记忆更新提案</div>
      <div class="head-actions">
        <n-button size="small" :disabled="acting || !proposals.length" @click="acceptAll">
          全部接受
        </n-button>
        <n-button
          size="small"
          type="primary"
          :loading="extracting"
          :disabled="extracting"
          @click="extract"
        >
          {{ extracting ? '提取中…' : '提取剧情变化' }}
        </n-button>
      </div>
    </div>

    <n-spin :show="loading">
      <div v-if="!batches.length" class="empty">
        <n-empty description="还没有提取记录。点击「提取剧情变化」让 AI 把本章发生的剧情整理为更新提案。" />
      </div>
      <template v-else>
        <div class="batch-bar">
          <div
            v-for="batch in batches"
            :key="batch.id"
            class="batch-item"
            :class="{ active: activeBatch?.id === batch.id }"
            @click="selectBatch(batch)"
          >
            <n-tag size="tiny" :bordered="false" :type="BATCH_STATUS_TYPES[batch.status]">
              {{ BATCH_STATUS_LABELS[batch.status] }}
            </n-tag>
            <span class="time">{{ formatTime(batch.created_at) }}</span>
            <span class="count">{{ batch.proposal_count ?? 0 }} 条</span>
          </div>
        </div>

        <template v-if="activeBatch">
          <div class="batch-summary">
            <span>待审核 {{ pendingCount }} · 已接受 {{ acceptedCount }}</span>
            <n-button
              v-if="canApply"
              size="small"
              type="success"
              :loading="applying"
              :disabled="applying"
              @click="apply"
            >
              提交已接受提案
            </n-button>
            <n-tag v-if="activeBatch.status === 'applied'" size="small" type="success" :bordered="false">
              已于 {{ formatTime(activeBatch.applied_at) }} 应用
            </n-tag>
          </div>

          <div v-if="skipped.length" class="skipped">
            <div class="skipped-title">提取时跳过（去重 / 无变化）：</div>
            <div v-for="(item, i) in skipped" :key="i" class="skipped-line">{{ item }}</div>
          </div>

          <n-empty v-if="!proposals.length" description="本次提取没有产生提案" class="empty" />
          <MemoryProposalCard
            v-for="proposal in proposals"
            :key="proposal.id"
            :proposal="proposal"
            :busy="acting || applying"
            @accept="onAccept"
            @reject="onReject"
            @edit="onEdit"
            @reset="onReset"
          />
        </template>
      </template>
    </n-spin>

    <MemoryProposalEditModal
      v-model:show="editing"
      :proposal="editingProposal"
      :busy="acting"
      @save="onSaveEdit"
    />
  </n-card>
</template>

<style scoped>
.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
.panel-title {
  font-weight: 600;
  font-size: 15px;
}
.head-actions {
  display: flex;
  gap: 8px;
}
.empty {
  padding: 12px 0;
}
.batch-bar {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 12px;
  max-height: 140px;
  overflow-y: auto;
}
.batch-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
}
.batch-item:hover {
  background: var(--sf-bg-hover, rgba(255, 255, 255, 0.06));
}
.batch-item.active {
  background: var(--sf-bg-active, rgba(32, 128, 240, 0.15));
}
.time {
  color: var(--sf-text-tertiary, #888);
}
.count {
  margin-left: auto;
  color: var(--sf-text-tertiary, #888);
}
.batch-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
  font-size: 12px;
  color: var(--sf-text-secondary, #aaa);
  flex-wrap: wrap;
}
.skipped {
  margin-bottom: 10px;
  padding: 8px 10px;
  border-radius: 8px;
  background: var(--sf-bg-soft, rgba(255, 255, 255, 0.04));
  font-size: 12px;
}
.skipped-title {
  color: var(--sf-text-tertiary, #888);
  margin-bottom: 4px;
}
.skipped-line {
  color: var(--sf-text-tertiary, #888);
  line-height: 1.6;
}
</style>
