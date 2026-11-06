<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  NButton,
  NCard,
  NDescriptions,
  NDescriptionsItem,
  NEmpty,
  NGrid,
  NGridItem,
  NProgress,
  NResult,
  NSpin,
  NStatistic,
  NTag,
} from 'naive-ui'
import {
  NOVEL_STATUS_LABELS,
  NOVEL_STATUS_TYPES,
  type NovelDetail,
} from '../api/novels'
import { extractError } from '../api/error'
import { useNovelStore } from '../stores/novels'
import { formatDateTime } from '../utils/format'

const route = useRoute()
const router = useRouter()
const store = useNovelStore()

const novel = ref<NovelDetail | null>(null)
const loading = ref(false)
const error = ref('')

const futureModules = [
  { title: '剧情记忆', desc: '自动提取事件并维护上下文记忆', phase: 'P4.1.3' },
]

async function load(id: string) {
  loading.value = true
  error.value = ''
  try {
    novel.value = await store.openNovel(id)
  } catch (err) {
    novel.value = null
    error.value = extractError(err, '小说不存在或已被删除')
  } finally {
    loading.value = false
  }
}

async function setDefault() {
  if (!novel.value) return
  await store.setDefault(novel.value.id)
  await load(novel.value.id)
}

onMounted(() => load(String(route.params.id)))
watch(
  () => route.params.id,
  (id) => {
    if (id) load(String(id))
  },
)
</script>

