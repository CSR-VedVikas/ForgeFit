import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import WorkoutCard from '../components/WorkoutCard'

function DayLinkPanel() {
  const [day, setDay] = useState(null)
  useEffect(() => {
    api('/api/stats/daily-link').then(setDay).catch(() => {})
  }, [])
  if (!day) return null
  return (
    <div className="panel">
      <h3>Today — workout + food linked</h3>
      <p style={{ margin: '0 0 0.5rem', fontSize: '0.95rem' }}>{day.summary}</p>
      <p style={{ color: 'var(--muted)', fontSize: '0.85rem', margin: '0 0 0.75rem' }}>
        {day.workout_count} workout(s) · {day.workout_minutes} min · {Math.round(day.volume_kg)} kg volume
      </p>
      <Link className="btn btn-ghost btn-sm" to="/app/log">
        Add / link food
      </Link>
    </div>
  )
}

export default function Dashboard() {
  const [data, setData] = useState(null)
  const [workouts, setWorkouts] = useState([])
  const [err, setErr] = useState('')

  useEffect(() => {
    api('/api/stats/dashboard')
      .then(setData)
      .catch((e) => setErr(e.message))
    api('/api/workouts?limit=15')
      .then(setWorkouts)
      .catch(() => {})
  }, [])

  if (err) return <p className="error">{err}</p>
  if (!data) return <p className="empty">Loading dashboard…</p>

  const balance = data.calorie_goal - data.calories_in + data.calories_burned

  return (
    <div>
      <h1 className="page-title">Today</h1>
      <p className="page-sub">Calories, volume, streak — keep the forge hot.</p>

      <div className="grid-stats">
        <div className="stat">
          <div className="label">Calories in</div>
          <div className="value">{Math.round(data.calories_in)}</div>
        </div>
        <div className="stat">
          <div className="label">Burned</div>
          <div className="value">{Math.round(data.calories_burned)}</div>
        </div>
        <div className="stat">
          <div className="label">Volume kg</div>
          <div className="value">{Math.round(data.volume_today)}</div>
        </div>
        <div className="stat">
          <div className="label">Streak</div>
          <div className="value">{data.streak_days}d</div>
        </div>
      </div>

      <div className="panel">
        <h3>Calorie balance vs goal {data.calorie_goal}</h3>
        <p style={{ margin: '0 0 0.5rem' }}>
          Net room: <strong style={{ color: 'var(--accent)' }}>{Math.round(balance)}</strong> kcal
        </p>
        <div className="progress">
          <span style={{ width: `${Math.min(100, (data.calories_in / data.calorie_goal) * 100)}%` }} />
        </div>
      </div>

      <DayLinkPanel />

      {data.challenge && (
        <div className="panel">
          <h3>Weekly volume challenge</h3>
          <p style={{ margin: '0 0 0.5rem' }}>
            {Math.round(data.challenge.current_volume)} / {Math.round(data.challenge.target_volume)} kg
          </p>
          <div className="progress">
            <span style={{ width: `${data.challenge.progress_pct}%` }} />
          </div>
        </div>
      )}

      <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
        <Link className="btn btn-primary" to="/app/log">
          Smart log
        </Link>
        <Link className="btn btn-ghost" to="/app/live">
          Live workout
        </Link>
        <Link className="btn btn-ghost" to="/app/heatmap">
          Muscle map
        </Link>
        <Link className="btn btn-ghost" to="/app/profile">
          Profile
        </Link>
      </div>

      <div className="panel">
        <h3>Recent PRs</h3>
        {data.recent_prs?.length ? (
          data.recent_prs.map((pr, i) => (
            <div className="list-row" key={i}>
              <span className="badge">PR</span>
              <div>
                <strong>{pr.exercise_name}</strong>
                <div style={{ color: 'var(--muted)', fontSize: '0.85rem' }}>
                  {pr.record_type.replace('_', ' ')} · {pr.value}
                </div>
              </div>
            </div>
          ))
        ) : (
          <p className="empty" style={{ padding: '0.5rem' }}>
            No PRs yet — smash a set.
          </p>
        )}
      </div>

      <div className="panel">
        <h3>Achievements</h3>
        {data.recent_achievements?.length ? (
          data.recent_achievements.map((a) => (
            <div className="list-row" key={a.id}>
              <span className="badge badge-accent">{a.icon_key}</span>
              <div>
                <strong>{a.title}</strong>
                <div style={{ color: 'var(--muted)', fontSize: '0.8rem' }}>
                  {new Date(a.earned_at).toLocaleString()}
                </div>
              </div>
            </div>
          ))
        ) : (
          <p className="empty" style={{ padding: '0.5rem' }}>
            Achievements unlock as you train.
          </p>
        )}
      </div>

      <h3 className="section-label">Previous workouts</h3>
      {!workouts.length && <p className="empty">No sessions yet — hit Live to train.</p>}
      {workouts.map((w) => (
        <WorkoutCard key={w.id} workout={w} />
      ))}
    </div>
  )
}
