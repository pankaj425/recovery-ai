import { createContext, useCallback, useContext, useState } from 'react'
import api, { TOKEN_KEY } from '../services/api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => {
    return localStorage.getItem(TOKEN_KEY)
  })

  const [user, setUser] = useState(() => {
    try {
      const savedUser = localStorage.getItem('recoveryai_user')
      return savedUser ? JSON.parse(savedUser) : null
    } catch {
      return null
    }
  })

  const login = useCallback(async (email, password) => {
    const response = await api.post('/auth/login', {
      email,
      password,
    })

    const accessToken = response.data.access_token
    const loggedInUser = response.data.user

    localStorage.setItem(TOKEN_KEY, accessToken)
    localStorage.setItem(
      'recoveryai_user',
      JSON.stringify(loggedInUser)
    )

    setToken(accessToken)
    setUser(loggedInUser)

    return response.data
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem('recoveryai_user')

    setToken(null)
    setUser(null)
  }, [])

  const value = {
    token,
    user,
    login,
    logout,
    isAuthenticated: Boolean(token),
  }

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}