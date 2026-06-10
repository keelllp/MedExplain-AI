"""Templated refusals (deterministic — never LLM-generated, so they can't leak)."""

from __future__ import annotations

from app.schemas.common import DISCLAIMER

# category -> (refused act phrase, "I can't ..." phrase)
_ACTS = {
    "diagnosis": ("tell you what condition you have", "diagnose conditions"),
    "treatment": ("tell you how to treat this", "recommend treatments"),
    "prescription": ("recommend a medication", "prescribe medication"),
    "dosage": ("advise on a dose", "advise on dosages"),
}


def build_refusal(category: str, marker: str | None = None) -> str:
    if category == "self_harm":
        return (
            "I can't help with that. If you might be in danger or are thinking about harming "
            "yourself, please contact your local emergency services or a healthcare professional "
            "right now.\n\n" + DISCLAIMER
        )

    refused, cant = _ACTS.get(category, _ACTS["diagnosis"])
    if marker:
        explain_line = (
            f"Explain what {marker} is and what an out-of-range value can generally be associated with."
        )
    else:
        explain_line = (
            "Explain what your results measure and what out-of-range values can generally be "
            "associated with."
        )
    return (
        f"I'm not able to {refused} — I'm an educational assistant, not a doctor, and I can't "
        f"{cant}.\n\n"
        f"Here's what I can help with instead:\n"
        f" - {explain_line}\n"
        f" - Show how a value compares to its reference range and its severity.\n"
        f" - Suggest specific questions you can ask your doctor.\n\n"
        f"{DISCLAIMER}"
    )
