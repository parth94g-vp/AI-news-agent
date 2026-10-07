import { createContext, useContext, useEffect, useState } from 'react'
import { api, getToken, setToken, setUnauthorizedHandler } from '../api/client'

const UserContext = createContext(null)
const STORAGE_KEY = 'news_agent_user'

export function UserProvider({ children }) {
  const [user, setUserState] = useState(() => {
    try { return JSON.parse(localStorage.getItem(STORAGE_KEY)) } catch { return null }
  })
  const [checking, setChecking] = useState(true)

  const logout = () => {
    api.logout().catch(() => {})  // best-effort; clear local state regardless
    setToken(null)
    setUserState(null)
    localStorage.removeItem(STORAGE_KEY)
  }

  const login = (authResult) => {
    setToken(authResult.token)
    const u = { user_id: authResult.user_id, username: authResult.username }
    setUserState(u)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(u))
  }

  useEffect(() => {
    setUnauthorizedHandler(() => {
      setUserState(null)
      localStorage.removeItem(STORAGE_KEY)
    })
  }, [])

  // On first load, verify any stored token is still valid (not expired/logged-out elsewhere)
  // rather than trusting what's in localStorage - the server is the source of truth.
  useEffect(() => {
    if (!getToken()) { setChecking(false); return }
    api.me().then((me) => {
      const u = { user_id: me.user_id, username: me.username }
      setUserState(u)
      localStorage.setItem(STORAGE_KEY, JSON.stringify(u))
    }).catch(() => {
      setToken(null)
      setUserState(null)
      localStorage.removeItem(STORAGE_KEY)
    }).finally(() => setChecking(false))
  }, [])

  return (
    <UserContext.Provider value={{ user, setUser: login, logout, checking }}>
      {children}
    </UserContext.Provider>
  )
}

export const useUser = () => useContext(UserContext)
