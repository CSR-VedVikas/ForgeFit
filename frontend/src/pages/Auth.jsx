import { useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { useAuth } from '../auth'

export default function AuthPage({ mode }) {
  const { user, login, register } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  if (user) return <Navigate to="/app" replace />

  async function onSubmit(e) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      if (mode === 'register') await register(email, password, displayName)
      else await login(email, password)
    } catch (err) {
      setError(err.message || 'Auth failed')
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
        <h1>{mode === 'register' ? 'Join the forge' : 'Welcome back'}</h1>
        <p className="sub">
          {mode === 'register' ? 'Create your account to track workouts & nutrition.' : 'Sign in to continue training.'}
        </p>
        {error && <div className="error">{error}</div>}
        {mode === 'register' && (
          <div className="field">
            <label>Display name</label>
            <input value={displayName} onChange={(e) => setDisplayName(e.target.value)} placeholder="Athlete" />
          </div>
        )}
        <div className="field">
          <label>Email</label>
          <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        <div className="field">
          <label>Password</label>
          <input type="password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} />
        </div>
        <button className="btn btn-primary btn-block" disabled={busy} type="submit">
          {busy ? '…' : mode === 'register' ? 'Create account' : 'Sign in'}
        </button>
        {mode === 'login' && (
          <p style={{ marginTop: '0.75rem', color: 'var(--muted)', fontSize: '0.9rem' }}>
            <Link to="/forgot-password">Forgot password?</Link>
          </p>
        )}
        <p style={{ marginTop: '1rem', color: 'var(--muted)', fontSize: '0.9rem' }}>
          {mode === 'register' ? (
            <>
              Already forging? <Link to="/login">Sign in</Link>
            </>
          ) : (
            <>
              New here? <Link to="/register">Create account</Link>
            </>
          )}
        </p>
      </form>
    </div>
  )
}
