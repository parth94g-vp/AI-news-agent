const BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

class ApiError extends Error {
  constructor(status, detail) {
    super(detail || `Request failed (${status})`)
    this.status = status
  }
}

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  })
  if (res.status === 204) return null
  const isJson = res.headers.get('content-type')?.includes('application/json')
  const body = isJson ? await res.json().catch(() => null) : null
  if (!res.ok) throw new ApiError(res.status, body?.detail || res.statusText)
  return body
}

export const api = {
  health: () => request('/api/health'),
  login: (username) => request('/api/auth/login', { method: 'POST', body: JSON.stringify({ username }) }),
  taxonomy: () => request('/api/taxonomy'),
  getPreferences: (userId) => request(`/api/users/${userId}/preferences`),
  setPreferences: (userId, preferences) =>
    request(`/api/users/${userId}/preferences`, { method: 'PUT', body: JSON.stringify({ preferences }) }),
  getDigest: (userId) => request(`/api/users/${userId}/digest`),
  refresh: (userId) => request(`/api/users/${userId}/refresh`, { method: 'POST' }),
  listSaved: (userId) => request(`/api/users/${userId}/saved`),
  toggleSave: (userId, articleId) => request(`/api/users/${userId}/articles/${articleId}/save`, { method: 'POST' }),
  setFeedback: (userId, articleId, rating, comment) =>
    request(`/api/users/${userId}/articles/${articleId}/feedback`, {
      method: 'POST', body: JSON.stringify({ rating, comment }),
    }),
  ask: (userId, question) =>
    request(`/api/users/${userId}/assistant`, { method: 'POST', body: JSON.stringify({ question }) }),
  getEmail: (userId) => request(`/api/users/${userId}/email`),
  setEmail: (userId, email) =>
    request(`/api/users/${userId}/email`, { method: 'PUT', body: JSON.stringify({ email }) }),
  trending: () => request('/api/trending'),
}

export { ApiError }
