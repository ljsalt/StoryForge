<script setup lang="ts">
import { ref, watch } from 'vue'
import {
  NButton,
  NEmpty,
  NForm,
  NFormItem,
  NGrid,
  NGridItem,
  NInput,
  NInputNumber,
  NModal,
  NTag,
  useDialog,
  useMessage,
} from 'naive-ui'
import { extractError } from '../../api/error'
import type { WorldCategory } from '../../api/world'
import { useWorldStore } from '../../stores/world'

const props = defineProps<{ show: boolean }>()
const emit = defineEmits<{ 'update:show': [value: boolean]; changed: [] }>()

const store = useWorldStore()
const message = useMessage()
const dialog = useDialog()

const editingId = ref<string | null>(null)
const name = ref('')
const description = ref('')
const sortOrder = ref(0)
const saving = ref(false)

watch(
  () => props.show,
  (show) => {
    if (show) resetForm()
  },
)

function resetForm() {
  editingId.value = null
  name.value = ''
  description.value = ''
  sortOrder.value = 0
}

function startEdit(category: WorldCategory) {
  editingId.value = category.id
  name.value = category.name
  description.value = category.description
  sortOrder.value = category.sort_order
}

async function submit() {
  const value = name.value.trim()
  if (!value) {
    message.error('分类名称不能为空')
    return
  }
  saving.value = true
  try {
    if (editingId.value) {
      await store.updateCategory(editingId.value, {
        name: value,
        description: description.value.trim(),
        sort_order: Number(sortOrder.value) || 0,
      })
      message.success('分类已更新')
    } else {
      await store.createCategory({
        name: value,
        description: description.value.trim(),
        sort_order: Number(sortOrder.value) || 0,
      })
      message.success('分类已创建')
    }
    resetForm()
    emit('changed')
  } catch (error) {
    message.error(extractError(error, '保存分类失败'))
  } finally {
    saving.value = false
  }
}

function removeCategory(category: WorldCategory) {
  if (category.entry_count > 0) {
    message.warning('该分类下仍有设定条目，请先把条目迁移到其他分类后再删除')
    return
  }
  dialog.warning({
    title: '删除分类',
    content: `确定删除分类“${category.name}”吗？此操作不可恢复。`,
    positiveText: '确认删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await store.removeCategory(category.id)
        if (editingId.value === category.id) resetForm()
        message.success('分类已删除')
        emit('changed')
      } catch (error) {
        message.error(extractError(error, '删除分类失败'))
      }
    },
  })
}
</script>

<template>
  <n-modal
    :show="show"
    preset="card"
    title="分类管理"
    :style="{ width: '640px', maxWidth: 'calc(100vw - 24px)' }"
    :bordered="false"
    @update:show="emit('update:show', $event)"
  >
    <n-form label-placement="top" size="small">
      <n-grid :x-gap="12" cols="1 s:2" responsive="screen">
        <n-grid-item>
          <n-form-item label="分类名称" required>
            <n-input v-model:value="name" maxlength="50" placeholder="例如：地理与区域" />
          </n-form-item>
        </n-grid-item>
        <n-grid-item>
          <n-form-item label="排序">
            <n-input-number v-model:value="sortOrder" :min="0" :max="100000" class="full" />
          </n-form-item>
        </n-grid-item>
      </n-grid>
      <n-form-item label="分类说明">
        <n-input
          v-model:value="description"
          maxlength="500"
          placeholder="可选，说明该分类包含哪些设定"
        />
      </n-form-item>
      <div class="form-actions">
        <n-button v-if="editingId" size="small" @click="resetForm">取消编辑</n-button>
        <n-button size="small" type="primary" :loading="saving" @click="submit">
          {{ editingId ? '保存修改' : '添加分类' }}
        </n-button>
      </div>
    </n-form>

    <div class="list-title">已有分类（{{ store.categories.length }}）</div>
    <n-empty v-if="!store.categories.length" description="暂无分类" />
    <div v-else class="category-list">
      <div v-for="category in store.categories" :key="category.id" class="category-item">
        <div class="category-info">
          <div class="name-row">
            <span class="name">{{ category.name }}</span>
            <n-tag size="tiny" round :bordered="false">排序 {{ category.sort_order }}</n-tag>
            <n-tag
              size="tiny"
              round
              :type="category.entry_count ? 'info' : 'default'"
              :bordered="false"
            >
              {{ category.entry_count }} 条
            </n-tag>
          </div>
          <div class="desc">{{ category.description || '暂无说明' }}</div>
        </div>
        <div class="item-actions">
          <n-button size="tiny" quaternary @click="startEdit(category)">编辑</n-button>
          <n-button
            size="tiny"
            quaternary
            type="error"
            :disabled="category.entry_count > 0"
            :title="
              category.entry_count > 0 ? '分类下仍有条目，暂不可删除' : '删除分类'
            "
            @click="removeCategory(category)"
          >
            删除
          </n-button>
        </div>
      </div>
    </div>
  </n-modal>
</template>

<style scoped>
.full {
  width: 100%;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.list-title {
  margin: 8px 0;
  font-size: 13px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.75);
}

.category-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 320px;
  overflow-y: auto;
}

.category-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.04);
}

.category-info {
  min-width: 0;
}

.name-row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.name {
  font-size: 14px;
  color: #fff;
}

.desc {
  margin-top: 2px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.45);
  word-break: break-word;
}

.item-actions {
  display: flex;
  flex: none;
  gap: 2px;
}
</style>
