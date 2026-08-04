# ForgeFit

Multi-user fitness PWA for logging workouts and meals. FastAPI + SQLite/Postgres + JWT on the backend; React/Vite on the frontend. Natural-language logging routes food/cardio calories through a Nutrition API and strength sets through OpenAI (with regex fallback), then fuzzy-matches exercises to a local catalog with form GIFs.

> **Status.** The API is production-hardened (see [Production readiness](#production-readiness)). The `design/` redesign is approved and specified but **not yet wired** to the API — the shipped frontend is still the original UI. The two are tracked separately on purpose.

## The redesign

`design/` holds the Modernist "ink" rebuild: `#171615` ground, `#ff563c` accent, Archivo, 0px radius, 2px rules. It replaces a light, clinical UI that had weak visual hierarchy and buried the one thing that matters mid-set — the next set.

The original UI is preserved at the [`v1.0-original`](../../releases/tag/v1.0-original) tag.

| | |
| --- | --- |
| Design system, tokens, lint rules | [`design/_ds/`](design/_ds/) |
| Screen prototypes | [`design/*.dc.html`](design/) |
| Frontend API contract (written, unwired) | [`design/frontend-api/`](design/frontend-api/) |
| Screen map + schema gaps | [`design/github.md`](design/github.md) |
| Remaining blockers | [`design/ForgeFit - Production Readiness.dc.html`](design/) |

See [`design/README.md`](design/README.md) for how to run the prototypes.

## Features

- Register / login, profile biometrics, password reset
- Live workouts: empty session or up to 3 saved routines; kg × reps set sheet; session timer + summary
- Smart Log NLP (parse → preview → confirm)
- Daily workout + food link, PRs / achievements, muscle heatmap, weekly volume challenge
- Exercises library with form GIFs; privacy page; PWA offline shell
- Docker deploy; rate limits; security headers; TLS

## Stack

| Layer | Tech |
| --- | --- |
| API | FastAPI, SQLAlchemy, Alembic, JWT |
| UI | React, Vite, PWA |
| NLP | OpenAI + Nutrition API (100 Days of Python portal) |
| Data | PostgreSQL in production, SQLite for local development |
| Media | Local `exercises-dataset-main` (~1,324 exercises, 180×180 GIFs) |

## Quick start

### 1. Backend

```bash
cd backend
python -m venv .venv
```

```bash
cp .env.example .env
```

Edit `.env` — at minimum set `JWT_SECRET`. Then:

```bash
pip install -r requirements.txt && alembic upgrade head && uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

`alembic upgrade head` is **required**, not optional — the app no longer creates its own tables and will refuse to serve against an out-of-date schema.

API docs: http://127.0.0.1:8001/docs (always off when `ENVIRONMENT=production`)

### 2. Frontend

```bash
cd frontend && npm install && npx vite --host 0.0.0.0 --port 5173
```

- Desktop: http://127.0.0.1:5173
- Vite proxies `/api` and `/media` to the backend on port 8001

### 3. Mobile on the same Wi-Fi

1. Keep backend on the PC (`127.0.0.1:8001`).
2. Start Vite with `--host 0.0.0.0` (above).
3. Find your PC LAN IP (`ipconfig` on Windows → IPv4).
4. On your phone open `http://<LAN-IP>:5173` (same Wi-Fi; allow Node through the firewall if prompted).

Development only. The LAN CORS pattern that makes this work is disabled in production by design.

## Authentication

Two tokens, since the refresh model landed:

| | Lifetime | Where it lives | Readable by JS |
| --- | --- | --- | --- |
| Access | 15 min | `Authorization: Bearer` | yes |
| Refresh | 14 days | httpOnly cookie, scoped `/api/auth` | no |

- `POST /api/auth/refresh` rotates: the presented token is revoked and a new one issued.
- Replaying an already-rotated token is treated as theft — **every** session for that user is revoked.
- `POST /api/auth/logout` genuinely revokes; it is unauthenticated so it still works after the access token expires.
- Changing or resetting a password signs every other device out.

## Environment variables

Copy `backend/.env.example` → `backend/.env` for development, or `deploy/production.env.example` → `deploy/production.env` for a deploy. **Never commit either.**

| Variable | Purpose |
| --- | --- |
| `JWT_SECRET` | **Required.** ≥32 chars in production; boot fails otherwise |
| `OPENAI_API_KEY` | Strength / intent NLP (optional; regex fallback without it) |
| `NUTRITION_APP_ID` / `NUTRITION_APP_KEY` | Food + exercise calories via 100 Days portal |
| `NUTRITION_API_BASE_URL` | Must end in `/v2` — pointing at `/docs` silently breaks food lookups |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token lifetime (default 15) |
| `REFRESH_TOKEN_EXPIRE_MINUTES` | Refresh token lifetime (default 14 days) |
| `REFRESH_COOKIE_SAMESITE` | `lax` unless API and frontend are on different sites |
| `DATABASE_URL` | SQLite locally; PostgreSQL required in production |
| `CORS_ORIGINS` | Comma-separated allowlist. Required in production |
| `ENVIRONMENT` | `development` or `production` |
| `ENABLE_DOCS` | Swagger/ReDoc. Forced off in production regardless |
| `BEHIND_PROXY` / `TRUSTED_PROXY_HOPS` | Read real client IPs from `X-Forwarded-For`. Only enable behind a proxy that overwrites it |
| `RATE_LIMIT_AUTH` / `RATE_LIMIT_NLP` | slowapi limits |
| `MAX_NLP_CHARS` | Cap on NLP input length |
| `SENTRY_DSN` | Optional error tracking |

Portal Nutrition keys (`app_…` / `nix_live_…`) must use the 100 Days base URL — not raw `trackapi.nutritionix.com`.

## Production readiness

The API **refuses to start** in production if any of these is true:

- `JWT_SECRET` is a placeholder or shorter than 32 characters
- `DATABASE_URL` is SQLite
- `ENABLE_DOCS` is true
- `CORS_ORIGINS` is empty

Failing to boot is deliberate. A server that starts with the shipped dev secret signs tokens anyone can forge, and nothing in the logs says so.

Generate a secret:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

**Still open before launch:** a restore-from-backup rehearsal, and the decision on whether ForgeFit ships as a web app or a store app (which changes where the token lives on mobile). Tracked in `design/ForgeFit - Production Readiness.dc.html`.

## Tests

```bash
cd backend && pytest -q
```

Must be run from `backend/` — the default `DATABASE_URL` is a relative SQLite path.

## Migrations

```bash
cd backend && alembic upgrade head
```

After model changes:

```bash
cd backend && alembic revision --autogenerate -m "describe change" && alembic upgrade head
```

Upgrading a database created before Alembic was wired in (it will have no `alembic_version` row):

```bash
cd backend && alembic stamp 0001 && alembic upgrade head
```

## Production (Docker)

```bash
cp deploy/production.env.example deploy/production.env
```

Fill in `JWT_SECRET`, `POSTGRES_PASSWORD` and `PUBLIC_ORIGIN`, put certificates in `deploy/certs/`, then:

```bash
docker compose --env-file deploy/production.env up --build -d
```

`--env-file` is required, not cosmetic: `env_file:` only populates the containers, while `${POSTGRES_PASSWORD}` in the compose file needs the value at interpolation time. Compose will refuse to start with a named error if either is missing.

The stack is Postgres + a one-shot `alembic upgrade head` + the API + nginx on 80/443. The API waits for the migration to complete. Without certificates, see the fallback block at the bottom of `deploy/nginx.conf`.

## Media attribution

Exercise images and GIFs are from the bundled dataset and are © [Gym visual](https://gymvisual.com/). See `exercises-dataset-main/README.md` and the in-app `/privacy` page. Do not claim ownership of that media; respect Gym visual's licensing if you redistribute commercially.

Application source code in this repository is MIT-licensed (see [LICENSE](LICENSE)). Third-party media and dependencies keep their own licenses.

## License

MIT — see [LICENSE](LICENSE).
