<script setup lang="ts">
import { NIcon, NResult, NTag } from 'naive-ui'
import { PeopleOutline } from '@vicons/ionicons5'
</script>

<template>
  <div class="page">
    <n-result status="info" title="人物管理" description="人物档案、关系图谱与人物记忆">
      <template #icon>
        <n-icon :size="64"><PeopleOutline /></n-icon>
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
