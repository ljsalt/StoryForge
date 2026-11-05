<script setup lang="ts">
import { NButton, NCard, NTag } from 'naive-ui'
import type { WorldEntry } from '../../api/world'
import { formatDateTime } from '../../utils/format'

defineProps<{ entry: WorldEntry }>()
defineEmits<{ open: []; edit: []; remove: [] }>()
</script>

<template>
  <n-card class="world-card" size="small" hoverable @click="$emit('open')">
    <div class="card-head">
      <div class="title-wrap">
        <div class="entry-name">{{ entry.name }}</div>
        <div class="category-name">{{ entry.category_name }}</div>
      </div>
      <n-tag v-if="entry.parent_name" size="tiny" round type="info" :bordered="false">
        子项 · {{ entry.parent_name }}
      </n-tag>
    </div>

    <div v-if="entry.tags.length" class="tag-row">
      <n-tag v-for="tag in entry.tags" :key="tag" size="tiny" round :bordered="false">
        {{ tag }}
      </n-tag>
    </div>

    <p class="summary">
      {{ entry.summary || entry.content || '暂无描述' }}
    </p>

    <div class="card-foot">
      <span class="meta">
        {{ Object.keys(entry.attributes).length }} 项属性 · 更新于
        {{ formatDateTime(entry.updated_at) }}
      </span>
      <div class="actions">
        <n-button size="tiny" quaternary @click.stop="$emit('edit')">编辑</n-button>
        <n-button size="tiny" quaternary type="error" @click.stop="$emit('remove')">
          删除
        </n-button>
      </div>
    </div>
  </n-card>
</template>

<style scoped>
.world-card {
  height: 100%;
  cursor: pointer;
}

.card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}

.entry-name {
  font-size: 16px;
  font-weight: 600;
  color: #fff;
  word-break: break-word;
}

.category-name {
  margin-top: 2px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.45);
}

.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.summary {
  margin: 10px 0 0;
  font-size: 13px;
  line-height: 1.7;
  color: rgba(255, 255, 255, 0.65);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  word-break: break-word;
}

.card-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: 10px;
}

.meta {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.4);
}

.actions {
  display: flex;
  gap: 2px;
  flex: none;
}

@media (max-width: 767px) {
  .card-foot {
    flex-wrap: wrap;
  }
}
</style>
