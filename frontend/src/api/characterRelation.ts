import { api } from './index'
import type { CharacterAttributeValue } from './character'

export interface CharacterRelationEvent {
  id: string
  relation_id: string
  event_type: 'created' | 'updated' | 'ended' | 'restored'
  title: string
  description: string
  previous_data: Record<string, unknown>
  new_data: Record<string, unknown>
  story_time: string | null
  chapter_id: string | null
  chapter_title?: string | null
  chapter_number?: number | null
  sequence: number
  created_at: string
}

export interface CharacterRelation {
  id: string
  novel_id: string
  source_character_id: string
  target_character_id: string
  source_name: string
  target_name: string
  relation_type: string
  status: 'active' | 'ended'
  description: string
  strength: number | null
  attributes: Record<string, CharacterAttributeValue>
  start_time: string | null
  end_time: string | null
  sort_order: number
  created_at: string
  updated_at: string
}

export interface CharacterCharacterRelation {
  relation: CharacterRelation
  direction: 'outgoing' | 'incoming'
}

export interface CharacterCharacterRelations {
  character_id: string
  outgoing: CharacterCharacterRelation[]
  incoming: CharacterCharacterRelation[]
}

export interface CharacterRelationPayload {
  source_character_id: string
  target_character_id: string
  relation_type: string
  description?: string
  strength?: number | null
  attributes?: Record<string, CharacterAttributeValue>
  start_time?: string | null
  story_time?: string | null
  chapter_id?: string | null
}

export interface CharacterRelationUpdatePayload {
  relation_type?: string
  description?: string
  strength?: number | null
  attributes?: Record<string, CharacterAttributeValue>
  start_time?: string | null
  chapter_id?: string | null
}

export interface CharacterRelationQuery {
  source_character_id?: string
  target_character_id?: string
  relation_type?: string
  status?: string
  only_active?: boolean
  search?: string
}

export const DEFAULT_CHAR_RELATION_TYPES = [
  '师徒', '同门', '亲属', '盟友', '敌对', '恋人', '朋友', '上司', '下属', '认识', '其他',
]

export const DEFAULT_CHAR_RELATION_STATUSES = [
  { label: '有效', value: 'active' },
  { label: '已结束', value: 'ended' },
]

export function listCharacterRelations(novelId: string, query?: CharacterRelationQuery) {
  return api.get<CharacterRelation[]>(
    `/api/novels/${novelId}/character-relations`,
    { params: query },
  )
}

export function createCharacterRelation(novelId: string, payload: CharacterRelationPayload) {
  return api.post<CharacterRelation>(
    `/api/novels/${novelId}/character-relations`, payload,
  )
}

export function createBidirectionalCharacterRelation(novelId: string, payload: CharacterRelationPayload) {
  return api.post<[CharacterRelation, CharacterRelation]>(
    `/api/novels/${novelId}/character-relations/bidirectional`, payload,
  )
}

export function getCharacterRelation(novelId: string, relationId: string) {
  return api.get<CharacterRelation>(
    `/api/novels/${novelId}/character-relations/${relationId}`,
  )
}

export function updateCharacterRelation(
  novelId: string,
  relationId: string,
  payload: CharacterRelationUpdatePayload,
) {
  return api.put<CharacterRelation>(
    `/api/novels/${novelId}/character-relations/${relationId}`, payload,
  )
}

export function endCharacterRelation(novelId: string, relationId: string) {
  return api.post<CharacterRelation>(
    `/api/novels/${novelId}/character-relations/${relationId}/end`,
  )
}

export function restoreCharacterRelation(novelId: string, relationId: string) {
  return api.post<CharacterRelation>(
    `/api/novels/${novelId}/character-relations/${relationId}/restore`,
  )
}

export function listCharacterRelationEvents(novelId: string, relationId: string) {
  return api.get<CharacterRelationEvent[]>(
    `/api/novels/${novelId}/character-relations/${relationId}/events`,
  )
}

export function listCharacterRelationsOfCharacter(
  novelId: string,
  characterId: string,
  includeEnded: boolean = true,
) {
  return api.get<CharacterCharacterRelations>(
    `/api/novels/${novelId}/characters/${characterId}/relations`,
    { params: { include_ended: includeEnded } },
  )
}
