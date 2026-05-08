import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface AuthState {
  token:     string | null
  csrfToken: string | null
  user:      { id: number; name: string; email: string; role: string; company_id: number } | null
  setTokens: (token: string, csrf?: string) => void
  setUser:   (user: AuthState['user']) => void
  logout:    () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    set => ({
      token:     null,
      csrfToken: null,
      user:      null,
      setTokens: (token, csrf) => set({ token, csrfToken: csrf ?? null }),
      setUser:   user => set({ user }),
      logout:    () => set({ token: null, csrfToken: null, user: null }),
    }),
    { name: 'voxflow-auth', partialize: s => ({ token: s.token, csrfToken: s.csrfToken, user: s.user }) }
  )
)
