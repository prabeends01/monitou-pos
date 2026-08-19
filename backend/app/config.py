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


settings = Settings()
