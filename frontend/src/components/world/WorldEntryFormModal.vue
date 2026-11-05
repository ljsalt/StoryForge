<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  NAlert,
  NButton,
  NDynamicTags,
  NForm,
  NFormItem,
  NGrid,
  NGridItem,
  NInput,
  NInputNumber,
  NModal,
  NSelect,
  useMessage,
} from 'naive-ui'
import { extractError } from '../../api/error'
import type { WorldCategory, WorldEntry } from '../../api/world'
import { useWorldStore } from '../../stores/world'

const props = defineProps<{
  show: boolean
  categories: WorldCategory[]
  entries: WorldEntry[]
  entry?: WorldEntry | null
  defaultCategoryId?: string
}>()

const emit = defineEmits<{ 'update:show': [value: boolean]; saved: [] }>()

const store = useWorldStore()
const message = useMessage()

const name = ref('')
const categoryId = ref('')
const summary = ref('')
const content = ref('')
const tags = ref<string[]>([])
const parentId = ref<string | null>(null)
const sortOrder = ref(0)
const attrRows = ref<{ key: string; value: string }[]>([])
const saving = ref(false)

const isEdit = computed(() => Boolean(props.entry))

const categoryOptions = computed(() =>
  props.categories.map((item) => ({ label: item.name, value: item.id })),
)

const parentOptions = computed(() =>
  props.entries
    .filter((item) => !props.entry || item.id !== props.entry.id)
    .map((item) => ({
      label: `${item.name}（${item.category_name}）`,
      value: item.id,
    })),
)

function resetForm() {
  const entry = props.entry
  if (entry) {
    name.value = entry.name
    categoryId.value = entry.category_id
    summary.value = entry.summary
    content.value = entry.content
    tags.value = [...entry.tags]
    parentId.value = entry.parent_id
    sortOrder.value = entry.sort_order
    attrRows.value = Object.entries(entry.attributes).map(([key, value]) => ({
      key,
      value: value === null ? '' : String(value),
    }))
  } else {
    name.value = ''
    categoryId.value = props.defaultCategoryId || props.categories[0]?.id || ''
    summary.value = ''
    content.value = ''
    tags.value = []
    parentId.value = null
    sortOrder.value = 0
    attrRows.value = []
  }
}

watch(
  () => [props.show, props.entry] as const,
  ([show]) => {
    if (show) resetForm()
  },
)

function addAttribute() {
  attrRows.value.push({ key: '', value: '' })
}

function removeAttribute(index: number) {
  attrRows.value.splice(index, 1)
}

function close() {
  emit('update:show', false)
}

function buildAttributes(): Record<string, string> | null {
  const result: Record<string, string> = {}
  for (const row of attrRows.value) {
    const key = row.key.trim()
    if (!key) {
      if (row.value.trim()) {
        message.error('存在未填写属性名的属性，请补全或删除该行')
        return null
      }
      continue
    }
    if (key in result) {
      message.error(`属性名“${key}”重复，请修改后再保存`)
      return null
    }
    result[key] = row.value
  }
  return result
}

async function submit() {
  const title = name.value.trim()
  if (!title) {
    message.error('设定名称不能为空')
    return
  }
  if (!categoryId.value) {
    message.error('请选择所属分类')
    return
  }
  const attributes = buildAttributes()
  if (attributes === null) return

  saving.value = true
  try {
    const payload = {
      name: title,
      category_id: categoryId.value,
      summary: summary.value.trim(),
      content: content.value.trim(),
      tags: tags.value.map((tag) => tag.trim()).filter(Boolean),
      attributes,
      parent_id: parentId.value || null,
      sort_order: Number(sortOrder.value) || 0,
    }
    if (props.entry) {
      await store.updateEntry(props.entry.id, payload)
      message.success('设定已保存')
    } else {
      await store.createEntry(payload)
      message.success('设定已创建')
    }
    emit('saved')
    close()
  } catch (error) {
    message.error(extractError(error, '保存设定失败'))
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <n-modal
    :show="show"
    preset="card"
    :title="isEdit ? '编辑世界观设定' : '新建世界观设定'"
    :style="{ width: '720px', maxWidth: 'calc(100vw - 24px)' }"
    :bordered="false"
    @update:show="emit('update:show', $event)"
  >
    <n-alert
      v-if="!categories.length"
      type="warning"
      :bordered="false"
      class="tip"
    >
      当前小说还没有分类，请先在「分类管理」中创建分类。
    </n-alert>

    <n-form label-placement="top" size="small">
      <n-form-item label="名称" required>
        <n-input v-model:value="name" maxlength="100" placeholder="例如：青木府城" />
      </n-form-item>

      <n-grid :x-gap="12" cols="1 s:2" responsive="screen">
        <n-grid-item>
          <n-form-item label="分类" required>
            <n-select
              v-model:value="categoryId"
              :options="categoryOptions"
              placeholder="选择分类"
            />
          </n-form-item>
        </n-grid-item>
        <n-grid-item>
          <n-form-item label="排序">
            <n-input-number v-model:value="sortOrder" :min="0" :max="100000" class="full" />
          </n-form-item>
        </n-grid-item>
      </n-grid>

      <n-form-item label="简介">
        <n-input
          v-model:value="summary"
          type="textarea"
          :autosize="{ minRows: 2, maxRows: 3 }"
          maxlength="500"
          show-count
          placeholder="一句话概括该设定"
        />
      </n-form-item>

      <n-form-item label="详细描述">
        <n-input
          v-model:value="content"
          type="textarea"
          :autosize="{ minRows: 8, maxRows: 16 }"
          maxlength="20000"
          show-count
          placeholder="完整记录该设定的来龙去脉、规则细节与创作备注"
        />
      </n-form-item>

      <n-form-item label="标签">
        <n-dynamic-tags v-model:value="tags" :max="10" />
      </n-form-item>

      <n-form-item label="自定义属性">
        <div class="attr-list">
          <div v-for="(row, index) in attrRows" :key="index" class="attr-row">
            <n-input v-model:value="row.key" placeholder="属性名，如 类型" maxlength="50" />
            <n-input v-model:value="row.value" placeholder="属性值，如 府城" maxlength="500" />
            <n-button size="small" quaternary type="error" @click="removeAttribute(index)">
              删除
            </n-button>
          </div>
          <n-button size="small" dashed @click="addAttribute">+ 添加属性</n-button>
        </div>
      </n-form-item>

      <n-form-item label="父级条目">
        <n-select
          v-model:value="parentId"
          :options="parentOptions"
          clearable
          filterable
          placeholder="可选，用于组织上下级设定"
        />
      </n-form-item>
    </n-form>

    <template #footer>
      <div class="footer">
        <n-button size="small" @click="close">取消</n-button>
        <n-button
          size="small"
          type="primary"
          :loading="saving"
          :disabled="!categories.length"
          @click="submit"
        >
          {{ isEdit ? '保存修改' : '创建设定' }}
        </n-button>
      </div>
    </template>
  </n-modal>
</template>

<style scoped>
.tip {
  margin-bottom: 12px;
}

.full {
  width: 100%;
}

.attr-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.attr-row {
  display: flex;
  gap: 8px;
  align-items: center;
}

.attr-row > :first-child {
  flex: 0 0 32%;
}

.attr-row > :nth-child(2) {
  flex: 1;
}

.footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

@media (max-width: 767px) {
  .attr-row {
    flex-wrap: wrap;
  }

  .attr-row > :first-child {
    flex: 1 1 100%;
  }

  .attr-row > :nth-child(2) {
    flex: 1 1 70%;
  }
}
</style>
