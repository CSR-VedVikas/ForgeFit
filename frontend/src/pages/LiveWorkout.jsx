import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, mediaUrl } from '../api'
import PRCelebration from '../components/PRCelebration'

function formatElapsed(ms) {
  const total = Math.max(0, Math.floor(ms / 1000))
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  return `${m}:${String(s).padStart(2, '0')}`
}

function onNumberChange(setter) {
  return (e) => {
    const raw = e.target.value
    if (raw === '') {
      setter('')
      return
    }
    if (!/^\d*\.?\d*$/.test(raw)) return
    setter(raw.replace(/^0+(?=\d)/, ''))
  }
}

/** @typedef {{ key: string, exercise_id: string, exercise_name: string, image?: string, gif_url?: string, weight: string, reps: string, done: boolean, set_number: number }} LiveRow */

export default function LiveWorkout() {
  const [view, setView] = useState('hub') // hub | builder | session
  const [routines, setRoutines] = useState([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [achievements, setAchievements] = useState(null)
  const [summary, setSummary] = useState(null)

  // builder
  const [editId, setEditId] = useState(null)
  const [routineName, setRoutineName] = useState('')
  const [picked, setPicked] = useState([])
  const [q, setQ] = useState('')
  const [results, setResults] = useState([])

  // session
  const [rows, setRows] = useState(/** @type {LiveRow[]} */ ([]))
  const [sessionTitle, setSessionTitle] = useState('Empty workout')
  const [running, setRunning] = useState(false)
  const [tick, setTick] = useState(0)
  const startRef = useRef(null)

  async function loadRoutines() {
    try {
      setRoutines(await api('/api/routines'))
    } catch {
      /* ignore */
    }
  }

  useEffect(() => {
    loadRoutines()
  }, [])

  useEffect(() => {
    if (!running) return
    const id = setInterval(() => setTick((t) => t + 1), 1000)
    return () => clearInterval(id)
  }, [running])

  useEffect(() => {
    if ((view !== 'builder' && view !== 'session') || !q.trim()) {
      setResults([])
      return
    }
    const t = setTimeout(() => {
      api(`/api/exercises?q=${encodeURIComponent(q)}&limit=12`).then(setResults).catch(() => {})
    }, 250)
    return () => clearTimeout(t)
  }, [q, view])

  function openBuilder(routine = null) {
    setError('')
    if (routine) {
      setEditId(routine.id)
      setRoutineName(routine.name)
      setPicked(
        routine.exercises.map((e) => ({
          id: e.exercise_id,
          name: e.exercise_name,
          image: e.image,
          gif_url: e.gif_url,
          default_sets: e.default_sets,
        }))
      )
    } else {
      if (routines.length >= 3) {
        setError('You can save up to 3 routines. Delete one to add another.')
        return
      }
      setEditId(null)
      setRoutineName('')
      setPicked([])
    }
    setQ('')
    setView('builder')
  }

  function addExerciseToRoutine(ex) {
    if (picked.some((p) => p.id === ex.id)) return
    setPicked((prev) => [...prev, { id: ex.id, name: ex.name, image: ex.image, gif_url: ex.gif_url, default_sets: 3 }])
    setQ('')
    setResults([])
  }

  async function saveRoutine(e) {
    e.preventDefault()
    if (!routineName.trim()) {
      setError('Name your routine')
      return
    }
    if (!picked.length) {
      setError('Add at least one exercise')
      return
    }
    setBusy(true)
    setError('')
    const body = {
      name: routineName.trim(),
      exercises: picked.map((p) => ({ exercise_id: p.id, default_sets: p.default_sets || 3 })),
    }
    try {
      if (editId) {
        await api(`/api/routines/${editId}`, { method: 'PUT', body: JSON.stringify(body) })
      } else {
        await api('/api/routines', { method: 'POST', body: JSON.stringify(body) })
      }
      await loadRoutines()
      setView('hub')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function deleteRoutine(id) {
    if (!confirm('Delete this routine?')) return
    try {
      await api(`/api/routines/${id}`, { method: 'DELETE' })
      await loadRoutines()
    } catch (err) {
      setError(err.message)
    }
  }

  function makeRowsFromExercises(exercises, title) {
    /** @type {LiveRow[]} */
    const next = []
    for (const ex of exercises) {
      const sets = ex.default_sets || 3
      for (let i = 1; i <= sets; i++) {
        next.push({
          key: `${ex.id || ex.exercise_id}-${i}-${Math.random().toString(36).slice(2, 7)}`,
          exercise_id: ex.id || ex.exercise_id,
          exercise_name: ex.name || ex.exercise_name,
          image: ex.image,
          gif_url: ex.gif_url,
          weight: '',
          reps: '',
          done: false,
          set_number: i,
        })
      }
    }
    setRows(next)
    setSessionTitle(title)
    const now = Date.now()
    startRef.current = now
    setRunning(true)
    setSummary(null)
    setError('')
    setView('session')
  }

  function startEmpty() {
    setRows([])
    setSessionTitle('Empty workout')
    const now = Date.now()
    startRef.current = now
    setRunning(true)
    setSummary(null)
    setError('')
    setView('session')
  }

  function startRoutine(routine) {
    makeRowsFromExercises(
      routine.exercises.map((e) => ({
        id: e.exercise_id,
        name: e.exercise_name,
        image: e.image,
        gif_url: e.gif_url,
        default_sets: e.default_sets || 3,
      })),
      routine.name
    )
  }

  async function addExerciseToSession(ex) {
    setRows((prev) => {
      const setNumber = prev.filter((r) => r.exercise_id === ex.id).length + 1
      return [
        ...prev,
        {
          key: `${ex.id}-${setNumber}-${Date.now()}`,
          exercise_id: ex.id,
          exercise_name: ex.name,
          image: ex.image,
          gif_url: ex.gif_url,
          weight: '',
          reps: '',
          done: false,
          set_number: setNumber,
        },
      ]
    })
    setQ('')
    setResults([])
  }

  function patchRow(key, patch) {
    setRows((prev) => prev.map((r) => (r.key === key ? { ...r, ...patch } : r)))
  }

  function addSetForExercise(exerciseId) {
    setRows((prev) => {
      const same = prev.filter((r) => r.exercise_id === exerciseId)
      const last = same[same.length - 1]
      if (!last) return prev
      let lastIdx = -1
      prev.forEach((r, i) => {
        if (r.exercise_id === exerciseId) lastIdx = i
      })
      const row = {
        key: `${exerciseId}-${same.length + 1}-${Date.now()}`,
        exercise_id: last.exercise_id,
        exercise_name: last.exercise_name,
        image: last.image,
        gif_url: last.gif_url,
        weight: last.weight,
        reps: last.reps,
        done: false,
        set_number: same.length + 1,
      }
      const next = [...prev]
      next.splice(lastIdx + 1, 0, row)
      return next
    })
  }

  function removeRow(key) {
    setRows((prev) => prev.filter((r) => r.key !== key))
  }

  const grouped = useMemo(() => {
    const order = []
    const map = new Map()
    for (const r of rows) {
      if (!map.has(r.exercise_id)) {
        map.set(r.exercise_id, [])
        order.push(r.exercise_id)
      }
      map.get(r.exercise_id).push(r)
    }
    return order.map((id) => ({ id, rows: map.get(id), name: map.get(id)[0].exercise_name, image: map.get(id)[0].image || map.get(id)[0].gif_url }))
  }, [rows])

  async function finish() {
    const done = rows.filter((r) => r.done)
    if (!done.length) {
      setError('Check off at least one set')
      return
    }
    for (const r of done) {
      const w = Number(r.weight)
      const reps = Number(r.reps)
      if (!Number.isFinite(w) || w < 0 || !Number.isFinite(reps) || reps <= 0) {
        setError(`Enter kg and reps for ${r.exercise_name} set ${r.set_number}`)
        return
      }
    }
    setBusy(true)
    const ended = Date.now()
    const started = startRef.current || ended
    const volume = done.reduce((a, r) => a + Number(r.weight) * Number(r.reps), 0)
    try {
      const workout = await api('/api/workouts', {
        method: 'POST',
        body: JSON.stringify({
          notes: sessionTitle,
          started_at: new Date(started).toISOString(),
          ended_at: new Date(ended).toISOString(),
          sets: done.map((r) => ({
            exercise_id: r.exercise_id,
            weight_kg: Number(r.weight),
            reps: Number(r.reps),
            set_number: r.set_number,
          })),
        }),
      })
      if (workout.new_achievements?.length) setAchievements(workout.new_achievements)
      let day = null
      try {
        day = await api('/api/stats/daily-link')
      } catch {
        /* optional */
      }
      setSummary({
        durationMs: ended - started,
        volume,
        setCount: done.length,
        exercises: [...new Set(done.map((s) => s.exercise_name))],
        workout,
        day,
      })
      setRows([])
      setRunning(false)
      startRef.current = null
      setView('hub')
      setQ('')
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  const elapsed = running && startRef.current ? Date.now() - startRef.current : 0
  void tick

  // --- Builder ---
  if (view === 'builder') {
    return (
      <div>
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => setView('hub')}>
          ← Back
        </button>
        <h1 className="page-title">{editId ? 'Edit routine' : 'New routine'}</h1>
        <p className="page-sub">Up to 3 routines. Add every exercise you want before you train.</p>
        <form className="panel" onSubmit={saveRoutine}>
          {error && <div className="error">{error}</div>}
          <div className="field">
            <label>Routine name</label>
            <input value={routineName} onChange={(e) => setRoutineName(e.target.value)} placeholder="Push / Legs / Pull" />
          </div>
          <div className="field">
            <label>Add exercise</label>
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search catalog…" />
          </div>
          {results.map((ex) => (
            <button key={ex.id} type="button" className="list-row result-row" onClick={() => addExerciseToRoutine(ex)}>
              <img className="thumb" src={mediaUrl(ex.image)} alt="" />
              <div style={{ textAlign: 'left' }}>
                <strong>{ex.name}</strong>
                <div style={{ color: 'var(--muted)', fontSize: '0.8rem' }}>
                  {ex.body_part} · {ex.equipment}
                </div>
              </div>
            </button>
          ))}
          {picked.map((p, i) => (
            <div className="list-row" key={p.id}>
              <img className="thumb" src={mediaUrl(p.image || p.gif_url)} alt="" />
              <div style={{ flex: 1 }}>
                <strong>{p.name}</strong>
                <div style={{ color: 'var(--muted)', fontSize: '0.8rem' }}>Default {p.default_sets || 3} sets</div>
              </div>
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={() => setPicked((prev) => prev.filter((_, j) => j !== i))}
              >
                Remove
              </button>
            </div>
          ))}
          <button className="btn btn-primary btn-block" type="submit" disabled={busy}>
            {busy ? 'Saving…' : 'Save routine'}
          </button>
        </form>
      </div>
    )
  }

  // --- Session ---
  if (view === 'session') {
    return (
      <div>
        <div className="session-timer panel">
          <div className="session-timer-row">
            <div>
              <div className="label">{sessionTitle}</div>
              <div className="clock">{formatElapsed(elapsed)}</div>
            </div>
            <span className="badge badge-accent">Live</span>
          </div>
        </div>

        <div className="panel">
          <div className="field">
            <label>Add exercise</label>
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search…" />
          </div>
          {results.map((ex) => (
            <button key={ex.id} type="button" className="list-row result-row" onClick={() => addExerciseToSession(ex)}>
              <img className="thumb" src={mediaUrl(ex.image)} alt="" />
              <div style={{ textAlign: 'left' }}>
                <strong>{ex.name}</strong>
              </div>
            </button>
          ))}
        </div>

        {!grouped.length && <p className="empty">Add an exercise to start logging sets.</p>}

        {grouped.map((g) => (
          <div className="panel set-sheet" key={g.id}>
            <div className="set-sheet-head">
              <img className="thumb" src={mediaUrl(g.image)} alt="" />
              <strong>{g.name}</strong>
            </div>
            <div className="set-grid-head">
              <span>SET</span>
              <span>KG</span>
              <span>REPS</span>
              <span>✓</span>
            </div>
            {g.rows.map((r) => (
              <div className={`set-grid-row ${r.done ? 'done' : ''}`} key={r.key}>
                <button type="button" className="set-num" onClick={() => removeRow(r.key)} title="Remove set">
                  {r.set_number}
                </button>
                <input
                  inputMode="decimal"
                  value={r.weight}
                  onChange={onNumberChange((v) => patchRow(r.key, { weight: v }))}
                  placeholder="0"
                  aria-label="kg"
                />
                <input
                  inputMode="numeric"
                  value={r.reps}
                  onChange={onNumberChange((v) => patchRow(r.key, { reps: v }))}
                  placeholder="0"
                  aria-label="reps"
                />
                <button
                  type="button"
                  className={`set-check ${r.done ? 'on' : ''}`}
                  onClick={() => patchRow(r.key, { done: !r.done })}
                  aria-label="Complete set"
                >
                  {r.done ? '✓' : ''}
                </button>
              </div>
            ))}
            <button type="button" className="btn btn-ghost btn-block btn-sm" onClick={() => addSetForExercise(g.id)}>
              + Add set
            </button>
          </div>
        ))}

        {error && <div className="error">{error}</div>}
        <button type="button" className="btn btn-primary btn-block" disabled={busy} onClick={finish}>
          {busy ? 'Saving…' : 'Finish workout'}
        </button>
        <button
          type="button"
          className="btn btn-ghost btn-block"
          style={{ marginTop: '0.5rem' }}
          onClick={() => {
            if (!confirm('Discard this session?')) return
            setRunning(false)
            startRef.current = null
            setRows([])
            setView('hub')
          }}
        >
          Cancel
        </button>
        <PRCelebration achievements={achievements} onClose={() => setAchievements(null)} />
      </div>
    )
  }

  // --- Hub ---
  return (
    <div>
      <h1 className="page-title">Workout</h1>
      <p className="page-sub">Start empty or run one of your 3 routines.</p>

      {summary && (
        <div className="panel summary-card">
          <h3>Workout summary</h3>
          <div className="grid-stats" style={{ marginBottom: '0.75rem' }}>
            <div className="stat">
              <div className="label">Duration</div>
              <div className="value" style={{ fontSize: '1.5rem' }}>{formatElapsed(summary.durationMs)}</div>
            </div>
            <div className="stat">
              <div className="label">Volume</div>
              <div className="value" style={{ fontSize: '1.5rem' }}>{Math.round(summary.volume)} kg</div>
            </div>
            <div className="stat">
              <div className="label">Sets</div>
              <div className="value" style={{ fontSize: '1.5rem' }}>{summary.setCount}</div>
            </div>
          </div>
          {summary.day && (
            <p style={{ color: 'var(--muted)', fontSize: '0.9rem' }}>{summary.day.summary}</p>
          )}
          <button type="button" className="btn btn-ghost" onClick={() => setSummary(null)}>
            Close
          </button>
        </div>
      )}

      {error && <div className="error">{error}</div>}

      <button type="button" className="btn btn-primary btn-block start-empty" onClick={startEmpty}>
        + Start Empty Workout
      </button>

      <div className="routines-head">
        <h2>Routines</h2>
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => openBuilder()} disabled={routines.length >= 3}>
          + New
        </button>
      </div>

      <div className="routine-actions">
        <button type="button" className="btn btn-ghost routine-action" onClick={() => openBuilder()}>
          New Routine
        </button>
        <Link className="btn btn-ghost routine-action" to="/app/library">
          Explore
        </Link>
      </div>

      <p className="my-routines-label">My Routines ({routines.length}/3)</p>

      {!routines.length && <p className="empty">No routines yet — create up to 3.</p>}

      {routines.map((r) => (
        <div className="routine-card" key={r.id}>
          <div className="routine-card-top">
            <h3>{r.name}</h3>
            <div className="routine-menu">
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => openBuilder(r)}>
                Edit
              </button>
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => deleteRoutine(r.id)}>
                Delete
              </button>
            </div>
          </div>
          <p className="routine-ex-preview">
            {r.exercises.map((e) => e.exercise_name).join(', ') || 'No exercises'}
          </p>
          <button type="button" className="btn btn-primary btn-block" onClick={() => startRoutine(r)}>
            Start Routine
          </button>
        </div>
      ))}

      <PRCelebration achievements={achievements} onClose={() => setAchievements(null)} />
    </div>
  )
}
