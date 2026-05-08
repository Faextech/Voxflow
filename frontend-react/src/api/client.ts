import axios, { AxiosError } from 'axios'
import { useAuthStore } from '@/store/auth'

/** Reads the voxflow_csrf cookie (set by Flask on login — not HttpOnly) */
function getCsrfCookie(): string {
  const match = document.cookie.match(/(?:^|;\s*)voxflow_csrf=([^;]+)/)
  return match ? decodeURIComponent(match[1]) : ''
}

export const api = axios.create({
  baseURL: '/',
  withCredentials: true, // sends cookies (voxflow_token, voxflow_csrf) automatically
})

// Inject JWT Bearer + CSRF header on every request
api.interceptors.request.use(config => {
  const token = useAuthStore.getState().token
  // JWT: stored in localStorage (zustand persist) — also available as HttpOnly cookie
  if (token) config.headers['Authorization'] = `Bearer ${token}`
  // CSRF: read from the non-HttpOnly voxflow_csrf cookie Flask sets on login
  const csrf = getCsrfCookie() || useAuthStore.getState().csrfToken
  if (csrf) config.headers['X-CSRF-Token'] = csrf
  return config
})

// Auto-retry on 401 using refresh token (stored as HttpOnly cookie)
api.interceptors.response.use(
  r => r,
  async (err: AxiosError) => {
    const original = err.config as typeof err.config & { _retry?: boolean }
    if (err.response?.status === 401 && !original?._retry) {
      original._retry = true
      try {
        const res = await axios.post('/auth/refresh', {}, { withCredentials: true })
        const newToken = res.data.token ?? res.data.access_token
        if (newToken) {
          useAuthStore.getState().setTokens(newToken, undefined)
          original.headers!['Authorization'] = `Bearer ${newToken}`
        }
        return api(original)
      } catch {
        useAuthStore.getState().logout()
        window.location.href = '/login'
      }
    }
    return Promise.reject(err)
  }
)
