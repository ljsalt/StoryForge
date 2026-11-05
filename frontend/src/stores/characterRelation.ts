import { defineStore } from 'pinia'
import { extractError } from '../api/error'
import { useCharacterStore } from './character'
import {
  createBidirectionalCharacterRelation,
  createCharacterRelation,
  endCharacterRelation,
  getCharacterRelation,
  listCharacterRelationEvents,
  listCharacterRelations,
  listCharacterRelationsOfCharacter,
  restoreCharacterRelation,
  updateCharacterRelation,
  type CharacterCharacterRelations,
  type CharacterRelation,
  type CharacterRelationEvent,
  type CharacterRelationPayload,
  type CharacterRelationQuery,
  type CharacterRelationUpdatePayload,
} from '../api/characterRelation'

interface CharacterRelationState {
  novelId: string
  relations: CharacterRelation[]
  relationTypes: string[]
  events: Record<string, CharacterRelationEvent[]>
  characterRelations: CharacterCharacterRelations | null
  search: string
  typeFilter: string
  statusFilter: string
  loading: boolean
  error: string
}

export const useCharacterRelationStore = defineStore('characterRelation', {
  state: (): CharacterRelationState => ({
    novelId: '',
    relations: [],
    relationTypes: [],
    events: {},
    characterRelations: null,
    search: '',
    typeFilter: '',
    statusFilter: '',
    loading: false,
    error: '',
  }),
  getters: {
    totalRelations: (state) => state.relations.length,
    activeRelations: (state) => state.relations.filter((r) => r.status === 'active'),
    endedRelations: (state) => state.relations.filter((r) => r.status === 'ended'),
  },
  actions: {
    reset() {
      this.novelId = ''
      this.relations = []
      this.relationTypes = []
      this.events = {}
      this.characterRelations = null
      this.search = ''
      this.typeFilter = ''
      this.statusFilter = ''
      this.loading = false
      this.error = ''
    },

    async load(novelId: string) {
      if (this.novelId !== novelId) {
        this.reset()
        this.novelId = novelId
      }
      await this.fetchRelations()
    },

    async fetchRelations() {
      if (!this.novelId) return
      this.loading = true
      this.error = ''
      try {
        const query: CharacterRelationQuery = {
          search: this.search.trim() || undefined,
          relation_type: this.typeFilter || undefined,
          status: this.statusFilter || undefined,
        }
        const { data } = await listCharacterRelations(this.novelId, query)
        this.relations = data
        this.relationTypes = Array.from(
          new Set(data.map((r) => r.relation_type).filter(Boolean)),
        )
      } catch (error) {
        this.error = extractError(error, '加载人物关系失败')
        throw error
      } finally {
        this.loading = false
      }
    },

    async create(payload: CharacterRelationPayload, bidirectional = false) {
      if (!this.novelId) return
      if (bidirectional) {
        const { data } = await createBidirectionalCharacterRelation(this.novelId, payload)
        await this.fetchRelations()
        return data
      }
      const { data } = await createCharacterRelation(this.novelId, payload)
      await this.fetchRelations()
      return data
    },

    async update(relationId: string, payload: CharacterRelationUpdatePayload) {
      const { data } = await updateCharacterRelation(this.novelId, relationId, payload)
      await this.fetchRelations()
      // 同步更新 events 缓存
      if (this.events[relationId]) {
        await this.fetchEvents(relationId)
      }
      return data
    },

    async end(relationId: string) {
      const { data } = await endCharacterRelation(this.novelId, relationId)
      await this.fetchRelations()
      await this.fetchEvents(relationId)
      return data
    },

    async restore(relationId: string) {
      const { data } = await restoreCharacterRelation(this.novelId, relationId)
      await this.fetchRelations()
      await this.fetchEvents(relationId)
      return data
    },

    async fetchEvents(relationId: string) {
      const { data } = await listCharacterRelationEvents(this.novelId, relationId)
      this.events = { ...this.events, [relationId]: data }
      return data
    },

    async fetchCharacterRelations(characterId: string) {
      const { data } = await listCharacterRelationsOfCharacter(this.novelId, characterId)
      this.characterRelations = data
      return data
    },

    getCachedRelation(relationId: string): CharacterRelation | undefined {
      return this.relations.find((r) => r.id === relationId)
    },
  },
})
