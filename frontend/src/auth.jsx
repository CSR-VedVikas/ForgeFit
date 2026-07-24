import { createContext, useContext, useEffect, useState } from 'react'
import { api, setToken } from './api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  async function refresh() {
    try {
      if (!localStorage.getItem('forgefit_token')) {
        setUser(null)
        return
      }
      const me = await api('/api/auth/me')
      setUser(me)
    } catch {
      setUser(null)
      setToken(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    refresh()
  }, [])

  async function login(email, password) {
    const data = await api('/api/auth/login/json', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    })
    setToken(data.access_token)
    await refresh()
  }

  async function register(email, password, display_name) {
    const data = await api('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password, display_name }),
    })
    setToken(data.access_token)
    await refresh()
  }

  function logout() {
    setToken(null)
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, refresh }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
