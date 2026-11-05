<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  NAlert,
  NButton,
  NCollapse,
  NCollapseItem,
  NForm,
  NFormItem,
  NGrid,
  NGridItem,
  NInput,
  NInputNumber,
  NSelect,
  NSlider,
  NSpin,
  NSwitch,
  NTag,
  useMessage,
} from 'naive-ui'
import { extractError } from '../../api/error'
import {
  aiGenerate,
  getAiRoute,
  AI_TASK_TYPE_LABELS,
  AI_TASK_TYPE_OPTIONS,
  type AiGenerateResult,
  type AiRoutePreview,
  type AiTaskType,
} from '../../api/ai'
import { useNovelStore } from '../../stores/novels'

const novelStore = useNovelStore()
const message = useMessage()

const novelId = ref<string | null>(null)
const taskType = ref<AiTaskType>('writer')
const systemPrompt = ref('')
const userPrompt = ref('')
const context = ref('')
const temperature = ref(0.7)
const maxTokens = ref(2048)
const includeReasoning = ref(false)

const routeInfo = ref<AiRoutePreview | null>(null)
const loadingRoute = ref(false)
const running = ref(false)
const result = ref<AiGenerateResult | null>(null)

const novelOptions = computed(() =>
  novelStore.novels.map((n) => ({ label: n.title, value: n.id })),
)

const resolvedFromLabel = computed(() => {
  const map: Record<string, string> = {
    explicit: '本次指定',
    task: '任务配置',
    default: '全局默认',
  }
  return routeInfo.value?.resolved_from ? map[routeInfo.value.resolved_from] : ''
})

async function loadRoute() {
  loadingRoute.value = true
  try {
    const { data } = await getAiRoute(taskType.value)
    routeInfo.value = data
  } catch (error) {
    routeInfo.value = null
  } finally {
    loadingRoute.value = false
  }
}

watch(taskType, loadRoute, { immediate: true })

async function run() {
  if (!novelId.value) {
    message.warning('请先选择小说')
    return
  }
  if (!userPrompt.value.trim()) {
    message.warning('请输入测试提示词')
    return
  }
  running.value = true
  result.value = null
  try {
    const { data } = await aiGenerate({
      novel_id: novelId.value,
      task_type: taskType.value,
      system_prompt: systemPrompt.value,
      user_prompt: userPrompt.value,
      context: context.value,
      temperature: temperature.value,
      max_tokens: maxTokens.value,
      include_reasoning: includeReasoning.value,
    })
    result.value = data
    if (!data.success) {
      message.warning(data.error_message || '调用未成功')
    }
  } catch (error) {
    message.error(extractError(error, '调用失败'))
  } finally {
    running.value = false
  }
}

function usageText(usage: Record<string, number>): string {
  const parts: string[] = []
  if (usage.prompt_tokens != null) parts.push(`输入 ${usage.prompt_tokens}`)
  if (usage.completion_tokens != null) parts.push(`输出 ${usage.completion_tokens}`)
  if (usage.total_tokens != null) parts.push(`合计 ${usage.total_tokens}`)
  return parts.join(' / ')
}
</script>

