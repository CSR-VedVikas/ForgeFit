/* ForgeFit — B1: the one data layer.
 *
 * Drop in at frontend/src/api/client.js. Replaces frontend/src/api.js.
 * Every screen goes through request(); nothing else calls fetch().
 *
 * What lives here and nowhere else:
 *   - the Authorization header
 *   - 401 handling (refresh once, then a single logout broadcast)
 *   - retry (idempotent methods only) and timeout
 *   - one error shape (ApiError) so eight screens don't parse detail eight ways
 *   - the online/offline signal the session queue reads
 *
 * Token storage is deliberately behind tokens.* so S5 (httpOnly cookie) is a
 * change in one object, not in every screen.
 */

const BASE = import.meta?.env?.VITE_API_BASE ?? '';
const TIMEOUT_MS = 12000;
const RETRIES = 2;             // idempotent methods only
const RETRY_BACKOFF = [400, 1200];

/* ── error shape ───────────────────────────────────────────── */

export class ApiError extends Error {
  constructor(status, detail, { code = null, retryable = false, path = '' } = {}) {
    super(typeof detail === 'string' ? detail : JSON.stringify(detail));
    this.name = 'ApiError';
    this.status = status;        // 0 = never reached the network
    this.detail = detail;
    this.code = code;
    this.retryable = retryable;
    this.path = path;
  }
  get isOffline() { return this.status === 0; }
  get isAuth() { return this.status === 401; }
  get isValidation() { return this.status === 400 || this.status === 422; }
  get isRateLimited() { return this.status === 429; }

  /* Screens render this, never .message — FastAPI 422 detail is an array. */
  get userMessage() {
    if (this.status === 0) return 'No connection. This will send when you are back online.';
    if (this.status === 401) return 'Your session expired. Sign in again.';
    if (this.status === 429) return 'Too many attempts. Wait a minute and try again.';
    if (this.status >= 500) return 'Something broke on our side. Try again.';
    if (Array.isArray(this.detail)) {
      const f = this.detail[0];
      return f?.msg ? `${(f.loc || []).slice(-1)[0] || 'Field'}: ${f.msg}` : 'That input was rejected.';
    }
    return typeof this.detail === 'string' ? this.detail : 'That did not work.';
  }
}

/* ── tokens ────────────────────────────────────────────────── */

const ACCESS_KEY = 'forgefit_token';

export const tokens = {
  access: () => localStorage.getItem(ACCESS_KEY),
  set(access) {
    if (access) localStorage.setItem(ACCESS_KEY, access);
    else localStorage.removeItem(ACCESS_KEY);
  },
  clear() { localStorage.removeItem(ACCESS_KEY); },
};

/* ── auth events (no window.location.href from inside a fetch) ── */

const listeners = new Set();
export const onAuthLost = fn => { listeners.add(fn); return () => listeners.delete(fn); };
let broadcasting = false;
function authLost() {
  if (broadcasting) return;      // eight parallel 401s must produce one logout
  broadcasting = true;
  tokens.clear();
  listeners.forEach(fn => { try { fn(); } catch { /* ignore */ } });
  setTimeout(() => { broadcasting = false; }, 1000);
}

/* Refresh. PR5 landed the route, so this is live.
 *
 * The refresh token is an httpOnly cookie scoped to /api/auth — credentials:
 * 'include' is what sends it, and no Authorization header goes with it. Only
 * the short-lived access token is visible to this file.
 *
 * The server rotates on every call and treats a replayed token as theft, so
 * two concurrent refreshes would revoke each other. The `refreshing` promise
 * below collapses them into one. */
const HAS_REFRESH = true;
let refreshing = null;
async function refresh() {
  if (!HAS_REFRESH) return false;
  refreshing = refreshing || (async () => {
    try {
      const res = await fetch(`${BASE}/api/auth/refresh`, {
        method: 'POST', credentials: 'include',
      });
      if (!res.ok) return false;
      const data = await res.json();
      tokens.set(data.access_token);
      return true;
    } catch { return false; }
    finally { refreshing = null; }
  })();
  return refreshing;
}

/* ── connectivity ──────────────────────────────────────────── */

export const isOnline = () => navigator.onLine !== false;

/* ── request ───────────────────────────────────────────────── */

const IDEMPOTENT = new Set(['GET', 'HEAD', 'PUT', 'DELETE']);
const inflight = new Map();    // dedupe identical concurrent GETs

export async function request(path, {
  method = 'GET', body, form, headers = {}, signal,
  auth = true, retry, timeout = TIMEOUT_MS,
} = {}) {
  const m = method.toUpperCase();
  const canRetry = retry ?? IDEMPOTENT.has(m);

  if (m === 'GET' && !signal) {
    const key = path;
    if (inflight.has(key)) return inflight.get(key);
    const p = attempt().finally(() => inflight.delete(key));
    inflight.set(key, p);
    return p;
  }
  return attempt();

  async function attempt(tries = 0, didRefresh = false) {
    const h = { ...headers };
    let payload;
    if (form) payload = form;                       // OAuth2 /login wants urlencoded
    else if (body !== undefined) {
      payload = JSON.stringify(body);
      h['Content-Type'] = 'application/json';
    }
    const t = tokens.access();
    if (auth && t) h.Authorization = `Bearer ${t}`;

    const ac = new AbortController();
    const timer = setTimeout(() => ac.abort(), timeout);
    if (signal) signal.addEventListener('abort', () => ac.abort(), { once: true });

    let res;
    try {
      res = await fetch(`${BASE}${path}`, { method: m, headers: h, body: payload, signal: ac.signal });
    } catch (e) {
      clearTimeout(timer);
      const offline = new ApiError(0, e.name === 'AbortError' ? 'Request timed out' : 'Network unreachable',
        { retryable: true, path });
      if (canRetry && tries < RETRIES) {
        await sleep(RETRY_BACKOFF[tries]);
        return attempt(tries + 1, didRefresh);
      }
      throw offline;
    }
    clearTimeout(timer);

    if (res.status === 401 && auth) {
      if (!didRefresh && await refresh()) return attempt(tries, true);
      authLost();
      throw new ApiError(401, 'Not authenticated', { path });
    }

    if (res.status === 429) {
      throw new ApiError(429, await detailOf(res), { path, retryable: true });
    }

    if (res.status >= 500 && canRetry && tries < RETRIES) {
      await sleep(RETRY_BACKOFF[tries]);
      return attempt(tries + 1, didRefresh);
    }

    if (!res.ok) throw new ApiError(res.status, await detailOf(res), { path });

    if (res.status === 204) return null;
    const ct = res.headers.get('content-type') || '';
    return ct.includes('application/json') ? res.json() : res.text();
  }
}

async function detailOf(res) {
  try {
    const data = await res.json();
    return data.detail ?? data;
  } catch { return res.statusText || 'Request failed'; }
}
const sleep = ms => new Promise(r => setTimeout(r, ms));

/* ── media ─────────────────────────────────────────────────── */

/* Catalogue images come off the /media static mount, not the bundle.
 * ExerciseListItem.image is already a path like "images/0001-2gPfomN.jpg". */
export function mediaUrl(p) {
  if (!p) return '';
  if (p.startsWith('http')) return p;
  return `${BASE}/media/${p.replace(/^\/?media\//, '')}`;
}
