import { api } from './index'

/** P4.1.3 章节连续性检查与剧情记忆更新接口 */

export type CheckStatus = 'pending' | 'running' | 'completed' | 'failed'
export type OverallResult = 'pass' | 'warning' | 'conflict'
export type Severity = 'info' | 'warning' | 'conflict'
export type ProposalType =
  | 'character_state'
  | 'character_relation'
  | 'character_secret'
  | 'plot_event'
  | 'chapter_summary'
  | 'world_entry'
export type ProposalStatus =
  | 'pending'
  | 'accepted'
  | 'modified'
  | 'rejected'
  | 'applied'
  | 'conflict'
export type BatchStatus =
  | 'pending_review'
  | 'partially_approved'
  | 'approved'
  | 'rejected'
  | 'applied'

export const SEVERITY_LABELS: Record<Severity, string> = {
  info: '提示',
  warning: '可能矛盾',
  conflict: '确定矛盾',
}

export const SEVERITY_TYPES: Record<Severity, 'default' | 'info' | 'warning' | 'error'> = {
  info: 'info',
  warning: 'warning',
  conflict: 'error',
}

export const OVERALL_LABELS: Record<OverallResult, string> = {
  pass: '通过',
  warning: '有疑点',
  conflict: '存在冲突',
}

export const OVERALL_TYPES: Record<OverallResult, 'success' | 'warning' | 'error'> = {
  pass: 'success',
  warning: 'warning',
  conflict: 'error',
}

export const CHECK_STATUS_LABELS: Record<CheckStatus, string> = {
  pending: '排队中',
  running: '检查中',
  completed: '已完成',
  failed: '失败',
}

export const PROPOSAL_TYPE_LABELS: Record<ProposalType, string> = {
  character_state: '人物状态',
  character_relation: '人物关系',
  character_secret: '人物秘密',
  plot_event: '剧情事件',
  chapter_summary: '章节摘要',
  world_entry: '世界观条目',
}

export const PROPOSAL_STATUS_LABELS: Record<ProposalStatus, string> = {
  pending: '待审核',
  accepted: '已接受',
  modified: '已修改',
  rejected: '已拒绝',
  applied: '已应用',
  conflict: '目标冲突',
}

export const PROPOSAL_STATUS_TYPES: Record<
  ProposalStatus,
  'default' | 'info' | 'success' | 'warning' | 'error'
> = {
  pending: 'default',
  accepted: 'success',
  modified: 'info',
  rejected: 'default',
  applied: 'success',
  conflict: 'error',
}

export const BATCH_STATUS_LABELS: Record<BatchStatus, string> = {
  pending_review: '待审核',
  partially_approved: '部分已审',
  approved: '审核完成',
  rejected: '全部拒绝',
  applied: '已应用',
}

export const BATCH_STATUS_TYPES: Record<
  BatchStatus,
  'default' | 'info' | 'success' | 'warning' | 'error'
> = {
  pending_review: 'warning',
  partially_approved: 'info',
  approved: 'success',
  rejected: 'default',
  applied: 'success',
}

export const OPERATION_LABELS: Record<string, string> = {
  create: '新增',
  update: '更新',
  end: '结束',
}

export interface ContinuityIssue {
  severity: Severity
  category: string
  description: string
  evidence: string
  reference: string
  suggestion: string
}

export interface ContinuityReport {
  overall: OverallResult
  issues: ContinuityIssue[]
}

export interface ContinuityCheck {
  id: string
  novel_id: string
  chapter_id: string | null
  status: CheckStatus
  overall_result: OverallResult | null
  report: ContinuityReport
  context_meta: {
    estimated_tokens?: number
    token_budget?: number
    omitted_sections?: { key: string; title: string; reason: string; dropped_items: number }[]
    warnings?: string[]
    auto_detected_characters?: string[]
  }
  model_id: string | null
  task_id: string | null
  error_code: string | null
  error_message: string | null
  created_at: string
  completed_at: string | null
}

