<script setup lang="ts">
import { NButton, NCard, NTag } from 'naive-ui'
import type { CharacterListItem } from '../../api/character'
import { formatDateTime } from '../../utils/format'

defineProps<{ character: CharacterListItem }>()
defineEmits<{ open: []; edit: []; remove: [] }>()

const lifeLabel: Record<string, { label: string; type: 'success' | 'error' | 'warning' }> = {
  alive: { label: '存活', type: 'success' },
  dead: { label: '已陨落', type: 'error' },
  unknown: { label: '状态不明', type: 'warning' },
}
</script>

<template>
  <n-card class="char-card" size="small" hoverable @click="$emit('open')">
    <div class="card-head">
      <div class="avatar" :style="{ background: character.avatar_color || '#3b5bdb' }">
        {{ character.name.charAt(0) }}
      </div>
      <div class="title-wrap">
        <div class="name-row">
          <span class="char-name">{{ character.name }}</span>
          <n-tag
            v-if="character.role"
            size="tiny"
            round
            :bordered="false"
            type="info"
          >
            {{ character.role }}
          </n-tag>
        </div>
        <div v-if="character.identity" class="identity">{{ character.identity }}</div>
        <div v-if="character.aliases.length" class="aliases">
          别名：{{ character.aliases.join('、') }}
        </div>
      </div>
    </div>

    <div v-if="character.tags.length" class="tag-row">
      <n-tag v-for="tag in character.tags" :key="tag" size="tiny" round :bordered="false">
        {{ tag }}
      </n-tag>
    </div>

    <div class="state-row">
      <n-tag
        size="tiny"
        round
        :type="lifeLabel[character.life_status]?.type ?? 'default'"
        :bordered="false"
      >
        {{ lifeLabel[character.life_status]?.label ?? character.life_status }}
      </n-tag>
      <span v-if="character.current_location" class="state-text">
        📍 {{ character.current_location }}
      </span>
      <span v-if="character.current_cultivation" class="state-text">
        ⚔️ {{ character.current_cultivation }}
      </span>
    </div>

    <div class="card-foot">
      <span class="meta">更新于 {{ formatDateTime(character.updated_at) }}</span>
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
.char-card {
  height: 100%;
  cursor: pointer;
}

.card-head {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.avatar {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  color: #fff;
  font-size: 20px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.title-wrap {
  flex: 1;
  min-width: 0;
}

.name-row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.char-name {
  font-size: 16px;
  font-weight: 600;
  color: #fff;
  word-break: break-word;
}

.identity {
  margin-top: 2px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.55);
}

.aliases {
  margin-top: 2px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.4);
}

.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.state-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
}

.state-text {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.55);
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
