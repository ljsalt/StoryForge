<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  NButton,
  NCard,
  NEmpty,
  NForm,
  NFormItem,
  NGrid,
  NGridItem,
  NInput,
  NModal,
  NPopconfirm,
  NSelect,
  NSpin,
  NSwitch,
  NTag,
  useDialog,
  useMessage,
} from 'naive-ui'
import { extractError } from '../../api/error'
import { formatDateTime } from '../../utils/format'
import {
  createPromptTemplate,
  deletePromptTemplate,
  listPromptTemplates,
  listTemplateVersions,
  restoreTemplateVersion,
  updatePromptTemplate,
  AI_TASK_TYPE_LABELS,
  AI_TASK_TYPE_OPTIONS,
  type PromptTemplate,
  type PromptTemplateVersion,
} from '../../api/ai'

const message = useMessage()
const dialog = useDialog()

const templates = ref<PromptTemplate[]>([])
const loading = ref(false)
const taskFilter = ref<string | null>(null)
const includeInactive = ref(false)

const showEditor = ref(false)
const editing = ref<PromptTemplate | null>(null)
const saving = ref(false)
const form = ref({
  name: '',
  task_type: 'writer',
  description: '',
  system_prompt: '',
  user_prompt_template: '',
  is_active: true,
})

const showVersions = ref(false)
const versions = ref<PromptTemplateVersion[]>([])
const versionsTemplate = ref<PromptTemplate | null>(null)
const loadingVersions = ref(false)

const filterOptions = computed(() => [
  { label: '全部任务类型', value: '' },
  ...AI_TASK_TYPE_OPTIONS,
])

async function load() {
  loading.value = true
  try {
    const { data } = await listPromptTemplates(taskFilter.value || undefined, includeInactive.value)
    templates.value = data
  } catch (error) {
    message.error(extractError(error, '加载模板失败'))
  } finally {
    loading.value = false
  }
}

onMounted(load)

function taskLabel(taskType: string): string {
  return AI_TASK_TYPE_LABELS[taskType as keyof typeof AI_TASK_TYPE_LABELS] || taskType
}

function openCreate() {
  editing.value = null
  form.value = {
    name: '',
    task_type: (taskFilter.value as string) || 'writer',
    description: '',
    system_prompt: '',
    user_prompt_template: '',
    is_active: true,
  }
  showEditor.value = true
}

function openEdit(template: PromptTemplate) {
  editing.value = template
  form.value = {
    name: template.name,
    task_type: template.task_type,
    description: template.description,
    system_prompt: template.system_prompt,
    user_prompt_template: template.user_prompt_template,
    is_active: template.is_active,
  }
  showEditor.value = true
}

async function save() {
  if (!form.value.name.trim()) {
    message.warning('请填写模板名称')
    return
  }
  saving.value = true
  try {
    if (editing.value) {
      await updatePromptTemplate(editing.value.id, { ...form.value })
      message.success('模板已更新（版本 +1）')
    } else {
      await createPromptTemplate({ ...form.value })
      message.success('模板已创建')
    }
    showEditor.value = false
    await load()
  } catch (error) {
    message.error(extractError(error, '保存失败'))
  } finally {
    saving.value = false
  }
}

function confirmDelete(template: PromptTemplate) {
  dialog.warning({
    title: '删除模板',
    content: `确定删除模板「${template.name}」吗？其全部版本历史将一并删除。`,
    positiveText: '确认删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await deletePromptTemplate(template.id)
        message.success('模板已删除')
        await load()
      } catch (error) {
        message.error(extractError(error, '删除失败'))
      }
    },
  })
}

async function openVersions(template: PromptTemplate) {
  versionsTemplate.value = template
  showVersions.value = true
  loadingVersions.value = true
  try {
    const { data } = await listTemplateVersions(template.id)
    versions.value = data
  } catch (error) {
    message.error(extractError(error, '加载版本失败'))
  } finally {
    loadingVersions.value = false
  }
}

