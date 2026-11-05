import { defineStore } from 'pinia'
import { extractError } from '../api/error'
import {
  createPlotEvent,
  deletePlotEvent,
  getPlotEvent,
  getPlotTimeline,
  listCharacterPlotEvents,
  listPlotEvents,
  updatePlotEvent,
  type PlotEvent,
  type PlotEventPayload,
  type PlotEventQuery,
  type PlotEventUpdatePayload,
  type PlotImportance,
  type PlotTimeline,
} from '../api/plotEvent'

interface PlotEventState {
  novelId: string
  events: PlotEvent[]
  timeline: PlotTimeline
  characterEvents: PlotEvent[]
  search: string
  chapterFilter: string
  characterFilter: string
  typeFilter: string
  importanceFilter: PlotImportance | ''
  loading: boolean
  error: string
}

export const usePlotEventStore = defineStore('plotEvent', {
  state: (): PlotEventState => ({
    novelId: '',
    events: [],
    timeline: { timed: [], untimed: [] },
    characterEvents: [],
    search: '',
    chapterFilter: '',
    characterFilter: '',
    typeFilter: '',
    importanceFilter: '',
    loading: false,
    error: '',
  }),
  getters: {
    totalEvents: (state) => state.events.length,
    eventTypes: (state) => {
      const types = new Set<string>()
      for (const event of state.events) if (event.event_type) types.add(event.event_type)
      return Array.from(types).sort()
    },
  },
  actions: {
    reset() {
      this.novelId = ''
      this.events = []
      this.timeline = { timed: [], untimed: [] }
      this.characterEvents = []
      this.search = ''
      this.chapterFilter = ''
      this.characterFilter = ''
      this.typeFilter = ''
      this.importanceFilter = ''
      this.loading = false
      this.error = ''
    },

    async load(novelId: string) {
      if (this.novelId !== novelId) {
        this.reset()
        this.novelId = novelId
      }
      await this.fetchEvents()
    },

    _query(): PlotEventQuery {
      return {
        search: this.search.trim() || undefined,
        chapter_id: this.chapterFilter || undefined,
        character_id: this.characterFilter || undefined,
        event_type: this.typeFilter || undefined,
        importance: this.importanceFilter || undefined,
      }
    },

    async fetchEvents() {
      if (!this.novelId) return
      this.loading = true
      this.error = ''
      try {
        const { data } = await listPlotEvents(this.novelId, this._query())
        this.events = data
      } catch (error) {
        this.error = extractError(error, '加载剧情事件失败')
        throw error
      } finally {
        this.loading = false
      }
    },

    async fetchTimeline() {
      if (!this.novelId) return
      this.loading = true
      this.error = ''
      try {
        const { data } = await getPlotTimeline(this.novelId, this._query())
        this.timeline = data
      } catch (error) {
        this.error = extractError(error, '加载剧情时间线失败')
        throw error
      } finally {
        this.loading = false
      }
    },

    async fetchCharacterEvents(characterId: string) {
      if (!this.novelId) return
      try {
        const { data } = await listCharacterPlotEvents(this.novelId, characterId)
        this.characterEvents = data
        return data
      } catch (error) {
        this.error = extractError(error, '加载人物剧情事件失败')
        throw error
      }
    },

    async fetchOne(eventId: string) {
      const { data } = await getPlotEvent(this.novelId, eventId)
      return data
    },

    async create(payload: PlotEventPayload) {
      const { data } = await createPlotEvent(this.novelId, payload)
      await this.fetchEvents()
      return data
    },

    async update(eventId: string, payload: PlotEventUpdatePayload) {
      const { data } = await updatePlotEvent(this.novelId, eventId, payload)
      await this.fetchEvents()
      return data
    },

    async remove(eventId: string) {
      await deletePlotEvent(this.novelId, eventId)
      await this.fetchEvents()
    },

    clearFilters() {
      this.search = ''
      this.chapterFilter = ''
      this.characterFilter = ''
      this.typeFilter = ''
      this.importanceFilter = ''
    },
  },
})
