/* ForgeFit — B2: a logged set must not need the network.
 *
 * frontend/src/api/session-queue.js
 *
 * The decision this file encodes: the live session is a LOCAL document.
 * Sets are written to IndexedDB as they are logged; the service is told once,
 * at finish, with POST /api/workouts. That matches the API — there is no
 * per-set endpoint — and it means a basement session survives a reload, a
 * crash, and a dead signal with no partial-session state on the server.
 *
 * Consequence the UI must accept: records (is_pr / pr_types) are authoritative
 * only after the finish call returns. The in-session record slab is a local
 * prediction; the Today and You counts are reconciled from the response.
 *
 * Idempotency: POST /api/workouts has no client key, so a retry after a lost
 * response can duplicate a session. Until `client_id` is added to
 * WorkoutCreate (gap W1), reconcile() checks the last few sessions for a match
 * before re-posting. Recommended fix in the doc; this is the safe interim.
 */

import { workouts } from './endpoints.js';
import { ApiError, isOnline } from './client.js';

const DB = 'forgefit';
const STORE = 'sessions';
const VERSION = 1;

function open() {
  return new Promise((res, rej) => {
    const r = indexedDB.open(DB, VERSION);
    r.onupgradeneeded = () => {
      const db = r.result;
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE, { keyPath: 'client_id' }).createIndex('state', 'state');
      }
    };
    r.onsuccess = () => res(r.result);
    r.onerror = () => rej(r.error);
  });
}

async function tx(mode, fn) {
  const db = await open();
  return new Promise((res, rej) => {
    const t = db.transaction(STORE, mode);
    const out = fn(t.objectStore(STORE));
    t.oncomplete = () => res(out?.result ?? out);
    t.onerror = () => rej(t.error);
  });
}

const uid = () =>
  (crypto.randomUUID?.() || `s_${Date.now()}_${Math.random().toString(36).slice(2)}`);

/* ── the live session document ─────────────────────────────── */

export const session = {
  /* Called when the user starts a workout. Returns the draft. */
  async start({ routine_id = null, notes = '' } = {}) {
    const draft = {
      client_id: uid(),
      state: 'open',
      started_at: new Date().toISOString(),
      ended_at: null,
      routine_id, notes,
      source_query: '',
      calories_burned: 0,
      sets: [],
      attempts: 0,
      last_error: null,
    };
    await tx('readwrite', s => s.put(draft));
    return draft;
  },

  /* Resume after a reload or a crash. */
  async open() {
    const all = await tx('readonly', s => s.getAll());
    return (all || []).find(d => d.state === 'open') || null;
  },

  /* Every logged set lands here first. Local write, no await on the network. */
  async addSet(client_id, { exercise_id, weight_kg = 0, reps, set_number = 1 }) {
    const d = await tx('readonly', s => s.get(client_id));
    if (!d) throw new Error('No open session');
    d.sets.push({ exercise_id, weight_kg, reps, set_number, logged_at: new Date().toISOString() });
    await tx('readwrite', s => s.put(d));
    return d;
  },

  async removeSet(client_id, index) {
    const d = await tx('readonly', s => s.get(client_id));
    if (!d) return null;
    d.sets.splice(index, 1);
    await tx('readwrite', s => s.put(d));
    return d;
  },

  async patch(client_id, fields) {
    const d = await tx('readonly', s => s.get(client_id));
    if (!d) return null;
    Object.assign(d, fields);
    await tx('readwrite', s => s.put(d));
    return d;
  },

  /* Finish: mark pending, then try once. Resolves with the server WorkoutOut
   * when it lands, or {queued:true} when it did not — the UI shows the session
   * as saved either way, because locally it is. */
  async finish(client_id, { calories_burned = 0, notes, source_query } = {}) {
    const d = await tx('readonly', s => s.get(client_id));
    if (!d) throw new Error('No such session');
    Object.assign(d, {
      state: 'pending',
      ended_at: new Date().toISOString(),
      calories_burned,
      notes: notes ?? d.notes,
      source_query: source_query ?? d.source_query,
    });
    await tx('readwrite', s => s.put(d));
    if (!isOnline()) return { queued: true, draft: d };
    return flushOne(d);
  },

  async pendingCount() {
    const all = await tx('readonly', s => s.getAll());
    return (all || []).filter(d => d.state === 'pending').length;
  },
};

/* ── flushing ──────────────────────────────────────────────── */

const done = new Set();   // subscribers: (workoutOut) => void
export const onSynced = fn => { done.add(fn); return () => done.delete(fn); };

function payloadOf(d) {
  return {
    notes: d.notes || '',
    source_query: d.source_query || '',
    calories_burned: d.calories_burned || 0,
    started_at: d.started_at,
    ended_at: d.ended_at,
    sets: d.sets.map(({ exercise_id, weight_kg, reps, set_number }) =>
      ({ exercise_id, weight_kg, reps, set_number })),
    /* Harmless today (extra="ignore" upstream), authoritative once W1 lands. */
    client_id: d.client_id,
  };
}

async function flushOne(d) {
  try {
    const out = await workouts.create(payloadOf(d));
    await tx('readwrite', s => s.delete(d.client_id));
    done.forEach(fn => { try { fn(out); } catch { /* ignore */ } });
    return { queued: false, workout: out };
  } catch (e) {
    d.attempts += 1;
    d.last_error = e instanceof ApiError ? { status: e.status, detail: e.userMessage } : { status: -1 };
    /* A 400 will never succeed on retry — usually an exercise_id the catalogue
     * does not know. Park it for the UI to surface rather than looping. */
    if (e instanceof ApiError && e.isValidation) d.state = 'rejected';
    await tx('readwrite', s => s.put(d));
    if (d.state === 'rejected') throw e;
    return { queued: true, draft: d, error: e };
  }
}

/* Did a previous attempt actually land? Compare started_at + set count against
 * the last few server sessions before posting again. */
async function reconcile(d) {
  try {
    const recent = await workouts.list(5);
    const t = Date.parse(d.started_at);
    return recent.find(w =>
      Math.abs(Date.parse(w.started_at) - t) < 60000 && w.sets.length === d.sets.length) || null;
  } catch { return null; }
}

export async function flush() {
  if (!isOnline()) return { sent: 0, queued: await session.pendingCount() };
  const all = (await tx('readonly', s => s.getAll())) || [];
  let sent = 0;
  for (const d of all.filter(x => x.state === 'pending')) {
    if (d.attempts > 0) {
      const already = await reconcile(d);
      if (already) {
        await tx('readwrite', s => s.delete(d.client_id));
        done.forEach(fn => { try { fn(already); } catch { /* ignore */ } });
        sent += 1;
        continue;
      }
    }
    const r = await flushOne(d).catch(() => null);
    if (r && !r.queued) sent += 1;
  }
  return { sent, queued: await session.pendingCount() };
}

/* Call once from App mount. */
export function startAutoFlush() {
  const go = () => { flush().catch(() => {}); };
  window.addEventListener('online', go);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) go(); });
  go();
  return () => window.removeEventListener('online', go);
}
