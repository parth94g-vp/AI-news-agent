import { NavLink } from 'react-router-dom'
import { useUser } from '../context/UserContext'

const links = [
  { to: '/', label: "Today's News", icon: '📰' },
  { to: '/saved', label: 'Saved', icon: '🔖' },
  { to: '/assistant', label: 'Ask the News', icon: '🤖' },
  { to: '/preferences', label: 'My Topics', icon: '🎯' },
]

export default function Sidebar({ onRefresh, refreshing }) {
  const { user, logout } = useUser()
  return (
    <aside className="w-64 shrink-0 h-screen sticky top-0 flex flex-col gap-4 p-4 border-r"
           style={{ borderColor: 'var(--border)' }}>
      <div className="flex items-center gap-2 px-2 py-3">
        <span className="text-2xl">📰</span>
        <span className="font-bold text-lg">AI News Agent</span>
      </div>
      <nav className="flex flex-col gap-1">
        {links.map((l) => (
          <NavLink key={l.to} to={l.to} end={l.to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-2 px-3 py-2 rounded-xl text-sm font-medium transition ${
                isActive ? 'text-white' : ''
              }`
            }
            style={({ isActive }) => ({
              background: isActive ? 'linear-gradient(135deg, var(--accent), var(--accent-2))' : 'transparent',
              color: isActive ? 'white' : 'var(--muted)',
            })}>
            <span>{l.icon}</span>{l.label}
          </NavLink>
        ))}
      </nav>
      <button className="btn btn-primary mt-2" disabled={refreshing} onClick={onRefresh}>
        {refreshing ? 'Refreshing…' : '🔄 Refresh my news'}
      </button>
      <div className="mt-auto pt-4 border-t flex items-center justify-between text-sm"
           style={{ borderColor: 'var(--border)' }}>
        <span style={{ color: 'var(--muted)' }}>Signed in as <b style={{ color: 'var(--text)' }}>{user?.username}</b></span>
        <button className="text-xs underline" style={{ color: 'var(--muted)' }} onClick={logout}>Sign out</button>
      </div>
    </aside>
  )
}
