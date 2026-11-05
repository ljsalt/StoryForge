import { defineStore } from 'pinia'
import * as novelApi from '../api/novels'
import type {
  Novel,
  NovelDetail,
  NovelPayload,
  NovelStatus,
} from '../api/novels'

const ACTIVE_NOVEL_KEY = 'storyforge:lastNovelId'

function readActiveId(): string | null {
  try {
    return localStorage.getItem(ACTIVE_NOVEL_KEY)
  } catch {
    return null
  }
}

function writeActiveId(id: string | null) {
  try {
    if (id) localStorage.setItem(ACTIVE_NOVEL_KEY, id)
    else localStorage.removeItem(ACTIVE_NOVEL_KEY)
  } catch {
    // 隐私模式下 localStorage 可能不可用，不影响主流程
  }
}

interface NovelState {
  novels: Novel[]
  current: NovelDetail | null
  defaultNovel: Novel | null
  loading: boolean
  error: string
  search: string
  statusFilter: NovelStatus | ''
}

export const useNovelStore = defineStore('novels', {
  state: (): NovelState => ({
    novels: [],
    current: null,
    defaultNovel: null,
    loading: false,
    error: '',
    search: '',
    statusFilter: '',
  }),
  getters: {
    count: (state) => state.novels.length,
    totalWords: (state) =>
      state.novels.reduce((sum, item) => sum + item.current_word_count, 0),
    recentNovels: (state) => state.novels.slice(0, 5),
  },
  actions: {
    async fetchList() {
      const { data } = await novelApi.listNovels({
        search: this.search.trim() || undefined,
        status: this.statusFilter || undefined,
      })
      this.novels = data
    },
    async fetchDefault() {
      const { data } = await novelApi.getDefaultNovel()
      this.defaultNovel = data ?? null
    },
    async load() {
      this.loading = true
      this.error = ''
      try {
        await Promise.all([this.fetchList(), this.fetchDefault()])
      } catch {
        this.error = '加载小说列表失败，请确认后端服务已启动'
        throw new Error('load-failed')
      } finally {
        this.loading = false
      }
    },
    /** 打开小说：始终以后端返回的数据为准 */
    async openNovel(id: string) {
      const { data } = await novelApi.getNovel(id)
      this.current = data
      writeActiveId(data.id)
      return data
    },
    /** 刷新后恢复：优先上次打开的小说，其次默认小说；后端确认失败则回退 */
    async restoreCurrent() {
      if (this.current) return this.current
      const candidates = [readActiveId(), this.defaultNovel?.id ?? null].filter(
        (id): id is string => Boolean(id),
      )
      for (const id of candidates) {
        try {
          const { data } = await novelApi.getNovel(id)
          this.current = data
          return data
        } catch {
          // 记录已失效，尝试下一个候选
        }
      }
      writeActiveId(null)
      return null
    },
    async createNovel(payload: NovelPayload) {
      const { data } = await novelApi.createNovel(payload)
      await this.load()
      return data
    },
    async updateNovel(id: string, payload: NovelPayload) {
      const { data } = await novelApi.updateNovel(id, payload)
      if (this.current?.id === id) this.current = data
      await this.load()
      return data
    },
    async removeNovel(id: string) {
      await novelApi.deleteNovel(id)
      if (this.current?.id === id) {
        this.current = null
        writeActiveId(null)
      }
      await this.load()
    },
    async setDefault(id: string) {
      await novelApi.setDefaultNovel(id)
      await this.load()
    },
    clearFilters() {
      this.search = ''
      this.statusFilter = ''
    },
  },
})
