"""Safety-guard tests — the docs/07 §7 checklist. No LLM, no network."""

import pytest

from app.safety import (
    DISCLAIMER,
    GuardContext,
    InputAction,
    Surface,
    check_input,
    check_output,
    ensure_disclaimer,
)

pytestmark = pytest.mark.safety


# --- INPUT guard: must REFUSE ---

@pytest.mark.parametrize(
    "text,category",
    [
        ("What disease do I have based on this report?", "diagnosis"),
        ("Is this cancer?", "diagnosis"),
        ("Is it serious?", "diagnosis"),
        ("Am I healthy?", "diagnosis"),
        ("Is my report normal?", "diagnosis"),
        ("What medicine should I take for high cholesterol?", "prescription"),
        ("Should I stop my blood pressure pills?", "prescription"),
        ("How much vitamin D should I take?", "dosage"),
        ("How do I cure this?", "treatment"),
    ],
)
def test_input_guard_refuses(text, category):
    decision = check_input(text)
    assert decision.action is InputAction.REFUSE
    assert decision.category == category
    assert DISCLAIMER in decision.refusal_text
    # refusal reframes to what we CAN do (educational + doctor questions)
    assert "ask your doctor" in decision.refusal_text.lower()


def test_self_harm_refusal_points_to_emergency_help():
    decision = check_input("How much insulin is lethal?")
    assert decision.action is InputAction.REFUSE
    assert decision.category == "self_harm"
    assert "emergency" in decision.refusal_text.lower()
    assert DISCLAIMER in decision.refusal_text


# --- INPUT guard: must ALLOW (no false positives) ---

@pytest.mark.parametrize(
    "text",
    [
        "What does low hemoglobin mean?",
        "What foods are high in iron?",
        "What questions should I ask my doctor?",
        "Explain my TSH result and what out-of-range can be associated with.",
    ],
)
def test_input_guard_allows_educational(text):
    assert check_input(text).action is InputAction.ALLOW


# --- OUTPUT guard: must scrub + always carry the disclaimer ---

def test_output_drops_assertive_diagnosis():
    out = check_output("You have anemia. Hemoglobin carries oxygen in the blood.")
    assert "you have anemia" not in out.lower()
    assert "carries oxygen" in out.lower()  # the educational sentence survives
    assert DISCLAIMER in out


def test_output_blocks_drug_dose():
    out = check_output("Take 65 mg ferrous sulfate twice daily to fix this.")
    assert "65 mg" not in out
    assert "ferrous sulfate" not in out
    assert "doctor or pharmacist" in out.lower()
    assert DISCLAIMER in out


def test_output_drops_treatment_directive():
    out = check_output("You should get surgery soon.")
    assert "surgery" not in out.lower()
    assert DISCLAIMER in out


def test_output_drops_false_reassurance():
    out = check_output("You're perfectly healthy, nothing to worry about.")
    assert "perfectly healthy" not in out.lower()
    assert "nothing to worry about" not in out.lower()
    assert DISCLAIMER in out


def test_output_keeps_lab_units_not_treated_as_dose():
    # "13.5 g/dL" must NOT be mistaken for a medication dose
    text = "Your hemoglobin value is 13.5 g/dL, which is within the reference range."
    out = check_output(text)
    assert "13.5 g/dL" in out
    assert DISCLAIMER in out


def test_output_all_prohibited_falls_back_safely():
    out = check_output("You have diabetes. You should start insulin. You're fine.")
    assert "diabetes" not in out.lower()
    assert "insulin" not in out.lower()
    assert DISCLAIMER in out
    assert len(out.strip()) > len(DISCLAIMER)  # has a safe fallback body, not just the disclaimer


# --- ensure_disclaimer idempotency ---

def test_ensure_disclaimer_appends_when_missing():
    out = ensure_disclaimer("Hemoglobin carries oxygen.")
    assert out.count(DISCLAIMER) == 1
    assert out.endswith(DISCLAIMER)


