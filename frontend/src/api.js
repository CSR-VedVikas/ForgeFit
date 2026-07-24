const API = ''

function getToken() {
  return localStorage.getItem('forgefit_token')
}

export function setToken(token) {
  if (token) localStorage.setItem('forgefit_token', token)
  else localStorage.removeItem('forgefit_token')
}

export async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) }
  if (!(options.body instanceof FormData) && options.body && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json'
  }
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`

  const res = await fetch(`${API}${path}`, { ...options, headers })
  if (res.status === 401) {
    setToken(null)
    if (!path.includes('/auth/')) {
      window.location.href = '/login'
    }
  }
  if (!res.ok) {
    let detail = res.statusText
    try {
      const data = await res.json()
      detail = data.detail || JSON.stringify(data)
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  if (res.status === 204) return null
  return res.json()
}

export const mediaUrl = (path) => {
  if (!path) return ''
  if (path.startsWith('http')) return path
  if (path.startsWith('images/')) return `/media/${path}`
  if (path.startsWith('videos/')) return `/media/${path}`
  return `/media/${path}`
}
