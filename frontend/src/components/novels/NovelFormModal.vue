<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { useMessage } from 'naive-ui'
import {
  NButton,
  NDynamicTags,
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
  NModal,
  NSelect,
  type SelectOption,
} from 'naive-ui'
import {
  GENRE_OPTIONS,
  NOVEL_STATUS_OPTIONS,
  type Novel,
  type NovelPayload,
  type NovelStatus,
} from '../../api/novels'
import { extractError } from '../../api/error'
import { useNovelStore } from '../../stores/novels'

const props = defineProps<{ show: boolean; novel: Novel | null }>()
const emit = defineEmits<{
  (e: 'update:show', value: boolean): void
  (e: 'saved'): void
}>()

const store = useNovelStore()
const message = useMessage()
const saving = ref(false)

const form = reactive({
  title: '',
  subtitle: '',
  description: '',
  genre: '',
  tags: [] as string[],
  status: 'planning' as NovelStatus,
  target_word_count: 100000,
})

const genreOptions: SelectOption[] = GENRE_OPTIONS.map((genre) => ({
  label: genre,
  value: genre,
}))

watch(
  () => props.show,
  (visible) => {
    if (!visible) return
    const novel = props.novel
    form.title = novel?.title ?? ''
    form.subtitle = novel?.subtitle ?? ''
    form.description = novel?.description ?? ''
    form.genre = novel?.genre ?? ''
    form.tags = [...(novel?.tags ?? [])]
    form.status = novel?.status ?? 'planning'
    form.target_word_count = novel?.target_word_count ?? 100000
  },
)

async function submit() {
  if (!form.title.trim()) {
    message.warning('请填写小说名称')
    return
  }
  if (
    !form.target_word_count ||
    form.target_word_count < 1 ||
    form.target_word_count > 10_000_000
  ) {
    message.warning('目标字数需为 1 至 10000000 之间的整数')
    return
  }

  const payload: NovelPayload = {
    title: form.title.trim(),
    subtitle: form.subtitle.trim(),
    description: form.description.trim(),
    genre: form.genre.trim(),
    tags: form.tags,
    status: form.status,
    target_word_count: Math.round(form.target_word_count),
  }

  saving.value = true
  try {
    if (props.novel) {
      await store.updateNovel(props.novel.id, payload)
      message.success('小说信息已更新')
    } else {
      await store.createNovel(payload)
      message.success('小说项目已创建')
    }
    emit('update:show', false)
    emit('saved')
  } catch (error) {
    message.error(extractError(error))
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <n-modal
    :show="show"
    preset="card"
    :title="novel ? '编辑小说' : '新建小说'"
    :style="{ width: 'min(620px, 92vw)' }"
    :mask-closable="false"
    @update:show="emit('update:show', $event)"
  >
    <n-form label-placement="top">
      <n-form-item label="小说名称" required>
        <n-input
          v-model:value="form.title"
          maxlength="100"
          show-count
          placeholder="例如：长夜行"
        />
      </n-form-item>
      <n-form-item label="副标题">
        <n-input v-model:value="form.subtitle" maxlength="100" placeholder="选填" />
      </n-form-item>
      <n-form-item label="小说简介">
        <n-input
          v-model:value="form.description"
          type="textarea"
          :rows="3"
          maxlength="2000"
          show-count
          placeholder="用几句话概括故事的核心设定与主线"
        />
      </n-form-item>
      <div class="grid-two">
        <n-form-item label="题材">
          <n-select
            v-model:value="form.genre"
            :options="genreOptions"
            filterable
            tag
            clearable
            placeholder="选择或输入自定义题材"
          />
        </n-form-item>
        <n-form-item label="创作状态">
          <n-select v-model:value="form.status" :options="NOVEL_STATUS_OPTIONS" />
        </n-form-item>
      </div>
      <n-form-item label="标签">
        <n-dynamic-tags v-model:value="form.tags" :max="10" />
      </n-form-item>
      <n-form-item label="目标字数">
        <n-input-number
          v-model:value="form.target_word_count"
          :min="1"
          :max="10000000"
          :step="1000"
          style="width: 100%"
        />
      </n-form-item>
    </n-form>

    <template #footer>
      <div class="footer">
        <n-button size="small" @click="emit('update:show', false)">取消</n-button>
        <n-button size="small" type="primary" :loading="saving" @click="submit">
          {{ novel ? '保存修改' : '创建项目' }}
        </n-button>
      </div>
    </template>
  </n-modal>
</template>

<style scoped>
.footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.grid-two {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

@media (max-width: 767px) {
  .grid-two {
    grid-template-columns: 1fr;
    gap: 0;
  }
}
</style>
