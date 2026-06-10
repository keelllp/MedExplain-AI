"""Application configuration via pydantic-settings.

All settings are read from environment variables prefixed ``MEDEXPLAIN_`` (and an
optional ``backend/.env`` file). Every setting has a safe local-dev default, so the
app boots with zero configuration on a laptop; production overrides via env.

Relative paths are resolved against the repository root (the parent of ``backend/``),
so ``data/medexplain.db`` always points at ``<repo>/data/medexplain.db`` regardless
of the process's current working directory.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> parents[3] == repository root
PROJECT_ROOT = Path(__file__).resolve().parents[3]

_DEFAULT_DEV_SECRET = "dev-only-change-me-please-use-a-long-random-secret"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MEDEXPLAIN_",
        env_file=(str(PROJECT_ROOT / "backend" / ".env"), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- environment ---
    env: str = "dev"  # dev | prod

    # --- security ---
    jwt_secret: str = _DEFAULT_DEV_SECRET
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # --- paths (relative -> resolved against PROJECT_ROOT) ---
    db_path: str = "data/medexplain.db"
    upload_dir: str = "data/uploads"
    vector_store_dir: str = "vector_store"
    knowledge_base_dir: str = "knowledge_base"

    # --- http ---
    cors_origins: str = "http://localhost:3000"
    max_upload_mb: int = 20

    # Warm-load the OCR engine at startup (production). Off by default so dev/test boot
    # stays fast and doesn't download OCR models; OCR loads lazily on first image page.
    ocr_warmup: bool = False

    # --- analysis limits / DoS guards (Phase 3) ---
    max_pages: int = 50                    # reject documents with more pages than this
    max_image_pixels: int = 40_000_000     # cap rendered/decoded pixels (pixel/decompression bombs)
    analysis_acquire_timeout: int = 600    # seconds to wait for the single analysis slot

    # --- llm providers (Phase 5) ---
    # Default generation policy assigned to NEW accounts. 'cloud' = use Gemini by default
    # (operator override of the privacy-first 'offline' default — see memory
    # gemini-free-tier-override; the free Gemini tier may train on inputs, so this is a
    # deliberate PHI trade-off). With no Gemini key configured, 'cloud' still degrades
    # safely to Ollama → offline template (no egress).
    default_llm_mode: str = "cloud"
    gemini_api_key: str = ""                  # when empty, 'cloud' mode is unavailable
    gemini_model: str = "gemini-2.5-flash"
    gemini_timeout: int = 20                   # seconds
    ollama_host: str = "http://localhost:11434"
    # Default to Gemma 3 4B: commercially licensed + strong grounding faithfulness.
    # (NOT qwen2.5 — its license is non-commercial. See memory: llm-provider-strategy.)
    ollama_model: str = "gemma3:4b"
    ollama_timeout: int = 180                  # seconds (CPU inference is slow)
    llm_temperature: float = 0.2               # low → grounded, low-drift explanations
    llm_max_output_tokens: int = 700

    # --- rag ---
    # False = deterministic canonical-name KB lookup (default; no heavy deps, exact for
    # known markers). True = ChromaDB + bge semantic retrieval (needs the 'rag' extra).
    use_semantic_rag: bool = False
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    chroma_collection: str = "medexplain_kb"

    # ------------------------------------------------------------------ #
    # Derived helpers
    # ------------------------------------------------------------------ #
    def _resolve(self, p: str) -> Path:
        path = Path(p)
        return path if path.is_absolute() else (PROJECT_ROOT / path)

    @property
    def db_file(self) -> Path:
        return self._resolve(self.db_path)

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.db_file.as_posix()}"

    @property
    def upload_path(self) -> Path:
        return self._resolve(self.upload_dir)

    @property
    def vector_store_path(self) -> Path:
        return self._resolve(self.vector_store_dir)

    @property
    def knowledge_base_path(self) -> Path:
        return self._resolve(self.knowledge_base_dir)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def gemini_available(self) -> bool:
        """Whether a Gemini key is configured at all (gates 'cloud' LLM mode)."""
        return bool(self.gemini_api_key.strip())

    @property
    def is_prod(self) -> bool:
        return self.env.lower() in ("prod", "production")

    def validate_runtime(self) -> None:
        """Fail fast on insecure production config. Called at app startup."""
        if self.is_prod and self.jwt_secret == _DEFAULT_DEV_SECRET:
            raise RuntimeError(
                "Refusing to start in prod with the default JWT secret. "
                "Set MEDEXPLAIN_JWT_SECRET to a strong random value."
            )
        # Credentials are allowed on CORS, so the origin list must be explicit (no '*').
        if "*" in self.cors_origin_list:
            raise RuntimeError(
                "CORS origins must be explicit when credentials are allowed; '*' is not permitted. "
                "Set MEDEXPLAIN_CORS_ORIGINS to specific origins."
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()


# Module-level singleton for convenient import: `from app.core.config import settings`
settings = get_settings()
