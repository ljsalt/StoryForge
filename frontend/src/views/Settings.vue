<script setup lang="ts">
import { onMounted } from 'vue'
import {
  NButton,
  NCard,
  NDescriptions,
  NDescriptionsItem,
  NEmpty,
  NTag,
} from 'naive-ui'
import { apiBaseURL } from '../api'
import { useSystemStore } from '../stores/system'

const system = useSystemStore()

onMounted(() => {
  system.refresh()
})
</script>

<template>
  <div class="page">
    <h2 class="page-title">系统设置</h2>

    <n-card title="后端服务" class="section-card">
      <n-descriptions :column="1" label-placement="left" bordered>
        <n-descriptions-item label="接口地址">
          {{ apiBaseURL }}
        </n-descriptions-item>
        <n-descriptions-item label="连接状态">
          <n-tag v-if="system.online" type="success" size="small" round>已连接</n-tag>
          <n-tag v-else type="error" size="small" round>未连接</n-tag>
        </n-descriptions-item>
        <n-descriptions-item label="后端版本">
          {{ system.health?.version ?? '-' }}
        </n-descriptions-item>
        <n-descriptions-item label="Python 版本">
          {{ system.info?.python_version ?? '-' }}
        </n-descriptions-item>
      </n-descriptions>
      <div class="actions">
        <n-button size="small" :loading="system.loading" @click="system.refresh()">
          刷新状态
        </n-button>
      </div>
    </n-card>

    <n-card title="数据目录" class="section-card">
      <n-descriptions v-if="system.info" :column="1" label-placement="left" bordered>
        <n-descriptions-item label="目录路径">
          {{ system.info.data_dir }}
        </n-descriptions-item>
        <n-descriptions-item label="目录状态">
          <n-tag
            :type="system.info.data_dir_status.exists ? 'success' : 'error'"
            size="small"
            round
          >
            {{ system.info.data_dir_status.exists ? '正常' : '缺失' }}
          </n-tag>
        </n-descriptions-item>
        <n-descriptions-item label="小说目录">
          {{ system.info.data_dir_status.novels_dir ? '已就绪' : '未创建' }}
        </n-descriptions-item>
        <n-descriptions-item label="备份目录">
          {{ system.info.data_dir_status.backups_dir ? '已就绪' : '未创建' }}
        </n-descriptions-item>
      </n-descriptions>
      <n-empty v-else description="后端离线，无法获取目录信息" />
    </n-card>

    <n-card title="关于" class="section-card">
      <n-descriptions :column="1" label-placement="left" bordered>
        <n-descriptions-item label="项目名称">
          {{ system.info?.project_name ?? 'StoryForge' }}
        </n-descriptions-item>
        <n-descriptions-item label="当前阶段">P1：项目初始化与基础访问</n-descriptions-item>
        <n-descriptions-item label="访问说明">
          服务仅监听可信局域网。手机与电脑连接同一 Wi-Fi 后，
          使用电脑局域网 IP 加端口 5173 即可访问前端。
        </n-descriptions-item>
      </n-descriptions>
    </n-card>
  </div>
</template>

<style scoped>
.page {
  max-width: 720px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.page-title {
  margin: 0;
  font-size: 22px;
  color: #fff;
}

.section-card {
  width: 100%;
}

.actions {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
