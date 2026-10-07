const BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'
const TOKEN_KEY = 'news_agent_token'

export const getToken = () => localStorage.getItem(TOKEN_KEY)
export const setToken = (token) => token ? localStorage.setItem(TOKEN_KEY, token) : localStorage.removeItem(TOKEN_KEY)

class ApiError extends Error {
  constructor(status, detail) {
    super(detail || `Request failed (${status})`)
    this.status = status
  }
}

// Fires when any request gets a 401, so the app can log the user out exactly once,
// globally - no individual page needs to handle "my token stopped working" itself.
let onUnauthorized = () => {}
export const setUnauthorizedHandler = (fn) => { onUnauthorized = fn }

async function request(path, options = {}) {
  const token = getToken()
  const res = await fetch(`${BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    },
    ...options,
  })
  if (res.status === 401) {
    setToken(null)
    onUnauthorized()
  }
  if (res.status === 204) return null
  const isJson = res.headers.get('content-type')?.includes('application/json')
  const body = isJson ? await res.json().catch(() => null) : null
  if (!res.ok) throw new ApiError(res.status, body?.detail || res.statusText)
  return body
}

export const api = {
  health: () => request('/api/health'),
  signup: (username, password) =>
    request('/api/auth/signup', { method: 'POST', body: JSON.stringify({ username, password }) }),
  login: (username, password) =>
    request('/api/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) }),
  logout: () => request('/api/auth/logout', { method: 'POST' }),
  me: () => request('/api/auth/me'),
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
