<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
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
import type { Character, CharacterAttributeValue } from '../../api/character'
import { DEFAULT_CHARACTER_ROLES } from '../../api/character'
import { useCharacterStore } from '../../stores/character'

const props = defineProps<{ show: boolean; character?: Character | null }>()
const emit = defineEmits<{ 'update:show': [value: boolean]; saved: [] }>()

const store = useCharacterStore()
const message = useMessage()

const isEdit = computed(() => Boolean(props.character))

const name = ref('')
const aliases = ref<string[]>([])
const gender = ref('')
const age = ref('')
const race = ref('')
const identity = ref('')
const role = ref('')
const appearance = ref('')
const personality = ref('')
const background = ref('')
const abilities = ref('')
const cultivation = ref('')
const affiliation = ref('')
const tags = ref<string[]>([])
const avatarColor = ref('')
const sortOrder = ref(0)
const attrRows = ref<{ key: string; value: string }[]>([])
const saving = ref(false)

const roleOptions = computed(() =>
  DEFAULT_CHARACTER_ROLES.map((r) => ({ label: r, value: r })),
)

function resetForm() {
  const c = props.character
  if (c) {
    name.value = c.name
    aliases.value = [...c.aliases]
    gender.value = c.gender
    age.value = c.age
    race.value = c.race
    identity.value = c.identity
    role.value = c.role
    appearance.value = c.appearance
    personality.value = c.personality
    background.value = c.background
    abilities.value = c.abilities
    cultivation.value = c.cultivation
    affiliation.value = c.affiliation
    tags.value = [...c.tags]
    avatarColor.value = c.avatar_color
    sortOrder.value = c.sort_order
    attrRows.value = Object.entries(c.attributes).map(([key, value]) => ({
      key,
      value: value === null ? '' : String(value),
    }))
  } else {
    name.value = ''
    aliases.value = []
    gender.value = ''
    age.value = ''
    race.value = ''
    identity.value = ''
    role.value = ''
    appearance.value = ''
    personality.value = ''
    background.value = ''
    abilities.value = ''
    cultivation.value = ''
    affiliation.value = ''
    tags.value = []
    avatarColor.value = ''
    sortOrder.value = 0
    attrRows.value = []
  }
}

watch(
  () => [props.show, props.character] as const,
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

function buildAttributes(): Record<string, CharacterAttributeValue> | null {
  const result: Record<string, CharacterAttributeValue> = {}
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
    const v = row.value
    if (v === '' || v === null) {
      result[key] = ''
    } else if (v === 'true') result[key] = true
    else if (v === 'false') result[key] = false
    else if (!Number.isNaN(Number(v)) && v.trim() !== '') result[key] = Number(v)
    else result[key] = v
  }
  return result
}

