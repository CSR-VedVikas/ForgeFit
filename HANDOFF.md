# ForgeFit — completion prompt

Paste this into a fresh Claude Code session opened at the repo root. It is
written for an engineer or agent picking the project up cold.

---

You are completing ForgeFit, a multi-user fitness PWA: FastAPI + SQLAlchemy +
Alembic backend, React/Vite frontend, PostgreSQL in production. Repo:
https://github.com/CSR-VedVikas/ForgeFit — work on branch `redesign`, which is
7 commits ahead of `main`. Read `README.md`, `design/README.md`,
`design/github.md`, and open `design/ForgeFit - Production Readiness.dc.html`
in a browser before touching anything.

## State as of 2026-09-21

**Backend is production-hardened. Do not re-audit it.** Commits
`e89c5ac`, `f5d994c`, `a29cfe6` on `redesign` closed blockers PR1–PR11 from
the readiness doc:

- `app/config.py` refuses a production boot on a placeholder/short
  `JWT_SECRET`, SQLite, `ENABLE_DOCS=true`, or empty `CORS_ORIGINS`.
- Auth is two-token: 15-min bearer access token + 14-day httpOnly refresh
  cookie scoped `/api/auth`, `SameSite=lax`. Rotation on refresh; replaying a
  rotated token revokes every session for that user. `POST /api/auth/logout`
  genuinely revokes. Table `refresh_tokens`, migration `0002`.
- `Base.metadata.create_all()` is gone. `alembic upgrade head` is mandatory
  and the app refuses to serve if the schema is not at head. `0001_initial`
  is a hand-written frozen baseline; head is `0003`.
- Compose runs Postgres 16 + a one-shot migrate service + API + nginx with
  TLS. Secrets come from gitignored `deploy/production.env`; bring it up with
  `docker compose --env-file deploy/production.env up -d --build`.
- 46 backend tests pass. Run them from `backend/`, not the repo root.
  `tests/conftest.py` resets the rate limiter per test — without it any
  file with more than ten registrations starts seeing 429s.

**PWA is installable** (commit `f2ec4de`): raster icons, apple-touch-icon,
`apple-mobile-web-app-capable`, and a network-first service worker for
navigations. `frontend/scripts/make-icons.py` regenerates icons.

**The redesign is approved, specified, and NOT wired.** `design/` holds the
Modernist "ink" design system, the API contract in `design/frontend-api/`
(`client.js`, `endpoints.js`, `session-queue.js`), and 2 of 9 prototypes. The
shipped frontend in `frontend/src` is still the original UI and still uses
`frontend/src/api.js`.

## Decisions already made — do not reopen

- **Web app / PWA, not a store app.** Token lives in an httpOnly refresh
  cookie + bearer access token. If a store binary is ever wanted, Capacitor
  wraps this build and the token moves to the platform keychain then.
- **One repo, not two.** The redesign is the next phase of this app.
  `v1.0-original` tags the pre-redesign UI.
- **Ink ground:** `#171615` ground, `#ff563c` accent, Archivo, 0px radius,
  2px rules, caps exercise names, Lucide tab-bar icons. The light-ground
  builds were rejected and removed.
- **Record moment is a footer slab**, not the old full-screen burst.
- **The live session is a local IndexedDB document** flushed once at finish
  via `POST /api/workouts`. There is no per-set endpoint. Records are
  authoritative only after the finish call returns.
- `verify_password` still truncates to 72 bytes on purpose — pre-existing
  accounts hold a hash of their first 72 bytes. New passwords are capped at
  the schema. Do not "fix" this.

## What remains, in order

### 0. Things only the owner can do — confirm before proceeding
- Rotate the OpenAI key, Nutritionix key, and `JWT_SECRET`. They sat in
  plaintext in a OneDrive-synced `backend/.env`. Never committed, but the
  file left the machine. Ask whether this is done; do not assume.
- Download the design export from
  https://claude.ai/design/p/07869a8a-38fe-4617-91ee-4818a886067d and run
  `python design/unpack-export.py <zip>`. It exits non-zero until all 9
  prototypes and `design/assets/ex-*.jpg` are present. The binaries cannot
  be pulled through a tool call — they get corrupted in transit. Do not try.

### 1. Merge `redesign` into `main`
Open the PR at https://github.com/CSR-VedVikas/ForgeFit/pull/new/redesign.
`main` still shows the pre-redesign README to every visitor. Merge with
`--no-ff` so the branch stays readable as history.

### 2. ~~Schema migration `0003`~~ — DONE 21 Sep 2026
Landed as `backend/alembic/versions/0003_schema_gaps.py` with 19 tests in
`tests/test_schema_gaps.py`. `design/frontend-api/endpoints.js` carries the
new routes. Kept here for the record; nothing left to do:

