import { createContext, useCallback, useContext, useState } from 'react'
import api, { TOKEN_KEY } from '../services/api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY))
  const [user, setUser] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('recoveryai_user') || 'null')
    } catch {
      return null
    }
  })

  const login = useCallback(async (email, password) => {
    const resp = await api.post('/auth/login', { email, password })
    localStorage.setItem(TOKEN_KEY, resp.data.access_token)
    localStorage.setItem('recoveryai_user', JSON.stringify(resp.data.user))
    setToken(resp.data.access_token)
    setUser(resp.data.user)
    return resp.data
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem('recoveryai_user')
    setToken(null)
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider value={{ token, user, login, logout, isAuthenticated: !!token }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
