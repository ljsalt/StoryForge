import { api } from './index'

/** P4.2 快速写作与写作预设接口 */

export type ContextMode = 'auto' | 'recent' | 'full' | 'custom'
export type QuickSessionStatus = 'drafting' | 'ready' | 'confirmed' | 'discarded' | 'failed'
export type SegmentStatus = 'completed' | 'failed'

export interface WritingPresetConfig {
  writing_style: string
  narrative_perspective: string
  person: string
  language_style: string
  dialogue_style: string
  style_constraints: string
  extra_prompt: string
  adult_genres: string[]
  relationship_background: string
  adult_narrative_style: string
  intensity: string
  conventions: string
  forbidden: string
}

export interface WritingPreset {
  id: string
  name: string
  description: string
  system_prompt: string
  config: WritingPresetConfig
  version: number
  is_active: boolean
  is_default: boolean
  variables: string[]
  created_at: string
  updated_at: string
}

export interface WritingPresetPayload {
  name: string
  description?: string
  system_prompt?: string
  config?: Partial<WritingPresetConfig>
  is_active?: boolean
  is_default?: boolean
}

export interface QuickWritingSegment {
  id: string
  session_id: string
  seq: number
  content: string
  word_count: number
  status: SegmentStatus
  error_code: string | null
  error_message: string | null
  task_id: string | null
  created_at: string
  updated_at: string
}

export interface QuickWritingSession {
  id: string
  novel_id: string
  chapter_id: string | null
  title: string
  user_requirement: string
  preset_id: string | null
  preset_name: string
  model_id: string | null
  model_label: string
  context_mode: ContextMode
  context_options: Record<string, unknown>
  style_overrides: Record<string, unknown>
  target_word_count: number
  segment_words: number
  auto_continuity: boolean
  auto_memory: boolean
  remind_memory: boolean
  status: QuickSessionStatus
  content: string
  word_count: number
  edited: boolean
  error_code: string | null
  error_message: string | null
  generating_seq: number | null
  created_at: string
  updated_at: string
  confirmed_at: string | null
  segments: QuickWritingSegment[]
  progress: {
    completed_segments: number
    total_segments: number
    target_word_count: number
    remaining_words: number
  }
}

export interface QuickWritingSessionCreate {
  title?: string
  user_requirement?: string
  preset_id?: string | null
  model_id?: string | null
  context_mode?: ContextMode
  context_options?: Record<string, unknown>
  style_overrides?: Record<string, unknown>
  target_word_count?: number
  segment_words?: number
  auto_continuity?: boolean
  auto_memory?: boolean
  remind_memory?: boolean
  chapter_id?: string | null
}

export interface QuickWritingSessionUpdate
  extends Partial<Omit<QuickWritingSessionCreate, 'chapter_id'>> {
  chapter_id?: string | null
}

export interface QuickWritingGenerateResult {
  session: QuickWritingSession
  segment_seq: number
  usage: Record<string, unknown>
  latency_ms: number | null
  task_id: string | null
  model: string
  provider: string
  resolved_from: string | null
  context_estimated_tokens: number
  context_token_budget: number
  context_omitted_sections: { key: string; title: string; reason: string; dropped_items: number }[]
  context_warnings: string[]
  discarded_manual_edits: boolean
}

export interface QuickWritingConfirmResult {
  chapter: {
    id: string
    novel_id: string
    chapter_number: number
    title: string
    summary: string
    status: string
    word_count: number
    created_at: string
    updated_at: string
  }
  mode: 'new_chapter' | 'replace_existing'
  session: QuickWritingSession
  reminders: {
    auto_continuity: boolean
    auto_memory: boolean
    remind_memory: boolean
  }
}

export interface QuickWritingMeta {
  context_modes: ContextMode[]
  context_mode_labels: Record<ContextMode, string>
  section_keys: string[]
  section_labels: Record<string, string>
}

export const CONTEXT_MODE_LABELS: Record<ContextMode, string> = {
  auto: '自动（记忆 + 最近章节）',
  recent: '最近章节优先',
  full: '完整设定',
  custom: '自定义注入',
}

export const CONTEXT_MODE_HINTS: Record<ContextMode, string> = {
  auto: '根据小说记忆与最近章节自动选择上下文，适合大多数情况',
  recent: '只保留最近章节正文与剧情记忆，适合紧接上一章继续写',
  full: '注入人物、世界观、关系与剧情记忆，适合需要严格一致的长篇续写',
  custom: '自行选择要注入的内容分区，完全控制上下文',
}

export const CONTEXT_SECTION_LABELS: Record<string, string> = {
  core_settings: '核心设定与世界观',
  current_task: '当前章节与写作要求',
  characters: '人物档案',
  character_states: '人物当前状态',
  character_relations: '人物关系',
  character_secrets: '人物秘密',
  plot_history: '剧情历史与章节摘要',
}

