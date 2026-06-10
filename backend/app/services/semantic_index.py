"""Optional semantic KB index — bge embeddings + a tiny numpy cosine store.

Deferred from Phase 5: ChromaDB does not build on this machine (chroma-hnswlib needs MSVC
build tools), so the semantic free-text retrieval path uses ``BAAI/bge-small-en-v1.5``
embeddings over a small on-disk numpy matrix instead. It is **off by default**
(``settings.use_semantic_rag = False``) — the chat/explanation paths use deterministic
canonical-name KB retrieval, which is exact for known markers. This module only augments
*general* free-text chat (questions that name no known biomarker) when explicitly enabled
via the ``rag`` extra (``uv sync --extra rag``) + ``MEDEXPLAIN_USE_SEMANTIC_RAG=true``.

Design parity with docs/08-rag-design.md §3: one chunk per KB ``## section``, embedded once
and persisted, re-embedded only when the corpus content hash or the index version changes.
sentence-transformers (heavy, pulls torch) is imported lazily so the default build never
needs it; if it is missing while enabled, ``search`` logs once and returns [] (chat then
falls back to its deterministic floor — never an error).
"""

from __future__ import annotations

import hashlib
import json
import threading

from app.core.config import settings
from app.core.logging import get_logger
from app.services import kb

logger = get_logger(__name__)

# Bump when the chunking strategy or embedding model changes (forces a clean re-embed).
INDEX_VERSION = 1

_lock = threading.Lock()
_state: dict | None = None  # {"matrix": np.ndarray, "chunks": list[kb.Chunk]}
_warned_missing = False


def is_enabled() -> bool:
    return settings.use_semantic_rag


def _slug(section: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in section.lower()).strip("-")


def _corpus_chunks() -> list[kb.Chunk]:
    """One chunk per (doc, ## section) — the same units the deterministic retriever cites."""
    chunks: list[kb.Chunk] = []
    for doc in kb.loaded_docs().values():
        for section, body in doc["sections"].items():
            if body.strip():
                chunks.append(kb.Chunk(body, doc["title"], section, doc["source_path"]))
    return chunks


def _content_hash(chunks: list[kb.Chunk]) -> str:
    h = hashlib.sha256()
    h.update(f"v{INDEX_VERSION}:{settings.embedding_model}".encode())
    for c in sorted(chunks, key=lambda x: (x.source_path, x.section)):
        h.update(c.source_path.encode())
        h.update(c.section.encode())
        h.update(c.text.encode())
    return h.hexdigest()


def _build(chunks):
    """Embed the corpus (lazy heavy imports). Returns an L2-normalized float32 matrix."""
    import numpy as np
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(settings.embedding_model)
    vecs = model.encode(
        [c.text for c in chunks], normalize_embeddings=True, convert_to_numpy=True
    )
    return np.asarray(vecs, dtype="float32")


def _load_or_build(chunks, content_hash):
    """Reuse the persisted matrix when its hash matches; otherwise embed + persist."""
    import numpy as np

    store = settings.vector_store_path
    matrix_path = store / "kb_vectors.npy"
    meta_path = store / "kb_meta.json"

    if matrix_path.exists() and meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if meta.get("hash") == content_hash and meta.get("count") == len(chunks):
                return np.load(matrix_path)
        except Exception:  # noqa: BLE001 — a corrupt cache just forces a rebuild
            logger.info("Semantic index cache unreadable; rebuilding")

    matrix = _build(chunks)
    try:
        store.mkdir(parents=True, exist_ok=True)
        np.save(matrix_path, matrix)
        meta_path.write_text(
            json.dumps({"hash": content_hash, "count": len(chunks)}), encoding="utf-8"
        )
    except Exception:  # noqa: BLE001 — persistence is best-effort; the in-memory index still works
        logger.info("Could not persist semantic index (continuing in-memory)")
    return matrix


def _ensure_index() -> dict | None:
    global _state, _warned_missing
    if _state is not None:
        return _state
    with _lock:
        if _state is not None:
            return _state
        chunks = _corpus_chunks()
        if not chunks:
            return None
        try:
            matrix = _load_or_build(chunks, _content_hash(chunks))
        except ImportError:
            if not _warned_missing:
                logger.warning(
                    "use_semantic_rag is on but sentence-transformers is not installed "
                    "(install the 'rag' extra). Falling back to deterministic retrieval."
                )
                _warned_missing = True
            return None
        except Exception:  # noqa: BLE001 — never let index build break a chat turn
            logger.exception("Semantic index build failed; using deterministic retrieval")
            return None
        _state = {"matrix": matrix, "chunks": chunks}
        return _state


def search(query: str, top_k: int = 3, min_score: float = 0.25) -> list[tuple[kb.Chunk, float]]:
    """Return up to ``top_k`` (chunk, cosine-score) pairs for a free-text query.

    Returns [] when the feature is disabled, the dep is missing, or nothing clears
    ``min_score`` — callers treat an empty result as "no semantic context" and degrade.
    """
    if not settings.use_semantic_rag or not query.strip():
        return []
    state = _ensure_index()
    if state is None:
        return []
    try:
        import numpy as np
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer(settings.embedding_model)
        q = model.encode([query], normalize_embeddings=True, convert_to_numpy=True)[0]
        scores = state["matrix"] @ np.asarray(q, dtype="float32")  # cosine (both normalized)
        order = np.argsort(scores)[::-1][:top_k]
        return [
            (state["chunks"][i], float(scores[i])) for i in order if float(scores[i]) >= min_score
        ]
    except Exception:  # noqa: BLE001
        logger.exception("Semantic search failed; degrading to no semantic context")
        return []
