<script setup lang="ts">
import { onMounted } from 'vue'
import {
  NAlert,
  NButton,
  NCard,
  NEmpty,
  NGrid,
  NGridItem,
  NStatistic,
  NTag,
} from 'naive-ui'
import { useSystemStore } from '../stores/system'

const system = useSystemStore()

onMounted(() => {
  system.refresh()
})

const stats = [
  { key: 'novels', label: '小说数量', value: '0' },
  { key: 'chapters', label: '章节总数', value: '0' },
  { key: 'characters', label: '人物档案', value: '0' },
  { key: 'words', label: '累计字数', value: '0' },
]

const plannedModules = [
  { title: 'AI 剧情规划', desc: '由 AI 自动规划长篇小说的整体剧情结构', phase: 'P2 阶段' },
  { title: '长篇章节生成', desc: 'AI 自动生成连贯、风格统一的长篇章节', phase: 'P2 阶段' },
  { title: '人物档案管理', desc: '人物设定、关系图谱与人物记忆管理', phase: 'P2 阶段' },
  { title: '世界观与剧情记忆', desc: '世界观设定管理与剧情上下文记忆', phase: 'P2 阶段' },
  { title: '多模型接入', desc: 'DeepSeek 官方 API 及 OpenAI 兼容 API', phase: 'P2 阶段' },
  { title: '模型预设管理', desc: 'System Prompt、作者设定与生成参数预设', phase: 'P2 阶段' },
  { title: '半自主创作', desc: 'AI 自主推进剧情，重大节点暂停并询问', phase: 'P3 阶段' },
  { title: '安卓端适配增强', desc: '手机端深度优化与离线使用支持', phase: '后续阶段' },
]
</script>

<template>
  <div class="dashboard">
    <div class="hero">
      <h1 class="hero-title">StoryForge</h1>
      <p class="hero-sub">本地优先的 AI 中文长篇小说创作工作室</p>
      <div class="hero-tags">
        <n-tag round size="small">版本 {{ system.version || '0.1.0-P1' }}</n-tag>
        <n-tag v-if="system.online" type="success" round size="small">系统状态：正常</n-tag>
        <n-tag v-else type="error" round size="small">系统状态：后端离线</n-tag>
      </div>
    </div>

    <n-alert v-if="system.error" type="error" class="backend-alert" closable>
      {{ system.error }}
      <n-button size="tiny" class="retry-btn" @click="system.refresh()">重试</n-button>
    </n-alert>

    <n-grid :x-gap="16" :y-gap="16" cols="1 s:2 m:4" responsive="screen">
      <n-grid-item v-for="item in stats" :key="item.key">
        <n-card size="small">
          <n-statistic :label="item.label" :value="item.value" />
        </n-card>
      </n-grid-item>
    </n-grid>

    <n-card title="最近创作记录" class="section-card">
      <n-empty description="暂无创作记录" size="large">
        <template #extra>
          <span class="empty-hint">开始创作功能将在 P2 阶段开放</span>
        </template>
      </n-empty>
    </n-card>

    <n-card title="规划中的功能模块" class="section-card">
      <n-grid :x-gap="16" :y-gap="16" cols="1 s:2 m:4" responsive="screen">
        <n-grid-item v-for="mod in plannedModules" :key="mod.title">
          <n-card size="small" embedded class="module-card">
            <div class="module-title">{{ mod.title }}</div>
            <div class="module-desc">{{ mod.desc }}</div>
            <n-tag size="tiny" round class="module-tag">{{ mod.phase }}</n-tag>
          </n-card>
        </n-grid-item>
      </n-grid>
    </n-card>
  </div>
</template>

<style scoped>
.dashboard {
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.hero {
  padding: 12px 0 4px;
}

.hero-title {
  margin: 0;
  font-size: 34px;
  font-weight: 700;
  color: #fff;
  letter-spacing: 1px;
}

.hero-sub {
  margin: 8px 0 12px;
  color: rgba(255, 255, 255, 0.55);
  font-size: 15px;
}

.hero-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.backend-alert {
  max-width: 640px;
}

.retry-btn {
  margin-left: 8px;
}

.section-card {
  width: 100%;
}

.empty-hint {
  color: rgba(255, 255, 255, 0.4);
  font-size: 13px;
}

.module-card {
  height: 100%;
}

.module-title {
  font-size: 15px;
  font-weight: 600;
  color: #fff;
  margin-bottom: 6px;
}

.module-desc {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.55);
  min-height: 38px;
}

.module-tag {
  margin-top: 10px;
}

@media (max-width: 767px) {
  .hero-title {
    font-size: 26px;
  }
}
</style>
