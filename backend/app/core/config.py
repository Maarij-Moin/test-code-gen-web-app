"""Application configuration loaded from environment variables."""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized application settings.

    Values can be overridden via environment variables or a local .env file.
    """

    # Project metadata used in logs and OpenAPI docs.
    PROJECT_NAME: str = "Automated Web App"

    # API base prefix for versioned routes.
    API_V1_STR: str = "/api/v1"

    # Filesystem base directory for persisted Chroma collections.
    CHROMA_BASE_DIR: str = Field(
        default="./chroma_polyglot_storage",
        validation_alias="CHROMA_DIR",
    )

    # Base directory where repositories are cloned locally.
    REPO_BASE_DIR: str = "./repo"

    # Embedding model identifier for vectorstore operations.
    EMBEDDING_MODEL_NAME: str = Field(
        default="BAAI/bge-base-en-v1.5",
        validation_alias="MODEL_NAME",
    )

    # Hostname or IP address for the FastAPI server.
    HOST: str = "0.0.0.0"

    # Port for the FastAPI server.
    PORT: int = 8000

    # PostgreSQL connection string (async).
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_test_db"

    # Redis connection string for cache and Celery.
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT configuration for user authentication.
    JWT_SECRET_KEY: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60

    # GitHub webhook secret for signature validation.
    GITHUB_WEBHOOK_SECRET: str = ""

    # Celery broker/backend configuration.
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    # Enable debug mode and verbose logging when true.
    DEBUG: bool = False

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug_mode(cls, value):
        if isinstance(value, str) and value.strip().lower() in {"release", "prod", "production"}:
            return False
        return value

    # Comma-separated CORS origins in .env, defaults to local dev origins.
    ALLOWED_ORIGINS: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )

    # AWS deployment placeholders (future use: IAM, S3, ECS, etc.).
    AWS_REGION: str = "us-east-1"
    AWS_S3_BUCKET: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


# Singleton settings instance used across the app.
settings = Settings()
