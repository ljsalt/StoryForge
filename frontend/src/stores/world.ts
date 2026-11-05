import { defineStore } from 'pinia'
import { extractError } from '../api/error'
import {
  createWorldCategory,
  createWorldEntry,
  createWorldRelation,
  deleteWorldCategory,
  deleteWorldEntry,
  deleteWorldRelation,
  getWorldEntry,
  getWorldStats,
  listWorldCategories,
  listWorldEntries,
  listWorldEntryRelations,
  listWorldRelations,
  updateWorldCategory,
  updateWorldEntry,
  updateWorldRelation,
  type WorldCategory,
  type WorldCategoryPayload,
  type WorldEntry,
  type WorldEntryPayload,
  type WorldEntryRelations,
  type WorldRelation,
  type WorldRelationPayload,
  type WorldStats,
} from '../api/world'

interface WorldState {
  novelId: string
  categories: WorldCategory[]
  entries: WorldEntry[]
  allEntries: WorldEntry[]
  currentEntry: WorldEntry | null
  stats: WorldStats | null
  search: string
  categoryFilter: string
  relations: WorldRelation[]
  relationsLoading: boolean
  relationTypeFilter: string
  relationSearch: string
  currentRelation: WorldRelation | null
  entryRelations: WorldEntryRelations | null
  loading: boolean
  error: string
}

