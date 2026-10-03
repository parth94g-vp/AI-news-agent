import { createContext, useContext, useEffect, useState } from 'react'

const UserContext = createContext(null)
const STORAGE_KEY = 'news_agent_user'

export function UserProvider({ children }) {
  const [user, setUserState] = useState(() => {
    try { return JSON.parse(localStorage.getItem(STORAGE_KEY)) } catch { return null }
  })

  useEffect(() => {
    if (user) localStorage.setItem(STORAGE_KEY, JSON.stringify(user))
    else localStorage.removeItem(STORAGE_KEY)
  }, [user])

  const logout = () => setUserState(null)
  return (
    <UserContext.Provider value={{ user, setUser: setUserState, logout }}>
      {children}
    </UserContext.Provider>
  )
}

export const useUser = () => useContext(UserContext)
