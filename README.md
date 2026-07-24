# ForgeFit

Multi-user fitness PWA for logging workouts and meals. FastAPI + SQLite + JWT on the backend; React/Vite on the frontend. Natural-language logging routes food/cardio calories through a Nutrition API and strength sets through OpenAI (with regex fallback), then fuzzy-matches exercises to a local catalog with form GIFs.

## Features

- Register / login, profile biometrics, password reset helpers
- Live workouts: empty session or up to 3 saved routines; kg × reps set sheet; session timer + summary
- Smart Log NLP (parse → preview → confirm)
- Daily workout + food link, PRs / achievements, muscle heatmap, weekly volume challenge
- Exercises library with form GIFs; privacy page; PWA offline shell
- Docker deploy; rate limits; security headers

## Stack

| Layer | Tech |
| --- | --- |
| API | FastAPI, SQLAlchemy, Alembic, JWT |
| UI | React, Vite, PWA |
| NLP | OpenAI + Nutrition API (100 Days of Python portal) |
| Data | SQLite (Postgres-ready via `DATABASE_URL`) |
| Media | Local `exercises-dataset-main` (~1,324 exercises, 180×180 GIFs) |

## Quick start

### 1. Backend

```bash
cd backend
python -m venv .venv

# Windows
.\.venv\Scripts\activate

# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env   # Windows: copy | Unix: cp .env.example .env
# Edit .env — set JWT_SECRET and optional API keys
uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

API docs: http://127.0.0.1:8001/docs (off when `ENVIRONMENT=production`)

### 2. Frontend

```bash
cd frontend
npm install
npx vite --host 0.0.0.0 --port 5173
```

- Desktop: http://127.0.0.1:5173  
- Vite proxies `/api` and `/media` to the backend on port 8001

### 3. Mobile on the same Wi‑Fi

1. Keep backend on the PC (`127.0.0.1:8001`).
2. Start Vite with `--host 0.0.0.0` (above).
3. Find your PC LAN IP (`ipconfig` on Windows → IPv4).
4. On your phone open `http://<LAN-IP>:5173` (same Wi‑Fi; allow Node through the firewall if prompted).

For public mobile access (any network), deploy with HTTPS (see Production). GitHub alone does not host the API.

## Environment variables

Copy `backend/.env.example` → `backend/.env` (never commit `.env`).

| Variable | Purpose |
| --- | --- |
| `OPENAI_API_KEY` | Strength / intent NLP (optional; regex fallback without it) |
| `NUTRITION_APP_ID` / `NUTRITION_APP_KEY` | Food + exercise calories via 100 Days portal |
| `NUTRITION_API_BASE_URL` | Default: `https://app.100daysofpython.dev/services/nutrition/v2` |
| `JWT_SECRET` | **Required** strong random string for auth tokens |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token lifetime (default 60) |
| `EXERCISES_JSON_PATH` / `MEDIA_ROOT` | Paths to the exercise dataset |
| `DATABASE_URL` | Default SQLite file under `backend/` |
| `CORS_ORIGINS` | Comma-separated allowed origins |
| `ENVIRONMENT` | `development` or `production` |
| `ENABLE_DOCS` | Swagger/ReDoc (`false` in production) |
| `RATE_LIMIT_AUTH` / `RATE_LIMIT_NLP` | slowapi limits |
| `MAX_NLP_CHARS` | Cap on NLP input length |
| `SENTRY_DSN` | Optional error tracking |

Portal Nutrition keys (`app_…` / `nix_live_…`) must use the 100 Days base URL — not raw `trackapi.nutritionix.com`.

## Tests

```bash
cd backend
pip install -r requirements.txt
pytest -q
```

## Migrations

```bash
cd backend
alembic upgrade head
# After model changes:
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

## Production (Docker)

```bash
docker compose up --build
# App: http://localhost:8080
```

Set in the host env / `.env` (not in git):

```env
ENVIRONMENT=production
ENABLE_DOCS=false
JWT_SECRET=<long-random>
CORS_ORIGINS=https://your-domain.com
ACCESS_TOKEN_EXPIRE_MINUTES=60
OPENAI_API_KEY=...
NUTRITION_APP_ID=...
NUTRITION_APP_KEY=...
```

## Media attribution

Exercise images and GIFs are from the bundled dataset and are © [Gym visual](https://gymvisual.com/). See `exercises-dataset-main/README.md` and the in-app `/privacy` page. Do not claim ownership of that media; respect Gym visual’s licensing if you redistribute commercially.

Application source code in this repository is MIT-licensed (see [LICENSE](LICENSE)). Third-party media and dependencies keep their own licenses.

## License

MIT — see [LICENSE](LICENSE).
