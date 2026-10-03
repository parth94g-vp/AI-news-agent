import { useCallback, useState } from 'react'
import { Outlet, useNavigate } from 'react-router-dom'
import Sidebar from './Sidebar'
import { api } from '../api/client'
import { useUser } from '../context/UserContext'
import { useToast } from './Toast'

export default function Layout() {
  const { user } = useUser()
  const toast = useToast()
  const navigate = useNavigate()
  const [refreshing, setRefreshing] = useState(false)
  const [lastRun, setLastRun] = useState(null)

  const handleRefresh = useCallback(async () => {
    setRefreshing(true)
    try {
      const result = await api.refresh(user.user_id)
      setLastRun(result)
      toast(`Refreshed: ${result.saved_count} articles in your digest.`)
      navigate('/')
      window.dispatchEvent(new CustomEvent('digest:refreshed'))
    } catch (e) {
      toast(e.message, 'error')
    } finally {
      setRefreshing(false)
    }
  }, [user, toast, navigate])

  return (
    <div className="flex min-h-screen">
      <Sidebar onRefresh={handleRefresh} refreshing={refreshing} />
      <main className="flex-1 p-6 md:p-10 max-w-5xl mx-auto w-full">
        {lastRun?.errors?.length > 0 && (
          <div className="card p-3 mb-4 text-sm" style={{ borderColor: 'var(--bad)' }}>
            <p className="font-semibold mb-1">Some sources had issues during the last refresh:</p>
            <ul className="list-disc list-inside" style={{ color: 'var(--muted)' }}>
              {lastRun.errors.slice(0, 5).map((e, i) => <li key={i}>{e}</li>)}
            </ul>
          </div>
        )}
        <Outlet />
      </main>
    </div>
  )
}
