from typing import List, Set
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, model_validator
from pathlib import Path


class Settings(BaseSettings):
    # API Configurations
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    # Authentication
    HEALER_API_KEY: str = ""
    ENVIRONMENT: str = "development"
    ENABLE_DEMO_ENDPOINT: bool = False
    CORS_ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    # LLM & Embedding Settings
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_MODEL: str = "google/gemini-2.5-flash"

    OPENAI_API_KEY: str = ""
    EMBEDDING_MODEL: str = "text-embedding-3-small"

    # Database Settings
    AUDIT_BACKEND: str = "postgres"
    POSTGRES_PASSWORD: str = ""
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/healer"
    SQLITE_PATH: str = "./healer_audit.db"

    # Monitoring Integrations
    PROMETHEUS_URL: str = "http://localhost:9090"
    LOKI_URL: str = "http://localhost:3100"

    # RAG Settings
    CHROMA_DB_DIR: str = "./chroma_db"
    CHROMA_SERVER_URL: str = ""  # server mode disabled pending upstream security fixes
    RUNBOOKS_DIR: str = "infra/runbooks"

    # Policy Gate Settings
    CONFIDENCE_THRESHOLD: float = Field(default=0.75, ge=0, le=1)
    ALLOWED_AUTO_ACTIONS: List[str] = ["RESTART_CONTAINER", "NOTIFY_ONLY"]
    REQUIRE_HUMAN_APPROVAL: bool = True

    # Docker Socket Settings
    DOCKER_HOST: str = "unix:///var/run/docker.sock"
    DOCKER_ALLOWED_SERVICES: str = ""  # comma-separated allowlist; empty denies all

    # Rate Limiting (requests per minute per client IP on /webhook/alert)
    RATE_LIMIT_PER_MINUTE: int = Field(default=30, ge=1)

    # Alert Deduplication (seconds window for same alert+service)
    DEDUP_WINDOW_SECONDS: int = Field(default=60, ge=0)

    # Execution Retry
    MAX_AUTO_EXECUTION_RETRIES: int = Field(default=1, ge=0, le=3)

    # Post-Action Verification (seconds to wait before checking Prometheus)
    VERIFY_DELAY_SECONDS: int = Field(default=15, ge=0, le=60)

    # Notifications
    SLACK_WEBHOOK_URL: str = ""

    # Kubernetes Settings
    K8S_NAMESPACE: str = "default"

    # Multi-service incident correlation (seconds window for related alerts)
    CORRELATION_WINDOW_SECONDS: int = Field(default=120, ge=0)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        secrets_dir="/run/secrets" if Path("/run/secrets").is_dir() else None,
    )

    @model_validator(mode="after")
    def validate_production(self):
        if self.CHROMA_SERVER_URL:
            raise ValueError("Chroma server mode is disabled pending upstream security fixes")
        if self.ENVIRONMENT not in {"development", "production"}:
            raise ValueError("ENVIRONMENT must be development or production")
        if self.ENVIRONMENT == "production":
            if len(self.HEALER_API_KEY) < 32:
                raise ValueError("Production requires HEALER_API_KEY with at least 32 characters")
            if not self.DOCKER_ALLOWED_SERVICES.strip():
                raise ValueError("Production requires DOCKER_ALLOWED_SERVICES")
            if self.audit_backend_name != "postgres":
                raise ValueError("Production requires PostgreSQL")
            if self.ENABLE_DEMO_ENDPOINT:
                raise ValueError("Disable ENABLE_DEMO_ENDPOINT in production")
        return self

    @property
    def allowed_actions_set(self) -> Set[str]:
        return {action.upper() for action in self.ALLOWED_AUTO_ACTIONS}

    @property
    def audit_backend_name(self) -> str:
        return self.AUDIT_BACKEND.lower().strip()


settings = Settings()
