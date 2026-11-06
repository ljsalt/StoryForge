<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NButton, NSpin, NTag, useMessage } from 'naive-ui'
import { getChapter, type Chapter } from '../api/chapter'
import { extractError } from '../api/error'
import ContinuityCheckPanel from '../components/continuity/ContinuityCheckPanel.vue'
import MemoryProposalList from '../components/continuity/MemoryProposalList.vue'

const route = useRoute()
const router = useRouter()
const message = useMessage()

const novelId = ref(String(route.params.novelId || ''))
const chapterId = ref(String(route.params.chapterId || ''))
const chapter = ref<Chapter | null>(null)
const loading = ref(false)
const pageError = ref('')

async function load() {
  loading.value = true
  pageError.value = ''
  try {
    chapter.value = (await getChapter(novelId.value, chapterId.value)).data
  } catch (error) {
    pageError.value = extractError(error, '加载章节失败')
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(
  () => [route.params.novelId, route.params.chapterId],
  () => {
    novelId.value = String(route.params.novelId || '')
    chapterId.value = String(route.params.chapterId || '')
    load()
  },
)
</script>

<template>
  <div class="page">
    <n-spin :show="loading">
      <template v-if="pageError">
        <div class="page-error">
          <n-tag type="error" :bordered="false">{{ pageError }}</n-tag>
          <n-button size="small" @click="router.push(`/novels/${novelId}/chapters`)">
            返回章节管理
          </n-button>
        </div>
      </template>
      <template v-else-if="chapter">
        <div class="page-header">
          <div class="header-left">
            <n-button size="small" quaternary @click="router.push(`/novels/${novelId}/chapters`)">
              ← 返回章节管理
            </n-button>
            <div>
              <h2 class="page-title">
                连续性与记忆 · 第 {{ chapter.chapter_number }} 章 {{ chapter.title }}
              </h2>
              <div class="page-sub">
                AI 只生成检查报告与更新提案，所有正式数据修改都必须经过人工审核。
              </div>
            </div>
          </div>
        </div>

        <div class="panels">
          <ContinuityCheckPanel :novel-id="novelId" :chapter-id="chapterId" />
          <MemoryProposalList :novel-id="novelId" :chapter-id="chapterId" />
        </div>
      </template>
    </n-spin>
  </div>
</template>

<style scoped>
.page {
  max-width: 1180px;
  margin: 0 auto;
  padding: 16px;
}
.page-header {
  margin-bottom: 16px;
}
.header-left {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  flex-wrap: wrap;
}
.page-title {
  margin: 0;
  font-size: 20px;
}
.page-sub {
  margin-top: 4px;
  font-size: 12px;
  color: var(--sf-text-tertiary, #888);
}
.page-error {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 40px 0;
  justify-content: center;
}
.panels {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  align-items: start;
}
@media (max-width: 900px) {
  .panels {
    grid-template-columns: 1fr;
  }
}
</style>
