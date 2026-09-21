/* ForgeFit — B1: every route the service actually exposes, one function each.
 *
 * frontend/src/api/endpoints.js. Paths verified against backend/app/routers/*.py
 * on 21 Sep 2026. If a screen wants something that is not in this file, the
 * endpoint does not exist.
 *
 * Migration 0003 closed every gap in the Track B table: N1 portions, N2 water,
 * N3 weigh-ins, N4 courses, N5 barcode, R1 prescription, W1 idempotency. The
 * comments that used to say "gap Nx" now say what the field does.
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
   * keep those in localStorage (see the doc).
   * A changed weight_kg also records a weigh-in (N3); an unchanged one does
   * not, so re-saving the Settings form never fabricates a trend point. */
  update: patch => request('/api/profile', { method: 'PUT', body: patch }),
  /* Newest first. Fuel's trend strip reverses it for drawing. */
  weighIns: (limit = 90) => request(`/api/profile/weigh-ins${qs({ limit })}`),
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
   * slab renders. Route writes through queue.js, never directly.
   * Send client_id (W1): a retry after a lost response returns the row the
   * first attempt created, with new_achievements empty so the slab does not
   * fire twice. Finishing a session also advances the active course (N4). */
  create: session => request('/api/workouts', { method: 'POST', body: session, retry: false }),
  list: (limit = 30) => request(`/api/workouts${qs({ limit })}`),
  get: id => request(`/api/workouts/${id}`),
  /* Last session's sets for one exercise — the "Prev" column. */
  ghost: exercise_id => request(`/api/workouts/ghost/${encodeURIComponent(exercise_id)}`),
};

/* ── routines (routers/routines.py — server caps at 3) ─────── */

export const routines = {
  list: () => request('/api/routines'),
  /* exercises: [{exercise_id, default_sets, target_weight_kg?, target_reps?}].
   * Targets are the builder's prescription (R1); null means no target, which
   * the session sheet renders as an empty prefill, not 0. */
  create: (name, exercises = []) => request('/api/routines', { method: 'POST', body: { name, exercises } }),
  update: (id, patch) => request(`/api/routines/${id}`, { method: 'PUT', body: patch }),
  remove: id => request(`/api/routines/${id}`, { method: 'DELETE' }),
};

/* ── nutrition (routers/nutrition.py) ──────────────────────── */

export const nutrition = {
  /* entry carries quantity + unit (N1) straight through from DraftFood or the
   * portion editor. Both optional; pre-N1 entries come back with null / "". */
  log: entry => request('/api/nutrition/log', { method: 'POST', body: entry, retry: false }),
  logBatch: entries => request('/api/nutrition/log/batch', { method: 'POST', body: entries, retry: false }),
  /* daily now also carries water_ml and water_goal_ml (35 ml/kg). */
  daily: day => request(`/api/nutrition/daily${qs({ date: day })}`),

  /* N2 — the water tile appends its increment; it does not send a total. */
  logWater: ml => request('/api/nutrition/water', { method: 'POST', body: { ml }, retry: false }),
  water: day => request(`/api/nutrition/water${qs({ date: day })}`),

  /* N5 — packaged product by UPC/EAN. Returns a DraftFood shape plus brand
   * and upc, so the portion editor treats it exactly like a parsed entry.
   * 404 = provider does not know the code; 502 = provider is down. Run the
   * camera pre-permission explainer BEFORE calling this. */
  barcode: upc => request(`/api/nutrition/barcode/${encodeURIComponent(upc)}`),
};

/* ── courses (routers/courses.py — N4) ─────────────────────── */

export const courses = {
  list: () => request('/api/courses'),
  /* null when not enrolled — Today then falls back to the routine picker.
   * Otherwise session_name is the kicker and current_week/current_day the
   * cursor; sessions_done/sessions_total drive the progress strip. */
  current: () => request('/api/courses/current'),
  /* Enrolling while another course is active abandons it. */
  enrol: course_id => request('/api/courses/enrol', { method: 'POST', body: { course_id } }),
  abandon: () => request('/api/courses/current', { method: 'DELETE' }),
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
