import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import { useUser } from '../context/UserContext'

export default function Login() {
  const { setUser } = useUser()
  const navigate = useNavigate()
  const [mode, setMode] = useState('login') // 'login' | 'signup'
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [hint, setHint] = useState('')

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true); setError(''); setHint('')
    try {
      const auth = mode === 'signup' ? await api.signup(username.trim(), password) : await api.login(username.trim(), password)
      setUser(auth)
      navigate('/')
    } catch (e) {
      setError(e.message)
      if (e instanceof ApiError) {
        if (mode === 'login' && e.message.toLowerCase().includes("hasn't set a password")) {
          setHint("This looks like an existing account from before passwords were added. Switch to Sign Up with the same username to set one.")
        } else if (mode === 'login' && e.message.toLowerCase().includes('no account')) {
          setHint('New here? Switch to Sign Up below.')
        } else if (mode === 'signup' && e.message.toLowerCase().includes('taken')) {
          setHint('Already have a password set? Switch to Log In below.')
        }
      }
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
        </div>

        <div className="flex rounded-xl p-1" style={{ background: 'var(--surface-2)' }}>
          {['login', 'signup'].map((m) => (
            <button key={m} type="button" onClick={() => { setMode(m); setError(''); setHint('') }}
                    className="flex-1 py-1.5 rounded-lg text-sm font-semibold transition"
                    style={mode === m ? { background: 'var(--accent)', color: 'white' } : { color: 'var(--muted)' }}>
              {m === 'login' ? 'Log In' : 'Sign Up'}
            </button>
          ))}
        </div>

        <input autoFocus value={username} onChange={(e) => setUsername(e.target.value)} placeholder="Username"
               autoComplete="username"
               className="rounded-xl px-4 py-2.5 bg-transparent border outline-none"
               style={{ borderColor: 'var(--border)' }} />
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Password"
               autoComplete={mode === 'signup' ? 'new-password' : 'current-password'}
               className="rounded-xl px-4 py-2.5 bg-transparent border outline-none"
               style={{ borderColor: 'var(--border)' }} />
        {mode === 'signup' && (
          <p className="text-xs -mt-2" style={{ color: 'var(--muted)' }}>At least 8 characters.</p>
        )}

        {error && <p className="text-sm" style={{ color: 'var(--bad)' }}>{error}</p>}
        {hint && <p className="text-sm" style={{ color: '#f0b429' }}>{hint}</p>}

        <button className="btn btn-primary" disabled={busy || !username.trim() || !password}>
          {busy ? 'Please wait…' : mode === 'signup' ? 'Create account' : 'Log in'}
        </button>
      </form>
    </div>
  )
}
