<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useMessage } from 'naive-ui'
import { NAlert, NButton, NTabPane, NTabs } from 'naive-ui'
import ProviderPanel from '../components/settings/ProviderPanel.vue'
import ModelPanel from '../components/settings/ModelPanel.vue'
import TaskAssignPanel from '../components/settings/TaskAssignPanel.vue'
import DefaultsPanel from '../components/settings/DefaultsPanel.vue'
import { extractError } from '../api/error'
import { useModelStore } from '../stores/models'

const store = useModelStore()
const message = useMessage()

const activeTab = ref('providers')
const loadError = ref('')
const loading = ref(false)

async function loadAll() {
  loading.value = true
  loadError.value = ''
  try {
    await store.loadAll()
  } catch (error) {
    loadError.value = extractError(error)
  } finally {
    loading.value = false
  }
}

async function retry() {
  await loadAll()
  if (!loadError.value) message.success('已重新加载配置')
}

onMounted(loadAll)
</script>

<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h2 class="page-title">系统设置</h2>
        <div class="page-sub">统一模型接口与 API 管理</div>
      </div>
    </div>

    <n-alert v-if="loadError" type="error" :bordered="false" class="load-error">
      {{ loadError }}
      <n-button size="tiny" class="retry-btn" @click="retry">重试</n-button>
    </n-alert>

    <n-tabs v-model:value="activeTab" type="line" animated class="settings-tabs">
      <n-tab-pane name="providers" tab="API 服务商">
        <ProviderPanel />
      </n-tab-pane>
      <n-tab-pane name="models" tab="模型管理">
        <ModelPanel />
      </n-tab-pane>
      <n-tab-pane name="tasks" tab="任务模型分配">
        <TaskAssignPanel />
      </n-tab-pane>
      <n-tab-pane name="defaults" tab="默认设置">
        <DefaultsPanel />
      </n-tab-pane>
    </n-tabs>
  </div>
</template>

<style scoped>
.page {
  max-width: 1080px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  margin-bottom: 16px;
  gap: 12px;
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

.load-error {
  margin-bottom: 16px;
  font-size: 13px;
}

.retry-btn {
  margin-left: 8px;
}

.settings-tabs :deep(.n-tabs-nav) {
  overflow-x: auto;
  flex-wrap: nowrap;
}
</style>
