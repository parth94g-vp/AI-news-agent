import { useState } from 'react'
import { api } from '../api/client'
import { useUser } from '../context/UserContext'
import { useToast } from './Toast'

function timeAgo(iso) {
  if (!iso) return 'Unknown time'
  const diffMs = Date.now() - new Date(iso + 'Z').getTime()
  const h = Math.floor(diffMs / 3_600_000)
  if (h < 1) return 'Just now'
  if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}

export default function ArticleCard({ article, onChange }) {
  const { user } = useUser()
  const toast = useToast()
  const [saved, setSaved] = useState(article.saved)
  const [feedback, setFeedback] = useState(article.feedback)
  const [showFb, setShowFb] = useState(false)
  const [comment, setComment] = useState('')
  const [busy, setBusy] = useState(false)

  const toggleSave = async () => {
    setBusy(true)
    try {
      const res = await api.toggleSave(user.user_id, article.id)
      setSaved(res.saved)
      onChange?.()
    } catch (e) { toast(e.message, 'error') } finally { setBusy(false) }
  }

  const submitFeedback = async (rating) => {
    try {
      await api.setFeedback(user.user_id, article.id, rating, comment)
      setFeedback(rating)
      setShowFb(false)
      toast('Thanks for the feedback!')
    } catch (e) { toast(e.message, 'error') }
  }

  return (
    <div className="card card-hover p-4 flex flex-col gap-3">
      <div className="flex gap-4">
        {article.image_url && (
          <img src={article.image_url} alt="" className="w-28 h-20 object-cover rounded-lg hidden sm:block"
               onError={(e) => { e.currentTarget.style.display = 'none' }} />
        )}
        <div className="flex-1 min-w-0">
          <a href={article.url} target="_blank" rel="noreferrer"
             className="font-semibold leading-snug hover:underline block">{article.title}</a>
          <div className="flex flex-wrap gap-x-2 gap-y-1 text-xs mt-1" style={{ color: 'var(--muted)' }}>
            <span>{article.source}</span>
            <span>·</span>
            <span>{timeAgo(article.published_at)}</span>
            {article.topic && <span className="chip" style={{ background: 'var(--surface-2)' }}>{article.topic} › {article.subtopic}</span>}
            {typeof article.relevance === 'number' && (
              <span className="chip" style={{ background: 'var(--surface-2)' }}>{Math.round(article.relevance * 100)}% match</span>
            )}
          </div>
        </div>
      </div>
      <p className="text-sm leading-relaxed" style={{ color: '#c7d0dc' }}>
        {article.summary || 'No summary available.'}
      </p>
      <div className="flex items-center gap-2 pt-1 relative">
        <button className="btn btn-ghost" disabled={busy} onClick={toggleSave}
                style={saved ? { background: 'var(--accent)', color: 'white', borderColor: 'var(--accent)' } : {}}>
          {saved ? '★ Saved' : '☆ Save'}
        </button>
        <a className="btn btn-ghost" href={article.url} target="_blank" rel="noreferrer">Read full ↗</a>
        <button className="btn btn-ghost ml-auto" onClick={() => setShowFb((s) => !s)}>
          {feedback === 1 ? '👍' : feedback === -1 ? '👎' : 'Feedback'}
        </button>
        {showFb && (
          <div className="absolute right-0 top-full mt-2 card p-3 w-64 z-10 flex flex-col gap-2 shadow-xl">
            <p className="text-xs" style={{ color: 'var(--muted)' }}>Was this summary helpful?</p>
            <div className="flex gap-2">
              <button className="btn btn-ghost flex-1" onClick={() => submitFeedback(1)}>👍 Helpful</button>
              <button className="btn btn-ghost flex-1" onClick={() => submitFeedback(-1)}>👎 Not helpful</button>
            </div>
            <input className="rounded-lg px-2 py-1 text-sm bg-transparent border" style={{ borderColor: 'var(--border)' }}
                   placeholder="Comment (optional)" value={comment} onChange={(e) => setComment(e.target.value)} />
          </div>
        )}
      </div>
    </div>
  )
}
