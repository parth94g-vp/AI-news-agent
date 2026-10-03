import { useRef, useState } from 'react'
import { api } from '../api/client'
import { useUser } from '../context/UserContext'
import Spinner from '../components/Spinner'

export default function Assistant() {
  const { user } = useUser()
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const bottomRef = useRef(null)

  const send = async (e) => {
    e.preventDefault()
    const question = input.trim()
    if (!question || busy) return
    setMessages((m) => [...m, { role: 'user', content: question }])
    setInput('')
    setBusy(true)
    try {
      const res = await api.ask(user.user_id, question)
      setMessages((m) => [...m, { role: 'assistant', content: res.answer, sources: res.sources }])
    } catch (e) {
      setMessages((m) => [...m, { role: 'assistant', content: `Error: ${e.message}`, sources: [] }])
    } finally {
      setBusy(false)
      setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' }), 50)
    }
  }

  const suggestions = ["What happened in AI today?", "Summarize today's technology news", "What are the major business stories?"]

  return (
    <div className="flex flex-col h-[calc(100vh-5rem)]">
      <h1 className="text-2xl font-bold mb-2">Ask the News</h1>
      <p className="text-sm mb-4" style={{ color: 'var(--muted)' }}>
        Answers come from the news collected in your database, with numbered sources.
      </p>
      <div className="flex-1 overflow-y-auto scrollbar-thin flex flex-col gap-4 pr-2">
        {messages.length === 0 && (
          <div className="flex flex-wrap gap-2">
            {suggestions.map((s) => (
              <button key={s} className="btn btn-ghost text-left" onClick={() => setInput(s)}>{s}</button>
            ))}
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`card p-4 max-w-2xl ${m.role === 'user' ? 'self-end' : 'self-start'}`}
               style={m.role === 'user' ? { background: 'var(--surface-2)' } : {}}>
            <p className="text-sm whitespace-pre-wrap">{m.content}</p>
            {m.sources?.length > 0 && (
              <div className="mt-3 pt-3 border-t flex flex-col gap-1" style={{ borderColor: 'var(--border)' }}>
                {m.sources.map((s, j) => (
                  <a key={s.id} href={s.url} target="_blank" rel="noreferrer" className="text-xs underline"
                     style={{ color: 'var(--muted)' }}>[{j + 1}] {s.title} — {s.source}</a>
                ))}
              </div>
            )}
          </div>
        ))}
        {busy && <Spinner label="Searching today's news…" />}
        <div ref={bottomRef} />
      </div>
      <form onSubmit={send} className="flex gap-2 mt-4">
        <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="e.g. What happened in AI today?"
               className="flex-1 rounded-xl px-4 py-2.5 bg-transparent border outline-none"
               style={{ borderColor: 'var(--border)' }} />
        <button className="btn btn-primary" disabled={busy || !input.trim()}>Send</button>
      </form>
    </div>
  )
}
