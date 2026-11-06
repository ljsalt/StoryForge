<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  NAlert,
  NButton,
  NCard,
  NEmpty,
  NInput,
  NModal,
  NSelect,
  NSpin,
  NTag,
  useDialog,
  useMessage,
} from 'naive-ui'
import { listChapters, type ChapterSummary } from '../api/chapter'
import { createContinuityCheck, createMemoryBatch } from '../api/continuity'
import { extractError } from '../api/error'
import { listModels, type ModelItem } from '../api/models'
import { type NovelDetail } from '../api/novels'
import {
  SESSION_STATUS_LABELS,
  SESSION_STATUS_TYPES,
  confirmQuickWritingSession,
  createQuickWritingSession,
  discardQuickWritingSession,
  generateQuickWritingSegment,
  getQuickWritingMeta,
  listQuickWritingSessions,
  listWritingPresets,
  previewQuickWritingContext,
  updateQuickWritingContent,
  updateQuickWritingSession,
  type QuickWritingConfirmResult,
  type QuickWritingGenerateResult,
  type QuickWritingMeta,
  type QuickWritingSession,
  type QuickWritingSessionCreate,
  type QuickWritingSessionUpdate,
  type WritingPreset,
} from '../api/quickWriting'
import QuickWritingPanel from '../components/quick-writing/QuickWritingPanel.vue'
import WritingPresetManager from '../components/quick-writing/WritingPresetManager.vue'
import WritingReader from '../components/quick-writing/WritingReader.vue'
import WritingSettings from '../components/quick-writing/WritingSettings.vue'
import { useNovelStore } from '../stores/novels'

const route = useRoute()
const router = useRouter()
const store = useNovelStore()
const message = useMessage()
const dialog = useDialog()

const novel = ref<NovelDetail | null>(null)
const novelId = computed(() => String(route.params.novelId || ''))

const sessions = ref<QuickWritingSession[]>([])
const activeId = ref<string | null>(null)
const creating = ref(false)
const presets = ref<WritingPreset[]>([])
const models = ref<ModelItem[]>([])
const meta = ref<QuickWritingMeta | null>(null)
const chapters = ref<ChapterSummary[]>([])

const loading = ref(false)
const busy = ref<'' | 'create' | 'generate' | 'save' | 'settings' | 'confirm' | 'discard'>('')
const requirement = ref('')
const readerSeq = ref<number | null>(null)
const lastGeneration = ref<QuickWritingGenerateResult | null>(null)
const lastConfirmed = ref<QuickWritingConfirmResult | null>(null)
const backgroundNotice = ref('')

const showPresetManager = ref(false)
const showConfirm = ref(false)
const showContextPreview = ref(false)
const contextPreview = ref<Awaited<ReturnType<typeof previewQuickWritingContext>>['data'] | null>(null)
const confirmForm = ref({
  mode: 'new_chapter' as 'new_chapter' | 'replace_existing',
  chapter_title: '',
  summary: '',
})

const session = computed(
  () => sessions.value.find((item) => item.id === activeId.value) || null,
)
const activeSessions = computed(() => sessions.value)
const confirmedSession = computed(() =>
  session.value ? session.value.status === 'confirmed' : false,
)
const readonly = computed(() =>
  session.value ? ['confirmed', 'discarded'].includes(session.value.status) : true,
)

const lastCompletedSeq = computed(() => {
  const segments = session.value?.segments || []
  const completed = segments.filter((item) => item.status === 'completed')
  return completed.length ? completed[completed.length - 1].seq : null
})

const rewriteSeq = computed(() => readerSeq.value || lastCompletedSeq.value)

const sessionOptions = computed(() =>
  activeSessions.value.map((item) => ({
    label: `${item.title || '未命名章节'} · ${SESSION_STATUS_LABELS[item.status]}`,
    value: item.id,
  })),
)

function replaceSession(updated: QuickWritingSession) {
  const index = sessions.value.findIndex((item) => item.id === updated.id)
  if (index >= 0) sessions.value[index] = updated
  else sessions.value.unshift(updated)
}

function applySession(updated: QuickWritingSession) {
  replaceSession(updated)
  activeId.value = updated.id
  requirement.value = updated.user_requirement
  readerSeq.value = null
}

async function refreshSession() {
  if (!session.value) return
  const list = (await listQuickWritingSessions(novelId.value)).data
  sessions.value = list
  const current = list.find((item) => item.id === activeId.value)
  if (!current) return
  requirement.value = current.user_requirement
}

