<script setup lang="ts">
import { computed } from 'vue'
import { NButton, NCard, NSpace, NTag } from 'naive-ui'
import {
  NOVEL_STATUS_LABELS,
  NOVEL_STATUS_TYPES,
  type Novel,
} from '../../api/novels'
import { formatDateTime } from '../../utils/format'

const props = defineProps<{ novel: Novel }>()
defineEmits<{
  (e: 'open'): void
  (e: 'edit'): void
  (e: 'remove'): void
  (e: 'set-default'): void
}>()

const PALETTES = [
  'linear-gradient(135deg, #3b5bdb 0%, #5c7cfa 100%)',
  'linear-gradient(135deg, #6741d9 0%, #9775fa 100%)',
  'linear-gradient(135deg, #0b7285 0%, #15aabf 100%)',
  'linear-gradient(135deg, #a61e4d 0%, #e64980 100%)',
  'linear-gradient(135deg, #2b8a3e 0%, #51cf66 100%)',
  'linear-gradient(135deg, #d9480f 0%, #ff922b 100%)',
]

const coverStyle = computed(() => {
  if (props.novel.cover_color) {
    return { background: props.novel.cover_color }
  }
  let hash = 0
  for (const char of props.novel.id) hash = (hash + char.charCodeAt(0)) % 997
  return { background: PALETTES[hash % PALETTES.length] }
})

const initial = computed(() => props.novel.title.trim().charAt(0) || '书')
</script>

<template>
  <n-card class="novel-card" :bordered="false" hoverable @click="$emit('open')">
    <div class="cover" :style="coverStyle">
      <span class="cover-letter">{{ initial }}</span>
      <n-tag v-if="novel.is_default" size="tiny" type="warning" round class="default-badge">
        默认项目
      </n-tag>
    </div>

    <div class="body">
      <div class="title-row">
        <span class="title" :title="novel.title">{{ novel.title }}</span>
        <n-tag size="tiny" :type="NOVEL_STATUS_TYPES[novel.status]" round>
          {{ NOVEL_STATUS_LABELS[novel.status] }}
        </n-tag>
      </div>
      <div v-if="novel.subtitle" class="subtitle">{{ novel.subtitle }}</div>
      <div class="tags">
        <n-tag v-if="novel.genre" size="small" round :bordered="false" type="info">
          {{ novel.genre }}
        </n-tag>
        <n-tag
          v-for="tag in novel.tags.slice(0, 3)"
          :key="tag"
          size="small"
          round
          :bordered="false"
        >
          {{ tag }}
        </n-tag>
        <span v-if="novel.tags.length > 3" class="more-tags">+{{ novel.tags.length - 3 }}</span>
      </div>
      <div class="description">
        {{ novel.description || '暂无简介' }}
      </div>
      <div class="meta">
        <span>目标 {{ novel.target_word_count.toLocaleString() }} 字</span>
        <span>当前 {{ novel.current_word_count.toLocaleString() }} 字</span>
        <span>更新于 {{ formatDateTime(novel.updated_at) }}</span>
      </div>
    </div>

    <div class="actions" @click.stop>
      <n-space :size="4" justify="space-between" align="center">
        <n-button size="tiny" type="primary" text @click="$emit('open')">打开项目</n-button>
        <n-space :size="4">
          <n-button v-if="!novel.is_default" size="tiny" text @click="$emit('set-default')">
            设为默认
          </n-button>
          <n-button size="tiny" text @click="$emit('edit')">编辑</n-button>
          <n-button size="tiny" text type="error" @click="$emit('remove')">删除</n-button>
        </n-space>
      </n-space>
    </div>
  </n-card>
</template>

<style scoped>
.novel-card {
  padding: 0;
  overflow: hidden;
  cursor: pointer;
  transition: transform 0.15s ease;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.novel-card:hover {
  transform: translateY(-2px);
}

.cover {
  height: 84px;
  border-radius: 8px 8px 0 0;
  display: flex;
  align-items: center;
  padding: 0 16px;
  position: relative;
}

.cover-letter {
  font-size: 40px;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.9);
  line-height: 1;
  text-shadow: 0 2px 6px rgba(0, 0, 0, 0.25);
}

.default-badge {
  position: absolute;
  top: 10px;
  right: 10px;
}

.body {
  padding: 14px 16px 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex: 1;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.title {
  font-size: 16px;
  font-weight: 600;
  color: #fff;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.subtitle {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.45);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: center;
  margin-top: 2px;
}

.more-tags {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.4);
}

.description {
  margin-top: 2px;
  font-size: 12px;
  line-height: 1.6;
  color: rgba(255, 255, 255, 0.55);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  min-height: 38px;
}

.meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.4);
}

.actions {
  padding: 5px 16px 11px;
}
</style>
