<script setup lang="ts">
import { computed, ref } from 'vue'
import { NButton, NCollapse, NCollapseItem, NTag } from 'naive-ui'
import {
  OPERATION_LABELS,
  PROPOSAL_STATUS_LABELS,
  PROPOSAL_STATUS_TYPES,
  PROPOSAL_TYPE_LABELS,
  type MemoryProposal,
} from '../../api/continuity'

const props = defineProps<{ proposal: MemoryProposal; busy: boolean }>()
const emit = defineEmits<{
  (e: 'accept', proposal: MemoryProposal): void
  (e: 'reject', proposal: MemoryProposal): void
  (e: 'edit', proposal: MemoryProposal): void
  (e: 'reset', proposal: MemoryProposal): void
}>()

const showDiff = ref(false)

const actionable = computed(() =>
  ['pending', 'conflict'].includes(props.proposal.status) && props.proposal.apply_supported,
)
const reviewed = computed(() => ['accepted', 'modified', 'rejected'].includes(props.proposal.status))

/** 目标对象当前数据与 before_json 是否仍一致（前端提示用，后端提交时仍会强校验） */
const stale = computed(() => {
  const before = props.proposal.before || {}
  const keys = Object.keys(before)
  if (!keys.length || !props.proposal.current) return false
  const current = props.proposal.current as Record<string, any>
  if (props.proposal.target_type === 'character_state') {
    const state = current?.state || {}
    return keys.some((k) => JSON.stringify(state[k] ?? null) !== JSON.stringify(before[k]))
  }
  if (props.proposal.target_type === 'chapter') {
    return JSON.stringify(current?.summary ?? null) !== JSON.stringify(before.summary)
  }
  if (props.proposal.target_type === 'character_relation') {
    return keys.some((k) => JSON.stringify(current?.[k] ?? null) !== JSON.stringify(before[k]))
  }
  return false
})

function preview(data: Record<string, any> | null): string {
  if (!data) return '—'
  const text = JSON.stringify(data, null, 2)
  return text.length > 600 ? `${text.slice(0, 600)}…` : text
}

const effective = computed(() => props.proposal.final || props.proposal.proposed)
</script>

<template>
  <div class="card" :class="{ dimmed: proposal.status === 'rejected' }">
    <div class="card-head">
      <n-tag size="tiny" :bordered="false" type="info">
        {{ PROPOSAL_TYPE_LABELS[proposal.proposal_type] || proposal.proposal_type }}
      </n-tag>
      <n-tag size="tiny" :bordered="false">{{ OPERATION_LABELS[proposal.operation] || proposal.operation }}</n-tag>
      <n-tag size="tiny" :bordered="false" :type="PROPOSAL_STATUS_TYPES[proposal.status]">
        {{ PROPOSAL_STATUS_LABELS[proposal.status] }}
      </n-tag>
      <n-tag v-if="stale && proposal.status !== 'applied'" size="tiny" type="warning">
        目标已变化
      </n-tag>
      <span class="confidence">置信度 {{ Math.round(proposal.confidence * 100) }}%</span>
    </div>

    <div v-if="proposal.status === 'conflict'" class="conflict-tip">
      目标无法解析或已不存在，请拒绝或暂时保留。
    </div>
    <div v-if="!proposal.apply_supported" class="conflict-tip">
      世界观条目本阶段仅作参考，不支持自动应用，请手动到世界观管理中处理。
    </div>

    <div class="reason">{{ proposal.reason || '（无提取理由）' }}</div>

    <n-collapse>
      <n-collapse-item title="正文证据 / 数据对比" name="detail">
        <div class="detail-block">
          <span class="label">原文证据</span>
          <p class="quote">{{ proposal.source_excerpt || '（未提供）' }}</p>
        </div>
        <div class="detail-block" @click="showDiff = true">
          <span class="label">{{ proposal.final ? '最终提交内容（用户已修改）' : 'AI 建议内容' }}</span>
          <pre class="json">{{ preview(effective) }}</pre>
        </div>
        <div v-if="Object.keys(proposal.before || {}).length" class="detail-block">
          <span class="label">修改前数据（提交时将校验是否过期）</span>
          <pre class="json">{{ preview(proposal.before) }}</pre>
        </div>
        <div v-if="proposal.final" class="detail-block">
          <span class="label">AI 原始建议（已被用户修改覆盖）</span>
          <pre class="json">{{ preview(proposal.proposed) }}</pre>
        </div>
        <div v-if="proposal.user_note" class="detail-block">
          <span class="label">审核备注</span>
          <p class="quote">{{ proposal.user_note }}</p>
        </div>
      </n-collapse-item>
    </n-collapse>

    <div class="card-actions">
      <template v-if="actionable">
        <n-button size="tiny" type="primary" :disabled="busy" @click="emit('accept', proposal)">
          接受
        </n-button>
        <n-button size="tiny" :disabled="busy" @click="emit('edit', proposal)">修改后接受</n-button>
        <n-button size="tiny" type="error" quaternary :disabled="busy" @click="emit('reject', proposal)">
          拒绝
        </n-button>
      </template>
      <n-button
        v-else-if="reviewed"
        size="tiny"
        quaternary
        :disabled="busy"
        @click="emit('reset', proposal)"
      >
        退回待审核
      </n-button>
      <span v-if="proposal.status === 'applied'" class="applied-hint">
        已应用于正式数据 {{ proposal.applied_at?.slice(0, 16).replace('T', ' ') }}
      </span>
    </div>
  </div>
</template>

<style scoped>
.card {
  border: 1px solid var(--sf-border, rgba(255, 255, 255, 0.08));
  border-radius: 8px;
  padding: 10px 12px;
  margin-bottom: 10px;
}
.card.dimmed {
  opacity: 0.55;
}
.card-head {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.confidence {
  margin-left: auto;
  font-size: 11px;
  color: var(--sf-text-tertiary, #888);
}
.conflict-tip {
  margin-top: 6px;
  font-size: 12px;
  color: var(--sf-warning, #e0a040);
}
.reason {
  margin-top: 6px;
  font-size: 13px;
  line-height: 1.5;
}
.detail-block {
  margin-bottom: 8px;
}
.label {
  font-size: 12px;
  color: var(--sf-text-tertiary, #888);
}
.quote {
  margin: 4px 0 0;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}
.json {
  margin: 4px 0 0;
  font-size: 11px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 220px;
  overflow-y: auto;
  padding: 6px 8px;
  border-radius: 6px;
  background: var(--sf-bg-soft, rgba(255, 255, 255, 0.04));
}
.card-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
  flex-wrap: wrap;
}
.applied-hint {
  font-size: 12px;
  color: var(--sf-text-tertiary, #888);
}
</style>
