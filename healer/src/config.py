from typing import List, Set
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # API Configurations
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    # LLM & Embedding Settings
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_MODEL: str = "google/gemini-2.5-flash"
    
    OPENAI_API_KEY: str = ""
    EMBEDDING_MODEL: str = "text-embedding-3-small"

    # Database Settings
    AUDIT_BACKEND: str = "postgres"
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/healer"
    SQLITE_PATH: str = "./healer_audit.db"
    
    # Monitoring Integrations
    PROMETHEUS_URL: str = "http://localhost:9090"
    LOKI_URL: str = "http://localhost:3100"

    # RAG Settings
    CHROMA_DB_DIR: str = "./chroma_db"
    RUNBOOKS_DIR: str = "infra/runbooks"

    # Policy Gate Settings
    CONFIDENCE_THRESHOLD: float = 0.75
    ALLOWED_AUTO_ACTIONS: List[str] = ["RESTART_CONTAINER", "NOTIFY_ONLY"]
    REQUIRE_HUMAN_APPROVAL: bool = False

    # Docker Socket Settings
    DOCKER_HOST: str = "unix:///var/run/docker.sock"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def allowed_actions_set(self) -> Set[str]:
        return {action.upper() for action in self.ALLOWED_AUTO_ACTIONS}

    @property
    def audit_backend_name(self) -> str:
        return self.AUDIT_BACKEND.lower().strip()

settings = Settings()
