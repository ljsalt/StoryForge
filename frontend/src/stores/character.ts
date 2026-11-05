import { defineStore } from 'pinia'
import { extractError } from '../api/error'
import {
  createCharacter,
  createCharacterSecret,
  deleteCharacter,
  deleteCharacterSecret,
  getCharacter,
  getCharacterState,
  listCharacters,
  listCharacterSecrets,
  updateCharacter,
  updateCharacterSecret,
  updateCharacterState,
  type Character,
  type CharacterListItem,
  type CharacterPayload,
  type CharacterSecret,
  type CharacterSecretPayload,
  type CharacterState,
  type CharacterStatePayload,
} from '../api/character'

interface CharacterStateShape {
  novelId: string
  characters: CharacterListItem[]
  currentCharacter: Character | null
  currentState: CharacterState | null
  secrets: CharacterSecret[]
  search: string
  roleFilter: string
  tagFilter: string
  sort: string
  loading: boolean
  error: string
}

export const useCharacterStore = defineStore('character', {
  state: (): CharacterStateShape => ({
    novelId: '',
    characters: [],
    currentCharacter: null,
    currentState: null,
    secrets: [],
    search: '',
    roleFilter: '',
    tagFilter: '',
    sort: '',
    loading: false,
    error: '',
  }),
  getters: {
    totalCharacters: (state) => state.characters.length,
    roleOptions: (state) => {
      const roles = new Set<string>()
      for (const c of state.characters) if (c.role) roles.add(c.role)
      return Array.from(roles)
    },
    tagOptions: (state) => {
      const tags = new Set<string>()
      for (const c of state.characters) for (const t of c.tags) tags.add(t)
      return Array.from(tags)
    },
  },
  actions: {
    reset() {
      this.novelId = ''
      this.characters = []
      this.currentCharacter = null
      this.currentState = null
      this.secrets = []
      this.search = ''
      this.roleFilter = ''
      this.tagFilter = ''
      this.sort = ''
      this.error = ''
    },

    async load(novelId: string) {
      if (this.novelId !== novelId) {
        this.reset()
        this.novelId = novelId
      }
      this.loading = true
      this.error = ''
      try {
        await this.fetchCharacters()
      } catch (error) {
        this.error = extractError(error, '加载人物失败')
        throw error
      } finally {
        this.loading = false
      }
    },

    async fetchCharacters() {
      if (!this.novelId) return
      const { data } = await listCharacters(this.novelId, {
        search: this.search.trim() || undefined,
        role: this.roleFilter || undefined,
        tag: this.tagFilter || undefined,
        sort: this.sort || undefined,
      })
      this.characters = data
    },

    async openCharacter(id: string) {
      if (!this.novelId) return null
      const { data } = await getCharacter(this.novelId, id)
      this.currentCharacter = data
      this.currentState = data.state
      return data
    },

    async fetchSecrets(characterId: string) {
      if (!this.novelId) return
      const { data } = await listCharacterSecrets(this.novelId, characterId)
      this.secrets = data
    },

    async create(payload: CharacterPayload) {
      const { data } = await createCharacter(this.novelId, payload)
      await this.fetchCharacters()
      return data
    },

    async update(characterId: string, payload: Partial<CharacterPayload>) {
      const { data } = await updateCharacter(this.novelId, characterId, payload)
      if (this.currentCharacter?.id === characterId) {
        this.currentCharacter = data
      }
      await this.fetchCharacters()
      return data
    },

    async remove(characterId: string) {
      await deleteCharacter(this.novelId, characterId)
      if (this.currentCharacter?.id === characterId) {
        this.currentCharacter = null
        this.currentState = null
        this.secrets = []
      }
      await this.fetchCharacters()
    },

    async updateState(characterId: string, payload: CharacterStatePayload) {
      const { data } = await updateCharacterState(this.novelId, characterId, payload)
      this.currentState = data
      // 同步详情中的 state
      if (this.currentCharacter?.id === characterId) {
        this.currentCharacter.state = data
      }
      await this.fetchCharacters()
      return data
    },

    async refreshState(characterId: string) {
      if (!this.novelId) return
      const { data } = await getCharacterState(this.novelId, characterId)
      this.currentState = data
      return data
    },

    async createSecret(characterId: string, payload: CharacterSecretPayload) {
      const { data } = await createCharacterSecret(this.novelId, characterId, payload)
      await this.fetchSecrets(characterId)
      return data
    },

    async updateSecret(
      characterId: string,
      secretId: string,
      payload: Partial<CharacterSecretPayload>,
    ) {
      const { data } = await updateCharacterSecret(
        this.novelId,
        characterId,
        secretId,
        payload,
      )
      await this.fetchSecrets(characterId)
      return data
    },

    async removeSecret(characterId: string, secretId: string) {
      await deleteCharacterSecret(this.novelId, characterId, secretId)
      if (this.currentCharacter?.id === characterId) {
        await this.fetchSecrets(characterId)
      }
    },

    setSearch(val: string) {
      this.search = val
      return this.fetchCharacters()
    },
    setRoleFilter(val: string) {
      this.roleFilter = val
      return this.fetchCharacters()
    },
    setTagFilter(val: string) {
      this.tagFilter = val
      return this.fetchCharacters()
    },
    setSort(val: string) {
      this.sort = val
      return this.fetchCharacters()
    },
    clearFilters() {
      this.search = ''
      this.roleFilter = ''
      this.tagFilter = ''
      this.sort = ''
      return this.fetchCharacters()
    },
  },
})