async function loadSessions(preferId?: string) {
  sessions.value = (await listQuickWritingSessions(novelId.value)).data
  const draft = sessions.value.find((item) =>
    ['drafting', 'ready', 'failed'].includes(item.status),
  )
  const fallback = sessions.value.find((item) => item.status === 'confirmed')
  const next =
    (preferId && sessions.value.some((item) => item.id === preferId) && preferId) ||
    (activeId.value && sessions.value.some((item) => item.id === activeId.value)
      ? activeId.value
      : null) ||
    draft?.id ||
    fallback?.id ||
    null
  activeId.value = next
  creating.value = !next
  requirement.value = next
    ? sessions.value.find((item) => item.id === next)?.user_requirement || ''
    : ''
}

async function loadAll() {
  loading.value = true
  try {
    const [novelData, presetRes, modelRes, metaRes, chapterRes] = await Promise.all([
      store.openNovel(novelId.value),
      listWritingPresets(true),
      listModels(),
      getQuickWritingMeta(),
      listChapters(novelId.value),
    ])
    novel.value = novelData
    presets.value = presetRes.data
    models.value = modelRes.data
    meta.value = metaRes.data
    chapters.value = chapterRes.data
    await loadSessions()
  } catch (err) {
    message.error(extractError(err, '加载快速写作数据失败'))
  } finally {
    loading.value = false
  }
}

async function createSession(payload: QuickWritingSessionCreate) {
  busy.value = 'create'
  try {
    const created = (await createQuickWritingSession(novelId.value, payload)).data
    sessions.value.unshift(created)
    applySession(created)
    creating.value = false
    message.success('已创建快速写作会话，可以直接生成正文')
  } catch (err) {
    message.error(extractError(err, '创建快速写作会话失败'))
  } finally {
    busy.value = ''
  }
}

async function ensureRequirementSaved() {
  if (!session.value) return
  const next = requirement.value.trim()
  if (next === session.value.user_requirement) return
  const updated = (
    await updateQuickWritingSession(novelId.value, session.value.id, {
      user_requirement: next,
    })
  ).data
  replaceSession(updated)
}

async function generate() {
  if (!session.value) return
  busy.value = 'generate'
  lastGeneration.value = null
  try {
    await ensureRequirementSaved()
    const result = (
      await generateQuickWritingSegment(novelId.value, session.value.id, {})
    ).data
    replaceSession(result.session)
    lastGeneration.value = result
    message.success(`第 ${result.segment_seq} 段生成完成`)
  } catch (err) {
    message.error(extractError(err, '生成失败，已完成内容已保留，可重试继续'))
    await refreshSession().catch(() => undefined)
  } finally {
    busy.value = ''
  }
}

async function rewrite() {
  if (!session.value || !rewriteSeq.value) return
  busy.value = 'generate'
  lastGeneration.value = null
  try {
    await ensureRequirementSaved()
    const result = (
      await generateQuickWritingSegment(novelId.value, session.value.id, {
        seq: rewriteSeq.value,
      })
    ).data
    replaceSession(result.session)
    lastGeneration.value = result
    if (result.discarded_manual_edits) {
      message.warning('重写段落已重建正文，先前的手工编辑被覆盖')
    } else {
      message.success(`第 ${result.segment_seq} 段已重写`)
    }
  } catch (err) {
    message.error(extractError(err, '重写失败，已保留原正文'))
    await refreshSession().catch(() => undefined)
  } finally {
    busy.value = ''
  }
}

async function saveContent(content: string) {
  if (!session.value) return
  busy.value = 'save'
  try {
    const updated = (
      await updateQuickWritingContent(novelId.value, session.value.id, content)
    ).data
    replaceSession(updated)
    message.success('草稿已保存')
  } catch (err) {
    message.error(extractError(err, '保存草稿失败'))
  } finally {
    busy.value = ''
  }
}

async function saveSettings(payload: QuickWritingSessionUpdate) {
  if (!session.value) return
  busy.value = 'settings'
  try {
    const updated = (
      await updateQuickWritingSession(novelId.value, session.value.id, payload)
    ).data
    replaceSession(updated)
    if (payload.user_requirement === undefined) {
      // 只更新配置时同步要求，避免覆盖正在输入的临时要求
      requirement.value = updated.user_requirement
    }
    message.success('写作设置已保存')
  } catch (err) {
    message.error(extractError(err, '保存写作设置失败'))
  } finally {
    busy.value = ''
  }
}

