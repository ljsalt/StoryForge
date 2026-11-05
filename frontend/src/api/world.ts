import { api } from './index'

export type WorldAttributeValue = string | number | boolean | null

export interface WorldCategory {
  id: string
  novel_id: string
  name: string
  description: string
  sort_order: number
  entry_count: number
  created_at: string
  updated_at: string
}

export interface WorldCategoryPayload {
  name: string
  description?: string
  sort_order?: number
}

export interface WorldEntry {
  id: string
  novel_id: string
  category_id: string
  category_name: string
  name: string
  summary: string
  content: string
  tags: string[]
  attributes: Record<string, WorldAttributeValue>
  parent_id: string | null
  parent_name: string | null
  sort_order: number
  created_at: string
  updated_at: string
}

export interface WorldEntryPayload {
  name: string
  category_id: string
  summary?: string
  content?: string
  tags?: string[]
  attributes?: Record<string, WorldAttributeValue>
  parent_id?: string | null
  sort_order?: number
}

export interface WorldEntryQuery {
  search?: string
  category_id?: string
  tag?: string
  parent_id?: string
}

export interface WorldCategoryCount {
  category_id: string
  name: string
  count: number
}

export interface WorldRelationTypeCount {
  relation_type: string
  count: number
}

export interface WorldStats {
  total_entries: number
  category_count: number
  by_category: WorldCategoryCount[]
  total_relations: number
  relation_type_count: number
  relation_by_type: WorldRelationTypeCount[]
  related_entry_count: number
  latest_updated_at: string | null
}

export interface WorldRelationEndpoint {
  id: string
  name: string
  category_id: string
  category_name: string
}

export interface WorldRelation {
  id: string
  novel_id: string
  source_entry_id: string
  target_entry_id: string
  relation_type: string
  description: string
  source: WorldRelationEndpoint
  target: WorldRelationEndpoint
  created_at: string
  updated_at: string
}

export interface WorldEntryRelation extends WorldRelation {
  direction: 'outgoing' | 'incoming'
}

export interface WorldEntryRelations {
  entry_id: string
  outgoing: WorldEntryRelation[]
  incoming: WorldEntryRelation[]
}

export interface WorldRelationPayload {
  source_entry_id: string
  target_entry_id: string
  relation_type: string
  description?: string
}

export interface WorldRelationQuery {
  relation_type?: string
  source_entry_id?: string
  target_entry_id?: string
  search?: string
}

/** 关系类型的建议默认值；用户仍可输入自定义类型。 */
export const DEFAULT_RELATION_TYPES = [
  '属于',
  '管辖',
  '位于',
  '控制',
  '联盟',
  '敌对',
  '贸易',
  '师承',
  '起源于',
  '依赖',
  '克制',
  '其他',
]

export function listWorldCategories(novelId: string) {
  return api.get<WorldCategory[]>(`/api/novels/${novelId}/world/categories`)
}

export function createWorldCategory(novelId: string, payload: WorldCategoryPayload) {
  return api.post<WorldCategory>(`/api/novels/${novelId}/world/categories`, payload)
}

export function updateWorldCategory(
  novelId: string,
  categoryId: string,
  payload: Partial<WorldCategoryPayload>,
) {
  return api.put<WorldCategory>(
    `/api/novels/${novelId}/world/categories/${categoryId}`,
    payload,
  )
}

export function deleteWorldCategory(novelId: string, categoryId: string) {
  return api.delete<{ deleted: boolean }>(
    `/api/novels/${novelId}/world/categories/${categoryId}`,
  )
}

export function listWorldEntries(novelId: string, query: WorldEntryQuery = {}) {
  return api.get<WorldEntry[]>(`/api/novels/${novelId}/world/entries`, {
    params: query,
  })
}

export function getWorldEntry(novelId: string, entryId: string) {
  return api.get<WorldEntry>(`/api/novels/${novelId}/world/entries/${entryId}`)
}

export function createWorldEntry(novelId: string, payload: WorldEntryPayload) {
  return api.post<WorldEntry>(`/api/novels/${novelId}/world/entries`, payload)
}

export function updateWorldEntry(
  novelId: string,
  entryId: string,
  payload: Partial<WorldEntryPayload>,
) {
  return api.put<WorldEntry>(
    `/api/novels/${novelId}/world/entries/${entryId}`,
    payload,
  )
}

export function deleteWorldEntry(novelId: string, entryId: string) {
  return api.delete<{ deleted: boolean }>(
    `/api/novels/${novelId}/world/entries/${entryId}`,
  )
}

export function getWorldStats(novelId: string) {
  return api.get<WorldStats>(`/api/novels/${novelId}/world/stats`)
}

export function listWorldRelations(novelId: string, query: WorldRelationQuery = {}) {
  return api.get<WorldRelation[]>(`/api/novels/${novelId}/world/relations`, {
    params: query,
  })
}

export function getWorldRelation(novelId: string, relationId: string) {
  return api.get<WorldRelation>(
    `/api/novels/${novelId}/world/relations/${relationId}`,
  )
}

export function createWorldRelation(novelId: string, payload: WorldRelationPayload) {
  return api.post<WorldRelation>(`/api/novels/${novelId}/world/relations`, payload)
}

export function updateWorldRelation(
  novelId: string,
  relationId: string,
  payload: Partial<WorldRelationPayload>,
) {
  return api.put<WorldRelation>(
    `/api/novels/${novelId}/world/relations/${relationId}`,
    payload,
  )
}

export function deleteWorldRelation(novelId: string, relationId: string) {
  return api.delete<{ deleted: boolean }>(
    `/api/novels/${novelId}/world/relations/${relationId}`,
  )
}

export function listWorldEntryRelations(novelId: string, entryId: string) {
  return api.get<WorldEntryRelations>(
    `/api/novels/${novelId}/world/entries/${entryId}/relations`,
  )
}
