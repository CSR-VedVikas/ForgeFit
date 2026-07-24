import { NavLink, Outlet, Link } from 'react-router-dom'
import { useAuth } from '../auth'

export default function AppShell() {
  const { user, logout } = useAuth()
  return (
    <div className="shell">
      <header className="shell-top">
        <Link to="/app" className="brand">
          FORGEFIT
        </Link>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <span style={{ color: 'var(--muted)', fontSize: '0.85rem' }}>{user?.display_name}</span>
          <button type="button" className="btn btn-ghost btn-sm" onClick={logout}>
            Log Out
          </button>
        </div>
      </header>
      <main className="shell-main">
        <Outlet />
      </main>
      <nav className="bottom-nav">
        <NavLink to="/app" end>
          <span className="nav-ico">◈</span>
          Home
        </NavLink>
        <NavLink to="/app/log">
          <span className="nav-ico">✦</span>
          Log
        </NavLink>
        <NavLink to="/app/live">
          <span className="nav-ico">▶</span>
          Live
        </NavLink>
        <NavLink to="/app/library">
          <span className="nav-ico">▣</span>
          Exercises
        </NavLink>
        <NavLink to="/app/profile">
          <span className="nav-ico">◎</span>
          Profile
        </NavLink>
      </nav>
    </div>
  )
}
