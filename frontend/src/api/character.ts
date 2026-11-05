import { api } from './index'

export type CharacterAttributeValue = string | number | boolean | null

export interface CharacterState {
  id: string
  character_id: string
  life_status: string
  current_location: string
  current_faction: string
  current_cultivation: string
  health_status: string
  emotional_state: string
  current_goal: string
  current_status: string
  attributes: Record<string, CharacterAttributeValue>
  updated_at: string
}

export interface CharacterSecret {
  id: string
  character_id: string
  title: string
  content: string
  secrecy_level: string
  reveal_status: string
  notes: string
  created_at: string
  updated_at: string
}

export interface Character {
  id: string
  novel_id: string
  name: string
  aliases: string[]
  gender: string
  age: string
  race: string
  identity: string
  role: string
  appearance: string
  personality: string
  background: string
  abilities: string
  cultivation: string
  affiliation: string
  tags: string[]
  attributes: Record<string, CharacterAttributeValue>
  avatar_color: string
  sort_order: number
  state: CharacterState | null
  created_at: string
  updated_at: string
}

export interface CharacterListItem {
  id: string
  novel_id: string
  name: string
  aliases: string[]
  identity: string
  role: string
  tags: string[]
  avatar_color: string
  life_status: string
  current_location: string
  current_cultivation: string
  sort_order: number
  created_at: string
  updated_at: string
}

export interface CharacterPayload {
  name: string
  aliases?: string[]
  gender?: string
  age?: string
  race?: string
  identity?: string
  role?: string
  appearance?: string
  personality?: string
  background?: string
  abilities?: string
  cultivation?: string
  affiliation?: string
  tags?: string[]
  attributes?: Record<string, CharacterAttributeValue>
  avatar_color?: string
  sort_order?: number
}

export interface CharacterStatePayload {
  life_status?: string
  current_location?: string
  current_faction?: string
  current_cultivation?: string
  health_status?: string
  emotional_state?: string
  current_goal?: string
  current_status?: string
  attributes?: Record<string, CharacterAttributeValue>
}

export interface CharacterSecretPayload {
  title: string
  content?: string
  secrecy_level?: string
  reveal_status?: string
  notes?: string
}

export interface CharacterQuery {
  search?: string
  role?: string
  tag?: string
  sort?: string
}

export const DEFAULT_CHARACTER_ROLES = [
  '主角',
  '重要配角',
  '普通配角',
  '反派',
  '导师',
  '对手',
  '路人',
  '其他',
]

export const DEFAULT_LIFE_STATUSES = [
  { label: '存活', value: 'alive' },
  { label: '已陨落', value: 'dead' },
  { label: '未知', value: 'unknown' },
]

export const DEFAULT_SECRECY_LEVELS = [
  { label: '公开', value: 'public' },
  { label: '受限', value: 'restricted' },
  { label: '机密', value: 'secret' },
]

export const DEFAULT_REVEAL_STATUSES = [
  { label: '未公开', value: 'unrevealed' },
  { label: '部分公开', value: 'partially_revealed' },
  { label: '已公开', value: 'revealed' },
]

export function listCharacters(novelId: string, query?: CharacterQuery) {
  return api.get<CharacterListItem[]>(`/api/novels/${novelId}/characters`, { params: query })
}

export function getCharacter(novelId: string, characterId: string) {
  return api.get<Character>(`/api/novels/${novelId}/characters/${characterId}`)
}

export function createCharacter(novelId: string, payload: CharacterPayload) {
  return api.post<Character>(`/api/novels/${novelId}/characters`, payload)
}

export function updateCharacter(
  novelId: string,
  characterId: string,
  payload: Partial<CharacterPayload>,
) {
  return api.put<Character>(`/api/novels/${novelId}/characters/${characterId}`, payload)
}

export function deleteCharacter(novelId: string, characterId: string) {
  return api.delete(`/api/novels/${novelId}/characters/${characterId}`)
}

export function getCharacterState(novelId: string, characterId: string) {
  return api.get<CharacterState>(
    `/api/novels/${novelId}/characters/${characterId}/state`,
  )
}

export function updateCharacterState(
  novelId: string,
  characterId: string,
  payload: CharacterStatePayload,
) {
  return api.put<CharacterState>(
    `/api/novels/${novelId}/characters/${characterId}/state`,
    payload,
  )
}

export function listCharacterSecrets(novelId: string, characterId: string) {
  return api.get<CharacterSecret[]>(
    `/api/novels/${novelId}/characters/${characterId}/secrets`,
  )
}

export function getCharacterSecret(
  novelId: string,
  characterId: string,
  secretId: string,
) {
  return api.get<CharacterSecret>(
    `/api/novels/${novelId}/characters/${characterId}/secrets/${secretId}`,
  )
}

export function createCharacterSecret(
  novelId: string,
  characterId: string,
  payload: CharacterSecretPayload,
) {
  return api.post<CharacterSecret>(
    `/api/novels/${novelId}/characters/${characterId}/secrets`,
    payload,
  )
}

export function updateCharacterSecret(
  novelId: string,
  characterId: string,
  secretId: string,
  payload: Partial<CharacterSecretPayload>,
) {
  return api.put<CharacterSecret>(
    `/api/novels/${novelId}/characters/${characterId}/secrets/${secretId}`,
    payload,
  )
}

export function deleteCharacterSecret(
  novelId: string,
  characterId: string,
  secretId: string,
) {
  return api.delete(
    `/api/novels/${novelId}/characters/${characterId}/secrets/${secretId}`,
  )
}
