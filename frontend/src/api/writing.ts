import { api } from './index'

/** P4.1.2 单章节创作工作流接口 */

export type WritingSessionStatus =
  | 'planning'
  | 'awaiting_plan_approval'
  | 'writing'
  | 'paused_for_user'
  | 'draft_ready'
  | 'completed'
  | 'cancelled'
  | 'failed'

export type SegmentStatus = 'pending' | 'generating' | 'completed' | 'failed'

export const WRITING_STATUS_LABELS: Record<WritingSessionStatus, string> = {
  planning: '准备计划',
  awaiting_plan_approval: '等待审核计划',
  writing: '正文写作中',
  paused_for_user: '已暂停',
  draft_ready: '草稿待确认',
  completed: '已写入章节',
  cancelled: '已取消',
  failed: '失败',
}

export const WRITING_STATUS_TYPES: Record<
  WritingSessionStatus,
  'default' | 'info' | 'success' | 'warning' | 'error'
> = {
  planning: 'default',
  awaiting_plan_approval: 'warning',
  writing: 'info',
  paused_for_user: 'warning',
  draft_ready: 'success',
  completed: 'success',
  cancelled: 'default',
  failed: 'error',
}

export const SEGMENT_STATUS_LABELS: Record<SegmentStatus, string> = {
  pending: '待生成',
  generating: '生成中',
  completed: '已完成',
  failed: '失败',
}

export interface PlanScene {
  name: string
  location: string
  characters: string[]
  purpose: string
  actions: string
  conflict: string
  result: string
  transition: string
}

export interface PlanPlotEvent {
  title: string
  description: string
}

export interface PlanDecision {
  decision_id: string
  title: string
  description: string
  context: string
  options: string[]
  recommended_option: string | null
  consequences: string
  is_required: boolean
}

export interface WritingPlan {
  id: string
  session_id: string
  novel_id: string
  version: number
  is_current: boolean
  chapter_goal: string
  opening: string
  scenes: PlanScene[]
  character_actions: string[]
  conflicts: string[]
  plot_events: PlanPlotEvent[]
  foreshadowing: string[]
  ending: string
  estimated_word_count: number
  major_decisions: PlanDecision[]
  source_model: string
  source_task_id: string | null
  created_at: string
  updated_at: string
  decisions?: WritingDecision[]
  session_status?: WritingSessionStatus
}

export interface WritingDecision {
  id: string
  plan_id: string
  decision_key: string
  title: string
  description: string
  context: string
  options: string[]
  recommended_option: string | null
  consequences: string
  is_required: boolean
  selected_option: string | null
  custom_answer: string
  resolved: boolean
  resolved_at: string | null
  sort_order: number
}

export interface DraftSegment {
  id: string
  draft_id: string
  scene_index: number
  sequence: number
  content: string
  status: SegmentStatus
  word_count: number
  attempt: number
  truncated: boolean
  error_code: string | null
  error_message: string | null
  created_at: string
  updated_at: string
}

export interface DraftProgress {
  completed_segments: number
  total_segments: number
  word_count: number
  target_word_count: number
}

export interface WritingDraft {
  id: string
  novel_id: string
  session_id: string
  plan_id: string | null
  chapter_id: string | null
  title: string
  content: string
  word_count: number
  status: 'drafting' | 'ready' | 'confirmed' | 'discarded'
  edited: boolean
  created_at: string
  updated_at: string
  confirmed_at: string | null
  segments: DraftSegment[]
  progress: DraftProgress
}

export interface WritingSession {
  id: string
  novel_id: string
  chapter_id: string | null
  title: string
  status: WritingSessionStatus
  task_type: string
  user_instruction: string
  pov_character_id: string | null
  target_word_count: number
  error_code: string | null
  error_message: string | null
  created_at: string
  updated_at: string
  completed_at: string | null
  plan_version?: number | null
  draft_status?: string | null
  draft_word_count?: number
  plan?: WritingPlan | null
  decisions?: WritingDecision[]
  draft?: WritingDraft | null
}

export interface WritingSessionPayload {
  title?: string
  chapter_id?: string | null
  user_instruction?: string
  pov_character_id?: string | null
  target_word_count?: number
}

export interface SegmentGenerateResult {
  segment: DraftSegment
  draft: WritingDraft
  usage: Record<string, number>
  latency_ms: number | null
  task_id: string | null
  context_estimated_tokens: number
  discarded_manual_edits: boolean
}

export function createWritingSession(novelId: string, payload: WritingSessionPayload) {
  return api.post<WritingSession>(`/api/novels/${novelId}/writing-sessions`, payload)
}

export function listWritingSessions(novelId: string, status?: WritingSessionStatus) {
  return api.get<WritingSession[]>(`/api/novels/${novelId}/writing-sessions`, {
    params: status ? { status } : undefined,
  })
}

