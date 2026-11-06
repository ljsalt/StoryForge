<script setup lang="ts">
import { computed, ref } from 'vue'
import { NCollapse, NCollapseItem, NEmpty, NTag } from 'naive-ui'
import {
  OVERALL_LABELS,
  OVERALL_TYPES,
  SEVERITY_LABELS,
  SEVERITY_TYPES,
  type ContinuityCheck,
  type Severity,
} from '../../api/continuity'

const props = defineProps<{ check: ContinuityCheck }>()

const severityFilter = ref<Severity | ''>('')
const issues = computed(() => props.check.report?.issues ?? [])
const filtered = computed(() =>
  severityFilter.value ? issues.value.filter((i) => i.severity === severityFilter.value) : issues.value,
)
const counts = computed(() => {
  const result: Record<string, number> = { info: 0, warning: 0, conflict: 0 }
  for (const issue of issues.value) result[issue.severity] = (result[issue.severity] || 0) + 1
  return result
})

const filterOptions: { label: string; value: Severity | '' }[] = [
  { label: '全部', value: '' },
  { label: '仅看矛盾', value: 'conflict' },
  { label: '仅看疑点', value: 'warning' },
  { label: '仅看提示', value: 'info' },
]
</script>

<template>
  <div class="report">
    <div v-if="check.status === 'failed'" class="failed">
      <n-tag type="error" :bordered="false">检查失败</n-tag>
      <span class="error-text">{{ check.error_message || check.error_code }}</span>
    </div>

    <template v-else-if="check.report">
      <div class="report-head">
        <n-tag v-if="check.overall_result" :bordered="false" :type="OVERALL_TYPES[check.overall_result]">
          {{ OVERALL_LABELS[check.overall_result] }}
        </n-tag>
        <span class="stat">矛盾 {{ counts.conflict }} · 疑点 {{ counts.warning }} · 提示 {{ counts.info }}</span>
      </div>

      <div v-if="issues.length" class="filters">
        <n-tag
          v-for="option in filterOptions"
          :key="option.value"
          size="small"
          class="filter-tag"
          :type="severityFilter === option.value ? 'primary' : 'default'"
          :bordered="severityFilter === option.value"
          @click="severityFilter = option.value"
        >
          {{ option.label }}
        </n-tag>
      </div>

      <n-empty v-if="!issues.length" description="未发现连续性问题" class="empty" />
      <n-empty v-else-if="!filtered.length" description="当前筛选下没有问题" class="empty" />

      <div v-for="(issue, index) in filtered" :key="index" class="issue">
        <div class="issue-head">
          <n-tag size="tiny" :bordered="false" :type="SEVERITY_TYPES[issue.severity]">
            {{ SEVERITY_LABELS[issue.severity] }}
          </n-tag>
          <n-tag size="tiny" :bordered="false">{{ issue.category || '其他' }}</n-tag>
          <span class="issue-desc">{{ issue.description }}</span>
        </div>
        <n-collapse>
          <n-collapse-item title="证据与依据" :name="index">
            <div class="detail">
              <div class="detail-row">
                <span class="label">章节原文证据</span>
                <p class="quote">{{ issue.evidence || '（模型未提供原文证据）' }}</p>
              </div>
              <div class="detail-row">
                <span class="label">冲突的历史依据</span>
                <p class="quote">{{ issue.reference || '（模型未提供依据）' }}</p>
              </div>
              <div class="detail-row">
                <span class="label">建议处理</span>
                <p class="quote">{{ issue.suggestion || '—' }}</p>
              </div>
            </div>
          </n-collapse-item>
        </n-collapse>
      </div>

      <div v-if="check.context_meta?.warnings?.length" class="context-meta">
        <div class="meta-title">上下文覆盖情况</div>
        <div v-for="(warning, i) in check.context_meta.warnings" :key="i" class="meta-line">
          {{ warning }}
        </div>
        <div class="meta-line">
          上下文约 {{ check.context_meta.estimated_tokens }} tokens
          （预算 {{ check.context_meta.token_budget }}）
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.report {
  border-top: 1px solid var(--sf-border, rgba(255, 255, 255, 0.08));
  padding-top: 12px;
}
.failed {
  display: flex;
  align-items: center;
  gap: 8px;
}
.error-text {
  font-size: 12px;
  color: var(--sf-text-secondary, #aaa);
}
.report-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}
.stat {
  font-size: 12px;
  color: var(--sf-text-tertiary, #888);
}
.filters {
  display: flex;
  gap: 6px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}
.filter-tag {
  cursor: pointer;
}
.empty {
  padding: 16px 0;
}
.issue {
  border: 1px solid var(--sf-border, rgba(255, 255, 255, 0.08));
  border-radius: 8px;
  padding: 8px 10px;
  margin-bottom: 8px;
}
.issue-head {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  flex-wrap: wrap;
}
.issue-desc {
  flex: 1;
  min-width: 180px;
  font-size: 13px;
  line-height: 1.5;
}
.detail {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.detail-row .label {
  font-size: 12px;
  color: var(--sf-text-tertiary, #888);
}
.quote {
  margin: 4px 0 0;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--sf-text-secondary, #bbb);
}
.context-meta {
  margin-top: 10px;
  padding: 8px 10px;
  border-radius: 8px;
  background: var(--sf-bg-soft, rgba(255, 255, 255, 0.04));
  font-size: 12px;
}
.meta-title {
  font-weight: 600;
  margin-bottom: 4px;
}
.meta-line {
  color: var(--sf-text-tertiary, #888);
  line-height: 1.6;
}
</style>
