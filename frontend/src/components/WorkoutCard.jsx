import { mediaUrl } from '../api'

function formatDuration(started, ended) {
  if (!started || !ended) return '—'
  const ms = new Date(ended) - new Date(started)
  if (ms <= 0) return '—'
  const total = Math.floor(ms / 1000)
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  if (h > 0) return `${h}h ${m}min`
  return `${m}min`
}

function groupExercises(sets) {
  const map = new Map()
  for (const s of sets || []) {
    const key = s.exercise_id || s.exercise_name
    if (!map.has(key)) {
      map.set(key, {
        name: s.exercise_name,
        image: s.image || s.gif_url,
        count: 0,
      })
    }
    map.get(key).count += 1
  }
  return [...map.values()]
}

export default function WorkoutCard({ workout }) {
  if (!workout) return null
  const prCount = (workout.sets || []).filter((s) => s.is_pr).length
  const groups = groupExercises(workout.sets)
  const title =
    workout.notes && workout.notes !== 'Live session'
      ? workout.notes
      : groups[0]?.name
        ? groups.length > 1
          ? `${groups[0].name.split(' ')[0]}…`
          : groups[0].name
        : 'Workout'
  const dateLabel = new Date(workout.started_at).toLocaleDateString(undefined, {
    weekday: 'long',
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
  const shown = groups.slice(0, 3)
  const more = groups.length - shown.length

  return (
    <article className="workout-card">
      <div className="workout-card-meta">
        <div>
          <div className="workout-card-date">{dateLabel}</div>
          <div className="workout-card-privacy">Only you</div>
        </div>
      </div>
      <h3 className="workout-card-title">{title}</h3>
      {workout.source_query ? (
        <p className="workout-card-notes">{workout.source_query}</p>
      ) : null}
      <div className="workout-card-stats">
        <div>
          <span className="muted">Time</span>
          <strong>{formatDuration(workout.started_at, workout.ended_at)}</strong>
        </div>
        <div>
          <span className="muted">Volume</span>
          <strong>{Math.round(workout.total_volume).toLocaleString()} kg</strong>
        </div>
        <div>
          <span className="muted">Records</span>
          <strong className={prCount ? 'pr-gold' : ''}>
            {prCount ? `🏆 ${prCount}` : '—'}
          </strong>
        </div>
      </div>
      <ul className="workout-card-ex">
        {shown.map((g) => (
          <li key={g.name}>
            <img className="thumb" src={mediaUrl(g.image)} alt="" />
            <span>
              {g.count} set{g.count === 1 ? '' : 's'} {g.name}
            </span>
          </li>
        ))}
      </ul>
      {more > 0 && (
        <p className="workout-card-more">See {more} more exercise{more === 1 ? '' : 's'}</p>
      )}
    </article>
  )
}
