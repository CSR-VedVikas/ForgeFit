import { createContext, useContext, useEffect, useState } from 'react'
import { api, setToken, onAuthLost, revokeSession } from './api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  async function refresh() {
    try {
      // No early return when localStorage is empty: the access token may have
      // been cleared while the 14-day refresh cookie is still good. api()
      // turns the 401 into a refresh and the session comes back on its own.
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
    // A refresh that fails mid-session clears the user; Private then redirects
    // to /login without reloading the page.
    return onAuthLost(() => setUser(null))
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
    // Revoke server-side too. Clearing localStorage alone left the refresh
    // cookie able to mint new access tokens for two weeks.
    revokeSession()
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
