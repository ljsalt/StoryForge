<script setup lang="ts">
import { NIcon, NResult, NTag } from 'naive-ui'
import { AlbumsOutline } from '@vicons/ionicons5'
</script>

<template>
  <div class="page">
    <n-result
      status="info"
      title="预设管理"
      description="模型预设：System Prompt、作者设定、上下文模板与生成参数"
    >
      <template #icon>
        <n-icon :size="64"><AlbumsOutline /></n-icon>
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
