import { useEffect, useState } from 'react'
import { api, mediaUrl } from '../api'

export default function History() {
  const [workouts, setWorkouts] = useState([])

  useEffect(() => {
    api('/api/workouts').then(setWorkouts).catch(() => {})
  }, [])

  return (
    <div>
      <h1 className="page-title">History</h1>
      <p className="page-sub">Past sessions — PR sets glow with badges.</p>

      {!workouts.length && <p className="empty">No workouts yet.</p>}

      {workouts.map((w) => (
        <div className="panel" key={w.id}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.5rem', flexWrap: 'wrap' }}>
            <strong>{new Date(w.started_at).toLocaleString()}</strong>
            <span style={{ color: 'var(--accent)' }}>{Math.round(w.total_volume)} kg · {Math.round(w.calories_burned)} kcal</span>
          </div>
          {w.sets.map((s) => (
            <div className="list-row" key={s.id}>
              <img className="thumb" src={mediaUrl(s.image || s.gif_url)} alt="" />
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center', flexWrap: 'wrap' }}>
                  <strong>{s.exercise_name}</strong>
                  {s.is_pr &&
                    (s.pr_types || ['pr']).map((t) => (
                      <span className="badge" key={t}>
                        {t === 'max_weight' ? '🏆 weight' : t === 'max_volume' ? '⚡ volume' : t === 'max_reps' ? '🔥 reps' : 'PR'}
                      </span>
                    ))}
                </div>
                <div style={{ color: 'var(--muted)', fontSize: '0.85rem' }}>
                  Set {s.set_number}: {s.weight_kg} kg × {s.reps} = {s.volume} kg
                </div>
              </div>
            </div>
          ))}
        </div>
      ))}
    </div>
  )
}
