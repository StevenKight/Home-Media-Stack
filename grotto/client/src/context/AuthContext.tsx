import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from 'react'

import {
  loginApiAuthLoginPost,
  readUsersMeApiAuthMeGet,
  registerApiAuthRegisterPost,
  requestPasswordResetApiAuthRequestPasswordResetPost,
  resetPasswordApiAuthResetPasswordPost,
} from '@/api'
import type { UserResponse } from '@/api'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface AuthContextValue {
  /** The currently authenticated user, or null if not logged in. */
  user: UserResponse | null
  /** True while the initial session is being restored on mount. */
  loading: boolean
  /** True once the session check has completed, regardless of outcome. */
  isAuthenticated: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, username: string, password: string) => Promise<void>
  logout: () => void
  requestPasswordReset: (email: string) => Promise<void>
  resetPassword: (token: string, newPassword: string) => Promise<void>
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

const AuthContext = createContext<AuthContextValue | null>(null)

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const TOKEN_KEY = 'access_token'

function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

function removeToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

function extractErrorMessage(error: unknown): string {
  if (error && typeof error === 'object' && 'detail' in error) {
    return String((error as { detail: unknown }).detail)
  }
  return 'An unexpected error occurred'
}

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserResponse | null>(null)
  const [loading, setLoading] = useState(true)

  // Restore session on mount if a token exists in localStorage.
  useEffect(() => {
    if (!getToken()) {
      setLoading(false)
      return
    }

    readUsersMeApiAuthMeGet()
      .then(({ data, error }) => {
        if (data) setUser(data)
        else if (error) removeToken() // token is invalid / expired
      })
      .finally(() => setLoading(false))
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const { data, error } = await loginApiAuthLoginPost({
      body: { email, password },
    })
    if (error) throw new Error(extractErrorMessage(error))

    setToken(data!.access_token)

    const { data: me, error: meError } = await readUsersMeApiAuthMeGet()
    if (meError) throw new Error(extractErrorMessage(meError))
    setUser(me!)
  }, [])

  const register = useCallback(
    async (email: string, username: string, password: string) => {
      const { error } = await registerApiAuthRegisterPost({
        body: { email, username, password },
      })
      if (error) throw new Error(extractErrorMessage(error))

      // Auto-login after successful registration.
      await login(email, password)
    },
    [login],
  )

  const logout = useCallback(() => {
    removeToken()
    setUser(null)
  }, [])

  const requestPasswordReset = useCallback(async (email: string) => {
    const { error } = await requestPasswordResetApiAuthRequestPasswordResetPost({
      query: { email },
    })
    if (error) throw new Error(extractErrorMessage(error))
  }, [])

  const resetPassword = useCallback(
    async (token: string, newPassword: string) => {
      const { error } = await resetPasswordApiAuthResetPasswordPost({
        query: { token, new_password: newPassword },
      })
      if (error) throw new Error(extractErrorMessage(error))
    },
    [],
  )

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        isAuthenticated: user !== null,
        login,
        register,
        logout,
        requestPasswordReset,
        resetPassword,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
