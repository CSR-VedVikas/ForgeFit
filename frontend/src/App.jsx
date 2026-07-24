import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './auth'
import Landing from './pages/Landing'
import AuthPage from './pages/Auth'
import Dashboard from './pages/Dashboard'
import SmartLog from './pages/SmartLog'
import LiveWorkout from './pages/LiveWorkout'
import Library from './pages/Library'
import History from './pages/History'
import Heatmap from './pages/Heatmap'
import Profile from './pages/Profile'
import Privacy from './pages/Privacy'
import ForgotPassword from './pages/ForgotPassword'
import ResetPassword from './pages/ResetPassword'
import AppShell from './components/AppShell'

function Private({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="boot">Loading ForgeFit…</div>
  if (!user) return <Navigate to="/login" replace />
  return children
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/privacy" element={<Privacy />} />
      <Route path="/login" element={<AuthPage mode="login" />} />
      <Route path="/register" element={<AuthPage mode="register" />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/reset-password" element={<ResetPassword />} />
      <Route
        path="/app"
        element={
          <Private>
            <AppShell />
          </Private>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="log" element={<SmartLog />} />
        <Route path="live" element={<LiveWorkout />} />
        <Route path="library" element={<Library />} />
        <Route path="history" element={<History />} />
        <Route path="heatmap" element={<Heatmap />} />
        <Route path="profile" element={<Profile />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
