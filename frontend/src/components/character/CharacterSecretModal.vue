<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { NButton, NForm, NFormItem, NGrid, NGridItem, NInput, NModal, NSelect, useMessage } from 'naive-ui'
import { extractError } from '../../api/error'
import type { CharacterSecret } from '../../api/character'
import { DEFAULT_REVEAL_STATUSES, DEFAULT_SECRECY_LEVELS } from '../../api/character'
import { useCharacterStore } from '../../stores/character'

const props = defineProps<{
  show: boolean
  characterId: string
  secret?: CharacterSecret | null
}>()
const emit = defineEmits<{ 'update:show': [value: boolean]; saved: [] }>()

const store = useCharacterStore()
const message = useMessage()

const isEdit = computed(() => Boolean(props.secret))

const title = ref('')
const content = ref('')
const secrecyLevel = ref('restricted')
const revealStatus = ref('unrevealed')
const notes = ref('')
const saving = ref(false)

const secrecyOptions = computed(() =>
  DEFAULT_SECRECY_LEVELS.map((item) => ({ label: item.label, value: item.value })),
)
const revealOptions = computed(() =>
  DEFAULT_REVEAL_STATUSES.map((item) => ({ label: item.label, value: item.value })),
)

watch(
  () => [props.show, props.secret] as const,
  ([show]) => {
    if (show) {
      const s = props.secret
      title.value = s?.title || ''
      content.value = s?.content || ''
      secrecyLevel.value = s?.secrecy_level || 'restricted'
      revealStatus.value = s?.reveal_status || 'unrevealed'
      notes.value = s?.notes || ''
    }
  },
)

function close() {
  emit('update:show', false)
}

async function submit() {
  const trimmed = title.value.trim()
  if (!trimmed) {
    message.error('秘密标题不能为空')
    return
  }
  saving.value = true
  try {
    const payload = {
      title: trimmed,
      content: content.value.trim(),
      secrecy_level: secrecyLevel.value.trim(),
      reveal_status: revealStatus.value.trim(),
      notes: notes.value.trim(),
    }
    if (isEdit.value && props.secret) {
      await store.updateSecret(props.characterId, props.secret.id, payload)
      message.success('秘密已更新')
    } else {
      await store.createSecret(props.characterId, payload)
      message.success('秘密已创建')
    }
    emit('saved')
    close()
  } catch (error) {
    message.error(extractError(error, '保存秘密失败'))
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <n-modal
    :show="show"
    preset="card"
    :title="isEdit ? '编辑秘密' : '新建秘密'"
    :style="{ width: '600px', maxWidth: 'calc(100vw - 24px)' }"
    :bordered="false"
    @update:show="emit('update:show', $event)"
  >
    <n-form label-placement="top" size="small">
      <n-form-item label="秘密标题" required>
        <n-input v-model:value="title" maxlength="200" placeholder="例如：真实身世" />
      </n-form-item>

      <n-grid :x-gap="12" cols="1 s:2" responsive="screen">
        <n-grid-item>
          <n-form-item label="保密等级">
            <n-select v-model:value="secrecyLevel" :options="secrecyOptions"  />
          </n-form-item>
        </n-grid-item>
        <n-grid-item>
          <n-form-item label="公开状态">
            <n-select v-model:value="revealStatus" :options="revealOptions"  />
          </n-form-item>
        </n-grid-item>
      </n-grid>

      <n-form-item label="具体内容">
        <n-input v-model:value="content" type="textarea" :autosize="{ minRows: 4, maxRows: 10 }" maxlength="5000" show-count />
      </n-form-item>

      <n-form-item label="备注">
        <n-input v-model:value="notes" type="textarea" :autosize="{ minRows: 2, maxRows: 4 }" maxlength="2000" show-count />
      </n-form-item>
    </n-form>

    <template #footer>
      <div class="footer">
        <n-button size="small" @click="close">取消</n-button>
        <n-button size="small" type="primary" :loading="saving" @click="submit">
          {{ isEdit ? '保存修改' : '创建秘密' }}
        </n-button>
      </div>
    </template>
  </n-modal>
</template>

<style scoped>
.footer { display: flex; justify-content: flex-end; gap: 8px; }
</style>
