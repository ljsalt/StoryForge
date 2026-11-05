import { defineStore } from 'pinia'
import {
  getHealth,
  getSystemInfo,
  type HealthResponse,
  type SystemInfo,
} from '../api'

interface SystemState {
  health: HealthResponse | null
  info: SystemInfo | null
  loading: boolean
  error: string
}

export const useSystemStore = defineStore('system', {
  state: (): SystemState => ({
    health: null,
    info: null,
    loading: false,
    error: '',
  }),
  getters: {
    online: (state) => state.health !== null && state.error === '',
    version: (state) => state.info?.version ?? state.health?.version ?? '',
  },
  actions: {
    async refresh() {
      this.loading = true
      this.error = ''
      try {
        const [healthRes, infoRes] = await Promise.all([getHealth(), getSystemInfo()])
        this.health = healthRes.data
        this.info = infoRes.data
      } catch {
        this.health = null
        this.info = null
        this.error = '无法连接后端服务，请确认后端已启动（端口 8000）'
      } finally {
        this.loading = false
      }
    },
  },
})