function openConfirm() {
  if (!session.value) return
  confirmForm.value = {
    mode: session.value.chapter_id ? 'replace_existing' : 'new_chapter',
    chapter_title: session.value.title,
    summary: '',
  }
  showConfirm.value = true
}

async function confirmSave() {
  if (!session.value) return
  busy.value = 'confirm'
  try {
    const result = (
      await confirmQuickWritingSession(novelId.value, session.value.id, {
        mode: confirmForm.value.mode,
        chapter_title: confirmForm.value.chapter_title.trim(),
        summary: confirmForm.value.summary.trim(),
      })
    ).data
    replaceSession(result.session)
    lastConfirmed.value = result
    showConfirm.value = false
    chapters.value = (await listChapters(novelId.value)).data
    message.success(`已保存为第 ${result.chapter.chapter_number} 章《${result.chapter.title}》`)

    const chapterId = result.chapter.id
    const tasks: Promise<unknown>[] = []
    if (result.reminders.auto_continuity) {
      tasks.push(createContinuityCheck(novelId.value, chapterId))
    }
    if (result.reminders.auto_memory) {
      tasks.push(createMemoryBatch(novelId.value, chapterId))
    }
    if (tasks.length) {
      backgroundNotice.value = '正在后台整理连续性问题与记忆提案，不会自动修改正式记忆。'
      Promise.all(tasks)
        .then(() => {
          backgroundNotice.value = '后台整理完成，可在连续性页面查看并逐条审核。'
        })
        .catch((err) => {
          backgroundNotice.value = `后台整理失败：${extractError(err, '未知错误')}`
        })
    }
  } catch (err) {
    message.error(extractError(err, '保存为正式章节失败'))
  } finally {
    busy.value = ''
  }
}

function discard() {
  if (!session.value) return
  dialog.warning({
    title: '放弃这个写作会话？',
    content: '正文草稿会保留为已放弃状态，不会写入正式章节。',
    positiveText: '放弃会话',
    negativeText: '取消',
    onPositiveClick: async () => {
      busy.value = 'discard'
      try {
        const updated = (
          await discardQuickWritingSession(novelId.value, session.value!.id)
        ).data
        replaceSession(updated)
        message.success('已放弃该会话')
      } catch (err) {
        message.error(extractError(err, '放弃会话失败'))
      } finally {
        busy.value = ''
      }
    },
  })
}

async function previewContext() {
  if (!session.value) return
  try {
    contextPreview.value = (
      await previewQuickWritingContext(novelId.value, session.value.id)
    ).data
    showContextPreview.value = true
  } catch (err) {
    message.error(extractError(err, '预览上下文失败'))
  }
}

async function onPresetSelect(presetId: string) {
  await saveSettings({ preset_id: presetId })
  presets.value = (await listWritingPresets(true)).data
}

async function onPresetsChanged() {
  presets.value = (await listWritingPresets(true)).data
}

function selectSession(id: string) {
  activeId.value = id
  creating.value = false
  lastGeneration.value = null
  lastConfirmed.value = null
  backgroundNotice.value = ''
  const target = sessions.value.find((item) => item.id === id)
  requirement.value = target?.user_requirement || ''
  readerSeq.value = null
}

function startNew() {
  creating.value = true
  activeId.value = null
  requirement.value = ''
  lastGeneration.value = null
  lastConfirmed.value = null
  backgroundNotice.value = ''
}

function goBack() {
  router.push(`/novels/${novelId.value}`)
}

function openContinuity() {
  if (!lastConfirmed.value) return
  router.push({
    name: 'chapter-continuity',
    params: {
      novelId: novelId.value,
      chapterId: lastConfirmed.value.chapter.id,
    },
  })
}

watch(
  () => route.params.novelId,
  (value) => {
    if (value) loadAll()
  },
)

onMounted(loadAll)
</script>