<template>
  <div class="page">
    <n-spin :show="loading">
      <n-result
        v-if="error"
        status="404"
        title="无法打开该小说"
        :description="error"
      >
        <template #footer>
          <n-button size="small" @click="router.push('/novels')">返回小说列表</n-button>
        </template>
      </n-result>

      <template v-else-if="novel">
        <div class="page-header">
          <n-button size="small" quaternary @click="router.push('/novels')">
            ← 返回小说列表
          </n-button>
          <div class="header-actions">
            <n-button
              v-if="!novel.is_default"
              size="small"
              @click="setDefault"
            >
              设为默认项目
            </n-button>
            <n-button size="small" @click="router.push(`/novels/${novel.id}/quick-writing`)">
              快速写作
            </n-button>
            <n-button size="small" type="primary" @click="router.push(`/novels/${novel.id}/writing`)">
              进入创作工作台
            </n-button>
          </div>
        </div>

        <n-card class="hero-card" :bordered="false">
          <div class="hero-cover">
            <span class="hero-letter">{{ novel.title.charAt(0) }}</span>
          </div>
          <div class="hero-info">
            <div class="title-row">
              <h1 class="novel-title">{{ novel.title }}</h1>
              <n-tag :type="NOVEL_STATUS_TYPES[novel.status]" size="small" round>
                {{ NOVEL_STATUS_LABELS[novel.status] }}
              </n-tag>
              <n-tag v-if="novel.is_default" type="warning" size="small" round>
                默认项目
              </n-tag>
            </div>
            <div v-if="novel.subtitle" class="novel-subtitle">{{ novel.subtitle }}</div>
            <div class="tag-row">
              <n-tag v-if="novel.genre" size="small" round type="info" :bordered="false">
                {{ novel.genre }}
              </n-tag>
              <n-tag
                v-for="tag in novel.tags"
                :key="tag"
                size="small"
                round
                :bordered="false"
              >
                {{ tag }}
              </n-tag>
              <span v-if="!novel.genre && !novel.tags.length" class="muted">
                暂未设置题材与标签
              </span>
            </div>
            <p class="description">{{ novel.description || '暂无简介' }}</p>
          </div>
        </n-card>

        <n-grid :x-gap="16" :y-gap="16" cols="1 s:2 m:4" responsive="screen">
          <n-grid-item>
            <n-card size="small">
              <n-statistic label="目标字数" :value="novel.target_word_count" />
            </n-card>
          </n-grid-item>
          <n-grid-item>
            <n-card size="small">
              <n-statistic label="当前字数" :value="novel.current_word_count" />
            </n-card>
          </n-grid-item>
          <n-grid-item>
            <n-card size="small">
              <n-statistic label="章节数量" :value="novel.stats.chapter_count" />
            </n-card>
          </n-grid-item>
          <n-grid-item>
            <n-card size="small">
              <n-statistic
                label="已完成章节"
                :value="novel.stats.completed_chapter_count"
              />
            </n-card>
          </n-grid-item>
          <n-grid-item>
            <n-card size="small">
              <n-statistic label="世界观条目" :value="novel.stats.world_entry_count" />
            </n-card>
          </n-grid-item>
          <n-grid-item>
            <n-card size="small">
              <n-statistic label="人物档案" :value="novel.stats.character_count" />
            </n-card>
          </n-grid-item>
          <n-grid-item>
            <n-card size="small">
              <n-statistic label="人物关系" :value="novel.stats.character_relation_count" />
            </n-card>
          </n-grid-item>
        </n-grid>

        <n-card title="世界观设定" size="small" class="world-entry">
          <div class="world-entry-body">
            <div class="world-entry-text">
              已收录 {{ novel.stats.world_entry_count }} 条世界观设定。管理地理、势力、
              世界规则、力量体系等资料，为后续人物与剧情创作提供统一背景。
            </div>
            <n-button
              size="small"
              type="primary"
              @click="router.push(`/novels/${novel.id}/world`)"
            >
              进入世界观
            </n-button>
          </div>
        </n-card>

        <n-card title="人物档案" size="small" class="world-entry">
          <div class="world-entry-body">
            <div class="world-entry-text">
              已录入 {{ novel.stats.character_count }} 位人物。档案包含人物基础信息、外貌性格、背景能力、
              当前状态与秘密。
            </div>
            <n-button
              size="small"
              type="primary"
              @click="router.push(`/novels/${novel.id}/characters`)"
            >
              进入人物档案
            </n-button>
          </div>
        </n-card>

        <n-card title="人物关系" size="small" class="world-entry">
          <div class="world-entry-body">
            <div class="world-entry-text">
              已记录 {{ novel.stats.character_relation_count }} 条有向人物关系。支持双向快捷创建、
              关系演变历史追踪、关系网络图和时间线查看。
            </div>
            <n-button
              size="small"
              type="primary"
              @click="router.push(`/novels/${novel.id}/character-relations`)"
            >
              进入人物关系
            </n-button>
          </div>
        </n-card>

        <n-card title="章节管理" size="small" class="world-entry">
          <div class="world-entry-body">
            <div class="world-entry-text">
              共 {{ novel.stats.chapter_count }} 章，已完成
              {{ novel.stats.completed_chapter_count }} 章，累计
              {{ novel.stats.word_count.toLocaleString() }} 字。支持章节目录、正文编辑、字数统计与顺序调整。
            </div>
            <n-button
              size="small"
              type="primary"
              @click="router.push(`/novels/${novel.id}/chapters`)"
            >
              进入章节管理
            </n-button>
          </div>
        </n-card>

        <n-card title="剧情事件" size="small" class="world-entry">
          <div class="world-entry-body">
            <div class="world-entry-text">
              记录故事事实、故事发生时间、关联章节与参与人物，并按故事时间形成剧情时间线。
            </div>
            <n-button
              size="small"
              type="primary"
              @click="router.push(`/novels/${novel.id}/plot-events`)"
            >
              进入剧情事件
            </n-button>
          </div>
        </n-card>

        <n-card title="创作工作台" size="small" class="world-entry">
          <div class="world-entry-body">
            <div class="world-entry-text">
              剧情导演生成结构化计划，审核重大剧情决定后由正文作者分段写作，
              草稿经你确认后才写入正式章节。
            </div>
            <n-button
              size="small"
              type="primary"
              @click="router.push(`/novels/${novel.id}/writing`)"
            >
              进入创作工作台
            </n-button>
          </div>
        </n-card>

        <n-card title="创作进度" size="small">
          <n-progress
            type="line"
            :percentage="
              novel.target_word_count
                ? Math.min(
                    100,
                    Math.round(
                      (novel.current_word_count / novel.target_word_count) * 100,
                    ),
                  )
                : 0
            "
            :height="10"
            indicator-placement="outside"
            processing
          />
          <div class="progress-hint">
            当前 {{ novel.current_word_count.toLocaleString() }} 字 / 目标
            {{ novel.target_word_count.toLocaleString() }} 字，按章节正文实际字数统计。
          </div>
        </n-card>

        <n-card title="项目信息" size="small">
          <n-descriptions :column="1" label-placement="left" bordered size="small">
            <n-descriptions-item label="小说 ID">
              <span class="mono">{{ novel.id }}</span>
            </n-descriptions-item>
            <n-descriptions-item label="创作状态">
              {{ NOVEL_STATUS_LABELS[novel.status] }}
            </n-descriptions-item>
            <n-descriptions-item label="创建时间">
              {{ formatDateTime(novel.created_at) }}
            </n-descriptions-item>
            <n-descriptions-item label="更新时间">
              {{ formatDateTime(novel.updated_at) }}
            </n-descriptions-item>
          </n-descriptions>
        </n-card>

        <div class="section-title">后续模块</div>
        <n-grid :x-gap="16" :y-gap="16" cols="1 s:2 m:4" responsive="screen">
          <n-grid-item v-for="module in futureModules" :key="module.title">
            <n-card size="small" embedded class="module-card">
              <div class="module-title">{{ module.title }}</div>
              <div class="module-desc">{{ module.desc }}</div>
              <n-tag size="tiny" round class="module-tag">尚未开放 · {{ module.phase }}</n-tag>
            </n-card>
          </n-grid-item>
        </n-grid>
      </template>

      <n-empty v-else description="暂无可显示的小说" />
    </n-spin>
  </div>
</template>

<style scoped>
.page {
  max-width: 1080px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
}

.header-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.hero-card {
  overflow: hidden;
}

.hero-cover {
  height: 96px;
  margin: -16px -16px 16px;
  background: linear-gradient(135deg, #3b5bdb 0%, #6741d9 100%);
  display: flex;
  align-items: center;
  padding: 0 24px;
}

.hero-letter {
  font-size: 46px;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.92);
  line-height: 1;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.novel-title {
  margin: 0;
  font-size: 24px;
  color: #fff;
}

.novel-subtitle {
  margin-top: 4px;
  font-size: 14px;
  color: rgba(255, 255, 255, 0.5);
}

.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
}

.muted {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.4);
}

.description {
  margin: 12px 0 0;
  font-size: 13px;
  line-height: 1.8;
  color: rgba(255, 255, 255, 0.65);
  white-space: pre-wrap;
}

.progress-hint {
  margin-top: 8px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.45);
}

.world-entry-body {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.world-entry-text {
  font-size: 13px;
  line-height: 1.7;
  color: rgba(255, 255, 255, 0.6);
  flex: 1;
  min-width: 200px;
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
}

.section-title {
  margin-top: 4px;
  font-size: 16px;
  font-weight: 600;
  color: #fff;
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
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
  min-height: 34px;
}

.module-tag {
  margin-top: 8px;
}
</style>
