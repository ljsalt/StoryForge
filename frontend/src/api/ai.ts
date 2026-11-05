import { api } from './index'

/** AI 任务类型 */
export type AiTaskType = 'planner' | 'writer' | 'editor' | 'assistant' | 'default'
export type AiTaskStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
export type ContextPov = 'author' | 'narrative' | 'character'

export const AI_TASK_TYPE_LABELS: Record<AiTaskType, string> = {
  planner: '剧情导演',
  writer: '正文作者',
  editor: '连续性检查',
  assistant: '通用助手',
  default: '默认任务',
}

export const AI_TASK_TYPE_OPTIONS = (Object.keys(AI_TASK_TYPE_LABELS) as AiTaskType[]).map(
  (value) => ({ label: AI_TASK_TYPE_LABELS[value], value }),
)

export const AI_STATUS_LABELS: Record<AiTaskStatus, string> = {
  pending: '等待中',
  running: '执行中',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消',
}

export const AI_STATUS_TYPES: Record<AiTaskStatus, 'default' | 'info' | 'success' | 'error' | 'warning'> = {
  pending: 'default',
  running: 'info',
  completed: 'success',
  failed: 'error',
  cancelled: 'warning',
}

export const POV_LABELS: Record<ContextPov, string> = {
  author: '作者视角（可见全部秘密）',
  narrative: '叙事视角（不注入秘密）',
  character: '角色视角（本阶段不注入秘密）',
}

export interface AiGeneratePayload {
  novel_id: string
  task_type?: AiTaskType
  model_id?: string | null
  system_prompt?: string
  user_prompt: string
  context?: string
  temperature?: number
  max_tokens?: number
  timeout?: number | null
  include_reasoning?: boolean
}

export interface AiGenerateResult {
  success: boolean
  content: string
  reasoning: string
  model: string
  provider: string
  task_type: string
  finish_reason: string | null
  truncated: boolean
  usage: Record<string, number>
  error_code: string | null
  error_message: string | null
  latency_ms: number
  resolved_from: string
  task_id: string | null
  test_only: boolean
}

export interface AiRoutePreview {
  task_type: string
  resolved: boolean
  model_id: string | null
  model_identifier: string | null
  provider_id: string | null
  provider_type: string | null
  resolved_from: string | null
  message: string
}

export interface ContextPreviewPayload {
  novel_id: string
  task_type?: AiTaskType
  chapter_id?: string | null
  character_ids?: string[] | null
  token_budget?: number | null
  pov?: ContextPov
  user_requirement?: string
}

export interface ContextSection {
  key: string
  title: string
  content: string
  tokens: number
  estimated: boolean
  included: boolean
  item_count: number
  priority: number
}

export interface ContextPreview {
  context_text: string
  sections: ContextSection[]
  estimated_tokens: number
  token_budget: number
  omitted_sections: { key: string; title: string; reason: string; dropped_items?: number }[]
  warnings: string[]
}

export interface PromptTemplate {
  id: string
  name: string
  task_type: string
  description: string
  system_prompt: string
  user_prompt_template: string
  version: number
  is_active: boolean
  variables: string[]
  created_at: string
  updated_at: string
}

export interface PromptTemplatePayload {
  name: string
  task_type: string
  description?: string
  system_prompt?: string
  user_prompt_template?: string
  is_active?: boolean
}

export interface PromptTemplateVersion {
  id: string
  template_id: string
  version: number
  name: string
  task_type: string
  description: string
  system_prompt: string
  user_prompt_template: string
  created_at: string
}

export interface AiTask {
  id: string
  novel_id: string
  task_type: string
  model_id: string | null
  model_identifier: string
  provider_id: string | null
  status: AiTaskStatus
  input_summary: string
  output_summary: string
  error_code: string | null
  error_message: string | null
  prompt_template_id: string | null
  template_version: number | null
  input_tokens: number | null
  output_tokens: number | null
  estimated_tokens: number | null
  truncated: boolean
  latency_ms: number | null
  started_at: string | null
  completed_at: string | null
  created_at: string
}

export function aiGenerate(payload: AiGeneratePayload) {
  return api.post<AiGenerateResult>('/api/ai/generate', payload)
}

export function getAiRoute(taskType: AiTaskType, modelId?: string | null) {
  return api.get<AiRoutePreview>('/api/ai/route', {
    params: { task_type: taskType, ...(modelId ? { model_id: modelId } : {}) },
  })
}

export function previewContext(payload: ContextPreviewPayload) {
  return api.post<ContextPreview>('/api/ai/context/preview', payload)
}

export function listPromptTemplates(taskType?: string, includeInactive = false) {
  return api.get<PromptTemplate[]>('/api/ai/prompt-templates', {
    params: {
      ...(taskType ? { task_type: taskType } : {}),
      include_inactive: includeInactive,
    },
  })
}

export function createPromptTemplate(payload: PromptTemplatePayload) {
  return api.post<PromptTemplate>('/api/ai/prompt-templates', payload)
}

export function updatePromptTemplate(id: string, payload: Partial<PromptTemplatePayload>) {
  return api.put<PromptTemplate>(`/api/ai/prompt-templates/${id}`, payload)
}

export function deletePromptTemplate(id: string) {
  return api.delete(`/api/ai/prompt-templates/${id}`)
}

export function listTemplateVersions(id: string) {
  return api.get<PromptTemplateVersion[]>(`/api/ai/prompt-templates/${id}/versions`)
}

export function restoreTemplateVersion(id: string, version: number) {
  return api.post<PromptTemplate>(`/api/ai/prompt-templates/${id}/restore/${version}`)
}

export function listAiTasks(
  novelId: string,
  filters: { status?: AiTaskStatus; task_type?: AiTaskType; limit?: number } = {},
) {
  return api.get<AiTask[]>('/api/ai/tasks', {
    params: { novel_id: novelId, ...filters },
  })
}

export function getAiTask(novelId: string, taskId: string) {
  return api.get<AiTask>(`/api/ai/tasks/${taskId}`, { params: { novel_id: novelId } })
}
