<script setup lang="ts">
import { computed, h, reactive, ref } from 'vue'
import { useDialog, useMessage } from 'naive-ui'
import {
  NAlert,
  NButton,
  NCard,
  NDataTable,
  NDescriptions,
  NDescriptionsItem,
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
  createModel,
  deleteModel,
  testModel,
  updateModel,
  type ModelItem,
  type ModelPayload,
  type ModelTestResult,
} from '../../api/models'
import { extractError } from '../../api/error'
import { useModelStore } from '../../stores/models'

const store = useModelStore()
const message = useMessage()
const dialog = useDialog()

const showModal = ref(false)
const saving = ref(false)
const editingId = ref<string | null>(null)
const testingId = ref<string | null>(null)
const showResult = ref(false)
const testResult = ref<ModelTestResult | null>(null)

const form = reactive({
  provider_id: '',
  name: '',
  model_id: '',
  remark: '',
  enabled: true,
})

const ERROR_LABELS: Record<string, string> = {
  network_error: '网络连接失败',
  timeout: '请求超时',
  invalid_api_key: 'API Key 无效',
  model_not_found: '模型不存在',
  quota_exceeded: '余额或配额不足',
  bad_request: '请求格式不兼容',
  server_error: '服务商返回错误',
  not_supported: '服务商不支持该接口',
  invalid_base_url: 'Base URL 不合法',
  missing_api_key: '尚未配置 API Key',
}

const providerOptions = computed<SelectOption[]>(() =>
  store.providers.map((item) => ({
    label: `${item.name}（${item.provider_type === 'deepseek' ? 'DeepSeek' : '兼容'}）`,
    value: item.id,
  })),
)

const columns: DataTableColumns<ModelItem> = [
  { title: '模型名称', key: 'name', minWidth: 120, ellipsis: { tooltip: true } },
  {
    title: '所属服务商',
    key: 'provider_name',
    minWidth: 130,
    ellipsis: { tooltip: true },
  },
  {
    title: '模型标识符',
    key: 'model_id',
    minWidth: 150,
    ellipsis: { tooltip: true },
  },
  { title: '备注', key: 'remark', minWidth: 120, ellipsis: { tooltip: true } },
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
    width: 190,
    render: (row) =>
      h(NSpace, { size: 4 }, () => [
        h(
          NButton,
          {
            size: 'tiny',
            text: true,
            type: 'primary',
            loading: testingId.value === row.id,
            onClick: () => runTest(row),
          },
          () => '测试连接',
        ),
        h(
          NButton,
          { size: 'tiny', text: true, onClick: () => openEdit(row) },
          () => '编辑',
        ),
        h(
          NButton,
          { size: 'tiny', text: true, type: 'error', onClick: () => confirmDelete(row) },
          () => '删除',
        ),
      ]),
  },
]

function openCreate() {
  if (!store.providers.length) {
    message.warning('请先添加 API 服务商')
    return
  }
  editingId.value = null
  form.provider_id = store.providers[0]?.id ?? ''
  form.name = ''
  form.model_id = ''
  form.remark = ''
  form.enabled = true
  showModal.value = true
}

function openEdit(row: ModelItem) {
  editingId.value = row.id
  form.provider_id = row.provider_id
  form.name = row.name
  form.model_id = row.model_id
  form.remark = row.remark
  form.enabled = row.enabled
  showModal.value = true
}

async function submit() {
  if (!form.provider_id) {
    message.warning('请选择所属服务商')
    return
  }
  if (!form.name.trim()) {
    message.warning('请填写模型名称')
    return
  }
  if (!form.model_id.trim()) {
    message.warning('请填写模型标识符')
    return
  }

  const payload: ModelPayload = {
    provider_id: form.provider_id,
    name: form.name.trim(),
    model_id: form.model_id.trim(),
    remark: form.remark.trim(),
    enabled: form.enabled,
  }

  saving.value = true
  try {
    if (editingId.value) {
      await updateModel(editingId.value, payload)
      message.success('模型已更新')
    } else {
      await createModel(payload)
      message.success('模型已添加')
    }
    showModal.value = false
    await store.refreshProviders()
  } catch (error) {
    message.error(extractError(error))
  } finally {
    saving.value = false
  }
}

async function toggleEnabled(row: ModelItem, value: boolean) {
  try {
    await updateModel(row.id, { enabled: value })
    message.success(value ? `已启用 ${row.name}` : `已停用 ${row.name}`)
    await store.refreshProviders()
  } catch (error) {
    message.error(extractError(error))
  }
}

