<script setup lang="ts">
import { h, reactive, ref } from 'vue'
import { useDialog, useMessage } from 'naive-ui'
import {
  NAlert,
  NButton,
  NCard,
  NDataTable,
  NForm,
  NFormItem,
  NInput,
  NModal,
  NSelect,
  NSpace,
  NSwitch,
  NTag,
  type DataTableColumns,
  type SelectOption,
} from 'naive-ui'
import {
  PROVIDER_TYPE_LABELS,
  createProvider,
  deleteProvider,
  updateProvider,
  type Provider,
  type ProviderPayload,
  type ProviderType,
} from '../../api/models'
import { extractError } from '../../api/error'
import { useModelStore } from '../../stores/models'

const store = useModelStore()
const message = useMessage()
const dialog = useDialog()

const showModal = ref(false)
const saving = ref(false)
const editingId = ref<string | null>(null)

const form = reactive({
  name: '',
  provider_type: 'deepseek' as ProviderType,
  base_url: 'https://api.deepseek.com',
  api_key: '',
  enabled: true,
})

const TYPE_DEFAULTS: Record<ProviderType, string> = {
  deepseek: 'https://api.deepseek.com',
  openai_compatible: 'https://api.openai.com/v1',
  custom: '',
}

const typeOptions: SelectOption[] = (
  Object.keys(PROVIDER_TYPE_LABELS) as ProviderType[]
).map((value) => ({ label: PROVIDER_TYPE_LABELS[value], value }))

const columns: DataTableColumns<Provider> = [
  { title: '名称', key: 'name', minWidth: 140, ellipsis: { tooltip: true } },
  {
    title: '类型',
    key: 'provider_type',
    width: 120,
    render: (row) => PROVIDER_TYPE_LABELS[row.provider_type],
  },
  {
    title: 'Base URL',
    key: 'base_url',
    minWidth: 200,
    ellipsis: { tooltip: true },
  },
  {
    title: 'API Key',
    key: 'api_key',
    width: 150,
    render: (row) =>
      row.has_api_key
        ? h(NTag, { type: 'success', size: 'small', round: true }, () => row.api_key_masked)
        : h(NTag, { size: 'small', round: true }, () => '未配置'),
  },
  {
    title: '启用',
    key: 'enabled',
    width: 80,
    render: (row) =>
      h(NSwitch, {
        value: row.enabled,
        size: 'small',
        onUpdateValue: (value: boolean) => toggleEnabled(row, value),
      }),
  },
  {
    title: '操作',
    key: 'actions',
    width: 150,
    render: (row) =>
      h(
        NSpace,
        { size: 4 },
        () => [
          h(
            NButton,
            { size: 'tiny', text: true, type: 'primary', onClick: () => openEdit(row) },
            () => '编辑',
          ),
          h(
            NButton,
            { size: 'tiny', text: true, type: 'error', onClick: () => confirmDelete(row) },
            () => '删除',
          ),
        ],
      ),
  },
]

function resetForm() {
  form.name = ''
  form.provider_type = 'deepseek'
  form.base_url = TYPE_DEFAULTS.deepseek
  form.api_key = ''
  form.enabled = true
}

function openCreate() {
  editingId.value = null
  resetForm()
  showModal.value = true
}

function openEdit(row: Provider) {
  editingId.value = row.id
  form.name = row.name
  form.provider_type = row.provider_type
  form.base_url = row.base_url
  form.api_key = ''
  form.enabled = row.enabled
  showModal.value = true
}

function handleTypeChange(value: ProviderType) {
  if (!editingId.value) {
    form.base_url = TYPE_DEFAULTS[value]
  }
}

async function submit() {
  if (!form.name.trim()) {
    message.warning('请填写服务商名称')
    return
  }
  if (!form.base_url.trim()) {
    message.warning('请填写 Base URL')
    return
  }

  const payload: ProviderPayload = {
    name: form.name.trim(),
    provider_type: form.provider_type,
    base_url: form.base_url.trim(),
    enabled: form.enabled,
  }
  // 编辑时留空表示不修改密钥；创建时留空表示暂不配置
  if (form.api_key.trim()) payload.api_key = form.api_key.trim()

  saving.value = true
  try {
    if (editingId.value) {
      await updateProvider(editingId.value, payload)
      message.success('服务商已更新')
    } else {
      await createProvider(payload)
      message.success('服务商已添加')
    }
    showModal.value = false
    await store.refreshProviders()
  } catch (error) {
    message.error(extractError(error))
  } finally {
    saving.value = false
  }
}

