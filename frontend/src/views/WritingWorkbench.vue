<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import {
  NAlert,
  NButton,
  NCard,
  NEmpty,
  NInput,
  NInputNumber,
  NModal,
  NProgress,
  NRadio,
  NRadioGroup,
  NSelect,
  NSpin,
  NSteps,
  NStep,
  NTag,
  useDialog,
  useMessage,
} from 'naive-ui'
import { extractError } from '../api/error'
import { listChapters, type ChapterSummary } from '../api/chapter'
import { useNovelStore } from '../stores/novels'
import { countWords } from '../api/chapter'
import {
  approveWritingPlan,
  cancelWritingSession,
  confirmWritingDraft,
  createWritingSession,
  generateWritingPlan,
  generateWritingSegment,
  getWritingSession,
  listWritingSessions,
  pauseWritingSession,
  regenerateWritingSegment,
  resolveWritingDecision,
  resumeWritingSession,
  deleteWritingSession,
  SEGMENT_STATUS_LABELS,
  updateWritingDraft,
  updateWritingPlan,
  WRITING_STATUS_LABELS,
  WRITING_STATUS_TYPES,
  type DraftSegment,
  type WritingDecision,
  type WritingSession,
  type WritingSessionStatus,
} from '../api/writing'

const route = useRoute()
const router = useRouter()
const store = useNovelStore()
const message = useMessage()
const dialog = useDialog()

const novelId = computed(() => String(route.params.id))
const novelTitle = ref('')

const chapters = ref<ChapterSummary[]>([])
const sessions = ref<WritingSession[]>([])
const selectedSessionId = ref<string | null>(null)
const active = ref<WritingSession | null>(null)
const loading = ref(false)
const busy = ref('')
const stageHint = ref('')

const showCreate = ref(false)
const createForm = ref({
  title: '',
  chapter_id: null as string | null,
  user_instruction: '',
  target_word_count: 3000,
})

const planExtra = ref('')
const showPlanEditor = ref(false)
const planJson = ref('')

const decisionDraft = ref<Record<string, { option: string | null; custom: string }>>({})

const draftTitle = ref('')
const draftContent = ref('')
const savedDraftContent = ref('')
const savedDraftTitle = ref('')
const maxTokens = ref(4096)
const confirmForm = ref({
  mode: 'new_chapter' as 'new_chapter' | 'replace_existing',
  chapter_title: '',
})

const dirty = computed(
  () => draftContent.value !== savedDraftContent.value || draftTitle.value !== savedDraftTitle.value,
)

const chapterOptions = computed(() => [
  { label: '新章节草稿（不关联已有章节）', value: '__new__' },
  ...chapters.value.map((c) => ({
    label: `第 ${c.chapter_number} 章 · ${c.title}`,
    value: c.id,
  })),
])

const plan = computed(() => active.value?.plan ?? null)
const decisions = computed<WritingDecision[]>(() => active.value?.decisions ?? [])
const draft = computed(() => active.value?.draft ?? null)

const stepIndex = computed(() => {
  const status = active.value?.status
  if (!status || status === 'planning' || status === 'failed') return 1
  if (status === 'awaiting_plan_approval') return 1
  if (status === 'writing' || status === 'paused_for_user') return 2
  if (status === 'draft_ready') return 3
  return 4
})

const unresolvedRequired = computed(() =>
  decisions.value.filter((d) => d.is_required && !d.resolved),
)

function syncDraftForm(data: WritingSession | null) {
  const d = data?.draft
  draftTitle.value = d?.title ?? ''
  draftContent.value = d?.content ?? ''
  savedDraftTitle.value = d?.title ?? ''
  savedDraftContent.value = d?.content ?? ''
}

function syncDecisions(data: WritingSession | null) {
  const next: Record<string, { option: string | null; custom: string }> = {}
  for (const decision of data?.decisions ?? []) {
    next[decision.decision_key] = {
      option: decision.selected_option,
      custom: decision.custom_answer,
    }
  }
  decisionDraft.value = next
}

async function loadBase() {
  try {
    const novel = await store.openNovel(novelId.value)
    novelTitle.value = novel.title
    chapters.value = (await listChapters(novelId.value)).data
    await loadSessions()
  } catch (error) {
    message.error(extractError(error, '加载小说信息失败'))
  }
}

