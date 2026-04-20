import os
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Central configuration for the entire application.
    Automatically reads from .env file.
    """

    # =========================
    # APP
    # =========================
    APP_NAME: str = "temporal-md-pipeline"
    ENV: str = Field(default="dev")

    # =========================
    # POSTGRES
    # =========================
    DB_HOST: str = Field(default="localhost")
    DB_PORT: int = Field(default=5432)
    DB_NAME: str = Field(default="md_pipeline")
    DB_USER: str = Field(default="user")
    DB_PASSWORD: str = Field(default="password")

    # SQLAlchemy URL
    DATABASE_URL: str | None = None

    # =========================
    # TEMPORAL
    # =========================
    TEMPORAL_HOST: str = Field(default="localhost:7233")
    TEMPORAL_TASK_QUEUE: str = Field(default="md-queue")

    # =========================
    # LLM (GGUF)
    # =========================
    LLM_MODEL_PATH: str = Field(default="./models/model.gguf")
    LLM_CTX_SIZE: int = Field(default=4096)
    LLM_THREADS: int = Field(default=4)
    LLM_GPU_LAYERS: int = Field(default=0)  # set >0 if GPU available
    LLM_MAX_TOKENS: int = Field(default=1024)
    LLM_TEMPERATURE: float = Field(default=0.2)

    # =========================
    # CHUNKING
    # =========================
    MAX_CHUNK_SIZE: int = Field(default=1200)

    # =========================
    # INTERNAL
    # =========================
    class Config:
        env_file = ".env"
        case_sensitive = True

    def build_db_url(self) -> str:
        """
        Construct DB URL if not explicitly provided.
        """
        return (
            f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    def get_database_url(self) -> str:
        """
        Returns final DB URL (explicit or constructed).
        """
        return self.DATABASE_URL or self.build_db_url()


@lru_cache()
def get_settings() -> Settings:
    """
    Cached settings instance (singleton-like).
    """
    return Settings()