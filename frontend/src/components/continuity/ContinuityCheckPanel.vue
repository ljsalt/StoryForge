<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { NButton, NCard, NEmpty, NSpin, NTag, useMessage } from 'naive-ui'
import {
  CHECK_STATUS_LABELS,
  OVERALL_LABELS,
  OVERALL_TYPES,
  createContinuityCheck,
  listContinuityChecks,
  type ContinuityCheck,
} from '../../api/continuity'
import { extractError } from '../../api/error'
import ContinuityReport from './ContinuityReport.vue'

const props = defineProps<{ novelId: string; chapterId: string }>()
const message = useMessage()

const checks = ref<ContinuityCheck[]>([])
const activeCheck = ref<ContinuityCheck | null>(null)
const loading = ref(false)
const running = ref(false)

async function load() {
  loading.value = true
  try {
    checks.value = (await listContinuityChecks(props.novelId, props.chapterId)).data
    if (checks.value.length && !activeCheck.value) {
      activeCheck.value = checks.value[0]
    }
  } catch (error) {
    message.error(extractError(error, '加载检查记录失败'))
  } finally {
    loading.value = false
  }
}

async function runCheck() {
  if (running.value) return // 防止重复点击
  running.value = true
  try {
    const check = (await createContinuityCheck(props.novelId, props.chapterId)).data
    message.success(
      check.overall_result === 'pass' ? '检查完成：未发现冲突' : '检查完成，请查看报告',
    )
    await load()
    activeCheck.value = check
  } catch (error) {
    message.error(extractError(error, '连续性检查失败'))
    await load() // 失败记录也要展示在历史里
  } finally {
    running.value = false
  }
}

function formatTime(value: string | null) {
  return value ? value.slice(0, 16).replace('T', ' ') : '—'
}

onMounted(load)
</script>

<template>
  <n-card size="small" class="panel">
    <div class="panel-head">
      <div class="panel-title">连续性检查</div>
      <n-button size="small" type="primary" :loading="running" :disabled="running" @click="runCheck">
        {{ running ? '检查中…' : '启动检查' }}
      </n-button>
    </div>

    <n-spin :show="loading">
      <div v-if="!checks.length" class="empty">
        <n-empty description="还没有检查记录。点击「启动检查」让 AI 核对本章与既有设定的一致性。" />
      </div>
      <template v-else>
        <div class="history">
          <div
            v-for="check in checks"
            :key="check.id"
            class="history-item"
            :class="{ active: activeCheck?.id === check.id }"
            @click="activeCheck = check"
          >
            <n-tag size="tiny" :bordered="false" :type="check.status === 'failed' ? 'error' : 'default'">
              {{ CHECK_STATUS_LABELS[check.status] }}
            </n-tag>
            <n-tag
              v-if="check.overall_result"
              size="tiny"
              :bordered="false"
              :type="OVERALL_TYPES[check.overall_result]"
            >
              {{ OVERALL_LABELS[check.overall_result] }}
            </n-tag>
            <span class="time">{{ formatTime(check.created_at) }}</span>
          </div>
        </div>
        <ContinuityReport v-if="activeCheck" :check="activeCheck" />
      </template>
    </n-spin>
  </n-card>
</template>

<style scoped>
.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 12px;
}
.panel-title {
  font-weight: 600;
  font-size: 15px;
}
.empty {
  padding: 12px 0;
}
.history {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 12px;
  max-height: 180px;
  overflow-y: auto;
}
.history-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 8px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
}
.history-item:hover {
  background: var(--sf-bg-hover, rgba(255, 255, 255, 0.06));
}
.history-item.active {
  background: var(--sf-bg-active, rgba(32, 128, 240, 0.15));
}
.time {
  color: var(--sf-text-tertiary, #888);
}
</style>
