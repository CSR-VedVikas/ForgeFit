import { useEffect, useState } from 'react'
import { api, mediaUrl } from '../api'

export default function Library() {
  const [items, setItems] = useState([])
  const [filters, setFilters] = useState({ body_parts: [], equipment: [] })
  const [q, setQ] = useState('')
  const [bodyPart, setBodyPart] = useState('')
  const [equipment, setEquipment] = useState('')
  const [detail, setDetail] = useState(null)
  const [flipped, setFlipped] = useState(false)

  useEffect(() => {
    api('/api/exercises/meta/filters').then(setFilters).catch(() => {})
  }, [])

  useEffect(() => {
    const params = new URLSearchParams({ limit: '48' })
    if (q) params.set('q', q)
    if (bodyPart) params.set('body_part', bodyPart)
    if (equipment) params.set('equipment', equipment)
    const t = setTimeout(() => {
      api(`/api/exercises?${params}`).then(setItems).catch(() => {})
    }, 200)
    return () => clearTimeout(t)
  }, [q, bodyPart, equipment])

  async function openDetail(id) {
    const ex = await api(`/api/exercises/${id}`)
    setDetail(ex)
    setFlipped(false)
  }

  return (
    <div>
      <h1 className="page-title">Exercises</h1>
      <p className="page-sub">1,324 exercises with form GIFs and cues. Media is 180×180 from the dataset.</p>

      <div className="filters">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search" />
        <select value={bodyPart} onChange={(e) => setBodyPart(e.target.value)}>
          <option value="">Body part</option>
          {filters.body_parts?.map((b) => (
            <option key={b} value={b}>
              {b}
            </option>
          ))}
        </select>
        <select value={equipment} onChange={(e) => setEquipment(e.target.value)}>
          <option value="">Equipment</option>
          {filters.equipment?.map((b) => (
            <option key={b} value={b}>
              {b}
            </option>
          ))}
        </select>
      </div>

      <div className="exercise-grid">
        {items.map((ex) => (
          <button key={ex.id} type="button" className="ex-card" onClick={() => openDetail(ex.id)}>
            <img src={mediaUrl(ex.image)} alt={ex.name} loading="lazy" />
            <div className="meta">
              <strong>{ex.name}</strong>
              <span>{ex.target}</span>
            </div>
          </button>
        ))}
      </div>

      {detail && (
        <div className="modal-backdrop" onClick={() => setDetail(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className={`flip ${flipped ? 'flipped' : ''}`}>
              <div className="flip-inner">
                <div className="flip-face">
                  <img
                    src={mediaUrl(detail.gif_url || detail.image)}
                    alt={detail.name}
                    style={{ width: '100%', borderRadius: 12, background: '#000' }}
                  />
                  <h2 style={{ fontFamily: 'var(--font-display)', letterSpacing: '0.04em', margin: '0.75rem 0 0.25rem' }}>
                    {detail.name}
                  </h2>
                  <p style={{ color: 'var(--muted)', margin: '0 0 0.75rem', fontSize: '0.9rem' }}>
                    {detail.body_part} · {detail.equipment} · {detail.target}
                  </p>
                </div>
                <div className="flip-face flip-back">
                  <h3 style={{ marginTop: 0 }}>Form cues</h3>
                  <ol>
                    {(detail.instruction_steps_en || []).map((step, i) => (
                      <li key={i} style={{ marginBottom: '0.4rem' }}>
                        {step}
                      </li>
                    ))}
                  </ol>
                </div>
              </div>
            </div>
            <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem', flexWrap: 'wrap' }}>
              <button type="button" className="btn btn-primary" onClick={() => setFlipped((f) => !f)}>
                {flipped ? 'Show form GIF' : 'Flip to cues'}
              </button>
              <button type="button" className="btn btn-ghost" onClick={() => setDetail(null)}>
                Close
              </button>
            </div>
            <p style={{ color: 'var(--muted)', fontSize: '0.75rem', marginTop: '0.75rem' }}>{detail.attribution}</p>
          </div>
        </div>
      )}
    </div>
  )
}
