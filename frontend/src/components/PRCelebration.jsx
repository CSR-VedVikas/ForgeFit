const ICONS = {
  'pr-weight': '🏆',
  'pr-volume': '⚡',
  'pr-reps': '🔥',
  'first-fire': '✦',
  'first-log': '◎',
  'streak-7': '🔥',
  challenge: '🎯',
}

export default function PRCelebration({ achievements, onClose }) {
  if (!achievements?.length) return null
  const a = achievements[0]
  return (
    <div className="pr-overlay" onClick={onClose} role="dialog">
      <div className="pr-burst">
        <div className="icon">{ICONS[a.icon_key] || '🏆'}</div>
        <h2>NEW PR</h2>
        <p style={{ color: 'var(--text)', maxWidth: '28ch', margin: '0 auto 1.25rem' }}>{a.title}</p>
        {achievements.length > 1 && (
          <p style={{ color: 'var(--muted)', fontSize: '0.9rem' }}>+{achievements.length - 1} more unlocked</p>
        )}
        <button type="button" className="btn btn-primary" onClick={onClose}>
          Keep forging
        </button>
      </div>
    </div>
  )
}
