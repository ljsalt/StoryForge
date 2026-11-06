<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { NButton, NInput, NModal, useMessage } from 'naive-ui'
import type { MemoryProposal } from '../../api/continuity'

const props = defineProps<{
  show: boolean
  proposal: MemoryProposal | null
  busy: boolean
}>()
const emit = defineEmits<{
  (e: 'update:show', value: boolean): void
  (e: 'save', payload: { final_json: Record<string, unknown>; user_note: string }): void
}>()

const message = useMessage()
const jsonText = ref('')
const userNote = ref('')

watch(
  () => [props.show, props.proposal],
  () => {
    if (props.show && props.proposal) {
      const source = props.proposal.final || props.proposal.proposed
      jsonText.value = JSON.stringify(source, null, 2)
      userNote.value = props.proposal.user_note || ''
    }
  },
  { immediate: true },
)

const valid = computed(() => {
  try {
    const parsed = JSON.parse(jsonText.value)
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed)
  } catch {
    return false
  }
})

function save() {
  if (!valid.value) {
    message.error('内容必须是合法的 JSON 对象')
    return
  }
  emit('save', { final_json: JSON.parse(jsonText.value), user_note: userNote.value.trim() })
}
</script>

<template>
  <n-modal
    :show="show"
    preset="card"
    title="修改提案内容"
    style="width: min(640px, 94vw)"
    @update:show="emit('update:show', $event)"
  >
    <div class="hint">
      修改后的内容才是最终提交内容；提交时不会再被 AI 覆盖。
      请保持字段结构与 AI 建议一致，仅调整取值。
    </div>
    <n-input
      v-model:value="jsonText"
      type="textarea"
      :rows="12"
      :status="valid || !jsonText ? undefined : 'error'"
      placeholder="提案内容 JSON"
      class="editor"
    />
    <n-input
      v-model:value="userNote"
      type="textarea"
      :rows="2"
      placeholder="审核备注（可选）"
      class="note"
    />
    <template #footer>
      <div class="footer">
        <n-button :disabled="busy" @click="emit('update:show', false)">取消</n-button>
        <n-button type="primary" :disabled="busy || !valid" :loading="busy" @click="save">
          保存并标记为已修改
        </n-button>
      </div>
    </template>
  </n-modal>
</template>

<style scoped>
.hint {
  font-size: 12px;
  color: var(--sf-text-tertiary, #888);
  margin-bottom: 10px;
  line-height: 1.6;
}
.editor {
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
}
.note {
  margin-top: 10px;
}
.footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
