import { useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { api } from '../api'

export default function ForgotPassword() {
  const [email, setEmail] = useState('')
  const [msg, setMsg] = useState('')
  const [token, setToken] = useState('')
  const [path, setPath] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const navigate = useNavigate()

  async function onSubmit(e) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      const res = await api('/api/auth/forgot-password', {
        method: 'POST',
        body: JSON.stringify({ email }),
      })
      setMsg(res.message)
      setToken(res.reset_token || '')
      setPath(res.reset_path || '')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-page">
      <form className="auth-card" onSubmit={onSubmit}>
        <Link to="/" className="brand">
          FORGEFIT
        </Link>
        <h1>Recover password</h1>
        <p className="sub">Enter your account email. In local/dev you’ll get a reset token on this screen.</p>
        {error && <div className="error">{error}</div>}
        {msg && <p style={{ color: 'var(--accent)' }}>{msg}</p>}
        <div className="field">
          <label>Email</label>
          <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        <button className="btn btn-primary btn-block" disabled={busy} type="submit">
          {busy ? '…' : 'Send reset'}
        </button>
        {token && (
          <div className="panel" style={{ marginTop: '1rem' }}>
            <p style={{ fontSize: '0.85rem', color: 'var(--muted)' }}>Dev reset token (expires in 1 hour):</p>
            <code style={{ wordBreak: 'break-all', fontSize: '0.75rem' }}>{token}</code>
            <button
              type="button"
              className="btn btn-ghost btn-block"
              style={{ marginTop: '0.75rem' }}
              onClick={() => navigate(path || `/reset-password?token=${encodeURIComponent(token)}`)}
            >
              Continue to reset password
            </button>
          </div>
        )}
      <p style={{ marginTop: '1rem', color: 'var(--muted)', fontSize: '0.9rem' }}>
        <Link to="/login">Back to sign in</Link>
      </p>
      </form>
    </div>
  )
}
