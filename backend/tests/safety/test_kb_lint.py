"""KB hedging lint (docs/08 §8.3) — a hard build gate.

The KB is the corpus the model is told to ground on AND the source the offline-template path
quotes directly, so un-hedged/diagnostic/directive phrasing there would propagate into
user-facing explanations. KB docs are NOT run through check_output() at request time (they
are source content, not generated prose); instead this test lints them offline and FAILS the
build on any assertive "you have", imperative drug directive, or drug-name+dose pattern.
"""

import re

import pytest

from app.core.config import settings
from app.safety.triggers import DOSE_RE

pytestmark = pytest.mark.safety

# Assertive diagnosis ("you have X", "you are diabetic") — the KB must stay hedged.
_ASSERTIVE = re.compile(r"\byou (?:have|are|will have|likely have|probably have|definitely)\b", re.I)
# Imperative drug/treatment directive aimed at the reader.
_IMPERATIVE = re.compile(
    r"\b(?:take|start|stop|begin|use|apply|inject|swallow|increase|decrease)\s+"
    r"(?:a |an |your |the |some )?"
    r"(?:\d|tablets?|pills?|capsules?|doses?|supplements?|medications?|medicines?|drugs?|"
    r"statins?|metformin|insulin|levothyroxine|ferrous|antibiotics?)",
    re.I,
)


def _kb_docs():
    kb_dir = settings.knowledge_base_path
    return sorted(kb_dir.glob("*.md"))


def test_kb_directory_is_present_and_nonempty():
    docs = _kb_docs()
    assert docs, f"no KB markdown docs found under {settings.knowledge_base_path}"


@pytest.mark.parametrize("doc", _kb_docs(), ids=lambda p: p.name)
def test_kb_doc_is_hedged(doc):
    text = doc.read_text(encoding="utf-8")
    violations = []
    if _ASSERTIVE.search(text):
        violations.append(f"assertive diagnosis: {_ASSERTIVE.search(text).group(0)!r}")
    if _IMPERATIVE.search(text):
        violations.append(f"imperative directive: {_IMPERATIVE.search(text).group(0)!r}")
    if DOSE_RE.search(text):
        violations.append(f"drug+dose: {DOSE_RE.search(text).group(0)!r}")
    assert not violations, f"{doc.name} has un-hedged phrasing: {violations}"