async function runTest(row: ModelItem) {
  testingId.value = row.id
  try {
    const { data } = await testModel(row.id)
    testResult.value = data
    showResult.value = true
    if (data.success) {
      message.success('连接测试成功')
    } else {
      message.warning(`连接测试失败：${ERROR_LABELS[data.error_code ?? ''] ?? '未知错误'}`)
    }
  } catch (error) {
    message.error(extractError(error))
  } finally {
    testingId.value = null
  }
}

function confirmDelete(row: ModelItem) {
  dialog.warning({
    title: '删除模型',
    content: `确定删除「${row.name}」吗？使用该模型的任务分配会自动回退到全局默认模型。`,
    positiveText: '确认删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await deleteModel(row.id)
        message.success('模型已删除')
        await store.refreshProviders()
      } catch (error) {
        message.error(extractError(error))
      }
    },
  })
}
</script>

<template>
  <n-card>
    <div class="toolbar">
      <div class="hint">模型标识符由你自行填写，例如服务商文档中的实际模型名。</div>
      <n-button type="primary" size="small" @click="openCreate">新增模型</n-button>
    </div>

    <n-alert v-if="!store.providers.length" type="warning" :bordered="false" class="tip">
      还没有任何 API 服务商，请先在「API 服务商」标签页添加。
    </n-alert>

    <n-data-table
      :columns="columns"
      :data="store.models"
      :loading="store.loading"
      :row-key="(row: ModelItem) => row.id"
      :scroll-x="880"
      :bordered="false"
      size="small"
    />

    <n-modal
      v-model:show="showModal"
      preset="card"
      :title="editingId ? '编辑模型' : '新增模型'"
      :style="{ width: 'min(560px, 92vw)' }"
    >
      <n-form label-placement="top">
        <n-form-item label="所属服务商" required>
          <n-select v-model:value="form.provider_id" :options="providerOptions" />
        </n-form-item>
        <n-form-item label="模型名称" required>
          <n-input v-model:value="form.name" placeholder="例如 剧情模型" />
        </n-form-item>
        <n-form-item label="模型标识符" required>
          <n-input v-model:value="form.model_id" placeholder="例如 deepseek-chat" />
        </n-form-item>
        <n-form-item label="备注">
          <n-input
            v-model:value="form.remark"
            type="textarea"
            :rows="2"
            maxlength="200"
            show-count
            placeholder="用途说明，例如用于正文写作"
          />
        </n-form-item>
        <n-form-item label="启用">
          <n-switch v-model:value="form.enabled" />
        </n-form-item>
      </n-form>

      <template #footer>
        <div class="footer-right">
          <n-button size="small" @click="showModal = false">取消</n-button>
          <n-button size="small" type="primary" :loading="saving" @click="submit">
            保存
          </n-button>
        </div>
      </template>
    </n-modal>

    <n-modal
      v-model:show="showResult"
      preset="card"
      title="连接测试结果"
      :style="{ width: 'min(520px, 92vw)' }"
    >
      <template v-if="testResult">
        <n-alert :type="testResult.success ? 'success' : 'error'" :bordered="false" class="tip">
          {{ testResult.success ? '连接成功' : `连接失败：${ERROR_LABELS[testResult.error_code ?? ''] ?? '未知错误'}` }}
        </n-alert>
        <n-descriptions :column="1" label-placement="left" bordered size="small">
          <n-descriptions-item label="模型标识符">
            {{ testResult.model_identifier }}
          </n-descriptions-item>
          <n-descriptions-item label="响应时间">
            {{ testResult.latency_ms }} ms
          </n-descriptions-item>
          <n-descriptions-item label="验证方式">
            {{ testResult.method === 'models' ? '模型列表接口（通常不产生费用）' : testResult.method === 'chat' ? '最小对话请求' : '未发起请求' }}
          </n-descriptions-item>
          <n-descriptions-item label="详细信息">
            {{ testResult.message }}
          </n-descriptions-item>
        </n-descriptions>
        <div class="cost-note">
          使用最小对话请求验证时，可能产生极少量 API 费用。
        </div>
      </template>
      <template #footer>
        <div class="footer-right">
          <n-button size="small" type="primary" @click="showResult = false">知道了</n-button>
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

.cost-note {
  margin-top: 12px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.45);
}

.footer-right {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}
</style>
