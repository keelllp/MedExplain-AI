"""The mandatory disclaimer + idempotent enforcement."""

from __future__ import annotations

from app.schemas.common import DISCLAIMER

# The full compliance footer (used on export / UI). The single mandatory sentence
# (DISCLAIMER) is the load-bearing element and must always be present.
DISCLAIMER_BLOCK = (
    "MedExplain AI is an educational tool, not a medical device. It does not diagnose "
    "conditions, recommend treatments, or prescribe medication. Reference ranges vary "
    "between laboratories. " + DISCLAIMER
)


def ensure_disclaimer(text: str) -> str:
    """Return text guaranteed to contain the mandatory disclaimer exactly once (idempotent)."""
    body = (text or "").strip()
    if DISCLAIMER.lower() in body.lower():
        return body
    if not body:
        return DISCLAIMER
    return f"{body}\n\n{DISCLAIMER}"
