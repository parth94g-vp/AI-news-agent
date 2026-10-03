import { useCallback, useEffect, useState } from 'react'
import { api } from '../api/client'
import { useUser } from '../context/UserContext'
import ArticleCard from '../components/ArticleCard'
import Spinner from '../components/Spinner'

export default function Saved() {
  const { user } = useUser()
  const [articles, setArticles] = useState(undefined)
  const [error, setError] = useState('')

  const load = useCallback(() => {
    api.listSaved(user.user_id).then(setArticles).catch((e) => setError(e.message))
  }, [user])

  useEffect(() => { load() }, [load])

  if (error) return <p style={{ color: 'var(--bad)' }}>{error}</p>
  if (articles === undefined) return <Spinner label="Loading saved articles…" />

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-bold">Saved Articles</h1>
      {articles.length === 0
        ? <div className="card p-8 text-center" style={{ color: 'var(--muted)' }}>Articles you bookmark will appear here.</div>
        : <div className="grid gap-3">{articles.map((a) => <ArticleCard key={a.id} article={a} onChange={load} />)}</div>}
    </div>
  )
}
