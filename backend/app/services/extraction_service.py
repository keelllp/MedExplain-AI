"""Biomarker extraction from OCR text + reconstructed tables.

Approach: **catalog-anchored** + regex. For each line/table-row we find a known
biomarker alias (longest alias wins, so "hdl cholesterol" beats "cholesterol"), then
parse the value/unit/reference-range near it. Anchoring on the catalog keeps results
to known biomarkers and avoids treating headers/footers as "tests".

Robust value/range selection (so we never produce a wrong abnormality flag):
  * the reference range is parsed first, with date/year guards so "2026-06-01" is NOT
    read as a range and a low>high parse is discarded;
  * the result value is the first number that lies OUTSIDE the matched range span
    (so a range printed before the value, or a range-only row, can't masquerade as the
    value — a range-only row yields no biomarker rather than a false "normal");
  * thousands separators are stripped (250,000 -> 250000);
  * digit-bearing unit tokens (10^6/uL) are blanked before the value search.

Deterministic regex is more reliable than NLP for tabular lab data; spaCy/MedSpaCy
free-text augmentation is a reserved future enhancement (see _augment_nlp).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.catalog import load_catalog

_NUM = r"[-+]?\d+(?:\.\d+)?"

# Bound the work done per analysis (garbage/huge OCR can't monopolize the slot).
_MAX_LINES = 4000
_MAX_LINE_LEN = 2000

# Qualitative result tokens.
_RESULT_WORDS = [
    "not detected", "non-reactive", "nonreactive", "negative", "positive",
    "reactive", "present", "absent", "trace", "detected", "nil",
]


@dataclass
class RawBiomarker:
    test_name: str
    canonical_name: str
    value: float | None
    value_text: str | None
    unit: str | None
    canonical_unit: str | None
    reference_low: float | None
    reference_high: float | None
    reference_range_text: str | None


def extract(raw_text: str, tables: list[dict] | None) -> list[RawBiomarker]:
    catalog = load_catalog()
    found: dict[str, RawBiomarker] = {}  # canonical_name -> first usable reading

    for line in _candidate_lines(raw_text, tables):
        match = _best_alias_match(line, catalog)
        if match is None:
            continue
        canonical, entry, m = match
        if canonical in found:
            continue
        raw_label = line[m.start() : m.end()]
        after = line[m.end() :]
        parsed = _parse_line(raw_label, canonical, entry, after, line)
        if parsed is not None:  # only claim the slot when we got a real reading
            found[canonical] = parsed

    return list(found.values())


def _candidate_lines(raw_text: str, tables: list[dict] | None) -> list[str]:
    lines: list[str] = []
    for tbl in tables or []:
        for row in tbl.get("rows", []):
            cells = [str(c).strip() for c in row if c not in (None, "")]
            if cells:
                lines.append("  ".join(cells))
    lines.extend((raw_text or "").splitlines())

    out: list[str] = []
    for ln in lines:
        ln = ln.strip()
        if ln:
            out.append(ln[:_MAX_LINE_LEN])
        if len(out) >= _MAX_LINES:
            break
    return out


def _best_alias_match(line: str, catalog: dict):
    lower = line.lower()
    best = None  # (canonical, entry, match, alias_len)
    for canonical, entry in catalog.items():
        for alias in entry.get("aliases", []):
            m = re.search(r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])", lower)
            if m and (best is None or len(alias) > best[3]):
                best = (canonical, entry, m, len(alias))
    if best is None:
        return None
    return best[0], best[1], best[2]


def _parse_line(raw_label, canonical, entry, after_raw, full_line_raw) -> RawBiomarker | None:
    after = _normalize_numbers(after_raw)
    full_line = _normalize_numbers(full_line_raw)
    low, high, range_text, range_span = _parse_range(after)

    if entry.get("type") == "qualitative":
        value_text = _find_result_word(after) or _find_result_word(full_line)
        if value_text is None:
            return None
        expected = entry.get("expected", [])
        return RawBiomarker(
            test_name=raw_label, canonical_name=canonical,
            value=None, value_text=value_text, unit=None, canonical_unit=None,
            reference_low=None, reference_high=None,
            reference_range_text=range_text or (expected[0].capitalize() if expected else None),
        )

    # numeric: blank digit-bearing units, then take the first number OUTSIDE the range.
    search_space = _blank_units(after, entry)
    value = _first_number_outside(search_space, range_span)
    if value is None:
        return None  # e.g. a range-only row — no result to record
    unit = _find_unit(after, entry)
    return RawBiomarker(
        test_name=raw_label, canonical_name=canonical,
        value=value, value_text=None, unit=unit, canonical_unit=entry.get("canonical_unit"),
        reference_low=low, reference_high=high, reference_range_text=range_text,
    )


def _normalize_numbers(s: str) -> str:
    # strip thousands/grouping separators between digits: 250,000 -> 250000, 1,50,000 -> 150000
    return re.sub(r"(?<=\d),(?=\d)", "", s)


def _looks_like_year(token: str) -> bool:
    t = token.lstrip("+-")
    return "." not in t and len(t) == 4  # 4-digit integer ~ a year


def _parse_range(s: str):
    """Parse a reference range -> (low, high, text, span). Any side may be None; span is
    the (start, end) of the matched range text in ``s`` (or None)."""
    for m in re.finditer(rf"({_NUM})\s*[-–—]\s*({_NUM})", s):
        a_str, b_str = m.group(1), m.group(2)
        # skip dates: another "-NN" / "/NN" right after, or a 4-digit (year) operand
        if re.match(r"[-/]\d", s[m.end() : m.end() + 2]):
            continue
        if _looks_like_year(a_str) or _looks_like_year(b_str):
            continue
        a, b = float(a_str), float(b_str)
        if a <= b:
            return a, b, m.group(0).strip(), m.span()
        # a > b is not a valid range (likely a date/identifier) — keep scanning
    m = re.search(rf"[<≤]\s*=?\s*({_NUM})", s)
    if m:
        return None, float(m.group(1)), m.group(0).strip(), m.span()
    m = re.search(rf"[>≥]\s*=?\s*({_NUM})", s)
    if m:
        return float(m.group(1)), None, m.group(0).strip(), m.span()
    m = re.search(rf"up to\s*({_NUM})", s, re.IGNORECASE)
    if m:
        return None, float(m.group(1)), m.group(0).strip(), m.span()
    return None, None, None, None


def _first_number_outside(s: str, range_span) -> float | None:
    for m in re.finditer(_NUM, s):
        if range_span is None or not (m.start() < range_span[1] and m.end() > range_span[0]):
            return float(m.group())
    return None


def _blank_units(s: str, entry: dict) -> str:
    """Replace unit tokens with equal-length spaces so digit-bearing units (10^6/uL) are
    not mistaken for the value, while keeping all other character positions aligned."""
    out = s
    for unit in entry.get("units", []):
        if not unit:
            continue
        lower = out.lower()
        start = 0
        while True:
            pos = lower.find(unit, start)
            if pos == -1:
                break
            out = out[:pos] + (" " * len(unit)) + out[pos + len(unit) :]
            lower = out.lower()
            start = pos + len(unit)
    return out


def _find_unit(s: str, entry: dict) -> str | None:
    lower = s.lower()
    for unit in entry.get("units", []):
        if unit and unit in lower:
            return entry.get("canonical_unit")
    return None


def _find_result_word(s: str) -> str | None:
    """Return the result token that appears EARLIEST in the string (the actual result,
    not the reference value that often follows it in parentheses)."""
    lower = s.lower()
    best = None  # (position, original_text)
    for word in _RESULT_WORDS:
        m = re.search(r"(?<![a-z])" + re.escape(word) + r"(?![a-z])", lower)
        if m and (best is None or m.start() < best[0]):
            best = (m.start(), s[m.start() : m.end()])
    return best[1] if best else None


def _augment_nlp(raw_text: str, found: dict) -> None:  # noqa: ARG001
    """Reserved hook for spaCy/MedSpaCy free-text augmentation (optional 'nlp' extra).

    Not wired in Phase 4: catalog-anchored regex covers tabular lab data reliably, and
    MedSpaCy's value is in clinical-narrative NER (discharge summaries) — a later phase.
    """
    return None