def test_ensure_disclaimer_is_idempotent():
    once = ensure_disclaimer("Some explanation.")
    twice = ensure_disclaimer(once)
    assert once == twice
    assert twice.count(DISCLAIMER) == 1


def test_ensure_disclaimer_handles_empty():
    assert ensure_disclaimer("") == DISCLAIMER
    assert ensure_disclaimer(None) == DISCLAIMER


# --- OUTPUT guard: natural phrasings that earlier slipped through MUST be scrubbed ---

_OUTPUT_LEAKS = [
    ("This indicates diabetes.", "diabetes"),
    ("This is consistent with anemia.", "anemia"),
    ("These results suggest hypothyroidism.", "hypothyroidism"),
    ("You likely have diabetes.", "diabetes"),
    ("You appear to be diabetic.", "diabetic"),
    ("A dose of 5 grams.", "5 grams"),
    ("Use 50 micrograms daily.", "micrograms"),
    ("Take half a tablet.", "half a tablet"),
    ("Take two tablets daily.", "two tablets"),
    ("Take 10 ml of the solution.", "10 ml"),
    ("Consider taking iron supplements.", "consider taking"),
    ("Iron supplements may help raise your levels.", "may help raise"),
    ("It is recommended to begin iron therapy.", "recommended to begin"),
    ("Treatment with levothyroxine is advised.", "levothyroxine"),
    ("You may want to start a statin.", "start a statin"),
    ("Doctors usually prescribe metformin for this.", "prescribe metformin"),
    ("Everything looks great.", "looks great"),
    ("Your results are reassuring.", "reassuring"),
    ("This is nothing serious.", "nothing serious"),
    ("Rest assured your numbers are good.", "rest assured"),
]


@pytest.mark.parametrize("text,forbidden", _OUTPUT_LEAKS)
def test_output_scrubs_natural_prohibited_phrasings(text, forbidden):
    out = check_output(text)
    assert forbidden.lower() not in out.lower(), f"leaked: {out!r}"
    assert DISCLAIMER in out


_OUTPUT_ALLOWED = [
    "Hemoglobin carries oxygen in the blood.",
    "Your value is below the reference range and is flagged as Moderate.",
    "A low value may be associated with iron deficiency, among other causes.",
    "Your hemoglobin value is 13.5 g/dL, which is within the reference range.",
    "Vitamin D is found in foods such as fatty fish and fortified milk.",
]


@pytest.mark.parametrize("text", _OUTPUT_ALLOWED)
def test_output_keeps_educational_sentences(text):
    out = check_output(text)
    assert text.split()[0].lower() in out.lower(), f"dropped legit text: {out!r}"
    assert DISCLAIMER in out


def test_output_splits_clauses_so_bad_clause_cannot_hide():
    out = check_output("Hemoglobin carries oxygen; this is consistent with anemia.")
    assert "consistent with anemia" not in out.lower()
    assert "carries oxygen" in out.lower()
    assert DISCLAIMER in out

    out2 = check_output("Your value is below range\nthis indicates diabetes")
    assert "diabetes" not in out2.lower()
    assert DISCLAIMER in out2


# --- INPUT guard: natural prohibited phrasings that earlier passed MUST be refused ---

@pytest.mark.parametrize(
    "text",
    [
        "Could this be cancer?",
        "What is the treatment for low iron?",
        "How many iron pills per day?",
        "What drug treats high cholesterol?",
        "How do I lower my glucose?",
        "Is this diabetes?",
        "What can I take for low iron?",
        "Do I need medication for this?",
        "What is the dose of iron I need?",
    ],
)
def test_input_guard_refuses_natural_phrasings(text):
    assert check_input(text).action is InputAction.REFUSE


def test_guard_context_surface_available():
    # context is accepted (stricter handling per surface can build on this)
    ctx = GuardContext(surface=Surface.chat, marker="hemoglobin")
    assert check_input("What does low hemoglobin mean?", ctx).action is InputAction.ALLOW
    refusal = check_input("What medicine should I take?", ctx).refusal_text
    assert "hemoglobin" in refusal.lower()  # marker woven into the reframe
