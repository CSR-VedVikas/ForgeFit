# ForgeFit

Multi-user fitness PWA for logging workouts and meals. FastAPI + SQLite/Postgres + JWT on the backend; React/Vite on the frontend. Natural-language logging splits meals into foods with OpenAI and looks each one up in USDA FoodData Central and Open Food Facts; strength sets are parsed by OpenAI (with a regex fallback) and fuzzy-matched to a local catalog with form GIFs; cardio calories come from the 100 Days of Python API.

## Features

- Register / login, profile biometrics, password reset
- Live workouts: empty session or up to 3 saved routines; kg × reps set sheet; session timer + summary
- Smart Log NLP (parse → preview → confirm), with a per-food choice of match from USDA or Open Food Facts and editable grams
- Food by barcode (Open Food Facts, USDA Branded as fallback)
- Daily workout + food link, PRs / achievements, muscle heatmap, weekly volume challenge
- Exercises library with form GIFs; privacy page; PWA offline shell
- Docker deploy; rate limits; security headers; TLS

## Stack

| Layer | Tech |
| --- | --- |
| API | FastAPI, SQLAlchemy, Alembic, JWT |
| UI | React, Vite, PWA |
| NLP | OpenAI `gpt-4o-mini` (regex fallback when unavailable) |
| Food data | USDA FoodData Central + Open Food Facts |
| Exercise calories | 100 Days of Python nutrition API |
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
| `OPENAI_API_KEY` | Smart Log parsing and food-match picking (optional; regex fallback without it) |
| `USDA_FDC_API_KEY` | Food search. Free key: https://fdc.nal.usda.gov/api-key-signup. Without it, food search uses Open Food Facts only |
| `NUTRITION_APP_ID` / `NUTRITION_APP_KEY` | Exercise calories via the 100 Days of Python portal |
| `NUTRITION_API_BASE_URL` | `https://app.100daysofpython.dev/v1/nutrition` — the provider moved there and dropped its food endpoints |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token lifetime (default 15) |
| `REFRESH_TOKEN_EXPIRE_MINUTES` | Refresh token lifetime (default 14 days) |
| `REFRESH_COOKIE_SAMESITE` | `lax` unless API and frontend are on different sites |
| `DATABASE_URL` | SQLite locally; PostgreSQL required in production |
| `CORS_ORIGINS` | Comma-separated allowlist. Required in production |
| `ENVIRONMENT` | `development` or `production` |
| `ENABLE_DOCS` | Swagger/ReDoc and `/openapi.json`. Forced off in production regardless |
| `EXPOSE_RESET_TOKEN` | Development only: return the password-reset token in the API response (there is no email delivery yet). Production refuses to start with it on |
| `BEHIND_PROXY` / `TRUSTED_PROXY_HOPS` | Read real client IPs from `X-Forwarded-For`. Only enable behind a proxy that overwrites it |
| `RATE_LIMIT_AUTH` / `RATE_LIMIT_NLP` | slowapi limits |
| `MAX_NLP_CHARS` | Cap on NLP input length |
| `SENTRY_DSN` | Optional error tracking |

Portal keys (`app_…` / `nix_live_…`) work only against the 100 Days base URL, not `trackapi.nutritionix.com`.

Open Food Facts needs no key. Its data is ODbL-licensed: the app shows "Food data from … Open Food Facts (ODbL)" wherever its results appear, and every request identifies ForgeFit in its User-Agent, as their API terms ask.

## Production readiness

The API **refuses to start** in production if any of these is true:

- `JWT_SECRET` is a placeholder or shorter than 32 characters
- `DATABASE_URL` is SQLite
- `ENABLE_DOCS` is true
- `CORS_ORIGINS` is empty
- `EXPOSE_RESET_TOKEN` is true

Failing to boot is deliberate. A server that starts with the shipped dev secret signs tokens anyone can forge, and nothing in the logs says so.

Generate a secret:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

**Still open before launch:** a restore-from-backup rehearsal.

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

## Backups

Nothing backs the database up by default. `deploy/backup.sh` does a nightly
compressed `pg_dump` with a 14-day retention window:

```bash
chmod +x deploy/backup.sh && crontab -e
```

Add: `15 3 * * * /home/ubuntu/ForgeFit/deploy/backup.sh >> ~/forgefit-backup.log 2>&1`

The restore procedure — and the rehearsal, which is still an open pre-launch
item — is documented at the bottom of that script. A backup you have never
restored is not a backup.

## Installing as an app

ForgeFit ships as a PWA. Open the site on a phone and use **Add to Home
Screen**; it launches standalone with no browser chrome. Raster icons live in
`frontend/public/icons/` and are generated by `frontend/scripts/make-icons.py`
— re-run it if the mark or palette changes.

There is no store binary. If one is wanted later, Capacitor can wrap this same
build without a frontend rewrite; that is the point at which the auth token
moves to the platform keychain.

## Media attribution

Exercise images and GIFs are from the bundled dataset and are © [Gym visual](https://gymvisual.com/). See `exercises-dataset-main/README.md` and the in-app `/privacy` page. Do not claim ownership of that media; respect Gym visual's licensing if you redistribute commercially.

Application source code in this repository is MIT-licensed (see [LICENSE](LICENSE)). Third-party media and dependencies keep their own licenses.

## License

MIT — see [LICENSE](LICENSE).
