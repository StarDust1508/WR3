from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Push .env into os.environ at import time. Pydantic Settings reads
# .env on its own but only into its own model — that's fine for our
# FastAPI code, but the audit-engine subpackages (and any library that
# calls `os.getenv` directly: GoPlus, Etherscan, OpenRouter, Alchemy)
# wouldn't see the keys. Doing it here means a single import path
# (`from wr3_api.config import …`) primes os.environ for the whole
# process, including the in-process scan worker.
#
# `override=False` keeps real environment variables winning over .env
# values — important so `CELERY_TASK_ALWAYS_EAGER=0 uvicorn …` and
# similar one-off overrides still work as expected.
_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
if _ENV_PATH.exists():
    load_dotenv(_ENV_PATH, override=False)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    wr3_env: str = Field(default="local")
    # Native Homebrew Postgres on macOS uses peer/trust auth without password.
    # Override via env for Docker or remote DB.
    database_url: str = Field(default="postgresql+asyncpg://localhost:5432/wr3")
    redis_url: str = Field(default="redis://localhost:6379/0")

    openrouter_api_key: str = Field(default="")
    openrouter_base_url: str = Field(default="https://openrouter.ai/api/v1")
    navyai_api_key: str = Field(default="")
    navyai_base_url: str = Field(default="https://api.navy/v1")
    local_llm_url: str = Field(default="http://localhost:8000/v1")
    local_llm_model: str = Field(default="Qwen/Qwen3-Coder-30B-A3B-Instruct")
    gemini_api_key: str = Field(default="")

    etherscan_api_key: str = Field(default="")
    bscscan_api_key: str = Field(default="")
    basescan_api_key: str = Field(default="")
    arbiscan_api_key: str = Field(default="")
    alchemy_api_key: str = Field(default="")
    # GoPlus Security: optional key for higher rate limit. Public endpoint
    # works keyless at ~30 req/min which suffices for an MVP.
    goplus_api_key: str = Field(default="")

    nextauth_secret: str = Field(default="dev-secret-do-not-use-in-prod")

    telegram_bot_token: str = Field(default="")
    telegram_webhook_secret: str = Field(default="")
    # Public-facing URL of the Mini App / web (e.g. Cloudflare Workers
    # deploy). The bot uses this to link users back from chat to the
    # Mini App; if empty we fall back to the API host (which is wrong —
    # a /tg/scan/<id> URL on the API host is a 404).
    next_public_site_url: str = Field(default="")

    r2_account_id: str = Field(default="")
    r2_access_key_id: str = Field(default="")
    r2_secret_access_key: str = Field(default="")
    r2_bucket_reports: str = Field(default="wr3-reports")

    sentry_dsn: str = Field(default="")

    @property
    def is_local(self) -> bool:
        return self.wr3_env == "local"


@lru_cache
def get_settings() -> Settings:
    return Settings()