async function loadSessions() {
  const { data } = await listWritingSessions(novelId.value)
  sessions.value = data
  if (!selectedSessionId.value && data.length) {
    selectedSessionId.value = data[0].id
  }
  if (selectedSessionId.value) {
    await loadSession(selectedSessionId.value)
  }
}

async function loadSession(sessionId: string) {
  loading.value = true
  try {
    const { data } = await getWritingSession(novelId.value, sessionId)
    active.value = data
    syncDraftForm(data)
    syncDecisions(data)
    confirmForm.value.chapter_title = data.draft?.title || data.title
    confirmForm.value.mode = 'new_chapter'
  } catch (error) {
    active.value = null
    message.error(extractError(error, '加载创作会话失败'))
  } finally {
    loading.value = false
  }
}

async function refreshAll() {
  await loadSessions()
  await loadBaseLists()
}

async function loadBaseLists() {
  const [chapterRes, sessionRes] = await Promise.all([
    listChapters(novelId.value),
    listWritingSessions(novelId.value),
  ])
  chapters.value = chapterRes.data
  sessions.value = sessionRes.data
}

onMounted(loadBase)

watch(selectedSessionId, (value) => {
  if (value) loadSession(value)
})

function selectSession(value: string) {
  selectedSessionId.value = value
}

async function createSession() {
  busy.value = 'create'
  try {
    const payload = {
      title: createForm.value.title,
      chapter_id:
        createForm.value.chapter_id === '__new__' ? null : createForm.value.chapter_id,
      user_instruction: createForm.value.user_instruction,
      target_word_count: createForm.value.target_word_count,
    }
    const { data } = await createWritingSession(novelId.value, payload)
    message.success('创作会话已创建')
    showCreate.value = false
    selectedSessionId.value = data.id
    await refreshAll()
    await loadSession(data.id)
  } catch (error) {
    message.error(extractError(error, '创建创作会话失败'))
  } finally {
    busy.value = ''
  }
}

async function runPlan() {
  if (!active.value) return
  busy.value = 'plan'
  stageHint.value = '剧情导演正在生成结构化计划…'
  try {
    await generateWritingPlan(novelId.value, active.value.id, {
      extra_instruction: planExtra.value,
      max_tokens: maxTokens.value,
    })
    message.success('剧情计划已生成，请审核')
    await refreshAll()
    await loadSession(active.value.id)
  } catch (error) {
    message.error(extractError(error, '生成剧情计划失败'))
    if (active.value) await loadSession(active.value.id)
  } finally {
    busy.value = ''
    stageHint.value = ''
  }
}

function openPlanEditor() {
  if (!plan.value) return
  planJson.value = JSON.stringify(
    {
      chapter_goal: plan.value.chapter_goal,
      opening: plan.value.opening,
      scenes: plan.value.scenes,
      character_actions: plan.value.character_actions,
      conflicts: plan.value.conflicts,
      plot_events: plan.value.plot_events,
      foreshadowing: plan.value.foreshadowing,
      ending: plan.value.ending,
      estimated_word_count: plan.value.estimated_word_count,
      major_decisions: plan.value.major_decisions,
    },
    null,
    2,
  )
  showPlanEditor.value = true
}

async function savePlanEdit() {
  if (!active.value) return
  let parsed: unknown
  try {
    parsed = JSON.parse(planJson.value)
  } catch {
    message.error('计划 JSON 格式不正确')
    return
  }
  busy.value = 'plan-save'
  try {
    await updateWritingPlan(novelId.value, active.value.id, parsed as never)
    showPlanEditor.value = false
    message.success('计划已更新')
    await loadSession(active.value.id)
  } catch (error) {
    message.error(extractError(error, '保存计划失败'))
  } finally {
    busy.value = ''
  }
}

async function resolveDecision(decision: WritingDecision, mode: 'option' | 'custom') {
  if (!active.value) return
  const state = decisionDraft.value[decision.decision_key]
  const payload =
    mode === 'custom'
      ? { custom_answer: state?.custom || '' }
      : { selected_option: state?.option || '' }
  busy.value = `decision-${decision.decision_key}`
  try {
    await resolveWritingDecision(
      novelId.value,
      active.value.id,
      decision.decision_key,
      payload,
    )
    message.success('重大决定已记录')
    await loadSession(active.value.id)
  } catch (error) {
    message.error(extractError(error, '记录决定失败'))
  } finally {
    busy.value = ''
  }
}

