from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# The value shipped in .env.example. Treated as "unset" in production.
DEV_JWT_SECRET = "dev-secret-change-me"
_PLACEHOLDER_SECRETS = {
    DEV_JWT_SECRET,
    "change-me-to-a-long-random-string",
    "changeme",
    "secret",
}

# Development convenience: let a phone on the same Wi-Fi reach the Vite host.
# Never applied in production — see effective_cors_origin_regex.
LAN_DEV_ORIGIN_REGEX = (
    r"https?://(localhost|127\.0\.0\.1"
    r"|192\.168\.\d{1,3}\.\d{1,3}"
    r"|10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    r"|172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}):(5173|4173|8080)"
)


class Settings(BaseSettings):
    openai_api_key: str = ""
    nutrition_app_id: str = ""
    nutrition_app_key: str = ""
    nutrition_api_base_url: str = "https://app.100daysofpython.dev/services/nutrition/v2"
    jwt_secret: str = DEV_JWT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_minutes: int = 60 * 24 * 14
    exercises_json_path: str = "../exercises-dataset-main/data/exercises.json"
    media_root: str = "../exercises-dataset-main"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    cors_origin_regex: str = LAN_DEV_ORIGIN_REGEX
    database_url: str = "sqlite:///./forgefit_clean.db"
    match_confidence_threshold: float = 0.75
    environment: str = "development"  # development | production
    sentry_dsn: str = ""
    enable_docs: bool = True
    rate_limit_auth: str = "10/minute"
    rate_limit_nlp: str = "20/minute"
    max_nlp_chars: int = 500

    # Refresh-token cookie (PR5). The refresh token is httpOnly and never
    # reaches JavaScript; only the short-lived access token does.
    refresh_cookie_name: str = "forgefit_refresh"
    refresh_cookie_path: str = "/api/auth"
    refresh_cookie_domain: str = ""
    refresh_cookie_samesite: str = "lax"  # lax | strict | none

    # Reverse-proxy awareness (PR11). Off by default: trusting
    # X-Forwarded-For when nothing strips it lets a client forge its own IP
    # and walk straight past the auth rate limit.
    behind_proxy: bool = False
    trusted_proxy_hops: int = 1

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def effective_cors_origin_regex(self) -> str | None:
        """PR3 — the LAN regex is a development affordance and must not survive
        into production, where it would make any host on a private-range
        address a credentialed origin. In production an explicit CORS_ORIGINS
        allowlist is the only way in."""
        if self.is_production:
            return None
        return self.cors_origin_regex or None

    @property
    def refresh_cookie_secure(self) -> bool:
        return self.is_production

    @property
    def uses_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @model_validator(mode="after")
    def _refuse_unsafe_production_boot(self) -> "Settings":
        """PR2 — fail loudly at startup rather than run misconfigured.

        A server that boots with the shipped dev secret signs tokens anyone
        can forge, and nothing in the logs says so. Refusing to start is the
        only failure mode that gets noticed.
        """
        if not self.is_production:
            return self

        problems: list[str] = []

        if self.jwt_secret in _PLACEHOLDER_SECRETS:
            problems.append(
                "JWT_SECRET is still a placeholder. Anyone reading this "
                "repository can mint a token for any user id."
            )
        elif len(self.jwt_secret) < 32:
            problems.append(
                f"JWT_SECRET is {len(self.jwt_secret)} characters; 32 is the "
                "minimum. Generate one with: python -c "
                '"import secrets; print(secrets.token_urlsafe(48))"'
            )

        if self.uses_sqlite:
            problems.append(
                "DATABASE_URL points at SQLite, which will not take "
                "concurrent writes across workers. Use PostgreSQL in "
                "production."
            )

        if self.enable_docs:
            problems.append("ENABLE_DOCS must be false in production.")

        if not self.cors_origin_list:
            problems.append(
                "CORS_ORIGINS is empty. Production requires an explicit "
                "origin allowlist — the development LAN regex is ignored here."
            )

        if self.refresh_cookie_samesite.lower() not in {"lax", "strict", "none"}:
            problems.append(
                "REFRESH_COOKIE_SAMESITE must be one of: lax, strict, none."
            )

        if problems:
            raise ValueError(
                "Refusing to start in production with an unsafe "
                "configuration:\n  - " + "\n  - ".join(problems)
            )

        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