<template>
  <div class="quick-page">
    <n-spin :show="loading">
      <div class="page-head">
        <div class="head-left">
          <n-button size="small" quaternary @click="goBack">返回</n-button>
          <div class="head-title">
            <span class="novel-name">{{ novel?.title || '快速写作' }}</span>
            <span class="page-name">快速写作</span>
          </div>
        </div>
        <div class="head-actions">
          <n-select
            v-if="sessions.length"
            :value="activeId"
            size="small"
            class="session-select"
            :options="sessionOptions"
            placeholder="选择写作会话"
            @update:value="selectSession"
          />
          <n-button size="small" @click="showPresetManager = true">写作预设</n-button>
          <n-button size="small" type="primary" @click="startNew">新建写作</n-button>
        </div>
      </div>

      <n-alert v-if="lastConfirmed" type="success" :bordered="false" class="top-alert">
        已保存为第 {{ lastConfirmed.chapter.chapter_number }} 章《{{ lastConfirmed.chapter.title }}》。
        <template v-if="backgroundNotice">{{ backgroundNotice }}</template>
        <template v-else>可手动进行连续性检查与记忆提取，正式记忆不会被自动修改。</template>
        <div class="alert-actions">
          <n-button size="tiny" @click="openContinuity">查看连续性</n-button>
        </div>
      </n-alert>

      <n-alert v-if="lastGeneration" type="info" :bordered="false" class="top-alert">
        本次上下文约 {{ lastGeneration.context_estimated_tokens }} tokens（预算
        {{ lastGeneration.context_token_budget }}），模型
        {{ lastGeneration.model || '任务默认' }}，来源
        {{ lastGeneration.resolved_from || 'task' }}。
        <template v-if="lastGeneration.context_omitted_sections.length">
          已按预算省略：{{ lastGeneration.context_omitted_sections.map((item) => item.title).join('、') }}
        </template>
      </n-alert>

      <QuickWritingPanel
        v-if="!session"
        :presets="presets"
        :models="models"
        :meta="meta"
        :chapters="chapters"
        :submitting="busy === 'create'"
        @create="createSession"
        @manage-presets="showPresetManager = true"
      />

      <template v-else>
        <WritingSettings
          :session="session"
          :presets="presets"
          :models="models"
          :meta="meta"
          :saving="busy === 'settings'"
          @save="saveSettings"
          @manage-presets="showPresetManager = true"
          @preview-context="previewContext"
        />

        <n-card size="small" class="requirement-card" :bordered="false">
          <div class="requirement-head">
            <span class="requirement-title">本次写作要求</span>
            <n-tag size="tiny" :type="SESSION_STATUS_TYPES[session.status]">
              {{ SESSION_STATUS_LABELS[session.status] }}
            </n-tag>
          </div>
          <n-input
            v-model:value="requirement"
            type="textarea"
            :autosize="{ minRows: 3, maxRows: 10 }"
            :disabled="readonly || busy === 'generate'"
            placeholder="描述你想写的内容，例如：继续上一章，描写主角与对手的冲突，重点写环境和心理活动。"
          />
          <div class="requirement-hint">
            临时要求只影响当前会话，不会修改写作预设。
          </div>
          <div class="requirement-actions">
            <n-button
              type="primary"
              :loading="busy === 'generate'"
              :disabled="readonly || !requirement.trim()"
              @click="generate"
            >
              {{ session.content ? '继续生成' : '生成正文' }}
            </n-button>
            <n-button
              v-if="rewriteSeq && session.content"
              :disabled="readonly || busy === 'generate'"
              @click="rewrite"
            >
              重写第 {{ rewriteSeq }} 段
            </n-button>
            <span v-if="busy === 'generate'" class="generating-hint">
              正在生成第 {{ (session.segments?.length || 0) + 1 }} 段，长正文可能需要数分钟…
            </span>
          </div>
        </n-card>

        <n-card size="small" class="reader-card" :bordered="false">
          <WritingReader
            :session="session"
            :saving="busy === 'save'"
            @save-content="saveContent"
            @view="readerSeq = $event"
          />
          <div v-if="!readonly" class="reader-footer">
            <n-button
              size="small"
              type="primary"
              :disabled="!session.content.trim()"
              @click="openConfirm"
            >
              保存为正式章节
            </n-button>
            <n-button size="small" quaternary type="error" @click="discard">
              放弃会话
            </n-button>
          </div>
          <div v-else-if="confirmedSession && session.chapter_id" class="reader-footer">
            <n-button size="small" @click="openContinuity">查看连续性</n-button>
          </div>
        </n-card>
      </template>

      <n-empty
        v-if="!session && !creating && sessions.length"
        description="选择一个写作会话继续，或新建快速写作"
        size="small"
        class="empty"
      />
    </n-spin>

    <WritingPresetManager
      v-model:show="showPresetManager"
      :novel-id="novelId"
      :selected-id="session?.preset_id"
      @changed="onPresetsChanged"
      @select="onPresetSelect"
    />

    <n-modal
      v-model:show="showConfirm"
      preset="card"
      title="保存为正式章节"
      class="confirm-modal"
      :bordered="false"
    >
      <div class="confirm-body">
        <div class="field">
          <label>保存方式</label>
          <n-select
            v-model:value="confirmForm.mode"
            size="small"
            :options="[
              { label: '另存为新章节（不会覆盖其它章节）', value: 'new_chapter' },
              ...(session?.chapter_id
                ? [{ label: '覆盖当前关联章节', value: 'replace_existing' }]
                : []),
            ]"
          />
        </div>
        <div class="field">
          <label>章节标题</label>
          <n-input v-model:value="confirmForm.chapter_title" size="small" placeholder="留空则使用会话标题" />
        </div>
        <div class="field">
          <label>章节摘要（可选）</label>
          <n-input
            v-model:value="confirmForm.summary"
            type="textarea"
            :autosize="{ minRows: 2, maxRows: 4 }"
            placeholder="留空则自动截取正文开头"
          />
        </div>
        <div class="confirm-hint">
          保存后可在连续性页面手动检查连续性问题、审核记忆提案。正式记忆不会被自动修改。
        </div>
      </div>
      <template #footer>
        <div class="modal-actions">
          <n-button size="small" @click="showConfirm = false">取消</n-button>
          <n-button
            size="small"
            type="primary"
            :loading="busy === 'confirm'"
            :disabled="!session?.content.trim()"
            @click="confirmSave"
          >
            确认保存
          </n-button>
        </div>
      </template>
    </n-modal>

    <n-modal
      v-model:show="showContextPreview"
      preset="card"
      title="上下文预览"
      class="confirm-modal"
      :bordered="false"
    >
      <div v-if="contextPreview" class="preview-body">
        <div class="preview-meta">
          约 {{ contextPreview.estimated_tokens }} tokens / 预算
          {{ contextPreview.token_budget }}
        </div>
        <div v-for="section in contextPreview.sections" :key="section.key" class="preview-item">
          <div class="preview-title">{{ section.title }}（{{ section.tokens }} tokens）</div>
          <div class="preview-text">{{ section.content }}</div>
        </div>
        <div v-if="contextPreview.omitted_sections.length" class="preview-omitted">
          因预算省略：{{ contextPreview.omitted_sections.map((item) => item.title).join('、') }}
        </div>
      </div>
    </n-modal>
  </div>
