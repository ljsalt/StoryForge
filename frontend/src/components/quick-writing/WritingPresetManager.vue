<script setup lang="ts">
import { ref, watch } from 'vue'
import {
  NButton,
  NCollapse,
  NCollapseItem,
  NEmpty,
  NInput,
  NModal,
  NPopconfirm,
  NTag,
  useMessage,
} from 'naive-ui'
import { extractError } from '../../api/error'
import {
  CONTEXT_SECTION_LABELS,
  copyWritingPreset,
  createWritingPreset,
  deleteWritingPreset,
  listWritingPresets,
  setDefaultWritingPreset,
  setNovelWritingPreset,
  updateWritingPreset,
  type WritingPresetConfig,
} from '../../api/quickWriting'

const props = defineProps<{
  show: boolean
  novelId: string
  selectedId?: string | null
}>()

const emit = defineEmits<{
  (event: 'update:show', value: boolean): void
  (event: 'changed'): void
  (event: 'select', value: string): void
}>()

const message = useMessage()
const presets = ref<any[]>([])
const loading = ref(false)
const saving = ref(false)
const editingId = ref<string | null>(null)

const emptyForm = () => ({
  name: '',
  description: '',
  system_prompt: '',
  is_active: true,
  config: {
    writing_style: '',
    narrative_perspective: '',
    person: '',
    language_style: '',
    dialogue_style: '',
    style_constraints: '',
    extra_prompt: '',
    adult_genres_text: '',
    relationship_background: '',
    adult_narrative_style: '',
    intensity: '',
    conventions: '',
    forbidden: '',
  } as Record<string, string> & { adult_genres_text: string },
})

const form = ref(emptyForm())

async function load() {
  loading.value = true
  try {
    presets.value = (await listWritingPresets(true)).data
  } catch (err) {
    message.error(extractError(err, '加载写作预设失败'))
  } finally {
    loading.value = false
  }
}

function resetForm() {
  editingId.value = null
  form.value = emptyForm()
}

function editPreset(preset: any) {
  editingId.value = preset.id
  const config = preset.config || ({} as Partial<WritingPresetConfig>)
  form.value = {
    name: preset.name,
    description: preset.description || '',
    system_prompt: preset.system_prompt || '',
    is_active: preset.is_active,
    config: {
      writing_style: config.writing_style || '',
      narrative_perspective: config.narrative_perspective || '',
      person: config.person || '',
      language_style: config.language_style || '',
      dialogue_style: config.dialogue_style || '',
      style_constraints: config.style_constraints || '',
      extra_prompt: config.extra_prompt || '',
      adult_genres_text: (config.adult_genres || []).join('、'),
      relationship_background: config.relationship_background || '',
      adult_narrative_style: config.adult_narrative_style || '',
      intensity: config.intensity || '',
      conventions: config.conventions || '',
      forbidden: config.forbidden || '',
    },
  }
}

function buildPayload() {
  const { adult_genres_text, ...rest } = form.value.config
  const config: Partial<WritingPresetConfig> = {
    ...rest,
    adult_genres: adult_genres_text
      .split(/[、,，]/)
      .map((item) => item.trim())
      .filter(Boolean),
  }
  return {
    name: form.value.name.trim(),
    description: form.value.description,
    system_prompt: form.value.system_prompt,
    is_active: form.value.is_active,
    config,
  }
}

async function save() {
  if (!form.value.name.trim()) {
    message.warning('请填写预设名称')
    return
  }
  saving.value = true
  try {
    if (editingId.value) {
      await updateWritingPreset(editingId.value, buildPayload())
      message.success('预设已更新')
    } else {
      await createWritingPreset(buildPayload())
      message.success('预设已创建')
    }
    resetForm()
    await load()
    emit('changed')
  } catch (err) {
    message.error(extractError(err, '保存预设失败'))
  } finally {
    saving.value = false
  }
}

async function copyPreset(preset: any) {
  try {
    await copyWritingPreset(preset.id)
    await load()
    emit('changed')
    message.success('已复制预设')
  } catch (err) {
    message.error(extractError(err, '复制预设失败'))
  }
}

async function removePreset(preset: any) {
  try {
    await deleteWritingPreset(preset.id)
    await load()
    emit('changed')
    message.success('预设已删除')
  } catch (err) {
    message.error(extractError(err, '删除预设失败'))
  }
}

async function makeDefault(preset: any) {
  try {
    await setDefaultWritingPreset(preset.id)
    await load()
    emit('changed')
    message.success('已设为全局默认预设')
  } catch (err) {
    message.error(extractError(err, '设置默认预设失败'))
  }
}

async function assignToNovel(preset: any) {
  try {
    await setNovelWritingPreset(props.novelId, preset.id)
    message.success('已设为本书默认预设')
    emit('changed')
  } catch (err) {
    message.error(extractError(err, '设置小说预设失败'))
  }
}

watch(
  () => props.show,
  (show) => {
    if (show) {
      resetForm()
      load()
    }
  },
)

defineExpose({ load })
</script>

