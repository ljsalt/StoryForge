import { createRouter, createWebHistory } from 'vue-router'
import MainLayout from '../layouts/MainLayout.vue'

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
          path: 'characters',
          name: 'characters',
          component: () => import('../views/CharacterManager.vue'),
          meta: { title: '人物管理' },
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

export default router
