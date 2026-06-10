"""LLM router: provider selection + HTTP calls to Ollama / Gemini (no extra client libs).

`complete()` returns (text, model_used) or None if no LLM is available (→ callers use the
deterministic offline template). Provider is chosen from the user's llm_mode + consent:
  * 'cloud' + consent + a configured key  -> Gemini (PAID; never the free tier for PHI),
    falling back to Ollama, then to None (offline template);
  * 'offline' (default)                    -> Ollama, then None.
The safety guard is applied by the CALLER (explanation_service / chat) to whatever this
returns — this module never bypasses it.
"""

from __future__ import annotations

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Shared system prompt (the same rules for every provider, so safety doesn't drift).
SYSTEM_PROMPT = (
    "You are MedExplain AI, an EDUCATIONAL assistant that helps a layperson understand a "
    "medical report. You are NOT a doctor. ABSOLUTE RULES: never diagnose; never recommend "
    "or name treatments; never recommend, name, or dose any medication; never reassure ('you're "
    "fine'); use hedged, general language ('may be associated with'); use ONLY the provided "
    "context and report data — do not invent facts, numbers, or studies. Write in plain, "
    "friendly language a non-expert can understand."
)


def resolve_provider(llm_mode: str, gemini_consent: bool) -> str:
    """'gemini' | 'ollama' (the offline-template fallback is signalled by complete() -> None)."""
    if llm_mode == "cloud" and gemini_consent and settings.gemini_available:
        return "gemini"
    return "ollama"


def complete(system: str, user: str, *, llm_mode: str, gemini_consent: bool = False):
    """Return (text, model_used) or None. Never raises."""
    provider = resolve_provider(llm_mode, gemini_consent)
    if provider == "gemini":
        text = _gemini(system, user)
        if text:
            return text, settings.gemini_model
        # fall through to local on any cloud failure (never silently to free Gemini)
    text = _ollama(system, user)
    if text:
        return text, f"ollama/{settings.ollama_model}"
    return None


def _ollama(system: str, user: str) -> str | None:
    try:
        resp = httpx.post(
            f"{settings.ollama_host}/api/generate",
            json={
                "model": settings.ollama_model,
                "system": system,
                "prompt": user,
                "stream": False,
                "options": {
                    "temperature": settings.llm_temperature,
                    "num_predict": settings.llm_max_output_tokens,
                },
            },
            timeout=settings.ollama_timeout,
        )
        resp.raise_for_status()
        return (resp.json().get("response") or "").strip() or None
    except Exception as exc:  # noqa: BLE001 - any failure => offline fallback
        logger.info("Ollama unavailable (%s); using offline template", type(exc).__name__)
        return None


def _gemini(system: str, user: str) -> str | None:
    if not settings.gemini_available:
        return None
    try:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{settings.gemini_model}:generateContent"
        )
        resp = httpx.post(
            url,
            params={"key": settings.gemini_api_key},
            json={
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"parts": [{"text": user}]}],
                "generationConfig": {
                    "temperature": settings.llm_temperature,
                    "maxOutputTokens": settings.llm_max_output_tokens,
                },
            },
            timeout=settings.gemini_timeout,
        )
        resp.raise_for_status()
        parts = resp.json()["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts).strip() or None
    except Exception as exc:  # noqa: BLE001
        logger.info("Gemini call failed (%s); falling back", type(exc).__name__)
        return None