function approvePlan() {
  if (!active.value) return
  if (unresolvedRequired.value.length) {
    message.warning('仍有必需重大决定未解决')
    return
  }
  dialog.warning({
    title: '确认剧情计划',
    content: '确认后将进入正文写作阶段，计划会被锁定用于本次写作。',
    positiveText: '确认并开始写作',
    negativeText: '再看看',
    onPositiveClick: async () => {
      busy.value = 'approve'
      try {
        await approveWritingPlan(novelId.value, active.value!.id, draftTitle.value)
        message.success('已进入写作阶段')
        await refreshAll()
        await loadSession(active.value!.id)
      } catch (error) {
        message.error(extractError(error, '确认计划失败'))
      } finally {
        busy.value = ''
      }
    },
  })
}

async function generateNextSegment() {
  if (!active.value) return
  busy.value = 'segment'
  stageHint.value = '正文作者正在生成下一段…'
  try {
    const { data } = await generateWritingSegment(novelId.value, active.value.id, {
      max_tokens: maxTokens.value,
    })
    if (data.discarded_manual_edits) {
      message.warning('继续生成会用已生成段落重建草稿，先前的手工编辑已被替换')
    }
    message.success(`第 ${data.segment.sequence} 段已生成`)
    await loadSession(active.value.id)
    await loadBaseLists()
  } catch (error) {
    message.error(extractError(error, '段落生成失败，已保存的草稿不受影响'))
    await loadSession(active.value.id)
  } finally {
    busy.value = ''
    stageHint.value = ''
  }
}

function regenerateSegment(segment: DraftSegment) {
  if (!active.value) return
  dialog.warning({
    title: `重新生成第 ${segment.sequence} 段`,
    content: '该段现有内容会被新内容替换，其他段落保持不变。',
    positiveText: '重新生成',
    negativeText: '取消',
    onPositiveClick: async () => {
      busy.value = 'segment'
      stageHint.value = `正在重新生成第 ${segment.sequence} 段…`
      try {
        const { data } = await regenerateWritingSegment(
          novelId.value,
          active.value!.id,
          segment.sequence,
          { max_tokens: maxTokens.value },
        )
        message.success(`第 ${data.segment.sequence} 段已重新生成`)
        await loadSession(active.value!.id)
      } catch (error) {
        message.error(extractError(error, '重新生成失败'))
        await loadSession(active.value!.id)
      } finally {
        busy.value = ''
        stageHint.value = ''
      }
    },
  })
}

async function saveDraft() {
  if (!active.value) return
  busy.value = 'draft-save'
  try {
    await updateWritingDraft(novelId.value, active.value.id, {
      title: draftTitle.value,
      content: draftContent.value,
    })
    message.success('草稿已保存')
    await loadSession(active.value.id)
  } catch (error) {
    message.error(extractError(error, '保存草稿失败，请先保留本地内容'))
  } finally {
    busy.value = ''
  }
}

async function togglePause() {
  if (!active.value) return
  busy.value = 'pause'
  try {
    if (active.value.status === 'writing') {
      await pauseWritingSession(novelId.value, active.value.id)
      message.success('已暂停，未完成段落保持原状')
    } else {
      await resumeWritingSession(novelId.value, active.value.id)
      message.success('已继续写作')
    }
    await loadSession(active.value.id)
    await loadBaseLists()
  } catch (error) {
    message.error(extractError(error, '操作失败'))
  } finally {
    busy.value = ''
  }
}

function cancelSession() {
  if (!active.value) return
  dialog.warning({
    title: '取消创作会话',
    content: '取消后本次会话结束，已生成的草稿会保留但不能再继续写作。',
    positiveText: '确认取消',
    negativeText: '继续创作',
    onPositiveClick: async () => {
      try {
        await cancelWritingSession(novelId.value, active.value!.id)
        message.success('会话已取消')
        await refreshAll()
        await loadSession(active.value!.id)
      } catch (error) {
        message.error(extractError(error, '取消失败'))
      }
    },
  })
}

