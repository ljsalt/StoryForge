import { api } from './index'
import type { PlotEvent } from './plotEvent'

export type ChapterStatus = 'planned' | 'drafting' | 'completed'

export interface ChapterSummary {
  id: string
  novel_id: string
  chapter_number: number
  volume_number: number | null
  title: string
  summary: string
  status: ChapterStatus
  word_count: number
  sort_order: number
  created_at: string
  updated_at: string
}

export interface Chapter extends ChapterSummary {
  content: string
}

export interface ChapterPayload {
  title: string
  chapter_number?: number
  volume_number?: number | null
  content?: string
  summary?: string
  status?: ChapterStatus
}

export interface ChapterUpdatePayload {
  title?: string
  chapter_number?: number
  volume_number?: number | null
  content?: string
  summary?: string
  status?: ChapterStatus
}

export interface ChapterQuery {
  status?: ChapterStatus | ''
  volume_number?: number
  search?: string
}

export interface ChapterStats {
  chapter_count: number
  completed_chapter_count: number
  drafting_chapter_count: number
  planned_chapter_count: number
  total_word_count: number
}

export interface ChapterRelationEvent {
  id: string
  relation_id: string
  event_type: 'created' | 'updated' | 'ended' | 'restored'
  title: string
  description: string
  previous_data: Record<string, unknown>
  new_data: Record<string, unknown>
  story_time: string | null
  chapter_id: string | null
  chapter_title: string | null
  chapter_number: number | null
  sequence: number
  created_at: string
  source_name: string
  target_name: string
}

export const CHAPTER_STATUS_LABELS: Record<ChapterStatus, string> = {
  planned: '计划中',
  drafting: '写作中',
  completed: '已完成',
}

export const CHAPTER_STATUS_TYPES: Record<
  ChapterStatus,
  'default' | 'info' | 'success'
> = {
  planned: 'default',
  drafting: 'info',
  completed: 'success',
}

export const CHAPTER_STATUS_OPTIONS = (
  Object.keys(CHAPTER_STATUS_LABELS) as ChapterStatus[]
).map((value) => ({ label: CHAPTER_STATUS_LABELS[value], value }))

/** 与后端一致的字数口径：非空白字符数 */
export function countWords(text: string): number {
  return text.replace(/\s/g, '').length
}

export function listChapters(novelId: string, params?: ChapterQuery) {
  return api.get<ChapterSummary[]>(`/api/novels/${novelId}/chapters`, { params })
}

export function getChapter(novelId: string, chapterId: string) {
  return api.get<Chapter>(`/api/novels/${novelId}/chapters/${chapterId}`)
}

export function createChapter(novelId: string, payload: ChapterPayload) {
  return api.post<Chapter>(`/api/novels/${novelId}/chapters`, payload)
}

export function updateChapter(
  novelId: string,
  chapterId: string,
  payload: ChapterUpdatePayload,
) {
  return api.put<Chapter>(`/api/novels/${novelId}/chapters/${chapterId}`, payload)
}

export function deleteChapter(novelId: string, chapterId: string) {
  return api.delete<{ deleted: boolean }>(`/api/novels/${novelId}/chapters/${chapterId}`)
}

export function reorderChapters(novelId: string, orderedIds: string[]) {
  return api.patch<ChapterSummary[]>(`/api/novels/${novelId}/chapters/reorder`, {
    ordered_ids: orderedIds,
  })
}

export function getChapterStats(novelId: string) {
  return api.get<ChapterStats>(`/api/novels/${novelId}/chapters/stats`)
}

export function listChapterPlotEvents(novelId: string, chapterId: string) {
  return api.get<PlotEvent[]>(`/api/novels/${novelId}/chapters/${chapterId}/events`)
}

export function listChapterRelationEvents(novelId: string, chapterId: string) {
  return api.get<ChapterRelationEvent[]>(
    `/api/novels/${novelId}/chapters/${chapterId}/relation-events`,
  )
}
