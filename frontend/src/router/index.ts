import { createRouter, createWebHistory } from 'vue-router'
import MainLayout from '../layouts/MainLayout.vue'
import { useNovelStore } from '../stores/novels'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      component: MainLayout,
      children: [
        {
          path: '',
          name: 'dashboard',
          component: () => import('../views/Dashboard.vue'),
          meta: { title: '创作首页' },
        },
        {
          path: 'novels',
          name: 'novels',
          component: () => import('../views/NovelManager.vue'),
          meta: { title: '小说管理' },
        },
        {
          path: 'novels/:id',
          name: 'novel-detail',
          component: () => import('../views/NovelDetail.vue'),
          meta: { title: '小说详情' },
        },
        {
          path: 'novels/:id/world',
          name: 'novel-world',
          component: () => import('../views/WorldManager.vue'),
          meta: { title: '世界观管理' },
        },
        {
          path: 'novels/:id/world/relations',
          name: 'novel-world-relations',
          component: () => import('../views/WorldRelations.vue'),
          meta: { title: '世界观关系' },
        },
        {
          path: 'novels/:id/characters',
          name: 'novel-characters',
          component: () => import('../views/CharacterManager.vue'),
          meta: { title: '人物档案' },
        },
        {
          path: 'novels/:id/character-relations',
          name: 'novel-character-relations',
          component: () => import('../views/CharacterRelations.vue'),
          meta: { title: '人物关系' },
        },
        {
          path: 'characters',
          name: 'characters',
          component: () => import('../views/CharacterManager.vue'),
          meta: { title: '人物档案' },
        },
        {
          path: 'character-relations',
          name: 'character-relations',
          component: () => import('../views/CharacterRelations.vue'),
          meta: { title: '人物关系' },
        },
        {
          path: 'presets',
          name: 'presets',
          component: () => import('../views/PresetManager.vue'),
          meta: { title: '预设管理' },
        },
        {
          path: 'settings',
          name: 'settings',
          component: () => import('../views/Settings.vue'),
          meta: { title: '系统设置' },
        },
      ],
    },
  ],
})

router.afterEach((to) => {
  const title = (to.meta.title as string) || ''
  document.title = title ? `${title} - StoryForge` : 'StoryForge'
})

// 顶层 /characters 和 /character-relations 入口：跳转到默认小说对应页面，
// 没有默认小说时回到小说列表，避免因缺少 novel_id 直接报错。
router.beforeEach(async (to) => {
  const topLevelTargets: Record<string, string> = {
    characters: 'novel-characters',
    'character-relations': 'novel-character-relations',
  }
  const novelRouteName = topLevelTargets[to.name as string]
  if (novelRouteName && !to.params.id) {
    try {
      const store = useNovelStore()
      if (!store.novels.length) await store.load()
      const defaultNovel = store.novels.find((n) => n.is_default) || store.novels[0]
      if (defaultNovel) {
        return { name: novelRouteName, params: { id: defaultNovel.id } }
      }
      return { name: 'novels' }
    } catch {
      return { name: 'novels' }
    }
  }
})

export default router
