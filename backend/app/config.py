from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_api_key: str = ""
    nutrition_app_id: str = ""
    nutrition_app_key: str = ""
    nutrition_api_base_url: str = "https://app.100daysofpython.dev/services/nutrition/v2"
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_minutes: int = 60 * 24 * 14
    exercises_json_path: str = "../exercises-dataset-main/data/exercises.json"
    media_root: str = "../exercises-dataset-main"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    # Allow LAN phones in development (Vite host)
    cors_origin_regex: str = r"https?://(localhost|127\.0\.0\.1|192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}):(5173|4173|8080)"
    database_url: str = "sqlite:///./forgefit_clean.db"
    match_confidence_threshold: float = 0.75
    environment: str = "development"  # development | production
    sentry_dsn: str = ""
    enable_docs: bool = True
    rate_limit_auth: str = "10/minute"
    rate_limit_nlp: str = "20/minute"
    max_nlp_chars: int = 500

    class Config:
        env_file = ".env"
        extra = "ignore"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
