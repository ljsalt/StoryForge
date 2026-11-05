<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { NCard, NTabPane, NTabs } from 'naive-ui'
import { useNovelStore } from '../stores/novels'
import AiTestPanel from '../components/ai/AiTestPanel.vue'
import ContextPreviewPanel from '../components/ai/ContextPreviewPanel.vue'
import PromptTemplatePanel from '../components/ai/PromptTemplatePanel.vue'
import AiTaskList from '../components/ai/AiTaskList.vue'

const novelStore = useNovelStore()
const tasksNovelId = ref<string | null>(null)

onMounted(() => {
  if (!novelStore.novels.length) {
    novelStore.load().catch(() => {})
  }
})
</script>

<template>
  <div class="page">
    <header class="header">
      <div>
        <h1 class="title">AI 引擎</h1>
        <p class="subtitle">
          统一模型调用、上下文组装与提示词模板的基础设施。本阶段不提供自动写作工作流，
          所有 AI 生成内容都不会自动写入章节。
        </p>
      </div>
    </header>

    <n-card :bordered="false" class="card">
      <n-tabs type="line" animated>
        <n-tab-pane name="test" tab="调用测试">
          <AiTestPanel />
        </n-tab-pane>
        <n-tab-pane name="context" tab="上下文预览">
          <ContextPreviewPanel />
        </n-tab-pane>
        <n-tab-pane name="templates" tab="提示词模板">
          <PromptTemplatePanel />
        </n-tab-pane>
        <n-tab-pane name="tasks" tab="任务记录">
          <AiTaskList v-model:novel-id="tasksNovelId" />
        </n-tab-pane>
      </n-tabs>
    </n-card>
  </div>
</template>

<style scoped>
.page { padding: 24px; max-width: 1200px; margin: 0 auto; }
.header { margin-bottom: 16px; }
.title { font-size: 22px; font-weight: 700; color: #fff; margin: 0; }
.subtitle { font-size: 13px; color: rgba(255, 255, 255, 0.5); margin: 6px 0 0; line-height: 1.7; }
.card { background: rgba(255, 255, 255, 0.03); }

@media (max-width: 640px) {
  .page { padding: 16px 12px; }
  .title { font-size: 19px; }
}
</style>
