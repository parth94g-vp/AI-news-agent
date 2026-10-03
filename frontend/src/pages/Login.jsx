import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { useUser } from '../context/UserContext'

export default function Login() {
  const { setUser } = useUser()
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true); setError('')
    try {
      const user = await api.login(name.trim())
      setUser(user)
      navigate('/')
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      <form onSubmit={submit} className="card p-8 w-full max-w-sm flex flex-col gap-4">
        <div className="text-center mb-2">
          <div className="text-4xl mb-2">📰</div>
          <h1 className="text-xl font-bold">AI News Agent</h1>
          <p className="text-sm mt-1" style={{ color: 'var(--muted)' }}>Enter your name to create or open your profile</p>
        </div>
        <input autoFocus value={name} onChange={(e) => setName(e.target.value)} placeholder="Your name"
               className="rounded-xl px-4 py-2.5 bg-transparent border outline-none"
               style={{ borderColor: 'var(--border)' }} />
        {error && <p className="text-sm" style={{ color: 'var(--bad)' }}>{error}</p>}
        <button className="btn btn-primary" disabled={busy || !name.trim()}>
          {busy ? 'Signing in…' : 'Sign in / create profile'}
        </button>
      </form>
    </div>
  )
}
