import { api } from './index'

export type ProviderType = 'deepseek' | 'openai_compatible' | 'custom'
export type TaskKey = 'planner' | 'writer' | 'editor' | 'assistant'

export interface Provider {
  id: string
  name: string
  provider_type: ProviderType
  base_url: string
  enabled: boolean
  has_api_key: boolean
  api_key_masked: string
  created_at: string
  updated_at: string
}

export interface ProviderPayload {
  name?: string
  provider_type?: ProviderType
  base_url?: string
  api_key?: string | null
  enabled?: boolean
}

export interface ModelItem {
  id: string
  provider_id: string
  provider_name: string
  provider_type: ProviderType
  name: string
  model_id: string
  remark: string
  enabled: boolean
  created_at: string
  updated_at: string
}

export interface ModelPayload {
  provider_id?: string
  name?: string
  model_id?: string
  remark?: string
  enabled?: boolean
}

export interface ModelTestResult {
  success: boolean
  latency_ms: number
  method: string
  error_code: string | null
  message: string
  model_identifier: string
}

export interface TaskSetting {
  task: TaskKey
  model_id: string | null
}

export interface ModelSettings {
  tasks: TaskSetting[]
  default_model_id: string | null
}

export const PROVIDER_TYPE_LABELS: Record<ProviderType, string> = {
  deepseek: 'DeepSeek 官方',
  openai_compatible: 'OpenAI 兼容',
  custom: '自定义',
}

export const TASK_LABELS: Record<TaskKey, string> = {
  planner: '剧情导演',
  writer: '正文作者',
  editor: '连续性编辑',
  assistant: '普通辅助',
}

export const TASK_DESCRIPTIONS: Record<TaskKey, string> = {
  planner: '负责剧情规划与结构推进',
  writer: '负责正文章节撰写',
  editor: '负责前后文一致性与修订建议',
  assistant: '负责摘要、命名等普通辅助任务',
}

export function listProviders() {
  return api.get<Provider[]>('/api/providers')
}

export function createProvider(payload: ProviderPayload) {
  return api.post<Provider>('/api/providers', payload)
}

export function updateProvider(id: string, payload: ProviderPayload) {
  return api.put<Provider>(`/api/providers/${id}`, payload)
}

export function deleteProvider(id: string) {
  return api.delete<{ deleted: boolean; deleted_models: number }>(
    `/api/providers/${id}`,
  )
}

export function listModels(providerId?: string) {
  return api.get<ModelItem[]>('/api/models', {
    params: providerId ? { provider_id: providerId } : undefined,
  })
}

export function createModel(payload: ModelPayload) {
  return api.post<ModelItem>('/api/models', payload)
}

export function updateModel(id: string, payload: ModelPayload) {
  return api.put<ModelItem>(`/api/models/${id}`, payload)
}

export function deleteModel(id: string) {
  return api.delete<{ deleted: boolean }>(`/api/models/${id}`)
}

export function testModel(modelId: string) {
  // 连接测试可能等待服务商响应，单独放宽超时
  return api.post<ModelTestResult>(
    '/api/models/test',
    { model_id: modelId },
    { timeout: 35000 },
  )
}

export function getModelSettings() {
  return api.get<ModelSettings>('/api/model-settings')
}

export function saveModelSettings(payload: {
  tasks: Partial<Record<TaskKey, string | null>>
  default_model_id: string | null
}) {
  return api.put<ModelSettings>('/api/model-settings', payload)
}