function confirmDraft() {
  if (!active.value) return
  dialog.warning({
    title: '确认写入正式章节',
    content:
      confirmForm.value.mode === 'replace_existing'
        ? '将用草稿内容覆盖原章节正文，此操作会更新章节标题、摘要与字数。'
        : '将另存为一个新章节，原章节内容保持不变。',
    positiveText: '确认写入',
    negativeText: '再检查一下',
    onPositiveClick: async () => {
      busy.value = 'confirm'
      try {
        await confirmWritingDraft(novelId.value, active.value!.id, {
          mode: confirmForm.value.mode,
          chapter_title: confirmForm.value.chapter_title,
        })
        message.success('已写入正式章节')
        savedDraftContent.value = draftContent.value
        savedDraftTitle.value = draftTitle.value
        await refreshAll()
        await loadSession(active.value!.id)
      } catch (error) {
        message.error(extractError(error, '写入章节失败'))
      } finally {
        busy.value = ''
      }
    },
  })
}

async function deleteSession() {
  const session = active.value
  if (!session) return
  dialog.warning({
    title: '删除创作会话',
    content: '会话、计划、决定与草稿都会被删除，已写入的正式章节不受影响。',
    positiveText: '确认删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await deleteWritingSession(novelId.value, session.id)
        message.success('会话已删除')
        if (selectedSessionId.value === session.id) {
          selectedSessionId.value = null
          active.value = null
        }
        await loadSessions()
        await loadBaseLists()
      } catch (error) {
        message.error(extractError(error, '删除失败'))
      }
    },
  })
}

function canGenerate(status?: WritingSessionStatus) {
  return status === 'writing'
}

function segmentLabel(segment: DraftSegment) {
  return `第 ${segment.sequence} 段 · ${SEGMENT_STATUS_LABELS[segment.status]}`
}

function onBeforeUnload(event: BeforeUnloadEvent) {
  if (dirty.value) {
    event.preventDefault()
    event.returnValue = ''
  }
}

onMounted(() => window.addEventListener('beforeunload', onBeforeUnload))
onBeforeUnmount(() => window.removeEventListener('beforeunload', onBeforeUnload))

onBeforeRouteLeave(() => {
  if (dirty.value) {
    return window.confirm('当前草稿有未保存的修改，确定离开吗？')
  }
  return true
})
</script>