export const SESSION_STATUS_LABELS: Record<QuickSessionStatus, string> = {
  drafting: '写作中',
  ready: '可保存',
  confirmed: '已保存',
  discarded: '已放弃',
  failed: '失败',
}

export const SESSION_STATUS_TYPES: Record<
  QuickSessionStatus,
  'default' | 'info' | 'success' | 'warning' | 'error'
> = {
  drafting: 'info',
  ready: 'success',
  confirmed: 'success',
  discarded: 'default',
  failed: 'error',
}

// ---- 预设管理 ----

export function listWritingPresets(includeInactive = true) {
  return api.get<WritingPreset[]>('/api/writing-presets', {
    params: { include_inactive: includeInactive },
  })
}

export function createWritingPreset(payload: WritingPresetPayload) {
  return api.post<WritingPreset>('/api/writing-presets', payload)
}

export function updateWritingPreset(id: string, payload: Partial<WritingPresetPayload>) {
  return api.put<WritingPreset>(`/api/writing-presets/${id}`, payload)
}

export function deleteWritingPreset(id: string) {
  return api.delete<{ deleted: boolean }>(`/api/writing-presets/${id}`)
}

export function copyWritingPreset(id: string, name = '') {
  return api.post<WritingPreset>(`/api/writing-presets/${id}/copy`, { name })
}

export function setDefaultWritingPreset(id: string) {
  return api.post<WritingPreset>(`/api/writing-presets/${id}/default`, {})
}

export function getNovelWritingPreset(novelId: string) {
  return api.get<{ novel_id: string; preset_id: string | null; preset: WritingPreset | null }>(
    `/api/novels/${novelId}/writing-preset`,
  )
}

export function setNovelWritingPreset(novelId: string, presetId: string | null) {
  return api.put(`/api/novels/${novelId}/writing-preset`, { preset_id: presetId })
}

// ---- 快速写作 ----

export function getQuickWritingMeta() {
  return api.get<QuickWritingMeta>('/api/quick-writing/meta')
}

export function listQuickWritingSessions(novelId: string, status?: string) {
  return api.get<QuickWritingSession[]>(
    `/api/novels/${novelId}/quick-writing-sessions`,
    { params: status ? { status } : undefined },
  )
}

export function createQuickWritingSession(novelId: string, payload: QuickWritingSessionCreate) {
  return api.post<QuickWritingSession>(
    `/api/novels/${novelId}/quick-writing-sessions`,
    payload,
  )
}

export function getQuickWritingSession(novelId: string, sessionId: string) {
  return api.get<QuickWritingSession>(
    `/api/novels/${novelId}/quick-writing-sessions/${sessionId}`,
  )
}

export function updateQuickWritingSession(
  novelId: string,
  sessionId: string,
  payload: QuickWritingSessionUpdate,
) {
  return api.patch<QuickWritingSession>(
    `/api/novels/${novelId}/quick-writing-sessions/${sessionId}`,
    payload,
  )
}

export function deleteQuickWritingSession(novelId: string, sessionId: string) {
  return api.delete(`/api/novels/${novelId}/quick-writing-sessions/${sessionId}`)
}

export function discardQuickWritingSession(novelId: string, sessionId: string) {
  return api.post<QuickWritingSession>(
    `/api/novels/${novelId}/quick-writing-sessions/${sessionId}/discard`,
    {},
  )
}

export function generateQuickWritingSegment(
  novelId: string,
  sessionId: string,
  payload: {
    seq?: number
    extra_instruction?: string
    temperature?: number
    max_tokens?: number
  } = {},
) {
  // 单段长正文可能耗时数分钟，单独放宽超时
  return api.post<QuickWritingGenerateResult>(
    `/api/novels/${novelId}/quick-writing-sessions/${sessionId}/generate`,
    payload,
    { timeout: 310000 },
  )
}

export function updateQuickWritingContent(
  novelId: string,
  sessionId: string,
  content: string,
) {
  return api.put<QuickWritingSession>(
    `/api/novels/${novelId}/quick-writing-sessions/${sessionId}/content`,
    { content },
  )
}

export function previewQuickWritingContext(novelId: string, sessionId: string) {
  return api.post<{
    context_text: string
    sections: { key: string; title: string; content: string; tokens: number }[]
    estimated_tokens: number
    token_budget: number
    omitted_sections: { key: string; title: string; reason: string; dropped_items: number }[]
    warnings: string[]
  }>(`/api/novels/${novelId}/quick-writing-sessions/${sessionId}/context-preview`)
}

export function confirmQuickWritingSession(
  novelId: string,
  sessionId: string,
  payload: {
    mode?: 'new_chapter' | 'replace_existing'
    chapter_title?: string
    summary?: string
  } = {},
) {
  return api.post<QuickWritingConfirmResult>(
    `/api/novels/${novelId}/quick-writing-sessions/${sessionId}/confirm`,
    payload,
    { timeout: 60000 },
  )
}
