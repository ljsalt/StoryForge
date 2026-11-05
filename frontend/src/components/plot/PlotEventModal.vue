<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import {
  NButton,
  NDivider,
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
  NModal,
  NSelect,
  NSpace,
  useMessage,
} from 'naive-ui'
import { extractError } from '../../api/error'
import { listWorldEntries } from '../../api/world'
import {
  PLOT_IMPORTANCE_OPTIONS,
  type PlotEvent,
  type PlotImportance,
} from '../../api/plotEvent'
import { useChapterStore } from '../../stores/chapter'
import { useCharacterStore } from '../../stores/character'
import { usePlotEventStore } from '../../stores/plotEvent'

const props = defineProps<{
  show: boolean
  novelId: string
  event?: PlotEvent | null
  defaultChapterId?: string | null
}>()
const emit = defineEmits<{ 'update:show': [v: boolean]; saved: [] }>()

const message = useMessage()
const characterStore = useCharacterStore()
const chapterStore = useChapterStore()
const plotStore = usePlotEventStore()

const saving = ref(false)
const locationOptions = ref<{ label: string; value: string }[]>([])

const form = reactive({
  title: '',
  description: '',
  eventType: '',
  storyTime: '',
  chapterId: null as string | null,
  locationId: null as string | null,
  locationName: '',
  importance: 'normal' as PlotImportance,
  sequence: 0,
})

const participants = reactive<
  { character_id: string | null; participant_role: string; description: string }[]
>([])

const isEdit = computed(() => Boolean(props.event))

const characterOptions = computed(() =>
  characterStore.characters.map((c) => ({ label: c.name, value: c.id })),
)
const chapterOptions = computed(() =>
  chapterStore.chapters.map((c) => ({
    label: `第 ${c.chapter_number} 章 ${c.title}`,
    value: c.id,
  })),
)

async function loadOptions() {
  try {
    if (!characterStore.characters.length || characterStore.novelId !== props.novelId) {
      await characterStore.load(props.novelId)
    }
    if (!chapterStore.chapters.length || chapterStore.novelId !== props.novelId) {
      await chapterStore.load(props.novelId)
    }
    const { data } = await listWorldEntries(props.novelId)
    locationOptions.value = data.map((entry) => ({ label: entry.name, value: entry.id }))
  } catch {
    // 选项加载失败不阻塞事件编辑；仍可手填地点名称
  }
}

function resetForm() {
  form.title = ''
  form.description = ''
  form.eventType = ''
  form.storyTime = ''
  form.chapterId = props.defaultChapterId || null
  form.locationId = null
  form.locationName = ''
  form.importance = 'normal'
  form.sequence = 0
  participants.splice(0, participants.length)
}

async function init() {
  if (props.event) {
    const event = props.event
    form.title = event.title
    form.description = event.description
    form.eventType = event.event_type
    form.storyTime = event.story_time || ''
    form.chapterId = event.chapter_id
    form.locationId = event.location_id
    form.locationName = event.location_name
    form.importance = event.importance
    form.sequence = event.sequence
    participants.splice(0, participants.length)
    for (const p of event.participants) {
      participants.push({
        character_id: p.character_id,
        participant_role: p.participant_role,
        description: p.description,
      })
    }
  } else {
    resetForm()
  }
  await loadOptions()
}

watch(
  () => [props.show, props.event, props.novelId] as const,
  ([show]) => {
    if (show) init()
  },
  { immediate: true },
)

function addParticipant() {
  participants.push({ character_id: null, participant_role: '', description: '' })
}

function removeParticipant(index: number) {
  participants.splice(index, 1)
}

function onLocationChange(value: string | null) {
  form.locationId = value
  const matched = locationOptions.value.find((item) => item.value === value)
  if (matched) form.locationName = matched.label
}

function close() {
  emit('update:show', false)
}