<template>
  <div class="page">
    <div class="page-header">
      <n-button size="small" quaternary @click="router.push(`/novels/${novelId}`)">
        ← 返回小说详情
      </n-button>
      <div class="header-title">
        <span class="novel-name">{{ novelTitle }}</span>
        <n-tag size="small" :bordered="false">创作工作台</n-tag>
      </div>
    </div>

    <n-alert v-if="dirty" type="warning" :show-icon="true" class="dirty-alert">
      草稿有未保存的修改，离开页面前请保存。
    </n-alert>

    <n-card size="small">
      <div class="toolbar">
        <n-select
          class="session-select"
          :value="selectedSessionId"
          :options="sessions.map((s) => ({
            label: `${s.title}（${WRITING_STATUS_LABELS[s.status]}）`,
            value: s.id,
          }))"
          placeholder="选择创作会话"
          @update:value="selectSession"
        />
        <n-button size="small" type="primary" @click="showCreate = !showCreate">
          {{ showCreate ? '收起' : '新建创作会话' }}
        </n-button>
        <n-button
          v-if="active"
          size="small"
          quaternary
          type="error"
          @click="deleteSession"
        >
          删除会话
        </n-button>
      </div>

      <div v-if="showCreate" class="create-form">
        <n-input v-model:value="createForm.title" size="small" placeholder="会话标题（可留空）" />
        <n-select
          v-model:value="createForm.chapter_id"
          size="small"
          :options="chapterOptions"
          placeholder="从已有章节开始 / 新章节草稿"
        />
        <n-input
          v-model:value="createForm.user_instruction"
          size="small"
          type="textarea"
          :autosize="{ minRows: 2, maxRows: 4 }"
          placeholder="本次写作的整体要求，例如：节奏紧凑、保持冷峻语气"
        />
        <div class="create-row">
          <span class="label">目标字数</span>
          <n-input-number v-model:value="createForm.target_word_count" size="small" :min="500" :max="10000" :step="100" />
          <n-button size="small" type="primary" :loading="busy === 'create'" @click="createSession">
            创建
          </n-button>
        </div>
      </div>
    </n-card>

    <n-spin :show="loading">
      <n-empty v-if="!active" description="选择或新建一个创作会话开始" />

      <template v-else>
        <n-card size="small">
          <div class="session-head">
            <div>
              <div class="session-title">{{ active.title }}</div>
              <div class="muted">
                目标 {{ active.target_word_count }} 字 · 创建于
                {{ active.created_at.slice(0, 19).replace('T', ' ') }}
              </div>
            </div>
            <div class="session-actions">
              <n-tag size="small" :type="WRITING_STATUS_TYPES[active.status]">
                {{ WRITING_STATUS_LABELS[active.status] }}
              </n-tag>
              <n-button
                v-if="['writing', 'paused_for_user'].includes(active.status)"
                size="tiny"
                :loading="busy === 'pause'"
                @click="togglePause"
              >
                {{ active.status === 'writing' ? '暂停' : '继续' }}
              </n-button>
              <n-button
                v-if="!['completed', 'cancelled', 'failed'].includes(active.status)"
                size="tiny"
                type="error"
                quaternary
                @click="cancelSession"
              >
                取消会话
              </n-button>
            </div>
          </div>
          <n-alert v-if="active.error_message" type="error" class="mt8">
            {{ active.error_message }}
          </n-alert>
          <n-steps :current="stepIndex" size="small" class="steps">
            <n-step title="创作目标" description="小说、章节与写作要求" />
            <n-step title="剧情计划" description="生成、审核与重大决定" />
            <n-step title="分段写作" description="逐段生成并保存临时草稿" />
            <n-step title="确认写入" description="编辑后写入正式章节" />
          </n-steps>
        </n-card>

        <!-- 1. 剧情计划 -->
        <n-card size="small" title="剧情计划">
          <div class="toolbar">
            <n-input
              v-model:value="planExtra"
              size="small"
              placeholder="给剧情导演的补充要求（可选）"
              class="flex1"
            />
            <n-input-number v-model:value="maxTokens" size="small" :min="256" :max="32768" :step="128" class="token-input" />
            <n-button
              size="small"
              type="primary"
              :loading="busy === 'plan'"
              :disabled="!['planning', 'failed', 'awaiting_plan_approval'].includes(active.status)"
              @click="runPlan"
            >
              {{ plan ? '重新生成计划' : '生成计划' }}
            </n-button>
            <n-button v-if="plan" size="small" @click="openPlanEditor">编辑计划 JSON</n-button>
          </div>

          <div v-if="stageHint" class="stage-hint">{{ stageHint }}</div>
          <div v-if="plan" class="plan-body">
            <div class="plan-meta">
              版本 v{{ plan.version }} · 预计 {{ plan.estimated_word_count }} 字
            </div>
            <div class="plan-block">
              <span class="label">章节目标</span>
              <p>{{ plan.chapter_goal }}</p>
            </div>
            <div class="plan-block">
              <span class="label">开场</span>
              <p>{{ plan.opening }}</p>
            </div>
            <div class="plan-block">
              <span class="label">场景（{{ plan.scenes.length }}）</span>
              <div v-for="(scene, index) in plan.scenes" :key="index" class="scene-item">
                <div class="scene-title">{{ index + 1 }}. {{ scene.name }} · {{ scene.location }}</div>
                <div class="scene-line">人物：{{ scene.characters.join('、') }}</div>
                <div class="scene-line">目的：{{ scene.purpose }}</div>
                <div class="scene-line">行动：{{ scene.actions }}</div>
                <div class="scene-line">冲突：{{ scene.conflict }}</div>
                <div class="scene-line">结果：{{ scene.result }}</div>
                <div class="scene-line">衔接：{{ scene.transition }}</div>
              </div>
            </div>
            <div class="plan-block">
              <span class="label">结尾</span>
              <p>{{ plan.ending }}</p>
            </div>
            <div class="plan-block">
              <span class="label">伏笔 / 冲突</span>
              <p>{{ plan.foreshadowing.join('；') || '无' }}</p>
              <p class="muted">{{ plan.conflicts.join('；') || '' }}</p>
            </div>
            <div v-if="unresolvedRequired.length" class="mt8">
              <n-alert type="warning">
                仍有 {{ unresolvedRequired.length }} 项必需的<strong>重大剧情决定</strong>未解决，解决后才能开始写作。
              </n-alert>
            </div>
            <div class="plan-actions">
              <n-button
                size="small"
                type="primary"
                :loading="busy === 'approve'"
                :disabled="active.status !== 'awaiting_plan_approval' || !!unresolvedRequired.length"
                @click="approvePlan"
              >
                确认计划并开始写作
              </n-button>
            </div>
          </div>
          <n-empty v-else description="尚未生成剧情计划" />
        </n-card>

        <!-- 2. 重大决定 -->
        <n-card v-if="decisions.length" size="small" title="重大剧情决定">
          <div v-for="decision in decisions" :key="decision.decision_key" class="decision-item">
            <div class="decision-head">
              <span class="decision-title">{{ decision.title }}</span>
              <n-tag size="tiny" :type="decision.resolved ? 'success' : (decision.is_required ? 'error' : 'default')">
                {{ decision.resolved ? '已解决' : decision.is_required ? '必需' : '可选' }}
              </n-tag>
            </div>
            <div class="scene-line">{{ decision.description }}</div>
            <div v-if="decision.context" class="scene-line muted">背景：{{ decision.context }}</div>
            <div v-if="decision.consequences" class="scene-line muted">后果：{{ decision.consequences }}</div>
            <n-radio-group
              v-model:value="decisionDraft[decision.decision_key].option"
              class="decision-options"
              :disabled="active.status !== 'awaiting_plan_approval'"
            >
              <n-radio
                v-for="option in decision.options"
                :key="option"
                :value="option"
              >
                {{ option }}
                <span v-if="option === decision.recommended_option" class="muted">（导演推荐）</span>
              </n-radio>
            </n-radio-group>
            <div class="decision-custom">
              <n-input
                v-model:value="decisionDraft[decision.decision_key].custom"
                size="small"
                placeholder="自定义选择（可选）"
              />
              <n-button
                size="small"
                :loading="busy === `decision-${decision.decision_key}`"
                :disabled="active.status !== 'awaiting_plan_approval'"
                @click="resolveDecision(decision, 'option')"
              >
                按选项确认
              </n-button>
              <n-button
                size="small"
                :disabled="active.status !== 'awaiting_plan_approval'"
                @click="resolveDecision(decision, 'custom')"
              >
                使用自定义
              </n-button>
            </div>
          </div>
        </n-card>

        <!-- 3. 正文写作 -->
        <n-card v-if="draft" size="small" title="正文生成进度">
          <div class="progress-row">
            <n-progress
              type="line"
              :percentage="
                draft.progress.total_segments
                  ? Math.round((draft.progress.completed_segments / draft.progress.total_segments) * 100)
                  : 0
              "
              :height="8"
              indicator-placement="outside"
            />
            <div class="muted">
              已完成 {{ draft.progress.completed_segments }}/{{ draft.progress.total_segments }} 段 ·
              当前 {{ draft.word_count }} 字 / 目标 {{ draft.progress.target_word_count }} 字
            </div>
          </div>

          <div class="segment-list">
            <div v-for="segment in draft.segments" :key="segment.id" class="segment-item">
              <div class="segment-head">
                <span>{{ segmentLabel(segment) }}</span>
                <span class="muted">{{ segment.word_count }} 字</span>
                <n-button
                  size="tiny"
                  quaternary
                  :disabled="!canGenerate(active.status) || busy === 'segment'"
                  @click="regenerateSegment(segment)"
                >
                  重新生成
                </n-button>
              </div>
              <div v-if="segment.error_message" class="segment-error">{{ segment.error_message }}</div>
              <div v-if="segment.content" class="segment-preview">{{ segment.content }}</div>
            </div>
          </div>

          <div class="segment-actions">
            <n-button
              size="small"
              type="primary"
              :loading="busy === 'segment'"
              :disabled="!canGenerate(active.status) || draft.status === 'confirmed'"
              @click="generateNextSegment"
            >
              生成下一段
            </n-button>
            <span v-if="active.status === 'paused_for_user'" class="muted">已暂停，请点击“继续”后再生成</span>
          </div>
        </n-card>

        <!-- 4. 草稿编辑 -->
        <n-card v-if="draft" size="small" title="草稿编辑">
          <n-input v-model:value="draftTitle" size="small" placeholder="章节标题" class="mb8" />
          <n-input
            v-model:value="draftContent"
            type="textarea"
            :autosize="{ minRows: 8, maxRows: 22 }"
            placeholder="草稿正文"
          />
          <div class="draft-actions">
            <span class="muted">当前 {{ countWords(draftContent) }} 字（非空白字符）</span>
            <n-button size="small" :loading="busy === 'draft-save'" @click="saveDraft">保存草稿</n-button>
          </div>
        </n-card>

        <!-- 5. 确认写入 -->
        <n-card v-if="draft" size="small" title="确认写入正式章节">
          <div class="confirm-row">
            <n-radio-group v-model:value="confirmForm.mode">
              <n-radio value="new_chapter">另存为新章节（默认，保留原文）</n-radio>
              <n-radio v-if="active.chapter_id" value="replace_existing">覆盖原章节</n-radio>
            </n-radio-group>
            <n-input v-model:value="confirmForm.chapter_title" size="small" placeholder="章节标题" class="flex1" />
            <n-button
              size="small"
              type="primary"
              :loading="busy === 'confirm'"
              :disabled="draft.status === 'confirmed'"
              @click="confirmDraft"
            >
              确认写入章节
            </n-button>
          </div>
          <div class="muted mt8">
            写入后会话结束，AI 不会自行修改章节、人物、世界观或剧情事件。
          </div>
        </n-card>
      </template>
    </n-spin>

    <n-modal v-model:show="showPlanEditor" preset="card" title="编辑计划 JSON" class="plan-modal">
      <n-input v-model:value="planJson" type="textarea" :autosize="{ minRows: 14, maxRows: 26 }" />
      <template #footer>
        <div class="modal-actions">
          <n-button size="small" @click="showPlanEditor = false">取消</n-button>
          <n-button size="small" type="primary" :loading="busy === 'plan-save'" @click="savePlanEdit">
            保存计划
          </n-button>
        </div>
      </template>
    </n-modal>
  </div>