async function restore(version: PromptTemplateVersion) {
  if (!versionsTemplate.value) return
  try {
    await restoreTemplateVersion(versionsTemplate.value.id, version.version)
    message.success(`已按 v${version.version} 内容生成新版本`)
    showVersions.value = false
    await load()
  } catch (error) {
    message.error(extractError(error, '恢复失败'))
  }
}
</script>

<template>
  <div class="panel">
    <div class="toolbar">
      <n-select
        :value="taskFilter"
        :options="filterOptions"
        class="filter"
        @update:value="(v: string) => { taskFilter = v || null; load() }"
      />
      <div class="inactive-toggle">
        <n-switch
          :value="includeInactive"
          size="small"
          @update:value="(v: boolean) => { includeInactive = v; load() }"
        />
        <span>显示已停用</span>
      </div>
      <n-button size="small" type="primary" @click="openCreate">新建模板</n-button>
    </div>

    <n-spin :show="loading">
      <n-empty v-if="!templates.length" description="暂无模板" />
      <div v-else class="list">
        <n-card v-for="tpl in templates" :key="tpl.id" size="small" class="item">
          <div class="item-head">
            <span class="item-title">{{ tpl.name }}</span>
            <n-tag size="small" round :bordered="false" type="info">{{ taskLabel(tpl.task_type) }}</n-tag>
            <n-tag size="small" round :bordered="false">v{{ tpl.version }}</n-tag>
            <n-tag v-if="!tpl.is_active" size="small" round :bordered="false" type="warning">已停用</n-tag>
          </div>
          <div v-if="tpl.description" class="item-desc">{{ tpl.description }}</div>
          <div class="item-meta">
            <span>变量：{{ tpl.variables.length ? tpl.variables.map((v) => '{' + v + '}').join('、') : '（无）' }}</span>
            <span>更新于 {{ formatDateTime(tpl.updated_at) }}</span>
          </div>
          <div class="item-actions">
            <n-button size="tiny" @click="openEdit(tpl)">编辑</n-button>
            <n-button size="tiny" quaternary @click="openVersions(tpl)">版本历史</n-button>
            <n-button size="tiny" quaternary type="error" @click="confirmDelete(tpl)">删除</n-button>
          </div>
        </n-card>
      </div>
    </n-spin>

    <n-modal
      :show="showEditor"
      preset="card"
      :title="editing ? `编辑模板（当前 v${editing.version}）` : '新建模板'"
      :style="{ width: '720px', maxWidth: 'calc(100vw - 24px)' }"
      :bordered="false"
      @update:show="showEditor = $event"
    >
      <n-form label-placement="top" size="small">
        <n-grid :x-gap="12" cols="1 s:2" responsive="screen">
          <n-grid-item>
            <n-form-item label="模板名称" required>
              <n-input v-model:value="form.name" maxlength="100" placeholder="例如：正文作者基础模板" />
            </n-form-item>
          </n-grid-item>
          <n-grid-item>
            <n-form-item label="任务类型" required>
              <n-select v-model:value="form.task_type" :options="AI_TASK_TYPE_OPTIONS" />
            </n-form-item>
          </n-grid-item>
        </n-grid>
        <n-form-item label="描述">
          <n-input v-model:value="form.description" maxlength="500" placeholder="模板用途说明" />
        </n-form-item>
        <n-form-item label="System Prompt（模型角色与规则）">
          <n-input
            v-model:value="form.system_prompt"
            type="textarea"
            :autosize="{ minRows: 3, maxRows: 8 }"
            placeholder="可使用 {变量名} 占位"
          />
        </n-form-item>
        <n-form-item label="User Prompt 模板（本次任务要求）">
          <n-input
            v-model:value="form.user_prompt_template"
            type="textarea"
            :autosize="{ minRows: 4, maxRows: 10 }"
            placeholder="例如：上下文：&#10;{context}&#10;&#10;任务：{task}"
          />
        </n-form-item>
        <n-form-item label="启用该模板">
          <n-switch v-model:value="form.is_active" />
        </n-form-item>
        <div class="var-hint">
          变量形如 {`{context}`}、{`{task}`}，渲染时所有变量都必须提供，缺失会被拒绝；
          模板只做纯文本替换，不会执行任何代码。
        </div>
      </n-form>
      <template #footer>
        <div class="footer">
          <n-button size="small" @click="showEditor = false">取消</n-button>
          <n-button size="small" type="primary" :loading="saving" @click="save">
            {{ editing ? '保存（版本 +1）' : '创建模板' }}
          </n-button>
        </div>
      </template>
    </n-modal>

    <n-modal
      :show="showVersions"
      preset="card"
      :title="versionsTemplate ? `「${versionsTemplate.name}」版本历史` : '版本历史'"
      :style="{ width: '720px', maxWidth: 'calc(100vw - 24px)' }"
      :bordered="false"
      @update:show="showVersions = $event"
    >
      <n-spin :show="loadingVersions">
        <n-empty v-if="!versions.length" description="暂无版本记录" />
        <div v-else class="version-list">
          <n-card v-for="v in versions" :key="v.id" size="small" class="item">
            <div class="item-head">
              <n-tag size="small" round :bordered="false" type="info">v{{ v.version }}</n-tag>
              <n-tag
                v-if="versionsTemplate && v.version === versionsTemplate.version"
                size="small" round :bordered="false" type="success"
              >当前版本</n-tag>
              <span class="item-meta">{{ formatDateTime(v.created_at) }}</span>
            </div>
            <div class="version-body">
              <div class="version-label">System Prompt</div>
              <pre class="content-pre">{{ v.system_prompt || '（空）' }}</pre>
              <div class="version-label">User Prompt 模板</div>
              <pre class="content-pre">{{ v.user_prompt_template || '（空）' }}</pre>
            </div>
            <div class="item-actions">
              <n-popconfirm
                v-if="versionsTemplate && v.version !== versionsTemplate.version"
                @positive-click="restore(v)"
              >
                <template #trigger>
                  <n-button size="tiny">恢复为此版本</n-button>
                </template>
                将按 v{{ v.version }} 内容生成一个新版本，历史不会丢失。确认恢复？
              </n-popconfirm>
            </div>
          </n-card>
        </div>
      </n-spin>
    </n-modal>
  </div>
