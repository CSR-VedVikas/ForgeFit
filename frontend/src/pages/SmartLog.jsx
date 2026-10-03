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
  const [barcode, setBarcode] = useState('')

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

  /* Every food carries all its options per 100 g, so switching the match or
   * editing the grams is arithmetic here — no second lookup. */
  function scaled(opt, grams) {
    const k = (Number(grams) || 0) / 100
    return {
      calories: opt.kcal_100g * k,
      protein: opt.protein_100g * k,
      carbs: opt.carbs_100g * k,
      fat: opt.fat_100g * k,
    }
  }

  function updateFood(i, fn) {
    setDraft((d) => {
      const foods = [...d.foods]
      foods[i] = fn(foods[i])
      return { ...d, foods }
    })
  }

  function chooseOption(i, idx) {
    updateFood(i, (f) => {
      const o = f.options[idx]
      return {
        ...f,
        selected: idx,
        food_name: o.name,
        brand: o.brand,
        source: o.source,
        source_ref: o.ref,
        ...scaled(o, f.grams),
      }
    })
  }

  function setGrams(i, grams) {
    updateFood(i, (f) => ({ ...f, grams, ...(f.options?.length ? scaled(f.options[f.selected], grams) : {}) }))
  }

  function removeFood(i) {
    setDraft((d) => ({ ...d, foods: d.foods.filter((_, j) => j !== i) }))
  }

  async function addBarcode() {
    const code = barcode.replace(/\D/g, '')
    if (!code) return
    setError('')
    setBusy(true)
    try {
      const food = await api(`/api/nutrition/barcode/${code}`)
      setDraft((d) =>
        d
          ? { ...d, foods: [...(d.foods || []), food] }
          : {
              intent: 'food',
              confidence: food.confidence,
              sets: [],
              foods: [food],
              cardio: [],
              calories_burned: 0,
              warnings: [],
              raw_query: '',
            }
      )
      setBarcode('')
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  const sourceName = (src) => (src === 'off' ? 'Open Food Facts' : src === 'usda' ? 'USDA' : src)
  const showsOFF = draft?.foods?.some((f) => f.options?.some((o) => o.source === 'off'))

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
              quantity: f.grams ?? null,
              unit: f.grams ? 'g' : '',
              source: f.source || '',
              source_ref: f.source_ref || '',
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
      <p className="page-sub">
        Type a workout or meal. Foods are matched in USDA and Open Food Facts — check the match and the grams
        before saving.
      </p>

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
        <div className="filters" style={{ marginTop: '0.75rem' }}>
          <input
            inputMode="numeric"
            value={barcode}
            onChange={(e) => setBarcode(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && addBarcode()}
            placeholder="Barcode"
            aria-label="Barcode"
          />
          <button type="button" className="btn btn-ghost" disabled={busy || !barcode.trim()} onClick={addBarcode}>
            Add by barcode
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
            <div className="list-row" key={`f-${i}`} style={{ display: 'block' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.5rem' }}>
                <div style={{ minWidth: 0 }}>
                  <strong>{f.food_name}</strong>
                  {f.brand && <span style={{ color: 'var(--muted)' }}> · {f.brand}</span>}
                  <div style={{ color: 'var(--muted)', fontSize: '0.85rem' }}>
                    {Math.round(f.calories)} kcal · P{Math.round(f.protein)} C{Math.round(f.carbs)} F
                    {Math.round(f.fat)}
                    {f.source && ` · ${sourceName(f.source)}`}
                  </div>
                </div>
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  onClick={() => removeFood(i)}
                  aria-label={`Remove ${f.food_name}`}
                >
                  ✕
                </button>
              </div>
              <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem', alignItems: 'center' }}>
                {f.options?.length > 1 && (
                  <select
                    value={f.selected}
                    onChange={(e) => chooseOption(i, Number(e.target.value))}
                    style={{ flex: 1, minWidth: 0 }}
                    aria-label={`Match for ${f.query || f.food_name}`}
                  >
                    {f.options.map((o, j) => (
                      <option key={`${o.source}-${o.ref}`} value={j}>
                        {sourceName(o.source)} · {o.name}
                        {o.brand ? ` (${o.brand})` : ''} · {Math.round(o.kcal_100g)} kcal/100 g
                      </option>
                    ))}
                  </select>
                )}
                <input
                  type="number"
                  min="0"
                  value={f.grams ?? ''}
                  onChange={(e) => setGrams(i, e.target.value === '' ? null : Number(e.target.value))}
                  style={{ width: '5.5rem' }}
                  aria-label="Grams"
                  title="Grams"
                />
                <span style={{ color: 'var(--muted)' }}>g</span>
              </div>
              {f.confidence < 0.8 && (
                <div style={{ color: 'var(--muted)', fontSize: '0.8rem', marginTop: '0.35rem' }}>
                  Unsure about this match — check it before saving.
                </div>
              )}
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

          {draft.foods?.length > 0 && (
            <p style={{ color: 'var(--muted)', fontSize: '0.75rem', marginTop: '0.75rem' }}>
              Food data from{' '}
              <a href="https://fdc.nal.usda.gov/" target="_blank" rel="noreferrer">
                USDA FoodData Central
              </a>
              {showsOFF && (
                <>
                  {' '}
                  and{' '}
                  <a href="https://world.openfoodfacts.org/" target="_blank" rel="noreferrer">
                    Open Food Facts
                  </a>{' '}
                  (ODbL)
                </>
              )}
              .
            </p>
          )}

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
