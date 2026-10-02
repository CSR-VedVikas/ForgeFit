# ForgeFit — completion prompt

Paste this into a fresh Claude Code session opened at the repo root. It is
written for an engineer or agent picking the project up cold.

---

You are completing ForgeFit, a multi-user fitness PWA: FastAPI + SQLAlchemy +
Alembic backend, React/Vite frontend, PostgreSQL in production. Repo:
https://github.com/CSR-VedVikas/ForgeFit. Read `README.md` before touching
anything, and run `git log --oneline main..HEAD` to see what is unmerged.

## State as of 2026-10-03

**Backend is production-hardened. Do not re-audit it.**

- `app/config.py` refuses a production boot on a placeholder/short
  `JWT_SECRET`, SQLite, `ENABLE_DOCS=true`, or empty `CORS_ORIGINS`.
- Auth is two-token: 15-min bearer access token + 14-day httpOnly refresh
  cookie scoped `/api/auth`, `SameSite=lax`. Rotation on refresh; replaying a
  rotated token revokes every session for that user. `POST /api/auth/logout`
  genuinely revokes. Table `refresh_tokens`, migration `0002`.
- `Base.metadata.create_all()` is gone. `alembic upgrade head` is mandatory
  and the app refuses to serve if the schema is not at head. `0001_initial`
  is a hand-written frozen baseline; head is `0003`.
- Migration `0003` added portions on food logs, water logs, weigh-in history,
  courses + enrolments, routine targets, and an idempotency key on workouts.
  19 tests in `tests/test_schema_gaps.py`.
- Compose runs Postgres 16 + a one-shot migrate service + API + nginx with
  TLS. Secrets come from gitignored `deploy/production.env`; bring it up with
  `docker compose --env-file deploy/production.env up -d --build`.
- 46 backend tests pass. Run them from `backend/`, not the repo root.
  `tests/conftest.py` resets the rate limiter per test — without it any file
  with more than ten registrations starts seeing 429s.

**PWA is installable:** raster icons, apple-touch-icon,
`apple-mobile-web-app-capable`, and a network-first service worker for
navigations. `frontend/scripts/make-icons.py` regenerates icons.

## Decisions already made — do not reopen

- **The UI is final.** The current dark design — near-black `#0a0a0b`, lime
  `#c8f542`, Bebas Neue + DM Sans — is what ships. Do not restyle it. Work in
  `frontend/src` is plumbing and features inside that design.
- **Web app / PWA, not a store app.** Token lives in an httpOnly refresh
  cookie + bearer access token. If a store binary is ever wanted, Capacitor
  wraps this build and the token moves to the platform keychain then.
- **Food data comes from two sources, both offered to the user:** USDA
  FoodData Central (generic foods, key in `USDA_FDC_API_KEY`) and Open Food
  Facts (packaged foods and barcodes, no key). OpenAI splits free text into
  items + amounts; the sources supply the numbers. The user sees and picks the
  match — never apply a lookup silently (USDA's top hit for "chicken breast
  cooked" is a breaded microwaved tender).
- `verify_password` still truncates to 72 bytes on purpose — pre-existing
  accounts hold a hash of their first 72 bytes. New passwords are capped at
  the schema. Do not "fix" this.

## What remains, in order

### 1. Frontend plumbing — blocks deploy
`frontend/src/api.js` predates the token model. Replace it with a
`frontend/src/api/` layer where every call goes through one `request()`:

- **Refresh handling — launch blocker.** On a 401, call
  `POST /api/auth/refresh` once with `credentials: 'include'`, retry, and only
  then sign out. Collapse concurrent refreshes into one promise: the server
  rotates on every call and treats a replayed token as theft. Without this,
  production users are signed out every 15 minutes.
- **Readable errors.** FastAPI 422 `detail` is an array; the sign-up screen
  currently prints it raw. One `ApiError` with a `userMessage`.
- **Logout** calls `POST /api/auth/logout` before clearing local state.
- **Optional:** an IndexedDB session queue so a set logged without signal is
  not lost; send `client_id` on `POST /api/workouts` (the server dedupes on it).

Backend, same pass: `services/openai_nlp.py` only falls back to the regex
parser when no key is set. Make it fall back on any OpenAI error too, so an
outage or empty balance never breaks Smart Log.

### 2. Food data sources
- **Exercise calories** stay on the 100 Days of Python API, which moved to
  `https://app.100daysofpython.dev/v1/nutrition` (headers `x-app-id`,
  `x-app-key`). Its food and barcode endpoints no longer exist. Update
  `nutrition_api_base_url` and drop the stale fallback bases.
- **Food:** add USDA FDC search (`/fdc/v1/foods/search`, 3,600 req/hour) and
  Open Food Facts (`/api/v2/product/{barcode}.json`; send
  `User-Agent: ForgeFit/<version> (+https://github.com/CSR-VedVikas/ForgeFit)`).
  Show **"Food data from Open Food Facts"** wherever its results appear — the
  data is ODbL-licensed and attribution is required.
- Barcode: Open Food Facts first, USDA Branded (GTIN) as fallback.

### 3. Merge to `main`
Via PR. `main` must only ever show the app as described here.

### 4. Deploy
Oracle Always Free (Ampere ARM, all images are multi-arch). Sequence: open
ports 80/443 in **both** the console security list and on-box `iptables`;
clone; fill `deploy/production.env` (including `USDA_FDC_API_KEY`); `up -d
--build backend` first so port 80 is free; certbot standalone; copy certs to
`deploy/certs/`; `up -d --build web`; `curl /api/health`. Install
`deploy/backup.sh` on cron and **rehearse a restore** — that rehearsal is a
launch gate, not a nice-to-have. Use separate production API keys from the
development ones.

### 5. Engineering report
Pending; the owner holds its brief.

## Constraints

- Match the surrounding code's comment density and idiom. Comments explain
  *why*, briefly.
- Run `pytest` from `backend/` before every commit; all must stay green.
- Never commit `.env`, `*.db`, `deploy/production.env`, `*.pem`, `*.key`, or
  `backups/`. `.gitignore` covers them; do not weaken it.
- Never put API keys in chat, commits, or logs. Verify a key by fingerprint
  and a live call, not by printing it.
- Commit messages: imperative subject, body explains why.
- Do not push to `main` directly. Branch, PR, merge.
- The exercise media is © Gym visual. Keep the attribution in `README.md`.

## Definition of done

- `frontend/src/api.js` is gone; every call goes through `frontend/src/api/`;
  a session survives past 15 minutes without re-login.
- Food search offers USDA and Open Food Facts results; barcode works; Open
  Food Facts attribution is visible; exercise calories work.
- Merged to `main` via PR.
- Live at the owner's domain over TLS; `/api/health` returns
  `"env":"production"`; a backup has been restored to a scratch database and
  its `users` row count matched production.
