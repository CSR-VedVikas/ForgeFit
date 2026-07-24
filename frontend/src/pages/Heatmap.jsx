import { useEffect, useState } from 'react'
import { api } from '../api'

export default function Heatmap() {
  const [items, setItems] = useState([])

  useEffect(() => {
    api('/api/stats/heatmap?days=7').then(setItems).catch(() => {})
  }, [])

  const max = Math.max(1, ...items.map((i) => i.set_count))

  return (
    <div>
      <h1 className="page-title">Muscle map</h1>
      <p className="page-sub">Where you forged volume this week.</p>

      <div className="panel heatmap-body">
        {!items.length && <p className="empty">Train to light up the map.</p>}
        {items
          .slice()
          .sort((a, b) => b.set_count - a.set_count)
          .map((row) => (
            <div className="heat-row" key={row.body_part}>
              <span style={{ textTransform: 'capitalize' }}>{row.body_part}</span>
              <div className="heat-bar">
                <span style={{ width: `${(row.set_count / max) * 100}%` }} />
              </div>
              <span style={{ color: 'var(--muted)', textAlign: 'right' }}>{row.set_count} sets</span>
            </div>
          ))}
      </div>
    </div>
  )
}
