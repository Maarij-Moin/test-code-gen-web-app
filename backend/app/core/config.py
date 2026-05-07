"""Application configuration loaded from environment variables."""

from pydantic import Field
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
    CHROMA_BASE_DIR: str = "./chroma_polyglot_storage"

    # Base directory where repositories are cloned locally.
    REPO_BASE_DIR: str = "./repo"

    # Embedding model identifier for vectorstore operations.
    EMBEDDING_MODEL_NAME: str = "BAAI/bge-base-en-v1.5"

    # Hostname or IP address for the FastAPI server.
    HOST: str = "0.0.0.0"

    # Port for the FastAPI server.
    PORT: int = 8000

    # Enable debug mode and verbose logging when true.
    DEBUG: bool = False

    # Comma-separated CORS origins in .env, defaults to local dev origins.
    ALLOWED_ORIGINS: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"]
    )

    # AWS deployment placeholders (future use: IAM, S3, ECS, etc.).
    AWS_REGION: str = "us-east-1"
    AWS_S3_BUCKET: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


# Singleton settings instance used across the app.
settings = Settings()