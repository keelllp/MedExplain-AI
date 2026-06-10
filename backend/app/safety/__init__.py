"""Non-negotiable safety layer (controlling per docs/07-safety-and-compliance.md).

Two-stage guard around EVERY user-facing generation:
  * check_input  — refuse diagnosis / treatment / prescription / dosage requests
  * check_output — scan generated/templated prose; block prohibited content; ALWAYS
                   guarantee the mandatory disclaimer (idempotent)

Pure Python (regex + keyword lists) — CPU-only, no external deps, unit-testable. Patterns
live in triggers.py (a Python module rather than YAML, so regex escaping is safe).
"""

from app.safety.disclaimer import DISCLAIMER, DISCLAIMER_BLOCK, ensure_disclaimer
from app.safety.guard import (
    GuardContext,
    InputAction,
    InputDecision,
    Surface,
    check_input,
    check_output,
)

__all__ = [
    "DISCLAIMER",
    "DISCLAIMER_BLOCK",
    "ensure_disclaimer",
    "GuardContext",
    "Surface",
    "InputAction",
    "InputDecision",
    "check_input",
    "check_output",
]
