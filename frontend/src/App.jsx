import { Navigate, Route, Routes } from 'react-router-dom'
import { UserProvider, useUser } from './context/UserContext'
import { ToastProvider } from './components/Toast'
import Layout from './components/Layout'
import Login from './pages/Login'
import Digest from './pages/Digest'
import Saved from './pages/Saved'
import Assistant from './pages/Assistant'
import Preferences from './pages/Preferences'

function RequireUser({ children }) {
  const { user, checking } = useUser()
  if (checking) {
    return <div className="min-h-screen flex items-center justify-center" style={{ color: 'var(--muted)' }}>Loading…</div>
  }
  return user ? children : <Navigate to="/login" replace />
}

function Routed() {
  const { user, checking } = useUser()
  if (checking) {
    return <div className="min-h-screen flex items-center justify-center" style={{ color: 'var(--muted)' }}>Loading…</div>
  }
  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to="/" replace /> : <Login />} />
      <Route element={<RequireUser><Layout /></RequireUser>}>
        <Route path="/" element={<Digest />} />
        <Route path="/saved" element={<Saved />} />
        <Route path="/assistant" element={<Assistant />} />
        <Route path="/preferences" element={<Preferences />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default function App() {
  return (
    <UserProvider>
      <ToastProvider>
        <Routed />
      </ToastProvider>
    </UserProvider>
  )
}
