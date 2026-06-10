"""Generate the per-report explanation: per-finding prose + overall summary + doctor
questions, all KB-grounded and passed through the safety OUTPUT guard.

Per-finding explanations are built deterministically from the KB + rule result (grounded,
hedged, safe). The overall summary is optionally rephrased by ONE LLM call (when available
and permitted by the user's llm_mode) and then guarded; otherwise it's the deterministic
template. Doctor questions are deterministic templates (inherently safe). Nothing here
emits prose that hasn't passed check_output()/ensure_disclaimer().
"""

from __future__ import annotations

from app.core.logging import get_logger
from app.safety import GuardContext, Surface, check_output
from app.services import kb, llm_service
from app.services.catalog import load_catalog

logger = get_logger(__name__)

_MAX_QUESTIONS = 8
_DEGRADED = "This result was flagged for your attention; please discuss it with your doctor."


def generate(report, biomarkers, findings, user) -> dict:
    bm_by_id = {b.id: b for b in biomarkers}
    abnormal = [f for f in findings if f.status == "abnormal"]

    # Each finding is isolated: a failure on one degrades to a safe guarded note rather
    # than failing the whole report.
    per_finding: dict[int, dict] = {}
    for finding in findings:
        bm = bm_by_id.get(finding.biomarker_id)
        if bm is None:
            continue
        try:
            chunks = kb.retrieve(bm.canonical_name, finding.direction)
            per_finding[finding.biomarker_id] = {
                "explanation": _explain_finding(bm, finding, chunks),
                "citations": [
                    {"n": i + 1, "doc_title": c.doc_title, "section": c.section, "source_path": c.source_path}
                    for i, c in enumerate(chunks)
                ],
            }
        except Exception:  # noqa: BLE001 - never let one finding sink the report
            logger.exception("Explanation failed for biomarker %s", finding.biomarker_id)
            per_finding[finding.biomarker_id] = {
                "explanation": check_output(_DEGRADED, GuardContext(surface=Surface.analyze)),
                "citations": [],
            }

    try:
        summary_text, generation_mode, model_used = _overall_summary(findings, abnormal, bm_by_id, user)
    except Exception:  # noqa: BLE001
        logger.exception("Overall summary generation failed")
        summary_text = check_output(
            "Here is an educational summary of your extracted results.",
            GuardContext(surface=Surface.analyze),
        )
        generation_mode, model_used = "offline_template", "offline-template"

    try:
        questions = _doctor_questions(abnormal, bm_by_id)
    except Exception:  # noqa: BLE001
        logger.exception("Doctor-question generation failed")
        questions = []

    return {
        "overall_summary": summary_text,
        "generation_mode": generation_mode,
        "model_used": model_used,
        "per_finding": per_finding,
        "doctor_questions": questions,
    }


# --- helpers ---

def _display(canonical_name: str | None, fallback: str) -> str:
    return load_catalog().get(canonical_name or "", {}).get("display") or fallback


def _value_str(bm) -> str:
    if bm.value is not None:
        unit = bm.unit or bm.canonical_unit
        return f"{bm.value:g} {unit}".strip() if unit else f"{bm.value:g}"
    return bm.value_text or "the reported result"


def _range_str(bm) -> str:
    if bm.reference_range_text:
        return bm.reference_range_text
    low, high = bm.reference_low, bm.reference_high
    if low is not None and high is not None:
        return f"{low:g}-{high:g}"
    if high is not None:
        return f"up to {high:g}"
    if low is not None:
        return f"at least {low:g}"
    return "the reference range"


def _direction_word(finding) -> str:
    return {"low": "low", "high": "high"}.get(finding.direction, "unexpected")


def _explain_finding(bm, finding, chunks) -> str:
    display = _display(bm.canonical_name, bm.test_name)
    what = chunks[0].text if chunks else ""
    directional = chunks[1].text if len(chunks) > 1 else ""
    qualitative = bm.value is None and bm.value_text is not None

    if finding.status == "abnormal" and qualitative:
        body = (
            f"{display}: {what} A result of {bm.value_text} is unexpected and may be associated "
            f"with several causes. {directional} Only a clinician can interpret your specific result."
        )
    elif finding.status == "abnormal":
        rel = {"low": "below", "high": "above"}.get(finding.direction, "outside")
        body = (
            f"{display}: {what} Your value ({_value_str(bm)}) is {rel} the reference range "
            f"({_range_str(bm)}) and is flagged as {finding.severity.capitalize()}. {directional} "
            f"Only a clinician can interpret your specific result."
        )
    elif qualitative:
        body = f"{display}: {what} A result of {bm.value_text} is within the expected range."
    else:
        body = (
            f"{display}: {what} Your value ({_value_str(bm)}) is within the reference range "
            f"({_range_str(bm)})."
        )
    return check_output(" ".join(body.split()), GuardContext(surface=Surface.analyze, marker=bm.canonical_name))


def _overall_summary(findings, abnormal, bm_by_id, user):
    if abnormal:
        parts = []
        for f in abnormal:
            bm = bm_by_id.get(f.biomarker_id)
            disp = _display(bm.canonical_name if bm else None, bm.test_name if bm else "a result")
            parts.append(f"{disp} ({_direction_word(f)}, {f.severity})")
        listed = "; ".join(parts)
        base = (
            f"This report has {len(abnormal)} result(s) flagged relative to the reference ranges: "
            f"{listed}. These are educational flags based on the printed or standard reference "
            f"ranges, not a diagnosis. A flagged value may be associated with a range of causes, "
            f"which only a clinician can interpret."
        )
    else:
        base = (
            f"All {len(findings)} assessed result(s) fall within their reference ranges based on "
            f"this report. This is an educational summary, not a diagnosis."
        )

    llm_mode = getattr(user, "llm_mode", "offline")
    consent = bool(getattr(user, "gemini_consent", 0))
    prompt = (
        "Rewrite the following report summary in 2-4 short, plain, hedged sentences for a "
        "layperson. Do NOT add any new facts, numbers, conditions, treatments, or medications. "
        "Do not reassure. Do not include a disclaimer.\n\nSUMMARY:\n" + base
    )
    completion = llm_service.complete(
        llm_service.SYSTEM_PROMPT, prompt, llm_mode=llm_mode, gemini_consent=consent
    )
    if completion is not None:
        text, model_used = completion
        mode = "ollama" if model_used.startswith("ollama") else "gemini"
        return check_output(text, GuardContext(surface=Surface.analyze)), mode, model_used
    return check_output(base, GuardContext(surface=Surface.analyze)), "offline_template", "offline-template"


def _doctor_questions(abnormal, bm_by_id) -> list[dict]:
    questions: list[dict] = []
    order = 0
    for finding in abnormal:
        bm = bm_by_id.get(finding.biomarker_id)
        display = _display(bm.canonical_name if bm else None, bm.test_name if bm else "this result")
        word = _direction_word(finding)
        text = (
            f"What might explain my unexpected {display} result?"
            if word == "unexpected"
            else f"What might be causing my {word} {display}?"
        )
        questions.append({"question_text": text, "category": "cause", "ordering": order})
        order += 1
        if order >= _MAX_QUESTIONS - 2:
            break
    questions.append({
        "question_text": "Should any of these results be re-checked or monitored over time?",
        "category": "follow-up", "ordering": order,
    })
    order += 1
    questions.append({
        "question_text": "Are there follow-up tests or lifestyle factors I should ask about?",
        "category": "clarification", "ordering": order,
    })
    return questions
