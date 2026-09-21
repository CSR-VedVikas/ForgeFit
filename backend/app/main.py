from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

from .config import get_settings
from .db import SessionLocal
from .logging_config import configure_logging, SecurityHeadersMiddleware, logger
from .rate_limit import limiter
from .services.seed_exercises import seed_exercises
from .routers import auth, profile, exercises, nlp, workouts, nutrition, stats, routines, courses

settings = get_settings()
configure_logging(settings.environment)


def _assert_schema_is_current() -> None:
    """PR4 — refuse to serve against a schema Alembic has not brought up to
    head. In development this is a loud warning with the command to run; in
    production it is fatal, because serving on a half-migrated database is how
    you get silent data loss rather than an error page."""
    from alembic.config import Config as AlembicConfig
    from alembic.script import ScriptDirectory
    from alembic.runtime.migration import MigrationContext
    from .db import engine

    backend_dir = Path(__file__).resolve().parent.parent
    cfg = AlembicConfig(str(backend_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    head = ScriptDirectory.from_config(cfg).get_current_head()

    with engine.connect() as conn:
        current = MigrationContext.configure(conn).get_current_revision()

    if current == head:
        return

    message = (
        f"Database schema is at {current or 'nothing'}, expected {head}. "
        "Run: alembic upgrade head"
    )
    if settings.is_production:
        raise RuntimeError(message)
    logger.warning('"schema_out_of_date":"%s"', message)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.sentry_dsn:
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.environment,
            traces_sample_rate=0.1 if settings.is_production else 0.0,
            integrations=[FastApiIntegration()],
        )
        logger.info('"sentry":"enabled"')

    # PR4 — schema is Alembic's job alone.
    #
    # Base.metadata.create_all() used to run here. It creates missing tables
    # but never alters existing ones, so it makes migrations look unnecessary
    # right up until the first ALTER, at which point each environment quietly
    # holds a different schema. `alembic upgrade head` is now a deploy step
    # (see deploy/ and the README); this only checks it was actually run.
    _assert_schema_is_current()

    db = SessionLocal()
    try:
        count = seed_exercises(db)
        if count:
            logger.info('"seeded_exercises":%s', count)
    finally:
        db.close()
    yield


docs_url = "/docs" if (settings.enable_docs and not settings.is_production) else None
redoc_url = "/redoc" if (settings.enable_docs and not settings.is_production) else None

app = FastAPI(
    title="ForgeFit API",
    version="1.1.0",
    lifespan=lifespan,
    docs_url=docs_url,
    redoc_url=redoc_url,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(SecurityHeadersMiddleware)

# PR11 — when nginx terminates the connection, every request otherwise arrives
# from the proxy's address and slowapi buckets all users together, which makes
# the 10/minute auth limit meaningless. Only trusted when BEHIND_PROXY is set:
# honouring X-Forwarded-For unconditionally would let any client forge its own
# source address and walk past the same limit.
if settings.behind_proxy:
    from starlette.middleware.trustedhost import TrustedHostMiddleware  # noqa: F401
    from .proxy import ProxyHeadersMiddleware

    app.add_middleware(ProxyHeadersMiddleware, hops=settings.trusted_proxy_hops)

# PR3 — allow_origin_regex is development-only. settings.effective_… returns
# None in production so the LAN pattern cannot combine with allow_credentials
# to make every host on a private-range address a trusted, credentialed origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=settings.effective_cors_origin_regex,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)

app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(exercises.router)
app.include_router(nlp.router)
app.include_router(workouts.router)
app.include_router(routines.router)
app.include_router(nutrition.router)
app.include_router(stats.router)
app.include_router(courses.router)
media_root = Path(settings.media_root)
if not media_root.is_absolute():
    backend_dir = Path(__file__).resolve().parent.parent
    project_root = backend_dir.parent
    candidates = [
        (backend_dir / media_root).resolve(),
        project_root / "exercises-dataset-main",
        backend_dir / "exercises-dataset-main",
    ]
    media_root = next((c for c in candidates if c.exists()), candidates[0])
else:
    media_root = media_root.resolve()

images = media_root / "images"
videos = media_root / "videos"
if images.exists():
    app.mount("/media/images", StaticFiles(directory=str(images)), name="images")
if videos.exists():
    app.mount("/media/videos", StaticFiles(directory=str(videos)), name="videos")


@app.get("/api/health")
def health():
    return {"status": "ok", "app": "ForgeFit", "env": settings.environment}


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    logger.exception('"unhandled":"%s"', str(exc).replace('"', "'"))
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
