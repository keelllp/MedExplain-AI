"""Chat turn generation: input guard → KB retrieval → ONE LLM call → output guard.

A separate single LLM call per user message (docs/08-rag-design.md §6) that reuses the
Phase 5 machinery wholesale: the same ``check_input``/``check_output`` guards, the same
``llm_service`` router (honoring the user's ``llm_mode``), and the same KB. Retrieval is
deterministic and canonical-name-keyed — report-scoped chat filters on the report's own
markers; general chat resolves markers named in the message (and, only when explicitly
enabled, augments unnamed free-text questions via the optional semantic index).

This module is pure (no DB, no network state of its own): the router fetches the report's
biomarkers/findings + recent history and passes them in, then persists what this returns —
exactly mirroring how ``explanation_service`` is driven by ``analysis_pipeline``. Every
returned answer (LLM, offline-template, or refusal) has already passed the output guard.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from app.core.logging import get_logger
from app.safety import GuardContext, InputAction, Surface, check_input, check_output, ensure_disclaimer
from app.services import kb, llm_service, semantic_index
from app.services.catalog import load_catalog

logger = get_logger(__name__)

_MAX_TARGETS = 3        # distinct markers pulled into one answer's context
_MAX_CHUNKS = 6         # cap total KB chunks fed to the model
_MAX_HISTORY = 6        # recent turns included for follow-up context
_CHUNK_TRIM = 600       # chars per chunk in the prompt / offline answer

_CHAT_TASK = (
    "Answer the user's QUESTION in 2-5 short, plain, hedged sentences a layperson can "
    "understand, using ONLY the KNOWLEDGE BASE CONTEXT and REPORT DATA above. If the answer "
    "is not in that context, say you don't have that information rather than guessing. Do not "
    "diagnose, do not recommend or name treatments or medications, and do not reassure. Cite "
    "each supporting fact with its [n] tag. Do not add a disclaimer — it is appended for you."
)


# --------------------------------------------------------------------------- #
# Marker resolution (free-text → canonical names that have a KB doc)
# --------------------------------------------------------------------------- #
@lru_cache
def _alias_index() -> list[tuple[str, str]]:
    """(alias_regex_token, canonical_name) for every KB-backed marker, longest alias first."""
    catalog = load_catalog()
    pairs: list[tuple[str, str]] = []
    for cano, entry in catalog.items():
        if cano not in kb.KB_MAP:
            continue
        terms = set(entry.get("aliases") or [])
        terms.add(cano.replace("_", " "))
        display = entry.get("display")
        if display:
            terms.add(display.lower())
        for term in terms:
            term = term.strip().lower()
            if term:
                pairs.append((term, cano))
    pairs.sort(key=lambda p: len(p[0]), reverse=True)  # longest match wins
    return pairs


def _resolve_markers(message: str) -> list[str]:
    """Canonical markers named in the message, in first-mention order (deduped)."""
    text = " " + message.lower() + " "
    found: list[str] = []
    for term, cano in _alias_index():
        if cano in found:
            continue
        if re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", text):
            found.append(cano)
    return found


def _display(cano: str | None) -> str:
    if not cano:
        return "this result"
    return load_catalog().get(cano, {}).get("display") or cano.replace("_", " ")


def _slug(section: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in section.lower()).strip("-")


# --------------------------------------------------------------------------- #
# Retrieval
# --------------------------------------------------------------------------- #
def _choose_targets(report_scoped, report_markers, mentioned, abnormal_markers) -> list[str]:
    if report_scoped:
        in_report = [m for m in mentioned if m in report_markers]
        if in_report:
            return in_report[:_MAX_TARGETS]
        if abnormal_markers:
            return abnormal_markers[:_MAX_TARGETS]
        return list(report_markers)[:2]
    return mentioned[:_MAX_TARGETS]


def _retrieve(targets, direction_by_marker, message, report_scoped):
    """Return deduped (Chunk, score) pairs. Deterministic keyed lookup first; the optional
    semantic index only augments a general question that named no known marker."""
    scored: list[tuple[kb.Chunk, float]] = []
    seen: set[tuple[str, str]] = set()

    def _add(chunk, score):
        key = (chunk.source_path, chunk.section)
        if key not in seen:
            seen.add(key)
            scored.append((chunk, score))

    for marker in targets:
        for chunk in kb.retrieve(marker, direction_by_marker.get(marker)):
            _add(chunk, 1.0)  # exact keyed match — deterministic, not a similarity score

    if not targets and not report_scoped and semantic_index.is_enabled():
        for chunk, score in semantic_index.search(message, top_k=3):
            _add(chunk, score)

    return scored[:_MAX_CHUNKS]


def _citation(chunk: kb.Chunk, score: float) -> dict:
    stem = Path(chunk.source_path).stem
    return {"doc": chunk.doc_title, "chunk_id": f"{stem}#{_slug(chunk.section)}", "score": round(score, 4)}


# --------------------------------------------------------------------------- #
# Prompt + offline floor
# --------------------------------------------------------------------------- #
def _report_data_block(targets, bm_by_cano, finding_by_cano) -> str:
    lines: list[str] = []
    for cano in targets:
        bm = bm_by_cano.get(cano)
        if bm is None:
            continue
        if bm.value is not None:
            unit = bm.unit or bm.canonical_unit or ""
            value = f"{bm.value:g} {unit}".strip()
        else:
            value = bm.value_text or "reported"
        rng = bm.reference_range_text or (
            f"{bm.reference_low:g}-{bm.reference_high:g}"
            if bm.reference_low is not None and bm.reference_high is not None
            else "n/a"
        )
        finding = finding_by_cano.get(cano)
        status = (
            f"{finding.status}/{finding.severity}/{finding.direction}" if finding else "not assessed"
        )
        lines.append(f"  - {_display(cano)}: value {value}; reference {rng}; status {status}")
    return "\n".join(lines)


def _build_prompt(message, scored, targets, bm_by_cano, finding_by_cano, history, report_scoped) -> str:
    parts: list[str] = []

    if scored:
        ctx_lines = [
            f"  [{i + 1}] {chunk.text.strip()[:_CHUNK_TRIM]}   (source: {chunk.doc_title} › {chunk.section})"
            for i, (chunk, _score) in enumerate(scored)
        ]
        parts.append("KNOWLEDGE BASE CONTEXT (authoritative; cite by [n]):\n" + "\n".join(ctx_lines))
    else:
        parts.append(
            "KNOWLEDGE BASE CONTEXT: (none found for this question — say you don't have that "
            "information rather than inventing it.)"
        )

    if report_scoped:
        data = _report_data_block(targets, bm_by_cano, finding_by_cano)
        if data:
            parts.append("REPORT DATA (the user's own extracted values; treat as given):\n" + data)

    if history:
        convo = "\n".join(f"  {m.role}: {m.content.strip()[:500]}" for m in history)
        parts.append("CONVERSATION SO FAR:\n" + convo)

    parts.append("QUESTION:\n" + message.strip())
    parts.append("TASK:\n" + _CHAT_TASK)
    return "\n\n".join(parts)


def _offline_answer(message, scored, ctx) -> str:
    if scored:
        body_parts = [chunk.text.strip()[:_CHUNK_TRIM] for chunk, _ in scored[:2]]
        text = (
            "Here is some general, educational information from the knowledge base: "
            + " ".join(body_parts)
            + " I'm currently running without a language model available, so this is a brief, "
            "general explanation rather than a tailored answer."
        )
    else:
        text = (
            "I can share general, educational information about what your results measure and what "
            "an out-of-range value can generally be associated with, but I don't have knowledge-base "
            "material specific to that question. You could ask about a specific marker — for example, "
            "what hemoglobin or glucose measures — or review the explanations on your report."
        )
    return check_output(text, ctx)


# --------------------------------------------------------------------------- #
# Public entry
# --------------------------------------------------------------------------- #
def answer_question(
    *, message, report_id, biomarkers, findings, history, user, allow_llm=True
) -> dict:
    """Produce one guarded chat answer. Returns
    ``{answer, citations, generation_mode, refused}`` — never raises for content reasons.

    ``report_id`` truthy ⇒ report-scoped (``biomarkers``/``findings`` are that report's).
    ``allow_llm=False`` forces the deterministic floor (used when the analysis slot is busy,
    so chat never runs heavy inference concurrently with a report analysis).
    """
    report_scoped = bool(report_id)
    bm_by_id = {b.id: b for b in biomarkers}
    bm_by_cano = {b.canonical_name: b for b in biomarkers if b.canonical_name}
    finding_by_cano = {
        bm_by_id[f.biomarker_id].canonical_name: f
        for f in findings
        if f.biomarker_id in bm_by_id and bm_by_id[f.biomarker_id].canonical_name
    }
    direction_by_marker = {c: f.direction for c, f in finding_by_cano.items()}
    report_markers = set(bm_by_cano)
    abnormal_markers = [
        bm_by_id[f.biomarker_id].canonical_name
        for f in findings
        if f.status == "abnormal"
        and f.biomarker_id in bm_by_id
        and bm_by_id[f.biomarker_id].canonical_name
    ]

    mentioned = _resolve_markers(message)
    primary = mentioned[0] if mentioned else (abnormal_markers[0] if (report_scoped and abnormal_markers) else None)
    ctx = GuardContext(surface=Surface.chat, marker=_display(primary) if primary else None)

    # Stage 1 — input guard (best-effort; the output guard below is authoritative).
    decision = check_input(message, ctx)
    if decision.action is InputAction.REFUSE:
        return {
            "answer": ensure_disclaimer(decision.refusal_text),  # first-party safe template
            "citations": [],
            "generation_mode": "offline_template",
            "refused": True,
        }

    # Stage 2 — retrieval (deterministic, canonical-name keyed).
    targets = _choose_targets(report_scoped, report_markers, mentioned, abnormal_markers)
    scored = _retrieve(targets, direction_by_marker, message, report_scoped)
    citations = [_citation(chunk, score) for chunk, score in scored]

    # Stage 3 — ONE generation call (LLM if permitted + available, else deterministic floor).
    completion = None
    if allow_llm:
        prompt = _build_prompt(
            message, scored, targets, bm_by_cano, finding_by_cano, history, report_scoped
        )
        try:
            completion = llm_service.complete(
                llm_service.SYSTEM_PROMPT,
                prompt,
                llm_mode=getattr(user, "llm_mode", "offline"),
                gemini_consent=bool(getattr(user, "gemini_consent", 0)),
            )
        except Exception:  # noqa: BLE001 — any LLM failure degrades to the floor, never errors
            logger.exception("Chat LLM call failed; using offline floor")
            completion = None

    # Stage 4 — output guard (authoritative) on whatever we produced.
    if completion is not None:
        text, model_used = completion
        mode = "ollama" if model_used.startswith("ollama") else "gemini"
        answer = check_output(text, ctx)
    else:
        answer = _offline_answer(message, scored, ctx)
        mode = "offline_template"

    return {"answer": answer, "citations": citations, "generation_mode": mode, "refused": False}