</template>

<style scoped>
.page {
  max-width: 1080px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.novel-name {
  font-size: 16px;
  font-weight: 600;
  color: #fff;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.session-select {
  min-width: 200px;
  flex: 1;
}

.create-form {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 12px;
}

.create-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.session-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
}

.session-title {
  font-size: 16px;
  font-weight: 600;
  color: #fff;
}

.session-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.steps {
  margin-top: 12px;
}

.muted {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.45);
}

.mt8 {
  margin-top: 8px;
  display: block;
}

.mb8 {
  margin-bottom: 8px;
}

.flex1 {
  flex: 1;
  min-width: 180px;
}

.token-input {
  width: 120px;
}

.stage-hint {
  margin-top: 8px;
  font-size: 12px;
  color: #f0b429;
}

.plan-body {
  margin-top: 10px;
}

.plan-meta {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.45);
  margin-bottom: 8px;
}

.plan-block {
  margin-bottom: 10px;
}

.label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.45);
}

.plan-block p {
  margin: 4px 0 0;
  font-size: 13px;
  line-height: 1.7;
  color: rgba(255, 255, 255, 0.75);
  white-space: pre-wrap;
}

.scene-item {
  border-left: 2px solid #3b5bdb;
  padding-left: 10px;
  margin-top: 8px;
}