export const useWorldStore = defineStore('world', {
  state: (): WorldState => ({
    novelId: '',
    categories: [],
    entries: [],
    allEntries: [],
    currentEntry: null,
    stats: null,
    search: '',
    categoryFilter: '',
    relations: [],
    relationsLoading: false,
    relationTypeFilter: '',
    relationSearch: '',
    currentRelation: null,
    entryRelations: null,
    loading: false,
    error: '',
  }),
  getters: {
    totalEntries: (state) => state.stats?.total_entries ?? state.entries.length,
    totalRelations: (state) => state.stats?.total_relations ?? state.relations.length,
    categoryOptions: (state) =>
      state.categories.map((item) => ({ label: item.name, value: item.id })),
    relationTypeOptions: (state) => {
      const types = new Set<string>()
      for (const item of state.stats?.relation_by_type ?? []) {
        types.add(item.relation_type)
      }
      for (const item of state.relations) types.add(item.relation_type)
      return Array.from(types)
    },
  },
  actions: {
    reset() {
      this.novelId = ''
      this.categories = []
      this.entries = []
      this.allEntries = []
      this.currentEntry = null
      this.stats = null
      this.search = ''
      this.categoryFilter = ''
      this.relations = []
      this.relationsLoading = false
      this.relationTypeFilter = ''
      this.relationSearch = ''
      this.currentRelation = null
      this.entryRelations = null
      this.error = ''
    },

    /** 加载指定小说的世界观数据；切换小说时彻底清空上一本的数据，避免缓存串用。 */
    async load(novelId: string) {
      if (this.novelId !== novelId) {
        this.reset()
        this.novelId = novelId
      }
      this.loading = true
      this.error = ''
      try {
        await Promise.all([
          this.fetchCategories(),
          this.fetchEntries(),
          this.fetchAllEntries(),
          this.fetchStats(),
          this.fetchRelations(),
        ])
      } catch (error) {
        this.error = extractError(error, '加载世界观设定失败')
        throw error
      } finally {
        this.loading = false
      }
    },

    async fetchCategories() {
      if (!this.novelId) return
      const { data } = await listWorldCategories(this.novelId)
      this.categories = data
    },

    async fetchEntries() {
      if (!this.novelId) return
      const { data } = await listWorldEntries(this.novelId, {
        search: this.search.trim() || undefined,
        category_id: this.categoryFilter || undefined,
      })
      this.entries = data
    },

    async fetchStats() {
      if (!this.novelId) return
      const { data } = await getWorldStats(this.novelId)
      this.stats = data
    },

    async fetchAllEntries() {
      if (!this.novelId) return
      const { data } = await listWorldEntries(this.novelId)
      this.allEntries = data
    },

    async fetchRelations() {
      if (!this.novelId) return
      this.relationsLoading = true
      try {
        const { data } = await listWorldRelations(this.novelId, {
          relation_type: this.relationTypeFilter || undefined,
          search: this.relationSearch.trim() || undefined,
        })
        this.relations = data
      } finally {
        this.relationsLoading = false
      }
    },

    async refreshMeta() {
      await Promise.all([this.fetchCategories(), this.fetchStats()])
    },

    async refreshRelations() {
      await Promise.all([this.fetchRelations(), this.fetchStats()])
    },

    async selectCategory(categoryId: string) {
      this.categoryFilter = categoryId
      await this.fetchEntries()
    },

    async setSearch(keyword: string) {
      this.search = keyword
      await this.fetchEntries()
    },

    async setRelationTypeFilter(relationType: string) {
      this.relationTypeFilter = relationType
      await this.fetchRelations()
    },

    async setRelationSearch(keyword: string) {
      this.relationSearch = keyword
      await this.fetchRelations()
    },

    clearRelationFilters() {
      this.relationTypeFilter = ''
      this.relationSearch = ''
    },

    clearFilters() {
      this.search = ''
      this.categoryFilter = ''
    },

    async openEntry(entryId: string) {
      if (!this.novelId) return null
      const { data } = await getWorldEntry(this.novelId, entryId)
      this.currentEntry = data
      return data
    },

    async fetchEntryRelations(entryId: string) {
      if (!this.novelId) return null
      const { data } = await listWorldEntryRelations(this.novelId, entryId)
      this.entryRelations = data
      return data
    },

    async createEntry(payload: WorldEntryPayload) {
      const { data } = await createWorldEntry(this.novelId, payload)
      await Promise.all([this.fetchEntries(), this.fetchAllEntries(), this.refreshMeta()])
      return data
    },

    async updateEntry(entryId: string, payload: Partial<WorldEntryPayload>) {
      const { data } = await updateWorldEntry(this.novelId, entryId, payload)
      this.currentEntry = data
      await Promise.all([this.fetchEntries(), this.fetchAllEntries(), this.refreshMeta()])
      return data
    },

    async removeEntry(entryId: string) {
      await deleteWorldEntry(this.novelId, entryId)
      if (this.currentEntry?.id === entryId) this.currentEntry = null
      await Promise.all([
        this.fetchEntries(),
        this.fetchAllEntries(),
        this.refreshMeta(),
        this.fetchRelations(),
      ])
    },

    async createCategory(payload: WorldCategoryPayload) {
      const { data } = await createWorldCategory(this.novelId, payload)
      await this.refreshMeta()
      return data
    },

    async updateCategory(categoryId: string, payload: Partial<WorldCategoryPayload>) {
      const { data } = await updateWorldCategory(this.novelId, categoryId, payload)
      await Promise.all([this.fetchCategories(), this.fetchEntries(), this.fetchStats()])
      return data
    },

    async removeCategory(categoryId: string) {
      await deleteWorldCategory(this.novelId, categoryId)
      if (this.categoryFilter === categoryId) {
        this.categoryFilter = ''
        await this.fetchEntries()
      }
      await this.refreshMeta()
    },

    async createRelation(payload: WorldRelationPayload) {
      const { data } = await createWorldRelation(this.novelId, payload)
      await this.refreshRelations()
      return data
    },

    async updateRelation(relationId: string, payload: Partial<WorldRelationPayload>) {
      const { data } = await updateWorldRelation(this.novelId, relationId, payload)
      await this.refreshRelations()
      return data
    },

    async removeRelation(relationId: string) {
      await deleteWorldRelation(this.novelId, relationId)
      if (this.currentRelation?.id === relationId) this.currentRelation = null
      await this.refreshRelations()
    },
  },
})
