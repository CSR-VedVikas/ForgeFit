export default function Privacy() {
  return (
    <div className="auth-page" style={{ alignItems: 'start', paddingTop: '2rem' }}>
      <article className="auth-card" style={{ width: 'min(720px, 100%)' }}>
        <h1>Privacy & media terms</h1>
        <p className="sub">ForgeFit — last updated October 2026</p>

        <h3>Your data</h3>
        <p>
          Account email, profile metrics, workouts, food logs, and achievements are stored in the app database
          for your account only. Passwords are hashed (bcrypt).
        </p>
        <p>
          Signing in creates two credentials. A short-lived access token (15 minutes) is kept in your browser's
          localStorage. A longer-lived session cookie (up to 14 days) is marked httpOnly, so page scripts cannot
          read it; it is used only to renew the access token. Signing out revokes the session on the server and
          deletes both. Changing or resetting your password signs out every device.
        </p>
        <p>
          Your device's time zone is sent with each request so that daily totals, streaks, and weekly challenges
          follow your local day. It is not stored.
        </p>

        <h3>Third-party APIs</h3>
        <p>
          Text you type into Smart Log is sent to OpenAI to split it into foods and exercises. Food names (not
          your account details) are looked up in USDA FoodData Central and Open Food Facts; barcodes are looked
          up in the same two databases. Cardio descriptions, with your weight, height, age and gender, are sent
          to the 100 Days of Python nutrition API to estimate calories burned. Do not enter sensitive personal
          data in Smart Log.
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
