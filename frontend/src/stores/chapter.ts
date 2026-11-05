import { defineStore } from 'pinia'
import { extractError } from '../api/error'
import {
  createChapter,
  deleteChapter,
  getChapter,
  getChapterStats,
  listChapters,
  reorderChapters,
  updateChapter,
  type Chapter,
  type ChapterPayload,
  type ChapterStats,
  type ChapterStatus,
  type ChapterSummary,
  type ChapterUpdatePayload,
} from '../api/chapter'

interface ChapterState {
  novelId: string
  chapters: ChapterSummary[]
  stats: ChapterStats
  search: string
  statusFilter: ChapterStatus | ''
  volumeFilter: number | null
  loading: boolean
  error: string
}

export const useChapterStore = defineStore('chapter', {
  state: (): ChapterState => ({
    novelId: '',
    chapters: [],
    stats: {
      chapter_count: 0,
      completed_chapter_count: 0,
      drafting_chapter_count: 0,
      planned_chapter_count: 0,
      total_word_count: 0,
    },
    search: '',
    statusFilter: '',
    volumeFilter: null,
    loading: false,
    error: '',
  }),
  getters: {
    totalChapters: (state) => state.chapters.length,
    completedChapters: (state) =>
      state.chapters.filter((c) => c.status === 'completed').length,
    volumes: (state) => {
      const values = new Set<number>()
      for (const chapter of state.chapters) {
        if (chapter.volume_number !== null) values.add(chapter.volume_number)
      }
      return Array.from(values).sort((a, b) => a - b)
    },
  },
  actions: {
    reset() {
      this.novelId = ''
      this.chapters = []
      this.stats = {
        chapter_count: 0,
        completed_chapter_count: 0,
        drafting_chapter_count: 0,
        planned_chapter_count: 0,
        total_word_count: 0,
      }
      this.search = ''
      this.statusFilter = ''
      this.volumeFilter = null
      this.loading = false
      this.error = ''
    },

    async load(novelId: string) {
      if (this.novelId !== novelId) {
        this.reset()
        this.novelId = novelId
      }
      await Promise.all([this.fetchChapters(), this.fetchStats()])
    },

    async fetchChapters() {
      if (!this.novelId) return
      this.loading = true
      this.error = ''
      try {
        const { data } = await listChapters(this.novelId, {
          search: this.search.trim() || undefined,
          status: this.statusFilter || undefined,
          volume_number: this.volumeFilter ?? undefined,
        })
        this.chapters = data
      } catch (error) {
        this.error = extractError(error, '加载章节失败')
        throw error
      } finally {
        this.loading = false
      }
    },

    async fetchStats() {
      if (!this.novelId) return
      try {
        const { data } = await getChapterStats(this.novelId)
        this.stats = data
      } catch (error) {
        this.error = extractError(error, '加载章节统计失败')
      }
    },

    async fetchOne(chapterId: string): Promise<Chapter> {
      const { data } = await getChapter(this.novelId, chapterId)
      return data
    },

    async create(payload: ChapterPayload) {
      const { data } = await createChapter(this.novelId, payload)
      await Promise.all([this.fetchChapters(), this.fetchStats()])
      return data
    },

    async update(chapterId: string, payload: ChapterUpdatePayload) {
      const { data } = await updateChapter(this.novelId, chapterId, payload)
      await Promise.all([this.fetchChapters(), this.fetchStats()])
      return data
    },

    async remove(chapterId: string) {
      await deleteChapter(this.novelId, chapterId)
      await Promise.all([this.fetchChapters(), this.fetchStats()])
    },

    async reorder(orderedIds: string[]) {
      const { data } = await reorderChapters(this.novelId, orderedIds)
      this.chapters = data
      return data
    },

    /** 上移/下移一章：只交换相邻章节，不改变其余顺序 */
    async move(chapterId: string, direction: -1 | 1) {
      const ids = this.chapters.map((item) => item.id)
      const index = ids.indexOf(chapterId)
      const target = index + direction
      if (index < 0 || target < 0 || target >= ids.length) return
      const next = [...ids]
      ;[next[index], next[target]] = [next[target], next[index]]
      await this.reorder(next)
    },
  },
})
