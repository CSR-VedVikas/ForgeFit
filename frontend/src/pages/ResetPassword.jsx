import { useMemo, useState } from 'react'
import { Link, Navigate, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'

export default function ResetPassword() {
  const { user } = useAuth()
  const [params] = useSearchParams()
  const initialToken = useMemo(() => params.get('token') || '', [params])
  const [token, setToken] = useState(initialToken)
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [done, setDone] = useState(false)
  const [busy, setBusy] = useState(false)

  if (user) return <Navigate to="/app" replace />

  async function onSubmit(e) {
    e.preventDefault()
    setError('')
    if (password !== confirm) {
      setError('Passwords do not match')
      return
    }
    setBusy(true)
    try {
      await api('/api/auth/reset-password', {
        method: 'POST',
        body: JSON.stringify({ token, new_password: password }),
      })
      setDone(true)
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
        <h1>Set new password</h1>
        <p className="sub">Paste your reset token if it isn’t already filled in.</p>
        {error && <div className="error">{error}</div>}
        {done ? (
          <p style={{ color: 'var(--accent)' }}>
            Password updated. <Link to="/login">Sign in</Link>
          </p>
        ) : (
          <>
            <div className="field">
              <label>Reset token</label>
              <input required value={token} onChange={(e) => setToken(e.target.value)} />
            </div>
            <div className="field">
              <label>New password</label>
              <input type="password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} />
            </div>
            <div className="field">
              <label>Confirm password</label>
              <input type="password" required minLength={8} value={confirm} onChange={(e) => setConfirm(e.target.value)} />
            </div>
            <button className="btn btn-primary btn-block" disabled={busy} type="submit">
              {busy ? '…' : 'Update password'}
            </button>
          </>
        )}
      </form>
    </div>
  )
}
