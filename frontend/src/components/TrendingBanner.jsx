import { useEffect, useState } from 'react'
import { api } from '../api/client'

export default function TrendingBanner() {
  const [items, setItems] = useState([])

  useEffect(() => {
    api.trending().then(setItems).catch(() => setItems([]))
  }, [])

  if (items.length === 0) return null

  return (
    <div className="card p-4 flex flex-col gap-2" style={{ borderColor: '#f0b429' }}>
      <h3 className="font-semibold flex items-center gap-2">🔥 Trending today</h3>
      <div className="flex flex-wrap gap-2">
        {items.slice(0, 6).map((t) => (
          <span key={`${t.topic}-${t.subtopic}`} className="chip" style={{ background: 'var(--surface-2)' }}>
            {t.subtopic} <span style={{ color: '#f0b429' }}>· {t.today_count} articles ({t.ratio.toFixed(1)}x normal)</span>
          </span>
        ))}
      </div>
    </div>
  )
}