async function submit() {
  if (!form.title.trim()) {
    message.error('事件标题不能为空')
    return
  }
  const participantPayload = participants
    .filter((p) => p.character_id)
    .map((p) => ({
      character_id: p.character_id as string,
      participant_role: p.participant_role.trim(),
      description: p.description.trim(),
    }))
  const ids = participantPayload.map((p) => p.character_id)
  if (new Set(ids).size !== ids.length) {
    message.error('同一人物不能重复参与同一事件')
    return
  }

  const payload = {
    title: form.title.trim(),
    description: form.description,
    event_type: form.eventType.trim(),
    story_time: form.storyTime.trim() || null,
    chapter_id: form.chapterId,
    location_id: form.locationId,
    location_name: form.locationName.trim(),
    importance: form.importance,
    sequence: form.sequence ?? 0,
    participants: participantPayload,
  }

  saving.value = true
  try {
    if (props.event) {
      await plotStore.update(props.event.id, payload)
      message.success('事件已更新')
    } else {
      await plotStore.create(payload)
      message.success('事件已创建')
    }
    emit('saved')
    close()
    await plotStore.fetchEvents()
  } catch (error) {
    message.error(extractError(error, '保存剧情事件失败'))
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <n-modal
    :show="show"
    preset="card"
    :title="isEdit ? '编辑剧情事件' : '新建剧情事件'"
    :style="{ width: 'min(760px, calc(100vw - 16px))' }"
    :mask-closable="false"
    @update:show="(v: boolean) => { if (!v) close() }"
  >
    <n-form label-placement="top" :show-feedback="false">
      <n-form-item label="事件标题（必填）">
        <n-input v-model:value="form.title" maxlength="200" placeholder="例如：林远发现顾长生隐瞒身世" />
      </n-form-item>
      <n-form-item label="事件描述">
        <n-input
          v-model:value="form.description"
          type="textarea"
          :autosize="{ minRows: 3, maxRows: 10 }"
          maxlength="20000"
          placeholder="描述具体发生了什么（这是故事事实，不是人物关系变化）"
        />
      </n-form-item>
      <div class="form-grid">
        <n-form-item label="事件类型（可自定义）">
          <n-input v-model:value="form.eventType" maxlength="80" placeholder="例如：转折 / 战斗 / 伏笔" />
        </n-form-item>
        <n-form-item label="重要程度">
          <n-select v-model:value="form.importance" :options="PLOT_IMPORTANCE_OPTIONS" />
        </n-form-item>
        <n-form-item label="事件顺序">
          <n-input-number v-model:value="form.sequence" :min="0" />
        </n-form-item>
      </div>
      <div class="form-grid">
        <n-form-item label="故事发生时间（故事世界内）">
          <n-input v-model:value="form.storyTime" maxlength="100" placeholder="例如：修仙历 3021 年 / 第三天" />
        </n-form-item>
        <n-form-item label="关联章节（可空）">
          <n-select
            v-model:value="form.chapterId"
            :options="chapterOptions"
            clearable
            filterable
            placeholder="选择章节"
          />
        </n-form-item>
      </div>
      <div class="form-grid">
        <n-form-item label="关联世界观地点（可空）">
          <n-select
            :value="form.locationId"
            :options="locationOptions"
            clearable
            filterable
            placeholder="选择地点条目"
            @update:value="onLocationChange"
          />
        </n-form-item>
        <n-form-item label="地点名称（可手填）">
          <n-input v-model:value="form.locationName" maxlength="200" placeholder="例如：无名山谷" />
        </n-form-item>
      </div>

      <n-divider style="margin: 8px 0 12px">参与人物</n-divider>
      <div v-if="!participants.length" class="participant-empty">
        尚未添加参与人物。一个事件可以关联多位角色。
      </div>
      <div v-for="(p, index) in participants" :key="index" class="participant-row">
        <n-select
          v-model:value="p.character_id"
          :options="characterOptions"
          filterable
          placeholder="选择人物"
          class="participant-select"
        />
        <n-input v-model:value="p.participant_role" placeholder="角色，如主角/目击者" class="participant-role" />
        <n-input v-model:value="p.description" placeholder="在该事件中的具体表现（可空）" class="participant-desc" />
        <n-button size="small" quaternary type="error" @click="removeParticipant(index)">移除</n-button>
      </div>
      <n-button size="small" dashed block style="margin-top: 8px" @click="addParticipant">
        + 添加参与人物
      </n-button>
    </n-form>

    <template #footer>
      <n-space justify="end">
        <n-button size="small" :disabled="saving" @click="close">取消</n-button>
        <n-button size="small" type="primary" :loading="saving" @click="submit">
          {{ isEdit ? '保存修改' : '创建事件' }}
        </n-button>
      </n-space>
    </template>
  </n-modal>
</template>

<style scoped>
.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.participant-empty {
  padding: 8px 0;
  font-size: 12px;
  color: var(--sf-text-tertiary, #999);
}
.participant-row {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}
.participant-select {
  width: 160px;
  flex-shrink: 0;
}
.participant-role {
  width: 150px;
  flex-shrink: 0;
}
.participant-desc {
  flex: 1;
  min-width: 0;
}
@media (max-width: 640px) {
  .form-grid {
    grid-template-columns: 1fr;
  }
  .participant-row {
    flex-wrap: wrap;
  }
  .participant-select,
  .participant-role {
    width: 100%;
  }
}
</style>
