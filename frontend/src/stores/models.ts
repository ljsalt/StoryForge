import { defineStore } from 'pinia'
import * as modelApi from '../api/models'
import type { ModelItem, ModelSettings, Provider } from '../api/models'

interface ModelState {
  providers: Provider[]
  models: ModelItem[]
  settings: ModelSettings
  loading: boolean
  loaded: boolean
}

export const useModelStore = defineStore('models', {
  state: (): ModelState => ({
    providers: [],
    models: [],
    settings: { tasks: [], default_model_id: null },
    loading: false,
    loaded: false,
  }),
  getters: {
    enabledModels: (state) => state.models.filter((item) => item.enabled),
    providerName(state) {
      return (providerId: string) =>
        state.providers.find((item) => item.id === providerId)?.name ?? '未知服务商'
    },
  },
  actions: {
    async loadAll() {
      this.loading = true
      try {
        const [providersRes, modelsRes, settingsRes] = await Promise.all([
          modelApi.listProviders(),
          modelApi.listModels(),
          modelApi.getModelSettings(),
        ])
        this.providers = providersRes.data
        this.models = modelsRes.data
        this.settings = settingsRes.data
        this.loaded = true
      } finally {
        this.loading = false
      }
    },
    async refreshProviders() {
      const [providersRes, modelsRes, settingsRes] = await Promise.all([
        modelApi.listProviders(),
        modelApi.listModels(),
        modelApi.getModelSettings(),
      ])
      this.providers = providersRes.data
      this.models = modelsRes.data
      this.settings = settingsRes.data
    },
  },
})