export function getWritingSession(novelId: string, sessionId: string) {
  return api.get<WritingSession>(
    `/api/novels/${novelId}/writing-sessions/${sessionId}`,
  )
}

export function updateWritingSession(
  novelId: string,
  sessionId: string,
  payload: Partial<WritingSessionPayload>,
) {
  return api.patch<WritingSession>(
    `/api/novels/${novelId}/writing-sessions/${sessionId}`,
    payload,
  )
}

export function deleteWritingSession(novelId: string, sessionId: string) {
  return api.delete<{ deleted: boolean }>(
    `/api/novels/${novelId}/writing-sessions/${sessionId}`,
  )
}

export function pauseWritingSession(novelId: string, sessionId: string) {
  return api.post<WritingSession>(
    `/api/novels/${novelId}/writing-sessions/${sessionId}/pause`,
  )
}

export function resumeWritingSession(novelId: string, sessionId: string) {
  return api.post<WritingSession>(
    `/api/novels/${novelId}/writing-sessions/${sessionId}/resume`,
  )
}

export function cancelWritingSession(novelId: string, sessionId: string) {
  return api.post<WritingSession>(
    `/api/novels/${novelId}/writing-sessions/${sessionId}/cancel`,
  )
}

export function generateWritingPlan(
  novelId: string,
  sessionId: string,
  payload: { extra_instruction?: string; max_tokens?: number } = {},
) {
  return api.post<{
    plan: WritingPlan
    decisions: WritingDecision[]
    warnings: string[]
    context_estimated_tokens: number
    usage: Record<string, number>
    latency_ms: number | null
    task_id: string | null
  }>(`/api/novels/${novelId}/writing-sessions/${sessionId}/plan/generate`, payload)
}

export function getWritingPlan(novelId: string, sessionId: string) {
  return api.get<WritingPlan>(
    `/api/novels/${novelId}/writing-sessions/${sessionId}/plan`,
  )
}

export function updateWritingPlan(
  novelId: string,
  sessionId: string,
  payload: Omit<WritingPlan, 'id' | 'session_id' | 'novel_id' | 'version' | 'is_current'
    | 'source_model' | 'source_task_id' | 'created_at' | 'updated_at' | 'decisions'
    | 'session_status'>,
) {
  return api.put<WritingPlan>(
    `/api/novels/${novelId}/writing-sessions/${sessionId}/plan`,
    payload,
  )
}

export function approveWritingPlan(
  novelId: string,
  sessionId: string,
  draftTitle?: string,
) {
  return api.post<{ session: WritingSession; draft: WritingDraft }>(
    `/api/novels/${novelId}/writing-sessions/${sessionId}/plan/approve`,
    { draft_title: draftTitle || '' },
  )
}

export function resolveWritingDecision(
  novelId: string,
  sessionId: string,
  decisionKey: string,
  payload: { selected_option?: string; custom_answer?: string },
) {
  return api.post<WritingPlan>(
    `/api/novels/${novelId}/writing-sessions/${sessionId}/decisions/${decisionKey}/resolve`,
    payload,
  )
}

export function getWritingDraft(novelId: string, sessionId: string) {
  return api.get<WritingDraft>(
    `/api/novels/${novelId}/writing-sessions/${sessionId}/draft`,
  )
}

export function updateWritingDraft(
  novelId: string,
  sessionId: string,
  payload: { title?: string; content?: string },
) {
  return api.put<WritingDraft>(
    `/api/novels/${novelId}/writing-sessions/${sessionId}/draft`,
    payload,
  )
}

export function generateWritingSegment(
  novelId: string,
  sessionId: string,
  payload: { sequence?: number; extra_instruction?: string; max_tokens?: number } = {},
) {
  return api.post<SegmentGenerateResult>(
    `/api/novels/${novelId}/writing-sessions/${sessionId}/draft/segments/generate`,
    payload,
    { timeout: 180000 },
  )
}

export function regenerateWritingSegment(
  novelId: string,
  sessionId: string,
  sequence: number,
  payload: { extra_instruction?: string; max_tokens?: number } = {},
) {
  return api.post<SegmentGenerateResult>(
    `/api/novels/${novelId}/writing-sessions/${sessionId}/draft/segments/${sequence}/regenerate`,
    payload,
    { timeout: 180000 },
  )
}

export interface ConfirmDraftResult {
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
  session_id: string
}

export function confirmWritingDraft(
  novelId: string,
  sessionId: string,
  payload: {
    mode: 'new_chapter' | 'replace_existing'
    chapter_title?: string
    summary?: string
  },
) {
  return api.post<ConfirmDraftResult>(
    `/api/novels/${novelId}/writing-sessions/${sessionId}/draft/confirm`,
    payload,
  )
}
