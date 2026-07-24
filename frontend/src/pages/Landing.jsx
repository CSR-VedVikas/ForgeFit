import { Link } from 'react-router-dom'
import { useAuth } from '../auth'
import QuoteRotator from '../components/QuoteRotator'

export default function Landing() {
  const { user } = useAuth()
  return (
    <div className="landing">
      <nav className="landing-nav">
        <span className="brand">FORGEFIT</span>
        <Link to={user ? '/app' : '/login'} className="btn btn-ghost btn-sm">
          {user ? 'Open app' : 'Sign in'}
        </Link>
      </nav>

      <section className="landing-hero">
        <p className="hero-eyebrow">Iron · Intent · Progress</p>
        <h1 className="brand-hero">
          <span className="brand-hero-line">FORGE</span>
          <span className="brand-hero-line accent">FIT</span>
        </h1>
        <div className="hero-rule" aria-hidden="true" />
        <h2 className="hero-tagline">Train harder. Track cleaner. Break records.</h2>
        <p className="lead">
          Log workouts and meals in plain English. Form GIFs, volume, and every PR — in one forge.
        </p>
        <div className="cta-row">
          <Link to={user ? '/app' : '/register'} className="btn btn-primary">
            {user ? 'Enter the forge' : 'Start forging'}
          </Link>
          <Link to="/login" className="btn btn-ghost">
            I have an account
          </Link>
        </div>
        <QuoteRotator />
        <p className="hero-privacy">
          <a href="/privacy">Privacy & media terms</a>
        </p>
      </section>
    </div>
  )
}
