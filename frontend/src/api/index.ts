import axios from 'axios'

// 后端地址统一在此配置。
// 默认按当前访问主机自动推导：手机通过 http://局域网IP:5173 访问前端时，
// API 自动指向同一台电脑的 http://局域网IP:8000，无需额外配置。
// 如需固定后端地址，可在 frontend/.env 中设置 VITE_API_BASE_URL。
const baseURL =
  import.meta.env.VITE_API_BASE_URL || `http://${window.location.hostname}:8000`

export const apiBaseURL = baseURL

export const api = axios.create({
  baseURL,
  timeout: 10000,
})

export interface HealthResponse {
  status: string
  version: string
  message: string
}

export interface SystemInfo {
  project_name: string
  version: string
  python_version: string
  data_dir: string
  data_dir_status: {
    exists: boolean
    novels_dir: boolean
    backups_dir: boolean
  }
}

export function getHealth() {
  return api.get<HealthResponse>('/api/health')
}

export function getSystemInfo() {
  return api.get<SystemInfo>('/api/system/info')
}
