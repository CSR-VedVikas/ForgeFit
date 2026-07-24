import { useEffect, useState } from 'react'

export default function RestTimer({ seconds = 90, onDone, active }) {
  const [left, setLeft] = useState(seconds)

  useEffect(() => {
    if (!active) return
    setLeft(seconds)
  }, [active, seconds])

  useEffect(() => {
    if (!active) return
    if (left <= 0) {
      try {
        navigator.vibrate?.(200)
      } catch {
        /* ignore */
      }
      onDone?.()
      return
    }
    const t = setTimeout(() => setLeft((x) => x - 1), 1000)
    return () => clearTimeout(t)
  }, [left, active, onDone])

  if (!active) return null
  const m = Math.floor(left / 60)
  const s = String(left % 60).padStart(2, '0')
  return (
    <div className={`rest-timer ${left === 0 ? 'done' : ''}`}>
      <div className="label" style={{ color: 'var(--muted)', marginBottom: '0.25rem' }}>
        Rest
      </div>
      <div className="clock">
        {m}:{s}
      </div>
      <button type="button" className="btn btn-ghost btn-sm" onClick={() => setLeft(0)} style={{ marginTop: '0.75rem' }}>
        Skip rest
      </button>
    </div>
  )
}
