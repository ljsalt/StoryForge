<script setup lang="ts">
import { onMounted } from 'vue'
import {
  NCard,
  NDescriptions,
  NDescriptionsItem,
  NEmpty,
  NTag,
} from 'naive-ui'
import { apiBaseURL } from '../../api'
import { useSystemStore } from '../../stores/system'

const system = useSystemStore()

onMounted(() => {
  if (!system.health) system.refresh()
})
</script>

<template>
  <div class="panels">
    <n-card title="后端服务">
      <n-descriptions :column="1" label-placement="left" bordered size="small">
        <n-descriptions-item label="接口地址">{{ apiBaseURL }}</n-descriptions-item>
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
        <n-descriptions-item label="当前阶段">P3.3：人物档案管理</n-descriptions-item>
      </n-descriptions>
    </n-card>

    <n-card title="数据与密钥存放位置">
      <n-descriptions
        v-if="system.info"
        :column="1"
        label-placement="left"
        bordered
        size="small"
      >
        <n-descriptions-item label="数据目录">
          {{ system.info.data_dir }}
        </n-descriptions-item>
        <n-descriptions-item label="数据库文件">
          data/storyforge.db（服务商、模型与任务分配配置）
        </n-descriptions-item>
        <n-descriptions-item label="加密主密钥">
          data/secrets/fernet.key（首次启动自动生成）
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
      </n-descriptions>
      <n-empty v-else description="后端离线，无法获取目录信息" />
    </n-card>

    <n-card title="安全说明">
      <ul class="security-list">
        <li>API Key 使用 Fernet 加密后存入本地 SQLite，浏览器与接口只返回脱敏状态（如 sk-****abcd）。</li>
        <li>API Key 不会写入浏览器 localStorage，也不会写入日志或提交到 Git。</li>
        <li>备份时请同时复制 <code>data/storyforge.db</code> 与 <code>data/secrets/fernet.key</code>。</li>
        <li>若只恢复数据库而丢失主密钥，已保存的 API Key 将无法解密，需要重新填写。</li>
        <li>自定义 Base URL 仅支持 http/https，默认禁止指向本机与内网地址；服务请勿暴露到公网。</li>
      </ul>
    </n-card>
  </div>
</template>

<style scoped>
.panels {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.security-list {
  margin: 0;
  padding-left: 18px;
  font-size: 13px;
  line-height: 1.8;
  color: rgba(255, 255, 255, 0.65);
}

.security-list code {
  font-size: 12px;
  padding: 1px 4px;
  border-radius: 3px;
  background-color: rgba(255, 255, 255, 0.08);
}
</style>
