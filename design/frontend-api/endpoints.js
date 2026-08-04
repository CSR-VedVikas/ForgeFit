/* ForgeFit — B1: every route the service actually exposes, one function each.
 *
 * frontend/src/api/endpoints.js. Paths verified against backend/app/routers/*.py
 * on 29 Jul 2026. If a screen wants something that is not in this file, the
 * endpoint does not exist — see the gaps table in the Track B wiring doc.
 */

import { request, tokens } from './client.js';

/* ── auth (routers/auth.py, prefix /api/auth) ──────────────── */

export const auth = {
  register: (email, password, display_name = '') =>
    request('/api/auth/register', { method: 'POST', auth: false, body: { email, password, display_name } })
      .then(keep),

  /* /login is OAuth2PasswordRequestForm — urlencoded, field is `username`.
   * /login/json takes {email, password}. Use the JSON one; it is ours. */
  login: (email, password) =>
    request('/api/auth/login/json', { method: 'POST', auth: false, body: { email, password } })
      .then(keep),

  me: () => request('/api/auth/me'),

  /* Response is generic by design. reset_token is present in development only
   * (and after S1, only there) — never branch the UI on it. */
  forgotPassword: email =>
    request('/api/auth/forgot-password', { method: 'POST', auth: false, body: { email } }),

  resetPassword: (token, new_password) =>
    request('/api/auth/reset-password', { method: 'POST', auth: false, body: { token, new_password } }),

  changePassword: (current_password, new_password) =>
    request('/api/auth/password', { method: 'PUT', body: { current_password, new_password } }),

  changeEmail: (password, new_email) =>
    request('/api/auth/email', { method: 'PUT', body: { password, new_email } }),

  /* PR5 — this actually revokes now. The server kills the refresh row and
   * clears the cookie; dropping the local access token is the second half.
   * Unauthenticated by design, so it still works past access-token expiry. */
  async signOut() {
    try {
      await fetch(`${import.meta?.env?.VITE_API_BASE ?? ''}/api/auth/logout`, {
        method: 'POST', credentials: 'include',
      });
    } catch { /* revoke is best-effort; the local clear below is not */ }
    tokens.clear();
  },
};

function keep(t) { tokens.set(t.access_token); return t; }

/* ── profile (routers/profile.py) ──────────────────────────── */

export const profile = {
  get: () => request('/api/profile'),
  /* Partial: display_name, gender, weight_kg, height_cm, age,
   * daily_calorie_goal, rest_seconds. Units and plate step are NOT here —
   * keep those in localStorage (see the doc). */
  update: patch => request('/api/profile', { method: 'PUT', body: patch }),
};

/* ── exercises (routers/exercises.py) ──────────────────────── */

export const exercises = {
  /* ids are strings ("0001"), not ints. */
  list: ({ q, body_part, equipment, target, limit = 50, offset = 0 } = {}) =>
    request(`/api/exercises${qs({ q, body_part, equipment, target, limit, offset })}`),
  filters: () => request('/api/exercises/meta/filters'),
  get: id => request(`/api/exercises/${encodeURIComponent(id)}`),
};

/* ── nlp (routers/nlp.py) ──────────────────────────────────── */

export const nlp = {
  /* Read draft.sets[].needs_confirm — the 0.75 threshold is server-side and
   * already applied. Do not compare match_confidence in the UI. */
  parse: (text, meal_type = 'snack') =>
    request('/api/nlp/parse', { method: 'POST', body: { text, meal_type } }),
};

/* ── workouts (routers/workouts.py) ────────────────────────── */

export const workouts = {
  /* One call per finished session — there is no per-set endpoint.
   * Response carries sets[].is_pr and sets[].pr_types (max_weight /
   * max_volume / max_reps) plus new_achievements: that is what the record
   * slab renders. Route writes through queue.js, never directly. */
  create: session => request('/api/workouts', { method: 'POST', body: session, retry: false }),
  list: (limit = 30) => request(`/api/workouts${qs({ limit })}`),
  get: id => request(`/api/workouts/${id}`),
  /* Last session's sets for one exercise — the "Prev" column. */
  ghost: exercise_id => request(`/api/workouts/ghost/${encodeURIComponent(exercise_id)}`),
};

/* ── routines (routers/routines.py — server caps at 3) ─────── */

export const routines = {
  list: () => request('/api/routines'),
  /* exercises: [{exercise_id, default_sets}] only. No target load or reps —
   * the builder's prescription has nowhere to persist yet (gap R1). */
  create: (name, exercises = []) => request('/api/routines', { method: 'POST', body: { name, exercises } }),
  update: (id, patch) => request(`/api/routines/${id}`, { method: 'PUT', body: patch }),
  remove: id => request(`/api/routines/${id}`, { method: 'DELETE' }),
};

/* ── nutrition (routers/nutrition.py) ──────────────────────── */

export const nutrition = {
  /* FoodLogCreate has no quantity/unit — portions cannot round-trip yet
   * (gap N1), even though nlp.parse returns them on DraftFood. */
  log: entry => request('/api/nutrition/log', { method: 'POST', body: entry, retry: false }),
  logBatch: entries => request('/api/nutrition/log/batch', { method: 'POST', body: entries, retry: false }),
  daily: day => request(`/api/nutrition/daily${qs({ date: day })}`),
};

/* ── stats (routers/stats.py) ──────────────────────────────── */

export const stats = {
  /* Today: calories_in/burned/goal, volume_today, streak_days, recent_prs,
   * challenge{progress_pct}, recent_achievements. All server-computed. */
  dashboard: () => request('/api/stats/dashboard'),
  dailyLink: day => request(`/api/stats/daily-link${qs({ date: day })}`),
  achievements: () => request('/api/stats/achievements'),
  /* Muscle map. body_part + set_count + volume, grouped. */
  heatmap: (days = 7) => request(`/api/stats/heatmap${qs({ days })}`),
  volume: (days = 30) => request(`/api/stats/volume${qs({ days })}`),
  /* One response carries duration_min, volume AND reps per day — the metric
   * switch on You is a client-side read of the same payload, not a re-query. */
  activity: (days = 90) => request(`/api/stats/activity${qs({ days })}`),
};

export const health = () => request('/api/health', { auth: false });

function qs(o) {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(o)) if (v !== undefined && v !== null && v !== '') p.set(k, v);
  const s = p.toString();
  return s ? `?${s}` : '';
}
