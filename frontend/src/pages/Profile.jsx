import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import WorkoutCard from '../components/WorkoutCard'

function handleFromUser(user) {
  if (!user) return 'athlete'
  if (user.display_name) return user.display_name.replace(/\s+/g, '').toLowerCase().slice(0, 24)
  return (user.email || 'athlete').split('@')[0]
}

export default function Profile() {
  const { user, refresh } = useAuth()
  const [tab, setTab] = useState('hub') // hub | settings
  const [activity, setActivity] = useState(null)
  const [workouts, setWorkouts] = useState([])
  const [metric, setMetric] = useState('duration')
  const [form, setForm] = useState(null)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState('')
  const [acctMsg, setAcctMsg] = useState('')
  const [acctErr, setAcctErr] = useState('')
  const [curPass, setCurPass] = useState('')
  const [newPass, setNewPass] = useState('')
  const [emailPass, setEmailPass] = useState('')
  const [newEmail, setNewEmail] = useState('')

  useEffect(() => {
    api('/api/stats/activity?days=90').then(setActivity).catch(() => {})
    api('/api/workouts?limit=20').then(setWorkouts).catch(() => {})
    api('/api/profile').then(setForm).catch((e) => setError(e.message))
  }, [])

  useEffect(() => {
    if (user?.email) setNewEmail(user.email)
  }, [user])

  const chart = useMemo(() => {
    const days = activity?.days || []
    const last = days.slice(-12)
    const values = last.map((d) => {
      if (metric === 'volume') return d.volume
      if (metric === 'reps') return d.reps
      return d.duration_min / 60
    })
    const max = Math.max(...values, 0.001)
    return last.map((d, i) => ({
      date: d.date,
      label: d.date.slice(5),
      value: values[i],
      pct: (values[i] / max) * 100,
    }))
  }, [activity, metric])

  function patch(key, value) {
    setForm((f) => ({ ...f, [key]: value }))
    setSaved(false)
  }

  async function save(e) {
    e.preventDefault()
    setError('')
    try {
      const updated = await api('/api/profile', {
        method: 'PUT',
        body: JSON.stringify({
          display_name: form.display_name,
          gender: form.gender,
          weight_kg: Number(form.weight_kg),
          height_cm: Number(form.height_cm),
          age: Number(form.age),
          daily_calorie_goal: Number(form.daily_calorie_goal),
          rest_seconds: Number(form.rest_seconds),
        }),
      })
      setForm(updated)
      setSaved(true)
      await refresh()
    } catch (err) {
      setError(err.message)
    }
  }

  async function changePassword(e) {
    e.preventDefault()
    setAcctErr('')
    setAcctMsg('')
    try {
      const res = await api('/api/auth/password', {
        method: 'PUT',
        body: JSON.stringify({ current_password: curPass, new_password: newPass }),
      })
      setAcctMsg(res.message)
      setCurPass('')
      setNewPass('')
    } catch (err) {
      setAcctErr(err.message)
    }
  }

  async function changeEmail(e) {
    e.preventDefault()
    setAcctErr('')
    setAcctMsg('')
    try {
      await api('/api/auth/email', {
        method: 'PUT',
        body: JSON.stringify({ password: emailPass, new_email: newEmail }),
      })
      setAcctMsg('Email updated.')
      setEmailPass('')
      await refresh()
    } catch (err) {
      setAcctErr(err.message)
    }
  }

  if (tab === 'settings') {
    if (!form) return <p className="empty">Loading…</p>
    return (
      <div>
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => setTab('hub')}>
          ← Profile
        </button>
        <h1 className="page-title">Settings</h1>
        <p className="page-sub">Biometrics, email, and password.</p>

        <form className="panel" onSubmit={save}>
          {error && <div className="error">{error}</div>}
          {saved && <p style={{ color: 'var(--accent)' }}>Saved.</p>}
          <div className="field">
            <label>Display name</label>
            <input value={form.display_name || ''} onChange={(e) => patch('display_name', e.target.value)} />
          </div>
          <div className="field">
            <label>Gender</label>
            <select value={form.gender} onChange={(e) => patch('gender', e.target.value)}>
              <option value="male">Male</option>
              <option value="female">Female</option>
            </select>
          </div>
          <div className="field">
            <label>Weight (kg)</label>
            <input type="number" step="0.1" value={form.weight_kg} onChange={(e) => patch('weight_kg', e.target.value)} />
          </div>
          <div className="field">
            <label>Height (cm)</label>
            <input type="number" step="0.1" value={form.height_cm} onChange={(e) => patch('height_cm', e.target.value)} />
          </div>
          <div className="field">
            <label>Age</label>
            <input type="number" value={form.age} onChange={(e) => patch('age', e.target.value)} />
          </div>
          <div className="field">
            <label>Daily calorie goal</label>
            <input type="number" value={form.daily_calorie_goal} onChange={(e) => patch('daily_calorie_goal', e.target.value)} />
          </div>
          <button className="btn btn-primary btn-block" type="submit">
            Save profile
          </button>
        </form>

        <div className="panel">
          <h3>Account security</h3>
          <p style={{ color: 'var(--muted)', fontSize: '0.9rem' }}>Signed in as {user?.email}</p>
          {acctErr && <div className="error">{acctErr}</div>}
          {acctMsg && <p style={{ color: 'var(--accent)' }}>{acctMsg}</p>}

          <form onSubmit={changeEmail} style={{ marginBottom: '1.25rem' }}>
            <div className="field">
              <label>New email</label>
              <input type="email" required value={newEmail} onChange={(e) => setNewEmail(e.target.value)} />
            </div>
            <div className="field">
              <label>Confirm with current password</label>
              <input type="password" required value={emailPass} onChange={(e) => setEmailPass(e.target.value)} />
            </div>
            <button className="btn btn-ghost btn-block" type="submit">
              Update email
            </button>
          </form>

          <form onSubmit={changePassword}>
            <div className="field">
              <label>Current password</label>
              <input type="password" required value={curPass} onChange={(e) => setCurPass(e.target.value)} />
            </div>
            <div className="field">
              <label>New password</label>
              <input type="password" required minLength={8} value={newPass} onChange={(e) => setNewPass(e.target.value)} />
            </div>
            <button className="btn btn-ghost btn-block" type="submit">
              Change password
            </button>
          </form>
        </div>
      </div>
    )
  }

  const handle = handleFromUser(user)
  const weekHours = activity?.week_hours ?? 0

  return (
    <div className="profile-hub">
      <div className="profile-top">
        <div>
          <div className="profile-handle">@{handle}</div>
          <h1 className="profile-name">{user?.display_name || handle}</h1>
        </div>
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => setTab('settings')} aria-label="Settings">
          ⚙ Settings
        </button>
      </div>

      <div className="profile-counts">
        <div>
          <strong>{activity?.workout_count ?? 0}</strong>
          <span>Workouts</span>
        </div>
        <div>
          <strong>0</strong>
          <span>Followers</span>
        </div>
        <div>
          <strong>0</strong>
          <span>Following</span>
        </div>
      </div>

      <div className="panel activity-panel">
        <div className="activity-head">
          <h3 style={{ margin: 0 }}>{weekHours.toFixed(1)} hours this week</h3>
          <span className="muted" style={{ fontSize: '0.8rem' }}>Last 3 months</span>
        </div>
        <div className="activity-chart">
          {chart.length ? (
            chart.map((b) => (
              <div className="activity-bar-wrap" key={b.date} title={`${b.label}: ${b.value.toFixed?.(1) ?? b.value}`}>
                <div className="activity-bar" style={{ height: `${Math.max(6, b.pct)}%` }} />
                <span>{b.label.slice(3)}</span>
              </div>
            ))
          ) : (
            <p className="empty" style={{ padding: '1rem 0' }}>
              Train to fill the chart.
            </p>
          )}
        </div>
        <div className="metric-pills">
          {['duration', 'volume', 'reps'].map((m) => (
            <button
              key={m}
              type="button"
              className={`metric-pill ${metric === m ? 'on' : ''}`}
              onClick={() => setMetric(m)}
            >
              {m[0].toUpperCase() + m.slice(1)}
            </button>
          ))}
        </div>
      </div>

      <h3 className="section-label">Dashboard</h3>
      <div className="profile-dash-grid">
        <Link to="/app" className="dash-tile">
          <span>📈</span>
          Statistics
        </Link>
        <Link to="/app/library" className="dash-tile">
          <span>🏋</span>
          Exercises
        </Link>
        <button type="button" className="dash-tile" onClick={() => setTab('settings')}>
          <span>📏</span>
          Measures
        </button>
        <Link to="/app/heatmap" className="dash-tile">
          <span>🗓</span>
          Calendar
        </Link>
      </div>

      <h3 className="section-label">Workouts</h3>
      {!workouts.length && <p className="empty">No workouts yet.</p>}
      {workouts.map((w) => (
        <WorkoutCard key={w.id} workout={w} />
      ))}
    </div>
  )
}