</template>

<style scoped>
.panel { padding-top: 4px; }
.toolbar { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; flex-wrap: wrap; }
.filter { width: 180px; }
.inactive-toggle { display: flex; align-items: center; gap: 6px; font-size: 12px; color: rgba(255, 255, 255, 0.6); }
.list { display: flex; flex-direction: column; gap: 8px; }
.item { background: rgba(255, 255, 255, 0.04); }
.item-head { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.item-title { font-size: 14px; font-weight: 600; color: #fff; }
.item-desc { font-size: 12px; color: rgba(255, 255, 255, 0.6); margin-top: 4px; }
.item-meta { display: flex; gap: 14px; flex-wrap: wrap; font-size: 12px; color: rgba(255, 255, 255, 0.45); margin-top: 6px; }
.item-actions { display: flex; gap: 6px; margin-top: 8px; flex-wrap: wrap; }
.footer { display: flex; justify-content: flex-end; gap: 8px; }
.var-hint { font-size: 12px; color: rgba(255, 255, 255, 0.45); line-height: 1.7; }
.version-list { display: flex; flex-direction: column; gap: 8px; }
.version-body { margin-top: 8px; }
.version-label { font-size: 12px; color: rgba(255, 255, 255, 0.5); margin: 6px 0 4px; }
.content-pre {
  margin: 0; padding: 8px 10px; background: rgba(255, 255, 255, 0.05);
  border-radius: 6px; font-size: 12px; line-height: 1.7; color: rgba(255, 255, 255, 0.8);
  white-space: pre-wrap; word-break: break-word; max-height: 180px; overflow: auto;
}
</style>
