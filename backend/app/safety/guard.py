"""The two-stage safety guard: check_input (refuse), check_output (scrub + disclaimer).

The OUTPUT guard is the load-bearing layer: it runs on EVERY generated/templated string
(LLM, offline-template, and rule-engine prose) before persistence, scrubs prohibited
content sentence-by-sentence, and guarantees the disclaimer. The input guard is a
best-effort English-keyword refuser that short-circuits prohibited requests before any
generation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from app.safety.disclaimer import ensure_disclaimer
from app.safety.refusal_templates import build_refusal
from app.safety.triggers import (
    DIAGNOSTIC_RE,
    DOSE_RE,
    INPUT_TRIGGERS,
    REASSURANCE_RE,
    TREATMENT_RE,
)


class Surface(str, Enum):
    analyze = "analyze"
    chat = "chat"
    export = "export"


@dataclass
class GuardContext:
    surface: Surface = Surface.chat
    marker: str | None = None


class InputAction(str, Enum):
    ALLOW = "allow"
    REFUSE = "refuse"


@dataclass
class InputDecision:
    action: InputAction
    category: str | None = None
    refusal_text: str | None = None


def check_input(text: str, context: GuardContext | None = None) -> InputDecision:
    context = context or GuardContext()
    normalized = " ".join((text or "").split())
    for category, patterns in INPUT_TRIGGERS:
        if any(p.search(normalized) for p in patterns):
            return InputDecision(
                action=InputAction.REFUSE,
                category=category,
                refusal_text=build_refusal(category, context.marker),
            )
    return InputDecision(action=InputAction.ALLOW)


# Split into clauses on sentence punctuation AND on semicolons / newlines, so a prohibited
# clause cannot hide inside an otherwise-safe sentence ("safe; this indicates diabetes").
_SENTENCE = re.compile(r"(?<=[.!?])\s+|\s*[;\n]+\s*")
_SAFE_DRUG_NOTE = "Discuss any medication questions with your doctor or pharmacist."
_EMPTY_FALLBACK = (
    "I can share general, educational information about your results, but only a clinician "
    "can interpret them."
)


def check_output(text: str, context: GuardContext | None = None) -> str:
    """Scrub prohibited content from generated prose and guarantee the disclaimer.

    Returns user-safe text (never raises). Sentences with a drug dose are replaced with a
    neutral note; assertive diagnoses, treatment directives, and false reassurance are
    dropped. If everything is removed, a safe educational fallback is used.
    """
    if not text or not text.strip():
        return ensure_disclaimer("")

    kept: list[str] = []
    for sentence in _SENTENCE.split(text.strip()):
        remediated = _remediate(sentence)
        if remediated is None:
            kept.append(sentence)
        elif remediated:  # non-empty replacement
            kept.append(remediated)
        # remediated == "" -> drop the sentence

    result = " ".join(s.strip() for s in kept if s.strip()).strip()
    if not result:
        result = _EMPTY_FALLBACK
    return ensure_disclaimer(result)


def _remediate(sentence: str) -> str | None:
    """None = keep as-is; "" = drop; str = replace."""
    if DOSE_RE.search(sentence):
        return _SAFE_DRUG_NOTE
    if TREATMENT_RE.search(sentence) or DIAGNOSTIC_RE.search(sentence) or REASSURANCE_RE.search(sentence):
        return ""
    return None