export interface MemoryProposal {
  id: string
  batch_id: string
  novel_id: string
  proposal_type: ProposalType
  target_type: string
  target_id: string | null
  operation: string
  before: Record<string, unknown>
  proposed: Record<string, any>
  final: Record<string, any> | null
  reason: string
  source_excerpt: string
  confidence: number
  status: ProposalStatus
  user_note: string
  apply_supported: boolean
  current: unknown
  created_at: string
  reviewed_at: string | null
  applied_at: string | null
}

export interface MemoryBatch {
  id: string
  novel_id: string
  chapter_id: string | null
  check_id: string | null
  status: BatchStatus
  report: { skipped?: string[]; unresolved?: number; counts?: Record<string, number> }
  created_at: string
  reviewed_at: string | null
  applied_at: string | null
  proposal_count?: number
  proposals?: MemoryProposal[]
}

export interface MemoryApplyResult {
  batch: MemoryBatch
  applied: { proposal_id: string; result: string }[]
}

export function createContinuityCheck(
  novelId: string,
  chapterId: string,
  payload: { character_ids?: string[]; model_id?: string; max_tokens?: number } = {},
) {
  return api.post<ContinuityCheck>(
    `/api/novels/${novelId}/chapters/${chapterId}/continuity-checks`,
    payload,
    { timeout: 310000 },
  )
}

export function listContinuityChecks(novelId: string, chapterId: string) {
  return api.get<ContinuityCheck[]>(
    `/api/novels/${novelId}/chapters/${chapterId}/continuity-checks`,
  )
}

export function getContinuityCheck(novelId: string, checkId: string) {
  return api.get<ContinuityCheck>(`/api/novels/${novelId}/continuity-checks/${checkId}`)
}

export function createMemoryBatch(
  novelId: string,
  chapterId: string,
  payload: { check_id?: string; model_id?: string; max_tokens?: number } = {},
) {
  return api.post<MemoryBatch>(
    `/api/novels/${novelId}/chapters/${chapterId}/memory-batches`,
    payload,
    { timeout: 310000 },
  )
}

export function listMemoryBatches(novelId: string, chapterId: string) {
  return api.get<MemoryBatch[]>(`/api/novels/${novelId}/chapters/${chapterId}/memory-batches`)
}

export function getMemoryBatch(novelId: string, batchId: string) {
  return api.get<MemoryBatch>(`/api/novels/${novelId}/memory-batches/${batchId}`)
}

export function updateMemoryProposal(
  novelId: string,
  proposalId: string,
  payload: { final_json: Record<string, unknown>; user_note?: string },
) {
  return api.patch<MemoryProposal>(
    `/api/novels/${novelId}/memory-proposals/${proposalId}`,
    payload,
  )
}

export function acceptMemoryProposal(novelId: string, proposalId: string, userNote = '') {
  return api.post<MemoryProposal>(
    `/api/novels/${novelId}/memory-proposals/${proposalId}/accept`,
    { user_note: userNote },
  )
}

export function rejectMemoryProposal(novelId: string, proposalId: string, userNote = '') {
  return api.post<MemoryProposal>(
    `/api/novels/${novelId}/memory-proposals/${proposalId}/reject`,
    { user_note: userNote },
  )
}

export interface ReviewItem {
  id: string
  action: 'accept' | 'reject' | 'modify' | 'reset'
  final_json?: Record<string, unknown>
  user_note?: string
}

export function reviewMemoryBatch(novelId: string, batchId: string, items: ReviewItem[]) {
  return api.post<MemoryBatch>(`/api/novels/${novelId}/memory-batches/${batchId}/review`, {
    items,
  })
}

export function applyMemoryBatch(novelId: string, batchId: string) {
  return api.post<MemoryApplyResult>(
    `/api/novels/${novelId}/memory-batches/${batchId}/apply`,
    {},
    { timeout: 60000 },
  )
}
