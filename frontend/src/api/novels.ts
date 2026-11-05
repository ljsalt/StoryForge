import { api } from './index'

export type NovelStatus = 'planning' | 'writing' | 'paused' | 'completed'

export interface Novel {
  id: string
  title: string
  subtitle: string
  description: string
  genre: string
  tags: string[]
  status: NovelStatus
  cover_color: string
  target_word_count: number
  current_word_count: number
  is_default: boolean
  created_at: string
  updated_at: string
}

export interface NovelStats {
  chapter_count: number
  completed_chapter_count: number
  character_count: number
  character_relation_count: number
  word_count: number
  world_entry_count: number
}

export interface NovelDetail extends Novel {
  stats: NovelStats
}

export interface NovelPayload {
  title: string
  subtitle?: string
  description?: string
  genre?: string
  tags?: string[]
  status?: NovelStatus
  target_word_count?: number
}

export const NOVEL_STATUS_LABELS: Record<NovelStatus, string> = {
  planning: '构思中',
  writing: '创作中',
  paused: '暂停',
  completed: '已完结',
}

export const NOVEL_STATUS_TYPES: Record<
  NovelStatus,
  'default' | 'info' | 'warning' | 'success'
> = {
  planning: 'default',
  writing: 'info',
  paused: 'warning',
  completed: 'success',
}

export const NOVEL_STATUS_OPTIONS = (
  Object.keys(NOVEL_STATUS_LABELS) as NovelStatus[]
).map((value) => ({ label: NOVEL_STATUS_LABELS[value], value }))

export const GENRE_OPTIONS = [
  '玄幻',
  '奇幻',
  '仙侠',
  '都市',
  '科幻',
  '历史',
  '悬疑',
  '武侠',
  '其他',
]

export function listNovels(params: { search?: string; status?: NovelStatus }) {
  return api.get<Novel[]>('/api/novels', { params })
}

export function getNovel(id: string) {
  return api.get<NovelDetail>(`/api/novels/${id}`)
}

export function getDefaultNovel() {
  return api.get<Novel | null>('/api/novels/default')
}

export function createNovel(payload: NovelPayload) {
  return api.post<NovelDetail>('/api/novels', payload)
}

export function updateNovel(id: string, payload: Partial<NovelPayload>) {
  return api.put<NovelDetail>(`/api/novels/${id}`, payload)
}

export function deleteNovel(id: string) {
  return api.delete<{ deleted: boolean; default_cleared: boolean }>(
    `/api/novels/${id}`,
  )
}

export function setDefaultNovel(id: string) {
  return api.put<Novel>(`/api/novels/${id}/default`)
}