<template>
  <div class="panel">
    <n-form label-placement="top" size="small">
      <n-grid :x-gap="12" cols="1 s:2" responsive="screen">
        <n-grid-item>
          <n-form-item label="选择小说" required>
            <n-select
              v-model:value="novelId"
              :options="novelOptions"
              filterable
              placeholder="选择测试所属小说"
            />
          </n-form-item>
        </n-grid-item>
        <n-grid-item>
          <n-form-item label="任务类型">
            <n-select v-model:value="taskType" :options="AI_TASK_TYPE_OPTIONS" />
          </n-form-item>
        </n-grid-item>
      </n-grid>

      <n-spin :show="loadingRoute">
        <n-alert
          v-if="routeInfo"
          :type="routeInfo.resolved ? 'info' : 'warning'"
          :bordered="false"
          class="route-alert"
        >
          <template v-if="routeInfo.resolved">
            当前路由模型：<b>{{ routeInfo.model_identifier }}</b>
            （{{ routeInfo.provider_type }} · {{ resolvedFromLabel }}）
          </template>
          <template v-else>{{ routeInfo.message }}</template>
        </n-alert>
      </n-spin>

      <n-form-item label="System Prompt（可选）">
        <n-input
          v-model:value="systemPrompt"
          type="textarea"
          :autosize="{ minRows: 2, maxRows: 5 }"
          placeholder="模型角色与规则，可留空"
        />
      </n-form-item>
      <n-form-item label="测试 Prompt" required>
        <n-input
          v-model:value="userPrompt"
          type="textarea"
          :autosize="{ minRows: 3, maxRows: 8 }"
          placeholder="例如：用一句话介绍玄幻小说《剑来》的开篇氛围"
        />
      </n-form-item>
      <n-form-item label="上下文内容（可选，模拟组装结果）">
        <n-input
          v-model:value="context"
          type="textarea"
          :autosize="{ minRows: 2, maxRows: 5 }"
          placeholder="粘贴或编写要注入的小说上下文，可留空"
        />
      </n-form-item>

      <n-grid :x-gap="16" cols="1 s:3" responsive="screen" class="params">
        <n-grid-item>
          <n-form-item :label="`temperature：${temperature}`">
            <n-slider v-model:value="temperature" :min="0" :max="2" :step="0.1" />
          </n-form-item>
        </n-grid-item>
        <n-grid-item>
          <n-form-item label="max_tokens">
            <n-input-number v-model:value="maxTokens" :min="1" :max="128000" class="full" />
          </n-form-item>
        </n-grid-item>
        <n-grid-item>
          <n-form-item label="返回思维链 reasoning">
            <n-switch v-model:value="includeReasoning" />
          </n-form-item>
        </n-grid-item>
      </n-grid>

      <div class="run-row">
        <n-button type="primary" :loading="running" :disabled="routeInfo?.resolved === false" @click="run">
          执行测试调用
        </n-button>
        <span class="hint">本接口仅用于链路测试，不会写入章节或剧情数据</span>
      </div>
    </n-form>

    <div v-if="result" class="result">
      <n-alert v-if="!result.success" type="error" :bordered="false">
        调用失败（{{ result.error_code }}）：{{ result.error_message }}
      </n-alert>

      <div class="meta-row">
        <n-tag size="small" round :bordered="false" :type="result.success ? 'success' : 'error'">
          {{ result.success ? '成功' : '失败' }}
        </n-tag>
        <n-tag size="small" round :bordered="false">{{ result.model }}</n-tag>
        <n-tag size="small" round :bordered="false" type="info">{{ result.provider }}</n-tag>
        <n-tag size="small" round :bordered="false">{{ AI_TASK_TYPE_LABELS[result.task_type as AiTaskType] || result.task_type }}</n-tag>
        <n-tag v-if="result.truncated" size="small" round :bordered="false" type="warning">已截断</n-tag>
        <span class="meta-text">耗时 {{ result.latency_ms }} ms</span>
        <span v-if="usageText(result.usage)" class="meta-text">{{ usageText(result.usage) }}</span>
        <span v-if="result.finish_reason" class="meta-text">finish：{{ result.finish_reason }}</span>
      </div>

      <template v-if="result.success">
        <div class="block-title">模型正文</div>
        <pre class="content-pre">{{ result.content }}</pre>
      </template>

      <n-collapse v-if="result.reasoning" class="reasoning">
        <n-collapse-item title="展开思维链 reasoning（非正文）" name="reasoning">
          <pre class="content-pre reasoning-pre">{{ result.reasoning }}</pre>
        </n-collapse-item>
      </n-collapse>
    </div>
  </div>
</template>

<style scoped>
.panel { padding-top: 4px; }
.full { width: 100%; }
.route-alert { margin-bottom: 8px; }
.params { margin-bottom: 4px; }
.run-row { display: flex; align-items: center; gap: 12px; margin: 8px 0 4px; flex-wrap: wrap; }
.hint { font-size: 12px; color: rgba(255, 255, 255, 0.4); }
.result { margin-top: 16px; border-top: 1px solid rgba(255, 255, 255, 0.08); padding-top: 12px; }
.meta-row { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin: 8px 0; }
.meta-text { font-size: 12px; color: rgba(255, 255, 255, 0.5); }
.block-title { font-size: 13px; font-weight: 600; color: #fff; margin: 10px 0 6px; }
.content-pre {
  margin: 0; padding: 10px 12px; background: rgba(255, 255, 255, 0.05);
  border-radius: 6px; font-size: 13px; line-height: 1.7; color: rgba(255, 255, 255, 0.85);
  white-space: pre-wrap; word-break: break-word; max-height: 360px; overflow: auto;
}
.reasoning { margin-top: 10px; }
.reasoning-pre { color: rgba(255, 255, 255, 0.6); }
</style>