<template>
  <n-modal
    :show="show"
    preset="card"
    title="写作预设管理"
    class="preset-modal"
    :bordered="false"
    @update:show="emit('update:show', $event)"
  >
    <div class="preset-layout">
      <div class="preset-list">
        <div class="list-head">
          <span class="hint">预设可与任意模型搭配使用，不会绑定模型。</span>
          <n-button size="tiny" @click="resetForm">新建预设</n-button>
        </div>
        <n-empty v-if="!presets.length && !loading" description="还没有写作预设" size="small" />
        <div v-for="preset in presets" :key="preset.id" class="preset-item">
          <div class="preset-main">
            <div class="preset-name-row">
              <span class="preset-name">{{ preset.name }}</span>
              <n-tag v-if="preset.is_default" size="tiny" type="warning">全局默认</n-tag>
              <n-tag v-if="!preset.is_active" size="tiny">已停用</n-tag>
              <n-tag v-if="selectedId === preset.id" size="tiny" type="success">当前使用</n-tag>
            </div>
            <div v-if="preset.description" class="preset-desc">{{ preset.description }}</div>
            <div class="preset-genres">
              <n-tag
                v-for="genre in preset.config?.adult_genres || []"
                :key="genre"
                size="tiny"
                :bordered="false"
              >
                {{ genre }}
              </n-tag>
            </div>
          </div>
          <div class="preset-actions">
            <n-button size="tiny" @click="emit('select', preset.id); emit('update:show', false)">
              选用
            </n-button>
            <n-button size="tiny" quaternary @click="editPreset(preset)">编辑</n-button>
            <n-button size="tiny" quaternary @click="copyPreset(preset)">复制</n-button>
            <n-button size="tiny" quaternary @click="makeDefault(preset)">设默认</n-button>
            <n-button size="tiny" quaternary @click="assignToNovel(preset)">设为本书</n-button>
            <n-popconfirm @positive-click="removePreset(preset)">
              <template #trigger>
                <n-button size="tiny" quaternary type="error">删除</n-button>
              </template>
              删除后不可恢复，确定删除该预设？
            </n-popconfirm>
          </div>
        </div>
      </div>

      <div class="preset-editor">
        <div class="editor-title">{{ editingId ? '编辑预设' : '新建预设' }}</div>
        <n-input v-model:value="form.name" placeholder="预设名称（必填）" size="small" />
        <n-input
          v-model:value="form.description"
          placeholder="一句话描述这个预设的用途"
          size="small"
        />
        <n-input
          v-model:value="form.system_prompt"
          type="textarea"
          :autosize="{ minRows: 3, maxRows: 6 }"
          placeholder="System Prompt（可选，作为作者的基础设定）"
        />
        <n-collapse class="editor-collapse">
          <n-collapse-item title="文风与叙事" name="style">
            <div class="field-grid">
              <n-input v-model:value="form.config.writing_style" size="small" placeholder="写作风格，如：冷峻、细腻" />
              <n-input v-model:value="form.config.narrative_perspective" size="small" placeholder="叙事视角，如：第三人称跟随主角" />
              <n-input v-model:value="form.config.person" size="small" placeholder="人称，如：第三人称" />
              <n-input v-model:value="form.config.language_style" size="small" placeholder="语言风格，如：短句、口语化" />
              <n-input v-model:value="form.config.dialogue_style" size="small" placeholder="对话风格，如：克制、少解释" />
              <n-input v-model:value="form.config.style_constraints" size="small" placeholder="文风限制，如：不用网络流行语" />
            </div>
          </n-collapse-item>
          <n-collapse-item title="成人向创作偏好（可选）" name="adult">
            <div class="field-grid single">
              <n-input v-model:value="form.config.adult_genres_text" size="small" placeholder="题材标签，用顿号分隔，如：慢热、成年角色" />
              <n-input v-model:value="form.config.relationship_background" type="textarea" :autosize="{ minRows: 2, maxRows: 4 }" placeholder="角色关系与背景设定" />
              <n-input v-model:value="form.config.adult_narrative_style" size="small" placeholder="叙事风格偏好" />
              <n-input v-model:value="form.config.intensity" size="small" placeholder="描写尺度偏好（自由填写）" />
              <n-input v-model:value="form.config.conventions" type="textarea" :autosize="{ minRows: 2, maxRows: 4 }" placeholder="自定义创作约定" />
              <n-input v-model:value="form.config.forbidden" type="textarea" :autosize="{ minRows: 2, maxRows: 4 }" placeholder="禁止出现的内容或设定" />
            </div>
          </n-collapse-item>
          <n-collapse-item title="其他要求" name="extra">
            <n-input v-model:value="form.config.extra_prompt" type="textarea" :autosize="{ minRows: 2, maxRows: 5 }" placeholder="其他自定义提示词" />
          </n-collapse-item>
        </n-collapse>
        <div class="editor-actions">
          <n-button size="small" @click="resetForm">清空</n-button>
          <n-button size="small" type="primary" :loading="saving" @click="save">保存预设</n-button>
        </div>
        <div class="editor-hint">
          可用分区：{{ Object.values(CONTEXT_SECTION_LABELS).join('、') }}。预设不会写入任何模型密钥。
        </div>
      </div>
    </div>
  </n-modal>
</template>

<style scoped>
.preset-modal {
  width: min(920px, 94vw);
}
.preset-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.05fr);
  gap: 16px;
}
.preset-list {
  min-width: 0;
}
.list-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}
.hint,
.editor-hint {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.45);
  line-height: 1.6;
  word-break: break-word;
}
.preset-item {
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  padding: 10px;
  margin-bottom: 8px;
  background: rgba(255, 255, 255, 0.02);
}
.preset-name-row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.preset-name {
  font-weight: 600;
  color: #fff;
  word-break: break-word;
}
.preset-desc {
  margin-top: 4px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.55);
  word-break: break-word;
}
.preset-genres {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 4px;
}
.preset-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 8px;
}
.preset-editor {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}
.editor-title {
  font-size: 14px;
  font-weight: 600;
  color: #fff;
}
.field-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}
.field-grid.single {
  grid-template-columns: minmax(0, 1fr);
}
.editor-collapse {
  margin-top: 4px;
}
.editor-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  flex-wrap: wrap;
}
@media (max-width: 760px) {
  .preset-layout {
    grid-template-columns: minmax(0, 1fr);
  }
  .field-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
