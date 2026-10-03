import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import { useUser } from '../context/UserContext'
import ArticleCard from '../components/ArticleCard'
import Spinner from '../components/Spinner'
import TrendingBanner from '../components/TrendingBanner'

export default function Digest() {
  const { user } = useUser()
  const [digest, setDigest] = useState(undefined) // undefined = loading, null = none yet
  const [error, setError] = useState('')

  const load = useCallback(() => {
    api.getDigest(user.user_id).then(setDigest).catch((e) => {
      if (e instanceof ApiError && e.status === 404) setDigest(null)
      else setError(e.message)
    })
  }, [user])

  useEffect(() => {
    load()
    window.addEventListener('digest:refreshed', load)
    return () => window.removeEventListener('digest:refreshed', load)
  }, [load])

  if (error) return <p style={{ color: 'var(--bad)' }}>{error}</p>
  if (digest === undefined) return <Spinner label="Loading your digest…" />
  if (digest === null) {
    return (
      <div className="card p-8 text-center">
        <p className="mb-2">No news yet.</p>
        <p className="text-sm" style={{ color: 'var(--muted)' }}>
          Choose your topics in <Link to="/preferences" className="underline">My Topics</Link>, then click
          <b> Refresh my news</b> in the sidebar.
        </p>
      </div>
    )
  }

  const byTopic = digest.entries.reduce((acc, e) => {
    (acc[e.topic || 'Other'] ??= {})[e.subtopic || '-'] ??= []
    acc[e.topic || 'Other'][e.subtopic || '-'].push(e)
    return acc
  }, {})

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold">
          Your news for {new Date(digest.digest_date).toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}
        </h1>
        {digest.is_stale && (
          <p className="text-sm mt-1" style={{ color: '#f0b429' }}>
            This digest isn't from today. Click <b>Refresh my news</b> for the latest.
          </p>
        )}
      </div>
      <TrendingBanner />
      {digest.overview && <div className="card p-4 text-sm leading-relaxed">{digest.overview}</div>}
      {Object.entries(byTopic).map(([topic, subs]) => (
        <section key={topic} className="flex flex-col gap-4">
          <h2 className="text-lg font-bold border-b pb-2" style={{ borderColor: 'var(--border)' }}>{topic}</h2>
          {Object.entries(subs).map(([sub, articles]) => (
            <div key={sub} className="flex flex-col gap-3">
              <h3 className="text-sm font-semibold" style={{ color: 'var(--muted)' }}>{sub}</h3>
              <div className="grid gap-3">
                {articles.map((a) => <ArticleCard key={a.id} article={a} onChange={load} />)}
              </div>
            </div>
          ))}
        </section>
      ))}
    </div>
  )
}
