<script setup lang="ts">
import { h, onBeforeUnmount, onMounted, ref, watch, type Component } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  NButton,
  NDrawer,
  NDrawerContent,
  NIcon,
  NMenu,
  NTag,
  type MenuOption,
} from 'naive-ui'
import {
  AlbumsOutline,
  BookOutline,
  HomeOutline,
  MenuOutline,
  PeopleOutline,
  SettingsOutline,
} from '@vicons/ionicons5'
import { useSystemStore } from '../stores/system'

const route = useRoute()
const router = useRouter()
const system = useSystemStore()

const isMobile = ref(false)
const drawerVisible = ref(false)
const activeKey = ref(route.path)

const media = window.matchMedia('(max-width: 767px)')
const syncMedia = () => {
  isMobile.value = media.matches
}

onMounted(() => {
  syncMedia()
  media.addEventListener('change', syncMedia)
  system.refresh()
})
onBeforeUnmount(() => media.removeEventListener('change', syncMedia))

watch(
  () => route.path,
  (path) => {
    activeKey.value = path
  },
)

function renderIcon(icon: Component) {
  return () => h(NIcon, null, { default: () => h(icon) })
}

const menuOptions: MenuOption[] = [
  { label: '创作首页', key: '/', icon: renderIcon(HomeOutline) },
  { label: '小说管理', key: '/novels', icon: renderIcon(BookOutline) },
  { label: '人物管理', key: '/characters', icon: renderIcon(PeopleOutline) },
  { label: '预设管理', key: '/presets', icon: renderIcon(AlbumsOutline) },
  { label: '系统设置', key: '/settings', icon: renderIcon(SettingsOutline) },
]

function handleSelect(key: string) {
  router.push(key)
  drawerVisible.value = false
}
</script>

<template>
  <div class="app-shell">
    <!-- 桌面端：固定侧边导航 -->
    <aside v-if="!isMobile" class="sider">
      <div class="logo">
        <span class="logo-name">StoryForge</span>
        <span class="logo-sub">AI 长篇小说工作室</span>
      </div>
      <n-menu
        class="sider-menu"
        :value="activeKey"
        :options="menuOptions"
        @update:value="handleSelect"
      />
      <div class="sider-footer">
        <n-tag v-if="system.online" type="success" size="small" round>后端在线</n-tag>
        <n-tag v-else type="error" size="small" round>后端离线</n-tag>
        <span class="version">v{{ system.version || '0.1.0-P1' }}</span>
      </div>
    </aside>

    <!-- 移动端：抽屉导航 -->
    <n-drawer v-model:show="drawerVisible" :width="240" placement="left">
      <n-drawer-content title="StoryForge" closable body-content-style="padding: 0;">
        <n-menu :value="activeKey" :options="menuOptions" @update:value="handleSelect" />
        <div class="drawer-footer">
          <n-tag v-if="system.online" type="success" size="small" round>后端在线</n-tag>
          <n-tag v-else type="error" size="small" round>后端离线</n-tag>
        </div>
      </n-drawer-content>
    </n-drawer>

    <div class="main">
      <!-- 移动端顶部栏 -->
      <header v-if="isMobile" class="mobile-header">
        <n-button quaternary circle aria-label="打开菜单" @click="drawerVisible = true">
          <template #icon>
            <n-icon><MenuOutline /></n-icon>
          </template>
        </n-button>
        <span class="mobile-title">{{ (route.meta.title as string) || 'StoryForge' }}</span>
        <span class="mobile-spacer" />
      </header>

      <main class="content">
        <router-view />
      </main>
    </div>
  </div>
</template>

<style scoped>
.app-shell {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

.sider {
  width: 220px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  border-right: 1px solid rgba(255, 255, 255, 0.09);
  background-color: #18181c;
}

.logo {
  padding: 20px 20px 16px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.logo-name {
  font-size: 20px;
  font-weight: 700;
  color: #fff;
}

.logo-sub {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.45);
}

.sider-menu {
  flex: 1;
}

.sider-footer {
  padding: 16px 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-top: 1px solid rgba(255, 255, 255, 0.09);
}

.version {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.45);
}

.drawer-footer {
  padding: 16px 20px;
}

.main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.mobile-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.09);
  background-color: #18181c;
}

.mobile-title {
  font-size: 16px;
  font-weight: 600;
  color: #fff;
}

.mobile-spacer {
  flex: 1;
}

.content {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 24px;
}

@media (max-width: 767px) {
  .content {
    padding: 16px;
  }
}
</style>