async function toggleEnabled(row: Provider, value: boolean) {
  try {
    await updateProvider(row.id, { enabled: value })
    message.success(value ? `已启用 ${row.name}` : `已停用 ${row.name}`)
    await store.refreshProviders()
  } catch (error) {
    message.error(extractError(error))
  }
}

function confirmDelete(row: Provider) {
  const relatedModels = store.models.filter((item) => item.provider_id === row.id)
  dialog.warning({
    title: '删除服务商',
    content: relatedModels.length
      ? `确定删除「${row.name}」吗？其下 ${relatedModels.length} 个模型会一并删除，相关任务分配将自动清空。`
      : `确定删除「${row.name}」吗？`,
    positiveText: '确认删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await deleteProvider(row.id)
        message.success('服务商已删除')
        await store.refreshProviders()
      } catch (error) {
        message.error(extractError(error))
      }
    },
  })
}

async function clearApiKey() {
  if (!editingId.value) return
  try {
    await updateProvider(editingId.value, { api_key: '' })
    message.success('API Key 已清除')
    showModal.value = false
    await store.refreshProviders()
  } catch (error) {
    message.error(extractError(error))
  }
}
</script>

<template>
  <n-card>
    <div class="toolbar">
      <div class="hint">支持多个服务商；API Key 只保存在后端，浏览器仅能看到脱敏状态。</div>
      <n-button type="primary" size="small" @click="openCreate">添加服务商</n-button>
    </div>

    <n-alert type="info" :bordered="false" class="tip">
      预设「DeepSeek 官方」的 Base URL 为 https://api.deepseek.com，可按需修改。
      自定义 Base URL 仅支持 http/https，默认禁止指向本机与内网地址。
    </n-alert>

    <n-data-table
      :columns="columns"
      :data="store.providers"
      :loading="store.loading"
      :row-key="(row: Provider) => row.id"
      :scroll-x="820"
      :bordered="false"
      size="small"
    />

    <n-modal
      v-model:show="showModal"
      preset="card"
      :title="editingId ? '编辑服务商' : '添加服务商'"
      class="form-modal"
      :style="{ width: 'min(560px, 92vw)' }"
    >
      <n-form label-placement="top">
        <n-form-item label="服务商名称" required>
          <n-input v-model:value="form.name" placeholder="例如 DeepSeek Official" />
        </n-form-item>
        <n-form-item label="服务商类型" required>
          <n-select
            v-model:value="form.provider_type"
            :options="typeOptions"
            @update:value="handleTypeChange"
          />
        </n-form-item>
        <n-form-item label="Base URL" required>
          <n-input
            v-model:value="form.base_url"
            placeholder="https://api.deepseek.com"
          />
        </n-form-item>
        <n-form-item label="API Key">
          <n-input
            v-model:value="form.api_key"
            type="password"
            show-password-on="click"
            :placeholder="editingId ? '留空则不修改已保存的密钥' : '粘贴 API Key，可稍后填写'"
            autocomplete="off"
          />
        </n-form-item>
        <n-form-item label="启用">
          <n-switch v-model:value="form.enabled" />
        </n-form-item>
      </n-form>
      <n-alert v-if="editingId" type="default" :bordered="false" class="tip">
        API Key 不会回显。如需更换，请直接输入新的密钥。
      </n-alert>

      <template #footer>
        <div class="footer">
          <n-button
            v-if="editingId"
            size="small"
            quaternary
            type="error"
            @click="clearApiKey"
          >
            清除已保存的密钥
          </n-button>
          <div class="footer-right">
            <n-button size="small" @click="showModal = false">取消</n-button>
            <n-button size="small" type="primary" :loading="saving" @click="submit">
              保存
            </n-button>
          </div>
        </div>
      </template>
    </n-modal>
  </n-card>
</template>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.hint {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.55);
}

.tip {
  margin-bottom: 12px;
  font-size: 12px;
}

.footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.footer-right {
  display: flex;
  gap: 8px;
  margin-left: auto;
}
</style>