async function submit() {
  const trimmed = name.value.trim()
  if (!trimmed) {
    message.error('人物姓名不能为空')
    return
  }
  const attributes = buildAttributes()
  if (attributes === null) return

  saving.value = true
  try {
    const payload = {
      name: trimmed,
      aliases: aliases.value.map((a) => a.trim()).filter(Boolean),
      gender: gender.value.trim(),
      age: age.value.trim(),
      race: race.value.trim(),
      identity: identity.value.trim(),
      role: role.value.trim(),
      appearance: appearance.value.trim(),
      personality: personality.value.trim(),
      background: background.value.trim(),
      abilities: abilities.value.trim(),
      cultivation: cultivation.value.trim(),
      affiliation: affiliation.value.trim(),
      tags: tags.value.map((t) => t.trim()).filter(Boolean),
      attributes,
      avatar_color: avatarColor.value.trim(),
      sort_order: Number(sortOrder.value) || 0,
    }
    if (isEdit.value && props.character) {
      await store.update(props.character.id, payload)
      message.success('人物档案已保存')
    } else {
      await store.create(payload)
      message.success('人物已创建')
    }
    emit('saved')
    close()
  } catch (error) {
    message.error(extractError(error, '保存人物失败'))
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <n-modal
    :show="show"
    preset="card"
    :title="isEdit ? '编辑人物档案' : '新建人物'"
    :style="{ width: '760px', maxWidth: 'calc(100vw - 24px)' }"
    :bordered="false"
    @update:show="emit('update:show', $event)"
  >
    <n-form label-placement="top" size="small">
      <n-form-item label="姓名" required>
        <n-input v-model:value="name" maxlength="100" placeholder="至少填写姓名，其他信息可后续补充" />
      </n-form-item>

      <n-grid :x-gap="12" cols="1 s:2" responsive="screen">
        <n-grid-item>
          <n-form-item label="别名">
            <n-dynamic-tags v-model:value="aliases" :max="20" />
          </n-form-item>
        </n-grid-item>
        <n-grid-item>
          <n-form-item label="人物定位">
            <n-select
              v-model:value="role"
              :options="roleOptions"
              clearable
              filterable
              placeholder="例如：主角、反派、配角"
            />
          </n-form-item>
        </n-grid-item>
      </n-grid>

      <n-grid :x-gap="12" cols="2 s:3 m:6" responsive="screen">
        <n-grid-item>
          <n-form-item label="性别">
            <n-input v-model:value="gender" maxlength="30" placeholder="女 / 男 / 其他" />
          </n-form-item>
        </n-grid-item>
        <n-grid-item>
          <n-form-item label="年龄">
            <n-input v-model:value="age" maxlength="40" placeholder="约两百岁 / 未知" />
          </n-form-item>
        </n-grid-item>
        <n-grid-item>
          <n-form-item label="种族">
            <n-input v-model:value="race" maxlength="50" placeholder="灵族 / 人族 / 魔族" />
          </n-form-item>
        </n-grid-item>
        <n-grid-item>
          <n-form-item label="身份">
            <n-input v-model:value="identity" maxlength="500" placeholder="青云宗弟子" />
          </n-form-item>
        </n-grid-item>
        <n-grid-item>
          <n-form-item label="所属势力">
            <n-input v-model:value="affiliation" maxlength="500" placeholder="青云宗" />
          </n-form-item>
        </n-grid-item>
        <n-grid-item>
          <n-form-item label="排序">
            <n-input-number v-model:value="sortOrder" :min="0" :max="100000" class="full" />
          </n-form-item>
        </n-grid-item>
      </n-grid>

      <n-form-item label="外貌描述">
        <n-input
          v-model:value="appearance"
          type="textarea"
          :autosize="{ minRows: 2, maxRows: 4 }"
          maxlength="5000"
          show-count
        />
      </n-form-item>

      <n-form-item label="性格描述">
        <n-input
          v-model:value="personality"
          type="textarea"
          :autosize="{ minRows: 2, maxRows: 4 }"
          maxlength="5000"
          show-count
        />
      </n-form-item>

      <n-form-item label="人物背景">
        <n-input
          v-model:value="background"
          type="textarea"
          :autosize="{ minRows: 3, maxRows: 6 }"
          maxlength="5000"
          show-count
        />
      </n-form-item>

      <n-grid :x-gap="12" cols="1 s:2" responsive="screen">
        <n-grid-item>
          <n-form-item label="能力与天赋">
            <n-input
              v-model:value="abilities"
              type="textarea"
              :autosize="{ minRows: 2, maxRows: 5 }"
              maxlength="5000"
              show-count
            />
          </n-form-item>
        </n-grid-item>
        <n-grid-item>
          <n-form-item label="修为 / 力量等级">
            <n-input v-model:value="cultivation" maxlength="200" placeholder="金丹后期 / 元婴初期" />
          </n-form-item>
          <n-form-item label="头像颜色">
            <n-input v-model:value="avatarColor" maxlength="20" placeholder="#3b5bdb" />
          </n-form-item>
        </n-grid-item>
      </n-grid>

      <n-form-item label="标签">
        <n-dynamic-tags v-model:value="tags" :max="10" />
      </n-form-item>

      <n-form-item label="自定义属性">
        <div class="attr-list">
          <div v-for="(row, index) in attrRows" :key="index" class="attr-row">
            <n-input v-model:value="row.key" placeholder="属性名" maxlength="50" />
            <n-input v-model:value="row.value" placeholder="属性值（留空或数字/布尔）" maxlength="500" />
            <n-button size="small" quaternary type="error" @click="removeAttribute(index)">删除</n-button>
          </div>
          <n-button size="small" dashed @click="addAttribute">+ 添加属性</n-button>
        </div>
      </n-form-item>
    </n-form>

    <template #footer>
      <div class="footer">
        <n-button size="small" @click="close">取消</n-button>
        <n-button size="small" type="primary" :loading="saving" @click="submit">
          {{ isEdit ? '保存修改' : '创建人物' }}
        </n-button>
      </div>
    </template>
  </n-modal>
</template>

<style scoped>
.full { width: 100%; }

.attr-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.attr-row {
  display: flex;
  gap: 8px;
  align-items: center;
}

.attr-row > :first-child { flex: 0 0 32%; }
.attr-row > :nth-child(2) { flex: 1; }

.footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

@media (max-width: 767px) {
  .attr-row { flex-wrap: wrap; }
  .attr-row > :first-child { flex: 1 1 100%; }
  .attr-row > :nth-child(2) { flex: 1 1 70%; }
}
</style>
