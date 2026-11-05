import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// host 0.0.0.0：允许局域网内手机等设备访问开发服务器
export default defineConfig({
  plugins: [vue()],
  server: {
    host: '0.0.0.0',
    port: 5173,
  },
})
