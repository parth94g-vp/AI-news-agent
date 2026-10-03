import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { useUser } from '../context/UserContext'
import { useToast } from '../components/Toast'
import Spinner from '../components/Spinner'

export default function Preferences() {
  const { user } = useUser()
  const toast = useToast()
  const [taxonomy, setTaxonomy] = useState(null)
  const [chosen, setChosen] = useState({})
  const [saving, setSaving] = useState(false)
  const [email, setEmail] = useState('')
  const [emailSaving, setEmailSaving] = useState(false)

  useEffect(() => {
    Promise.all([api.taxonomy(), api.getPreferences(user.user_id), api.getEmail(user.user_id)])
      .then(([tax, prefs, mail]) => {
        setTaxonomy(tax.taxonomy)
        setChosen(prefs)
        setEmail(mail.email || '')
      }).catch((e) => toast(e.message, 'error'))
  }, [user, toast])

  const saveEmail = async () => {
    setEmailSaving(true)
    try {
      await api.setEmail(user.user_id, email.trim() || null)
      toast(email.trim() ? 'Daily digest email set.' : 'Digest email removed.')
    } catch (e) { toast(e.message, 'error') } finally { setEmailSaving(false) }
  }

  if (!taxonomy) return <Spinner label="Loading topics…" />

  const toggle = (topic, sub) => {
    setChosen((c) => {
      const current = new Set(c[topic] || [])
      current.has(sub) ? current.delete(sub) : current.add(sub)
      const next = { ...c }
      if (current.size) next[topic] = [...current]; else delete next[topic]
      return next
    })
  }

  const save = async () => {
    setSaving(true)
    try {
      await api.setPreferences(user.user_id, chosen)
      toast('Preferences saved.')
    } catch (e) { toast(e.message, 'error') } finally { setSaving(false) }
  }

  const totalSelected = Object.values(chosen).reduce((n, arr) => n + arr.length, 0)

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">My Topics</h1>
          <p className="text-sm mt-1" style={{ color: 'var(--muted)' }}>Choose subtopics to personalize your digest.</p>
        </div>
        <button className="btn btn-primary" disabled={saving} onClick={save}>
          {saving ? 'Saving…' : `Save preferences (${totalSelected})`}
        </button>
      </div>
      <div className="card p-4 flex flex-col gap-2 max-w-xl">
        <h3 className="font-semibold">📧 Daily email digest</h3>
        <p className="text-sm" style={{ color: 'var(--muted)' }}>
          Get your personalized digest emailed to you automatically every morning. Leave blank to turn it off.
        </p>
        <div className="flex gap-2">
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                 placeholder="you@example.com"
                 className="flex-1 rounded-xl px-4 py-2 bg-transparent border outline-none"
                 style={{ borderColor: 'var(--border)' }} />
          <button className="btn btn-primary" disabled={emailSaving} onClick={saveEmail}>
            {emailSaving ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
      <div className="grid md:grid-cols-2 gap-4">
        {Object.entries(taxonomy).map(([topic, subs]) => (
          <div key={topic} className="card p-4">
            <h3 className="font-semibold mb-3">{topic}</h3>
            <div className="flex flex-wrap gap-2">
              {subs.map((sub) => {
                const active = (chosen[topic] || []).includes(sub)
                return (
                  <button key={sub} onClick={() => toggle(topic, sub)}
                          className="chip border transition"
                          style={active
                            ? { background: 'var(--accent)', borderColor: 'var(--accent)', color: 'white' }
                            : { borderColor: 'var(--border)', color: 'var(--muted)' }}>
                    {sub}
                  </button>
                )
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
