<script setup lang="ts">
import { NIcon, NResult, NTag } from 'naive-ui'
import { BookOutline } from '@vicons/ionicons5'
</script>

<template>
  <div class="page">
    <n-result status="info" title="小说管理" description="创建与管理你的长篇小说项目">
      <template #icon>
        <n-icon :size="64"><BookOutline /></n-icon>
      </template>
      <template #footer>
        <n-tag round size="small">P2 阶段开放</n-tag>
      </template>
    </n-result>
  </div>
</template>

<style scoped>
.page {
  max-width: 720px;
  margin: 0 auto;
  padding-top: 48px;
}
</style>
