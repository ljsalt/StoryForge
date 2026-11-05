<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  NAlert,
  NButton,
  NCheckbox,
  NForm,
  NFormItem,
  NGrid,
  NGridItem,
  NInput,
  NModal,
  NSelect,
  useMessage,
} from 'naive-ui'
import { extractError } from '../../api/error'
import {
  DEFAULT_RELATION_TYPES,
  type WorldRelation,
} from '../../api/world'
import { useWorldStore } from '../../stores/world'

const props = defineProps<{
  show: boolean
  relation?: WorldRelation | null
  defaultSourceId?: string
  defaultTargetId?: string
}>()

const emit = defineEmits<{ 'update:show': [value: boolean]; saved: [] }>()

const store = useWorldStore()
const message = useMessage()

const sourceId = ref<string | null>(null)
const targetId = ref<string | null>(null)
const relationType = ref('')
const description = ref('')
const createReverse = ref(false)
const saving = ref(false)

const isEdit = computed(() => Boolean(props.relation))

const entryOptions = computed(() =>
  store.allEntries.map((item) => ({
    label: `${item.name}（${item.category_name}）`,
    value: item.id,
  })),
)

const typeOptions = computed(() => {
  const options = [...DEFAULT_RELATION_TYPES]
  if (props.relation && !options.includes(props.relation.relation_type)) {
    options.push(props.relation.relation_type)
  }
  return options.map((item) => ({ label: item, value: item }))
})

function resetForm() {
  const relation = props.relation
  if (relation) {
    sourceId.value = relation.source_entry_id
    targetId.value = relation.target_entry_id
    relationType.value = relation.relation_type
    description.value = relation.description
    createReverse.value = false
  } else {
    sourceId.value = props.defaultSourceId || null
    targetId.value = props.defaultTargetId || null
    relationType.value = ''
    description.value = ''
    createReverse.value = false
  }
}

watch(
  () => [props.show, props.relation, props.defaultSourceId, props.defaultTargetId] as const,
  ([show]) => {
    if (show) resetForm()
  },
)

function close() {
  emit('update:show', false)
}

async function submit() {
  const source = sourceId.value
  const target = targetId.value
  const type = relationType.value.trim()

  if (!source || !target) {
    message.error('请选择起点条目与终点条目')
    return
  }
  if (source === target) {
    message.error('起点和终点不能是同一条设定')
    return
  }
  if (!type) {
    message.error('关系类型不能为空')
    return
  }

  const payload = {
    source_entry_id: source,
    target_entry_id: target,
    relation_type: type,
    description: description.value.trim(),
  }

  saving.value = true
  try {
    if (props.relation) {
      await store.updateRelation(props.relation.id, payload)
      message.success('关系已保存')
    } else {
      await store.createRelation(payload)
      message.success('关系已创建')
      if (createReverse.value) {
        try {
          await store.createRelation({
            source_entry_id: target,
            target_entry_id: source,
            relation_type: type,
            description: description.value.trim(),
          })
          message.success('已同时创建反向关系')
        } catch (error) {
          message.warning(extractError(error, '反向关系未能创建'))
        }
      }
    }
    emit('saved')
    close()
  } catch (error) {
    message.error(extractError(error, '保存关系失败'))
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <n-modal
    :show="show"
    preset="card"
    :title="isEdit ? '编辑关系' : '新建关系'"
    :style="{ width: '640px', maxWidth: 'calc(100vw - 24px)' }"
    :bordered="false"
    @update:show="emit('update:show', $event)"
  >
    <n-alert v-if="!store.allEntries.length" type="warning" :bordered="false" class="tip">
      当前小说还没有世界观条目，请先创建至少两条设定后再建立关系。
    </n-alert>

    <n-form label-placement="top" size="small">
      <n-grid :x-gap="12" cols="1 s:2" responsive="screen">
        <n-grid-item>
          <n-form-item label="起点条目" required>
            <n-select
              v-model:value="sourceId"
              :options="entryOptions"
              filterable
              clearable
              placeholder="搜索并选择起点条目"
            />
          </n-form-item>
        </n-grid-item>
        <n-grid-item>
          <n-form-item label="终点条目" required>
            <n-select
              v-model:value="targetId"
              :options="entryOptions"
              filterable
              clearable
              placeholder="搜索并选择终点条目"
            />
          </n-form-item>
        </n-grid-item>
      </n-grid>

      <n-form-item label="关系类型" required>
        <n-select
          v-model:value="relationType"
          :options="typeOptions"
          filterable
          tag
          clearable
          placeholder="选择常用类型，或直接输入自定义类型后回车"
        />
      </n-form-item>

      <n-form-item label="关系描述">
        <n-input
          v-model:value="description"
          type="textarea"
          :autosize="{ minRows: 3, maxRows: 8 }"
          maxlength="2000"
          show-count
          placeholder="记录这条关系的背景、条件或细节，例如：远东皇朝直接任命府城官员。"
        />
      </n-form-item>

      <n-form-item v-if="!isEdit" label="双向关系">
        <n-checkbox v-model:checked="createReverse">
          同时创建反向关系（终点 → 起点 / 相同类型）
        </n-checkbox>
      </n-form-item>
    </n-form>

    <template #footer>
      <div class="footer">
        <n-button size="small" @click="close">取消</n-button>
        <n-button
          size="small"
          type="primary"
          :loading="saving"
          :disabled="!store.allEntries.length"
          @click="submit"
        >
          {{ isEdit ? '保存修改' : '创建关系' }}
        </n-button>
      </div>
    </template>
  </n-modal>
</template>

<style scoped>
.tip {
  margin-bottom: 12px;
}

.footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