.scene-title {
  font-size: 13px;
  font-weight: 600;
  color: #fff;
}

.scene-line {
  font-size: 12px;
  line-height: 1.7;
  color: rgba(255, 255, 255, 0.6);
}

.plan-actions {
  margin-top: 10px;
}

.decision-item {
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  padding: 10px;
  margin-bottom: 10px;
}

.decision-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.decision-title {
  font-size: 14px;
  font-weight: 600;
  color: #fff;
}

.decision-options {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: 8px;
}

.decision-custom {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
  flex-wrap: wrap;
}

.progress-row {
  margin-bottom: 10px;
}

.segment-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.segment-item {
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.03);
  padding: 8px 10px;
}

.segment-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.75);
  flex-wrap: wrap;
}

.segment-error {
  margin-top: 4px;
  font-size: 12px;
  color: #e88080;
}

.segment-preview {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.7;
  color: rgba(255, 255, 255, 0.55);
  max-height: 84px;
  overflow: hidden;
  white-space: pre-wrap;
}

.segment-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 10px;
  flex-wrap: wrap;
}

.draft-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: 8px;
  flex-wrap: wrap;
}

.confirm-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.plan-modal {
  width: 760px;
  max-width: 92vw;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.dirty-alert {
  margin-bottom: 0;
}

@media (max-width: 640px) {
  .page {
    gap: 10px;
  }

  .steps {
    overflow-x: auto;
  }

  .confirm-row,
  .decision-custom,
  .draft-actions {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