| Gap | Fix |
| --- | --- |
| N1 | `food_logs` gains `quantity` (float, nullable) and `unit` (string). `services/nlp_router.py` already parses `DraftFood.quantity`/`.unit` then drops them on save — stop dropping them. |
| N2 | New `water_logs` table: `user_id`, `ml`, `logged_at`. |
| N3 | New `weigh_ins` table: `user_id`, `weight_kg`, `recorded_at`. `Profile.weight_kg` becomes the latest row's value, not the source of truth. |
| N4 | New `courses` and `course_enrolments` tables. A course has `weeks`, `days_per_week`, `weekly_load_step`; an enrolment tracks `current_week`, `current_day`. Finishing a session advances it. |
| N5 | Barcode lookup: a new `nutrition_api.product_by_barcode()` hitting Nutritionix's item endpoint, separate from `natural_nutrients()`. |
| R1 | `routine_exercises` gains `target_weight_kg` and `target_reps` so the builder's prescription can persist. |
| W1 | `WorkoutCreate` gains optional `client_id` (unique per user). `POST /api/workouts` returns the existing row on a duplicate instead of inserting. `session-queue.js` already sends it. |

Note for the next migration: `0001_initial` is now hand-written, frozen text.
It was briefly built from `Base.metadata` at runtime, which drifted with the
models and would have double-created the 0003 columns on a fresh install. A
baseline must never reference a moving target.

### 3. Wire the redesign into `frontend/src` — days 5–17 in the readiness doc
Order is read-only screens, then writes, then queue-backed screens, then Fuel.
The prototypes are the spec; `design/frontend-api/endpoints.js` is the
contract and every route in it is verified against `backend/app/routers/`.

1. Move `design/frontend-api/*` to `frontend/src/api/`. Delete
   `frontend/src/api.js`. Every screen goes through `request()`; nothing else
   calls `fetch()`.
2. Call `startAutoFlush()` once from App mount; subscribe to `onAuthLost` to
   route to sign-in.
3. Rebuild each page on the ink system, one PR per screen, in this order:
   Landing/Auth/Reset (`ForgeFitEntry-Ink`) → Today → Library → Muscle map →
   You → Settings → Train + Routine builder → Live Workout + record slab
   (`LiveWorkout-Ink`) → Smart log → Fuel + portion editor + barcode →
   Courses → Privacy & data.
4. Units and plate increment live in `localStorage`, not the profile — the
   API has no field for them. Rest default and plate increment are props into
   the session sheet.
5. Every screen needs its designed state for: cold cache, unreachable
   server, expired session, queued writes, read-only past days, server
   refusals, empty ranges. The prototypes show each.
6. When the last screen lands: flip `GROUND`/`ACCENT` in
   `frontend/scripts/make-icons.py` to `#171615`/`#ff563c`, regenerate, and
   update `theme_color`/`background_color` in `manifest.json`. Not before —
   the icon must match what actually ships.

### 4. Deploy
Oracle Always Free (Ampere ARM, all images are multi-arch). Runbook is in the
session history and summarised in `README.md` → Production. Sequence: open
ports 80/443 in **both** the console security list and on-box `iptables`;
clone `-b redesign` (or `main` once merged); fill `deploy/production.env`;
`up -d --build backend` first so port 80 is free; certbot standalone; copy
certs to `deploy/certs/`; `up -d --build web`; `curl /api/health`.
Install `deploy/backup.sh` on cron and **rehearse a restore** — that
rehearsal is a launch gate, not a nice-to-have.

### 5. Engineering report — pending deliverable since 28 Jul 2026
Write `design/ForgeFit - Engineering Report.dc.html` (or `.md` if the doc
runtime is unavailable): the full project explained SDE-to-SDE, chronological,
with file names. Not a summary. It must cover:

- The starting point — the light, clinical, low-hierarchy original UI and
  the pain points that drove the redesign.
- Every design decision and why, including rejected options: ink vs light,
  caps exercise names, Lucide icons, the footer-slab record moment vs the
  full-screen burst.
- Screen-by-screen build notes for all eight screens plus landing/auth.
- Technical problems and their diagnosis: the percentage-height bug where the
  app root resolved against an auto-height wrapper (fixed with
  `position:absolute; inset:0`), and the PR panel's animation stranded by
  per-second re-renders (moved to state-driven).
- The state model: what lives where, how settings propagate into the session
  sheet.
- The security work: the July audit's 11 S-findings, then the August
  readiness pass's 11 PR-blockers, severities, and why they were ordered as
  they were.
- What remains and the open decisions the owner still holds.

## Constraints

- Match the surrounding code's comment density and idiom. The backend
  comments explain *why*, briefly; keep that.
- Run `pytest` from `backend/` before every commit. 27 must stay green and
  each schema gap gets a test.
- Never commit `.env`, `*.db`, `deploy/production.env`, `*.pem`, `*.key`,
  `design/scraps/`, `design/uploads/`, or `backups/`. `.gitignore` already
  covers them; do not weaken it.
- Commit messages: imperative subject, body explains why, end with
  `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.
- Do not push to `main` directly. Branch, PR, merge.
- The exercise media is © Gym visual. Keep the attribution in `README.md`
  and `design/README.md` intact.

## Definition of done

- `main` == `redesign`, merged via PR.
- `design/unpack-export.py` exits 0.
- ~~Migration `0003` applied; a test exists per gap N1–N5, R1, W1.~~ Done.
- Every page in `frontend/src/pages/` is on the ink system and calls the API
  only through `frontend/src/api/`. `frontend/src/api.js` is deleted.
- Icons and manifest are on the ink palette.
- The site is live at the owner's domain over TLS; `/api/health` returns
  `"env":"production"`; a backup has been restored to a scratch database and
  its `users` row count matched production.
- The engineering report exists and an engineer who has never seen the
  project could rebuild the decisions from it.
