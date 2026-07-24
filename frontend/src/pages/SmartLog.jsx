import { useState } from 'react'
import { api, mediaUrl } from '../api'
import PRCelebration from '../components/PRCelebration'

export default function SmartLog() {
  const [text, setText] = useState('')
  const [draft, setDraft] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [achievements, setAchievements] = useState(null)
  const [mealType, setMealType] = useState('snack')
  const [dayLink, setDayLink] = useState(null)

  async function parse() {
    setError('')
    setBusy(true)
    setDraft(null)
    try {
      const res = await api('/api/nlp/parse', {
        method: 'POST',
        body: JSON.stringify({ text, meal_type: mealType }),
      })
      setDraft(res)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  function updateSet(i, patch) {
    setDraft((d) => {
      const sets = [...d.sets]
      sets[i] = { ...sets[i], ...patch }
      return { ...d, sets }
    })
  }

  function pickSuggestion(i, sug) {
    updateSet(i, {
      exercise_id: sug.id,
      exercise_name: sug.name,
      match_confidence: sug.score,
      needs_confirm: false,
    })
  }

  async function save() {
    if (!draft) return
    setBusy(true)
    setError('')
    try {
      const readySets = (draft.sets || []).filter((s) => s.exercise_id)
      if (readySets.length) {
        const workout = await api('/api/workouts', {
          method: 'POST',
          body: JSON.stringify({
            source_query: draft.raw_query,
            calories_burned: draft.calories_burned || 0,
            sets: readySets.map((s) => ({
              exercise_id: s.exercise_id,
              weight_kg: s.weight_kg,
              reps: s.reps,
              set_number: s.set_number,
            })),
          }),
        })
        if (workout.new_achievements?.length) setAchievements(workout.new_achievements)
      }
      if (draft.foods?.length) {
        await api('/api/nutrition/log/batch', {
          method: 'POST',
          body: JSON.stringify(
            draft.foods.map((f) => ({
              query_text: draft.raw_query,
              food_name: f.food_name,
              calories: f.calories,
              protein: f.protein,
              carbs: f.carbs,
              fat: f.fat,
              meal_type: mealType,
              source_confidence: f.confidence,
            }))
          ),
        })
      }
      if (!readySets.length && !draft.foods?.length) {
        setError('Nothing to save — confirm exercises or check parse results')
      } else {
        setText('')
        setDraft(null)
        try {
          setDayLink(await api('/api/stats/daily-link'))
        } catch {
          setDayLink(null)
        }
      }
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <h1 className="page-title">Smart Log</h1>
      <p className="page-sub">Type a workout or meal. Nutrition API + OpenAI route for highest confidence.</p>

      <div className="panel nlp-box">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder='e.g. "bench press 3x8 at 60kg then ran 20 minutes and ate 2 eggs"'
        />
        <div className="filters" style={{ marginTop: '0.75rem' }}>
          <select value={mealType} onChange={(e) => setMealType(e.target.value)}>
            <option value="breakfast">Breakfast</option>
            <option value="lunch">Lunch</option>
            <option value="dinner">Dinner</option>
            <option value="snack">Snack</option>
          </select>
          <button type="button" className="btn btn-primary" disabled={busy || !text.trim()} onClick={parse}>
            {busy ? 'Parsing…' : 'Parse'}
          </button>
        </div>
        {error && <div className="error">{error}</div>}
      </div>

      {draft && (
        <div className="panel">
          <h3>
            Preview · {draft.intent} · confidence {(draft.confidence * 100).toFixed(0)}%
          </h3>
          {draft.warnings?.length > 0 && (
            <ul className="warn-list">
              {draft.warnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          )}

          {draft.sets?.map((s, i) => (
            <div key={i} style={{ marginBottom: '0.85rem' }}>
              <div className="set-editor">
                <input
                  value={s.exercise_name}
                  onChange={(e) => updateSet(i, { exercise_name: e.target.value })}
                  title="Exercise"
                />
                <input
                  type="number"
                  value={s.weight_kg}
                  onChange={(e) => updateSet(i, { weight_kg: Number(e.target.value) })}
                  title="kg"
                />
                <input
                  type="number"
                  value={s.reps}
                  onChange={(e) => updateSet(i, { reps: Number(e.target.value) })}
                  title="reps"
                />
                <span className={s.needs_confirm ? 'badge' : 'badge badge-accent'}>
                  {(s.match_confidence * 100).toFixed(0)}%
                </span>
              </div>
              {s.needs_confirm && s.suggestions?.length > 0 && (
                <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
                  {s.suggestions.map((sug) => (
                    <button
                      key={sug.id}
                      type="button"
                      className="btn btn-ghost btn-sm"
                      onClick={() => pickSuggestion(i, sug)}
                    >
                      {sug.name}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ))}

          {draft.foods?.map((f, i) => (
            <div className="list-row" key={`f-${i}`}>
              <div>
                <strong>{f.food_name}</strong>
                <div style={{ color: 'var(--muted)', fontSize: '0.85rem' }}>
                  {Math.round(f.calories)} kcal · P{Math.round(f.protein)} C{Math.round(f.carbs)} F
                  {Math.round(f.fat)}
                </div>
              </div>
            </div>
          ))}

          {draft.cardio?.map((c, i) => (
            <div className="list-row" key={`c-${i}`}>
              <div>
                <strong>{c.name}</strong>
                <div style={{ color: 'var(--muted)', fontSize: '0.85rem' }}>
                  {c.duration_min ? `${c.duration_min} min · ` : ''}
                  {Math.round(c.calories)} kcal burned
                </div>
              </div>
            </div>
          ))}

          <button type="button" className="btn btn-primary btn-block" style={{ marginTop: '1rem' }} disabled={busy} onClick={save}>
            Confirm & save
          </button>
        </div>
      )}

      {dayLink && (
        <div className="panel day-link-box">
          <h3>Linked day summary</h3>
          <p style={{ margin: 0 }}>{dayLink.summary}</p>
        </div>
      )}

      <PRCelebration achievements={achievements} onClose={() => setAchievements(null)} />
    </div>
  )
}