</template>

<style scoped>
.quick-page {
  max-width: 1040px;
  margin: 0 auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  box-sizing: border-box;
  width: 100%;
}
.page-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
}
.head-left {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.head-title {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.novel-name {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.45);
  word-break: break-word;
}
.page-name {
  font-size: 18px;
  font-weight: 600;
  color: #fff;
}
.head-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.session-select {
  min-width: 200px;
}
.top-alert {
  margin-top: 4px;
}
.alert-actions {
  margin-top: 6px;
}
.requirement-card,
.reader-card {
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.08);
}
.requirement-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 6px;
}
.requirement-title {
  font-size: 15px;
  font-weight: 600;
  color: #fff;
}
.requirement-hint,
.generating-hint,
.confirm-hint {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.45);
  margin-top: 6px;
  line-height: 1.6;
  word-break: break-word;
}
.requirement-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 10px;
}
.reader-footer {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}
.confirm-modal {
  width: min(560px, 92vw);
}
.confirm-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.field label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.45);
}
.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
.preview-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 60vh;
  overflow-y: auto;
}
.preview-meta,
.preview-omitted {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
}
.preview-item {
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  padding: 8px;
}
.preview-title {
  font-size: 12px;
  color: #63e2b7;
  margin-bottom: 4px;
}
.preview-text {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  max-height: 140px;
  overflow-y: auto;
}
.empty {
  padding: 32px 0;
}
@media (max-width: 640px) {
  .quick-page {
    padding: 12px;
  }
  .head-actions {
    width: 100%;
  }
  .session-select {
    flex: 1 1 100%;
    min-width: 0;
    width: 100%;
  }
  .head-actions :deep(.n-button) {
    flex: 1 1 auto;
  }
}
</style>
