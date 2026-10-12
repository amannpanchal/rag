"""
Application configuration using pydantic-settings.
All values are loaded from environment variables (or .env file).
"""



from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict



class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application 
    APP_NAME: str = "Sagefold API"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"         # development | staging | production
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"


    # ── Google Gemini ──────────────────────────────────────────────────────────
    GOOGLE_API_KEY: str
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_EMBEDDING_MODEL: str = "models/gemini-embedding-001"
    EMBEDDING_DIMENSION: int = 3072          # gemini-embedding-001 output dimension
    EMBEDDING_BATCH_SIZE: int = 5          # chunks per embed API call

    # ── RAG retrieval ───────────────────────────────────────────────────────────
    RETRIEVAL_TOP_K: int = 5                # default chunks to retrieve per query
    RETRIEVAL_MIN_SCORE: float = 0.63        # minimum cosine similarity score threshold
    RETRIEVAL_MAX_GAP: float = 0.05          # maximum score difference from top score to keep a candidate
    MAX_HISTORY_PAIRS: int = 3             # conversation turns kept in context window

    # ── Context window / memory ────────────────────────────────────────────────
    MODEL_CONTEXT_WINDOW: int | None = None  # override; otherwise derived from GEMINI_MODEL
    OUTPUT_TOKEN_RESERVE: int = 2048
    RETRIEVAL_TOKEN_BUDGET: int = 8000
    HISTORY_TOKEN_BUDGET: int = 4000
    MEMORY_STRATEGY: str = "summarize"      # recent_window | summarize
    SUMMARY_TRIGGER_PAIRS: int = 8

    # ── Auth / sessions ────────────────────────────────────────────────────────
    SESSION_COOKIE_NAME: str = "sagefold_session"
    SESSION_TTL_SECONDS: int = 60 * 60 * 24 * 14
    LOGIN_RATE_LIMIT_ATTEMPTS: int = 8
    LOGIN_RATE_LIMIT_WINDOW_SECONDS: int = 60

    # ── Embedding Resiliency ──────────────────────────────────────────────────
    MAX_EMBED_RETRIES: int = 5
    INITIAL_BACKOFF: float = 1.0
    MAX_BACKOFF: float = 16.0
    ENABLE_JITTER: bool = True
    MAX_CONCURRENT_EMBEDDINGS: int = 1


    # ── PostgreSQL ─
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "raguser"
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str = "ragdb"

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def postgres_dsn_sync(self) -> str:
        """Sync DSN used for health-check ping only."""
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # ── Qdrant ─────
    QDRANT_HOST: str = "qdrant"
    QDRANT_PORT: int = 6333
    QDRANT_API_KEY: str | None = None        # optional; required for Qdrant Cloud
    QDRANT_COLLECTION: str = "documents"



    @property
    def qdrant_url(self) -> str:
        host = self.QDRANT_HOST.strip()
        if host.startswith("http://") or host.startswith("https://"):
            return host
        return f"http://{host}:{self.QDRANT_PORT}"

    @property
    def cors_origin_list(self) -> list[str]:
        origins = list(self.CORS_ORIGINS or [])
        if "*" in origins and self.ENVIRONMENT != "production":
            return ["http://localhost:3000", "http://127.0.0.1:3000"]
        return [origin for origin in origins if origin != "*"] or [
            "http://localhost:3000"
        ]

    @property
    def resolved_context_window(self) -> int:
        if self.MODEL_CONTEXT_WINDOW:
            return self.MODEL_CONTEXT_WINDOW
        model = (self.GEMINI_MODEL or "").lower()
        registry = {
            "gemini-1.5-pro": 2_097_152,
            "gemini-1.5-flash": 1_048_576,
            "gemini-2.0-flash": 1_048_576,
            "gemini-2.5-flash": 1_048_576,
            "gemini-2.5-pro": 1_048_576,
            "gemini-3.5-flash": 1_048_576,
            "gemini-3-flash": 1_048_576,
        }
        for key, size in registry.items():
            if key in model:
                return size
        return 128_000

    # ── Upload limits ──────────────────────────────────────────────────────────
    MAX_UPLOAD_SIZE_MB: int = 50            # per-file size limit
    MAX_FILES_PER_UPLOAD: int = 10

    # ── PDF Chunking 
    MIN_CHUNK_SIZE: int = 500              # target minimum chars per chunk
    MAX_CHUNK_SIZE: int = 2000             # max chars before recursive split
    CHUNK_OVERLAP: int = 200               # chars shared between consecutive chunks

    # ── CORS ───────
    CORS_ORIGINS: list[str] = ["*"]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton of Settings."""
    return Settings()  # type: ignore[call-arg]
