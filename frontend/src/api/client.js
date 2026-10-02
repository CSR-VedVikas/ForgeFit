/* ForgeFit — the one data layer.
 *
 * Every screen calls api(); nothing else calls fetch(). The exported names
 * and call shape are the same as the old src/api.js, so no screen changed.
 * What lives here and nowhere else:
 *
 *   - the access token (localStorage) and the Authorization header
 *   - refresh: on a 401, exchange the httpOnly refresh cookie for a new
 *     access token once, retry, and only then report the session lost
 *   - the user's timezone, sent on every request so "today" means their day
 *   - one error shape, whose .message is fit to show a person
 */

const TOKEN_KEY = 'forgefit_token'
const TIMEOUT_MS = 30000 // Smart Log waits on OpenAI and the nutrition provider

/* Auth endpoints whose 401 means "wrong credentials", not "session expired".
 * Refreshing on these would turn a mistyped password into a silent retry. */
const NO_REFRESH = ['/api/auth/login', '/api/auth/register', '/api/auth/refresh',
  '/api/auth/logout', '/api/auth/forgot-password', '/api/auth/reset-password']

const TIMEZONE = (() => {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || ''
  } catch {
    return ''
  }
})()

/* ── token ─────────────────────────────────────────────────────── */

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

/* ── session lost ──────────────────────────────────────────────── */

/* The old layer did window.location.href = '/login' from inside a fetch,
 * which reloaded the whole app and dropped whatever the user was doing.
 * Now AuthProvider subscribes and clears the user; the router redirects. */
const listeners = new Set()
export function onAuthLost(fn) {
  listeners.add(fn)
  return () => listeners.delete(fn)
}
function authLost() {
  setToken(null)
  listeners.forEach((fn) => {
    try {
      fn()
    } catch {
      /* a broken listener must not stop the others */
    }
  })
}

/* ── errors ────────────────────────────────────────────────────── */

export class ApiError extends Error {
  constructor(status, detail, path) {
    super(messageFor(status, detail))
    this.name = 'ApiError'
    this.status = status // 0 = never reached the server
    this.detail = detail
    this.path = path
  }
}

const FIELD_LABELS = { display_name: 'Display name', new_password: 'New password',
  current_password: 'Current password', new_email: 'New email' }

function fieldLabel(loc) {
  const key = Array.isArray(loc) ? loc[loc.length - 1] : ''
  if (!key || typeof key !== 'string') return ''
  return FIELD_LABELS[key] || key.charAt(0).toUpperCase() + key.slice(1).replace(/_/g, ' ')
}

/* Screens render err.message, so it has to read like a sentence. FastAPI's
 * 422 detail is an array of objects; the old layer stringified it, which is
 * how raw JSON ended up on the sign-up form. */
function messageFor(status, detail) {
  if (status === 0) {
    return detail === 'timeout'
      ? 'The server took too long to respond. Please try again.'
      : "Can't reach ForgeFit. Check your connection and try again."
  }
  if (status === 429) return 'Too many attempts. Wait a minute and try again.'
  if (status >= 500) return 'Something went wrong on our side. Please try again.'
  if (Array.isArray(detail) && detail.length) {
    const first = detail[0] || {}
    const label = fieldLabel(first.loc)
    // Pydantic appends a long explanation after a colon; keep the headline.
    const msg = String(first.msg || 'is invalid').split(': ')[0]
    return label ? `${label}: ${msg.charAt(0).toLowerCase()}${msg.slice(1)}.` : `${msg}.`
  }
  if (typeof detail === 'string' && detail) return detail
  if (status === 401) return 'Your session has expired. Please sign in again.'
  return "That didn't work. Please try again."
}

async function detailOf(res) {
  try {
    const data = await res.json()
    return data?.detail ?? data
  } catch {
    return res.statusText
  }
}

/* ── refresh ───────────────────────────────────────────────────── */

/* The server rotates the refresh token on every call and treats a replayed
 * one as theft, revoking every session. Two screens that 401 at once must
 * therefore share a single refresh, never race two. */
let refreshing = null

function refreshSession() {
  if (!refreshing) {
    refreshing = fetch('/api/auth/refresh', {
      method: 'POST',
      credentials: 'same-origin', // carries the httpOnly cookie
      headers: TIMEZONE ? { 'X-Timezone': TIMEZONE } : {},
    })
      .then(async (res) => {
        if (!res.ok) return false
        const data = await res.json()
        setToken(data.access_token)
        return true
      })
      .catch(() => false)
      .finally(() => {
        refreshing = null
      })
  }
  return refreshing
}

/* ── request ───────────────────────────────────────────────────── */

async function send(path, options) {
  const headers = { ...(options.headers || {}) }
  if (!(options.body instanceof FormData) && options.body && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json'
  }
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  if (TIMEZONE) headers['X-Timezone'] = TIMEZONE

  const ac = new AbortController()
  const timer = setTimeout(() => ac.abort(), TIMEOUT_MS)
  try {
    return await fetch(path, { ...options, headers, credentials: 'same-origin', signal: ac.signal })
  } catch (e) {
    throw new ApiError(0, e?.name === 'AbortError' ? 'timeout' : 'offline', path)
  } finally {
    clearTimeout(timer)
  }
}

export async function api(path, options = {}) {
  let res = await send(path, options)

  if (res.status === 401 && !NO_REFRESH.some((p) => path.startsWith(p))) {
    if (await refreshSession()) res = await send(path, options)
    if (res.status === 401) {
      authLost()
      throw new ApiError(401, null, path)
    }
  }

  if (!res.ok) throw new ApiError(res.status, await detailOf(res), path)
  if (res.status === 204) return null
  return res.json()
}

/* Revokes the refresh token server-side and clears the cookie. Best effort:
 * the caller clears local state regardless. */
export function revokeSession() {
  return fetch('/api/auth/logout', { method: 'POST', credentials: 'same-origin' }).catch(() => {})
}

/* ── media ─────────────────────────────────────────────────────── */

export const mediaUrl = (path) => {
  if (!path) return ''
  if (path.startsWith('http')) return path
  return `/media/${path.replace(/^\/?media\//, '')}`
}
