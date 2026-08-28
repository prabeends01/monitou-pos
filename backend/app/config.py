from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Postgres-only — docker-compose exposes it on host port 5433 (see
    # docker-compose.yml). No SQLite fallback for dev; `docker compose up`
    # or a reachable Postgres is required. (pytest still uses an in-memory
    # SQLite fixture for fast, isolated tests — that's test infra, not "the"
    # application database.)
    database_url: str = "postgresql+psycopg://monitou:monitou@localhost:5433/monitou"
    jwt_secret_key: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 12

    # Subscription lifecycle (CLAUDE.md Section 11.8) — "architecture should
    # allow a configurable grace period," so these are settings, not
    # constants baked into services/subscription_lifecycle.py.
    subscription_expiring_window_days: int = 30  # ACTIVE -> EXPIRING starts this many days before renewal_date
    subscription_grace_period_days: int = 15  # EXPIRED -> GRACE_PERIOD lasts this many days past renewal_date


settings = Settings()
