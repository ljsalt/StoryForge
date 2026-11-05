<script setup lang="ts">
import { NButton, NDescriptions, NDescriptionsItem, NEmpty, NModal, NTag } from 'naive-ui'
import type { WorldRelation } from '../../api/world'
import { formatDateTime } from '../../utils/format'

defineProps<{ show: boolean; relation: WorldRelation | null }>()
const emit = defineEmits<{
  'update:show': [value: boolean]
  edit: []
  remove: []
}>()
</script>

<template>
  <n-modal
    :show="show"
    preset="card"
    title="关系详情"
    :style="{ width: '560px', maxWidth: 'calc(100vw - 24px)' }"
    :bordered="false"
    @update:show="emit('update:show', $event)"
  >
    <n-empty v-if="!relation" description="暂无关系内容" />

    <div v-else class="body">
      <div class="relation-title">
        <span class="endpoint">{{ relation.source.name }}</span>
        <n-tag size="small" round type="success" :bordered="false">
          {{ relation.relation_type }}
        </n-tag>
        <span class="arrow">→</span>
        <span class="endpoint">{{ relation.target.name }}</span>
      </div>

      <div class="category-row">
        <span class="muted">{{ relation.source.category_name }}</span>
        <span class="muted">→</span>
        <span class="muted">{{ relation.target.category_name }}</span>
      </div>

      <section class="block">
        <div class="block-title">关系描述</div>
        <p class="text">{{ relation.description || '暂无关系描述' }}</p>
      </section>

      <n-descriptions :column="1" label-placement="left" size="small" class="info">
        <n-descriptions-item label="起点">
          {{ relation.source.name }}（{{ relation.source.category_name }}）
        </n-descriptions-item>
        <n-descriptions-item label="终点">
          {{ relation.target.name }}（{{ relation.target.category_name }}）
        </n-descriptions-item>
        <n-descriptions-item label="创建时间">
          {{ formatDateTime(relation.created_at) }}
        </n-descriptions-item>
        <n-descriptions-item label="更新时间">
          {{ formatDateTime(relation.updated_at) }}
        </n-descriptions-item>
      </n-descriptions>
    </div>

    <template #footer>
      <div v-if="relation" class="footer">
        <n-button size="small" type="error" ghost @click="emit('remove')">删除关系</n-button>
        <div class="right">
          <n-button size="small" @click="emit('update:show', false)">关闭</n-button>
          <n-button size="small" type="primary" @click="emit('edit')">编辑关系</n-button>
        </div>
      </div>
    </template>
  </n-modal>
</template>

<style scoped>
.relation-title {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 18px;
  color: #fff;
}

.endpoint {
  word-break: break-word;
}

.arrow {
  color: #7ea2ff;
}

.category-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 6px;
}

.muted {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.4);
}

.block {
  margin-top: 16px;
}

.block-title {
  margin-bottom: 6px;
  font-size: 13px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.75);
}

.text {
  margin: 0;
  font-size: 13px;
  line-height: 1.8;
  color: rgba(255, 255, 255, 0.7);
  white-space: pre-wrap;
  word-break: break-word;
}

.info {
  margin-top: 16px;
}

.footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.right {
  display: flex;
  gap: 8px;
}
</style>
