<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  NAlert,
  NButton,
  NCard,
  NEmpty,
  NGrid,
  NGridItem,
  NSpin,
  NStatistic,
  NTag,
} from 'naive-ui'
import { NOVEL_STATUS_LABELS, NOVEL_STATUS_TYPES } from '../api/novels'
import { formatDateTime } from '../utils/format'
import { useNovelStore } from '../stores/novels'
import { useSystemStore } from '../stores/system'

const system = useSystemStore()
const novels = useNovelStore()
const router = useRouter()

onMounted(() => {
  system.refresh()
  novels.load().catch(() => undefined)
})

const stats = computed(() => [
  { key: 'novels', label: '小说数量', value: novels.count.toLocaleString() },
  { key: 'chapters', label: '章节总数', value: '0' },
  { key: 'characters', label: '人物档案', value: '0' },
  { key: 'words', label: '累计字数', value: novels.totalWords.toLocaleString() },
])

const plannedModules = [
  { title: '小说项目管理', desc: '创建、切换与维护多部小说项目', phase: 'P3.1 已完成' },
  { title: '世界观管理', desc: '世界观设定、规则与势力体系', phase: 'P3.2' },
  { title: '人物档案管理', desc: '人物设定、关系图谱与成长弧线', phase: 'P3.3' },
  { title: '剧情记忆管理', desc: '剧情事件、线索与上下文记忆', phase: 'P3.4' },
  { title: '长篇章节生成', desc: 'AI 自动生成连贯、风格统一的长篇章节', phase: 'P3.5' },
  { title: 'AI 剧情规划', desc: '由 AI 自动规划长篇小说的整体剧情结构', phase: 'P3 阶段' },
  { title: '模型预设管理', desc: 'System Prompt、作者设定与生成参数预设', phase: '后续阶段' },
  { title: '半自主创作', desc: 'AI 自主推进剧情，重大节点暂停并询问', phase: '后续阶段' },
]

function goCreate() {
  router.push({ path: '/novels', query: { create: '1' } })
}

function openNovel(id: string) {
  router.push(`/novels/${id}`)
}
</script>

<template>
  <div class="dashboard">
    <div class="hero">
      <h1 class="hero-title">StoryForge</h1>
      <p class="hero-sub">本地优先的 AI 中文长篇小说创作工作室</p>
      <div class="hero-tags">
        <n-tag round size="small">版本 {{ system.version || '0.3.0-P3.1' }}</n-tag>
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
      <template #header-extra>
        <n-button size="tiny" type="primary" @click="goCreate">新建小说</n-button>
      </template>

      <n-spin :show="novels.loading">
        <div v-if="novels.recentNovels.length" class="recent-list">
          <div
            v-for="novel in novels.recentNovels"
            :key="novel.id"
            class="recent-row"
            @click="openNovel(novel.id)"
          >
            <div class="recent-main">
              <div class="recent-title-row">
                <span class="recent-title">{{ novel.title }}</span>
                <n-tag
                  v-if="novel.is_default"
                  size="tiny"
                  type="warning"
                  round
                >
                  默认项目
                </n-tag>
                <n-tag size="tiny" :type="NOVEL_STATUS_TYPES[novel.status]" round>
                  {{ NOVEL_STATUS_LABELS[novel.status] }}
                </n-tag>
              </div>
              <div class="recent-sub">
                {{ novel.subtitle || novel.genre || '暂无副标题' }}
              </div>
            </div>
            <div class="recent-meta">
              <span>{{ novel.current_word_count.toLocaleString() }} / {{ novel.target_word_count.toLocaleString() }} 字</span>
              <span>{{ formatDateTime(novel.updated_at) }}</span>
            </div>
          </div>
        </div>

        <n-empty v-else description="暂无创作记录" size="large">
          <template #extra>
            <div class="empty-actions">
              <span class="empty-hint">创建第一部小说，开始你的长篇创作</span>
              <n-button size="small" type="primary" @click="goCreate">创建小说</n-button>
            </div>
          </template>
        </n-empty>
      </n-spin>
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

.empty-actions {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
}

.recent-list {
  display: flex;
  flex-direction: column;
}

.recent-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 8px;
  border-radius: 6px;
  cursor: pointer;
  transition: background-color 0.15s ease;
}

.recent-row:hover {
  background-color: rgba(255, 255, 255, 0.05);
}

.recent-main {
  min-width: 0;
}

.recent-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.recent-title {
  font-size: 14px;
  font-weight: 600;
  color: #fff;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}

.recent-sub {
  margin-top: 3px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.45);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.recent-meta {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.4);
  white-space: nowrap;
  flex-shrink: 0;
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

  .recent-row {
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
  }

  .recent-meta {
    align-items: flex-start;
    flex-direction: row;
    gap: 10px;
    flex-wrap: wrap;
    white-space: normal;
  }
}
</style>
