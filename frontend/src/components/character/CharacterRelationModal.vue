<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  NButton,
  NForm,
  NFormItem,
  NGrid,
  NGridItem,
  NInput,
  NInputNumber,
  NModal,
  NSelect,
  NSwitch,
  NText,
  useMessage,
} from 'naive-ui'
import { extractError } from '../../api/error'
import { useCharacterStore } from '../../stores/character'
import { useCharacterRelationStore } from '../../stores/characterRelation'
import { DEFAULT_CHAR_RELATION_TYPES } from '../../api/characterRelation'
import type { CharacterRelation, CharacterRelationPayload } from '../../api/characterRelation'

const props = defineProps<{
  show: boolean
  relation?: CharacterRelation | null
  defaultSourceId?: string
  defaultTargetId?: string
}>()
const emit = defineEmits<{ 'update:show': [v: boolean]; saved: [] }>()

const characterStore = useCharacterStore()
const relationStore = useCharacterRelationStore()
const message = useMessage()

const isEdit = computed(() => Boolean(props.relation))

const sourceId = ref('')
const targetId = ref('')
const relationType = ref('')
const description = ref('')
const strength = ref<number | null>(null)
const bidirectional = ref(false)
const saving = ref(false)

const characterOptions = computed(() =>
  characterStore.characters.map((c) => ({
    label: c.name,
    value: c.id,
    tooltip: c.identity ? `${c.name} — ${c.identity}` : c.name,
  })),
)

const typeOptions = computed(() =>
  DEFAULT_CHAR_RELATION_TYPES.map((t) => ({ label: t, value: t })),
)

watch(
  () => [props.show, props.relation, props.defaultSourceId, props.defaultTargetId] as const,
  ([show]) => {
    if (!show) return
    if (props.relation) {
      sourceId.value = props.relation.source_character_id
      targetId.value = props.relation.target_character_id
      relationType.value = props.relation.relation_type
      description.value = props.relation.description
      strength.value = props.relation.strength
      bidirectional.value = false
    } else {
      sourceId.value = props.defaultSourceId || ''
      targetId.value = props.defaultTargetId || ''
      relationType.value = ''
      description.value = ''
      strength.value = null
      bidirectional.value = false
    }
  },
)

function close() {
  emit('update:show', false)
}

async function submit() {
  const sId = sourceId.value.trim()
  const tId = targetId.value.trim()
  const type = relationType.value.trim()

  if (!sId || !tId) {
    message.error('请选择发起人物和目标人物')
    return
  }
  if (sId === tId) {
    message.error('发起人物和目标人物不能是同一个人')
    return
  }
  if (!type) {
    message.error('请填写关系类型')
    return
  }

  const payload: CharacterRelationPayload = {
    source_character_id: sId,
    target_character_id: tId,
    relation_type: type,
    description: description.value.trim(),
    strength: strength.value,
    attributes: {},
  }

  saving.value = true
  try {
    if (isEdit.value && props.relation) {
      await relationStore.update(props.relation.id, payload)
      message.success('关系已更新')
    } else {
      await relationStore.create(payload, bidirectional.value)
      message.success(bidirectional.value ? '双向关系已创建' : '关系已创建')
    }
    emit('saved')
    close()
  } catch (error) {
    message.error(extractError(error, '保存失败'))
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <n-modal
    :show="show"
    preset="card"
    :title="isEdit ? '编辑人物关系' : '建立人物关系'"
    :style="{ width: '640px', maxWidth: 'calc(100vw - 24px)' }"
    :bordered="false"
    @update:show="emit('update:show', $event)"
  >
    <n-form label-placement="top" size="small">
      <n-grid :x-gap="12" cols="1 s:2" responsive="screen">
        <n-grid-item>
          <n-form-item label="发起人物" required>
            <n-select
              v-model:value="sourceId"
              :options="characterOptions"
              filterable
              placeholder="选择发起关系的人物"
            />
          </n-form-item>
        </n-grid-item>
        <n-grid-item>
          <n-form-item label="目标人物" required>
            <n-select
              v-model:value="targetId"
              :options="characterOptions"
              filterable
              placeholder="选择关系指向的人物"
            />
          </n-form-item>
        </n-grid-item>
      </n-grid>

      <n-form-item label="关系类型" required>
        <n-select
          v-model:value="relationType"
          :options="typeOptions"
          filterable
          placeholder="师徒 / 盟友 / 敌对 / 自定义"
        />
      </n-form-item>

      <n-form-item label="关系描述">
        <n-input
          v-model:value="description"
          type="textarea"
          :autosize="{ minRows: 2, maxRows: 5 }"
          maxlength="2000"
          show-count
          placeholder="例如：顾长生收林远为徒，传授御剑术。"
        />
      </n-form-item>

      <n-grid :x-gap="12" cols="1 s:2" responsive="screen">
        <n-grid-item>
          <n-form-item label="关系强度（0-100 可选）">
            <n-input-number
              v-model:value="strength"
              :min="0"
              :max="100"
              placeholder="例如信任度 60"
              class="full"
            />
          </n-form-item>
        </n-grid-item>
        <n-grid-item>
          <n-form-item v-if="!isEdit" label="">
            <div class="bid-row">
              <n-switch v-model:value="bidirectional" />
              <span class="bid-label">同时建立反向关系（两次独立记录）</span>
            </div>
          </n-form-item>
          <n-form-item v-else label="">
            <n-text depth="3" class="hint">
              编辑仅影响当前这一条关系。要新增反向关系请返回列表再建立。
            </n-text>
          </n-form-item>
        </n-grid-item>
      </n-grid>
    </n-form>

    <template #footer>
      <div class="footer">
        <n-button size="small" @click="close">取消</n-button>
        <n-button size="small" type="primary" :loading="saving" @click="submit">
          {{ isEdit ? '保存修改' : bidirectional ? '创建双向' : '创建关系' }}
        </n-button>
      </div>
    </template>
  </n-modal>
</template>

<style scoped>
.full { width: 100%; }
.footer { display: flex; justify-content: flex-end; gap: 8px; }
.bid-row { display: flex; align-items: center; gap: 8px; padding-top: 4px; }
.bid-label { font-size: 13px; color: rgba(255,255,255,0.75); }
.hint { font-size: 12px; line-height: 1.6; }
</style>
