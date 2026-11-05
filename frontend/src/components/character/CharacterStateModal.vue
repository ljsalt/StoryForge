<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  NButton,
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
import type { CharacterState, CharacterAttributeValue } from '../../api/character'
import { DEFAULT_LIFE_STATUSES } from '../../api/character'
import { useCharacterStore } from '../../stores/character'

const props = defineProps<{
  show: boolean
  characterId: string
  state?: CharacterState | null
}>()
const emit = defineEmits<{ 'update:show': [value: boolean]; saved: [] }>()

const store = useCharacterStore()
const message = useMessage()

const lifeStatus = ref('alive')
const currentLocation = ref('')
const currentFaction = ref('')
const currentCultivation = ref('')
const healthStatus = ref('')
const emotionalState = ref('')
const currentGoal = ref('')
const currentStatus = ref('')
const attrRows = ref<{ key: string; value: string }[]>([])
const saving = ref(false)

const lifeStatusOptions = computed(() =>
  DEFAULT_LIFE_STATUSES.map((item) => ({ label: item.label, value: item.value })),
)

watch(
  () => [props.show, props.state] as const,
  ([show]) => {
    if (show) {
      const s = props.state
      lifeStatus.value = s?.life_status || 'alive'
      currentLocation.value = s?.current_location || ''
      currentFaction.value = s?.current_faction || ''
      currentCultivation.value = s?.current_cultivation || ''
      healthStatus.value = s?.health_status || ''
      emotionalState.value = s?.emotional_state || ''
      currentGoal.value = s?.current_goal || ''
      currentStatus.value = s?.current_status || ''
      attrRows.value = Object.entries(s?.attributes || {}).map(([k, v]) => ({
        key: k,
        value: v === null ? '' : String(v),
      }))
    }
  },
)

function close() {
  emit('update:show', false)
}

function addAttribute() {
  attrRows.value.push({ key: '', value: '' })
}

function removeAttribute(index: number) {
  attrRows.value.splice(index, 1)
}

function buildAttributes(): Record<string, CharacterAttributeValue> | null {
  const result: Record<string, CharacterAttributeValue> = {}
  for (const row of attrRows.value) {
    const key = row.key.trim()
    if (!key) {
      if (row.value.trim()) {
        message.error('存在未填写属性名的属性')
        return null
      }
      continue
    }
    if (key in result) {
      message.error(`属性名“${key}”重复`)
      return null
    }
    const v = row.value
    if (v === '' || v === null) result[key] = ''
    else if (v === 'true') result[key] = true
    else if (v === 'false') result[key] = false
    else if (!Number.isNaN(Number(v)) && v.trim() !== '') result[key] = Number(v)
    else result[key] = v
  }
  return result
}

async function submit() {
  const attributes = buildAttributes()
  if (attributes === null) return
  saving.value = true
  try {
    await store.updateState(props.characterId, {
      life_status: lifeStatus.value.trim(),
      current_location: currentLocation.value.trim(),
      current_faction: currentFaction.value.trim(),
      current_cultivation: currentCultivation.value.trim(),
      health_status: healthStatus.value.trim(),
      emotional_state: emotionalState.value.trim(),
      current_goal: currentGoal.value.trim(),
      current_status: currentStatus.value.trim(),
      attributes,
    })
    message.success('当前状态已更新')
    emit('saved')
    close()
  } catch (error) {
    message.error(extractError(error, '保存当前状态失败'))
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <n-modal
    :show="show"
    preset="card"
    title="编辑当前状态"
    :style="{ width: '640px', maxWidth: 'calc(100vw - 24px)' }"
    :bordered="false"
    @update:show="emit('update:show', $event)"
  >
    <div class="hint">
      这里描述人物在当前剧情时间点的即时状态。人物长期设定留在档案里，此处会随剧情更新。
    </div>

    <n-form label-placement="top" size="small">
      <n-grid :x-gap="12" cols="2 s:4" responsive="screen">
        <n-grid-item>
          <n-form-item label="生死状态">
            <n-select
              v-model:value="lifeStatus"
              :options="lifeStatusOptions"
            />
          </n-form-item>
        </n-grid-item>
        <n-grid-item>
          <n-form-item label="当前位置">
            <n-input v-model:value="currentLocation" maxlength="500" />
          </n-form-item>
        </n-grid-item>
        <n-grid-item>
          <n-form-item label="当前阵营">
            <n-input v-model:value="currentFaction" maxlength="500" />
          </n-form-item>
        </n-grid-item>
        <n-grid-item>
          <n-form-item label="当前修为">
            <n-input v-model:value="currentCultivation" maxlength="200" />
          </n-form-item>
        </n-grid-item>
      </n-grid>

      <n-form-item label="伤势与健康">
        <n-input v-model:value="healthStatus" type="textarea" :autosize="{ minRows: 2, maxRows: 4 }" maxlength="2000" show-count />
      </n-form-item>
      <n-form-item label="当前情绪">
        <n-input v-model:value="emotionalState" type="textarea" :autosize="{ minRows: 2, maxRows: 4 }" maxlength="2000" show-count />
      </n-form-item>
      <n-form-item label="当前目标">
        <n-input v-model:value="currentGoal" type="textarea" :autosize="{ minRows: 2, maxRows: 4 }" maxlength="2000" show-count />
      </n-form-item>
      <n-form-item label="其他状态描述">
        <n-input v-model:value="currentStatus" type="textarea" :autosize="{ minRows: 2, maxRows: 4 }" maxlength="2000" show-count />
      </n-form-item>

      <n-form-item label="状态自定义属性">
        <div class="attr-list">
          <div v-for="(row, index) in attrRows" :key="index" class="attr-row">
            <n-input v-model:value="row.key" placeholder="属性名" maxlength="50" />
            <n-input v-model:value="row.value" placeholder="值" maxlength="500" />
            <n-button size="small" quaternary type="error" @click="removeAttribute(index)">删除</n-button>
          </div>
          <n-button size="small" dashed @click="addAttribute">+ 添加属性</n-button>
        </div>
      </n-form-item>
    </n-form>

    <template #footer>
      <div class="footer">
        <n-button size="small" @click="close">取消</n-button>
        <n-button size="small" type="primary" :loading="saving" @click="submit">保存</n-button>
      </div>
    </template>
  </n-modal>
</template>

<style scoped>
.hint {
  margin-bottom: 12px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.45);
}
.attr-list { display: flex; flex-direction: column; gap: 8px; }
.attr-row { display: flex; gap: 8px; align-items: center; }
.attr-row > :first-child { flex: 0 0 32%; }
.attr-row > :nth-child(2) { flex: 1; }
.footer { display: flex; justify-content: flex-end; gap: 8px; }
</style>
