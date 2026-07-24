export default function Privacy() {
  return (
    <div className="auth-page" style={{ alignItems: 'start', paddingTop: '2rem' }}>
      <article className="auth-card" style={{ width: 'min(720px, 100%)' }}>
        <h1>Privacy & media terms</h1>
        <p className="sub">ForgeFit — last updated July 2026</p>

        <h3>Your data</h3>
        <p>
          Account email, profile metrics, workouts, food logs, and achievements are stored in the app database
          for your account only. Passwords are hashed (bcrypt). JWT tokens are stored in your browser
          (localStorage) until you sign out.
        </p>

        <h3>Third-party APIs</h3>
        <p>
          Natural-language food and calorie estimates may be sent to the Nutrition API provider. Workout text
          may be sent to OpenAI (or your configured NLP provider) for parsing. Do not enter sensitive personal
          data in NLP fields.
        </p>

        <h3>Exercise media</h3>
        <p>
          Exercise thumbnails and form GIFs are ©{" "}
          <a href="https://gymvisual.com/" target="_blank" rel="noreferrer">
            Gym visual
          </a>
          , redistributed with the exercises dataset under its license terms. Attribution is shown on exercise
          detail screens. Obtain your own media license from Gym visual before commercial redistribution of the
          animations.
        </p>

        <h3>Contact</h3>
        <p>For deletion requests or questions, contact the operator hosting this ForgeFit instance.</p>

        <a className="btn btn-ghost" href="/">
          Back
        </a>
      </article>
    </div>
  )
}
