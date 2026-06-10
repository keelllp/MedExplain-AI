"""Build a report-summary PDF (Phase 10).

Pure-Python (fpdf2, no native deps). The full disclaimer block is printed on EVERY page via
the footer (docs/07). Raw chat is excluded by default; when included, each assistant turn is
re-passed through the output guard before embedding (D-EXPORT-CHAT). Text is sanitized to the
core-font (latin-1) range so an em-dash / smart quote in an LLM summary can never crash export.
"""

from __future__ import annotations

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from app.safety import DISCLAIMER, DISCLAIMER_BLOCK, GuardContext, Surface, check_output
from app.services.catalog import load_catalog

_BRAND = (17, 103, 92)
_INK = (29, 42, 37)
_MUTED = (92, 107, 99)

_UNICODE_FIXES = {
    "—": "-", "–": "-", "‘": "'", "’": "'", "“": '"',
    "”": '"', "…": "...", " ": " ", "•": "-", "→": "->",
    "µ": "u", "≥": ">=", "≤": "<=", "°": " deg",
}


def _safe(text) -> str:
    """Latin-1-safe text for fpdf2 core fonts (replace common unicode, drop the rest)."""
    if text is None:
        return ""
    s = str(text)
    for bad, good in _UNICODE_FIXES.items():
        s = s.replace(bad, good)
    return s.encode("latin-1", "replace").decode("latin-1")


class _ReportPDF(FPDF):
    def footer(self) -> None:
        self.set_y(-18)
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(*_MUTED)
        self.multi_cell(0, 3.2, _safe(DISCLAIMER_BLOCK), align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_y(-6)
        self.set_font("Helvetica", "", 7)
        self.cell(0, 4, _safe(f"Page {self.page_no()}"), align="C")


def _p(pdf: _ReportPDF, text: str, *, h: float = 5, size: int = 10, style: str = "", color=_INK) -> None:
    """A left-aligned paragraph that always starts at the left margin (avoids the width-0
    multi_cell cursor drift that otherwise collapses the next cell's available width)."""
    pdf.set_font("Helvetica", style, size)
    pdf.set_text_color(*color)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(0, h, _safe(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def _heading(pdf: _ReportPDF, text: str) -> None:
    pdf.ln(2)
    _p(pdf, text, h=6, size=12, style="B", color=_BRAND)
    pdf.set_draw_color(220, 220, 220)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(2)


def _display(canonical_name, fallback) -> str:
    return load_catalog().get(canonical_name or "", {}).get("display") or fallback


def _value_str(bm) -> str:
    if bm.value is not None:
        unit = bm.unit or bm.canonical_unit or ""
        return f"{bm.value:g} {unit}".strip()
    return bm.value_text or "-"


def _ref_str(bm) -> str:
    if bm.reference_range_text:
        return bm.reference_range_text
    low, high = bm.reference_low, bm.reference_high
    if low is not None and high is not None:
        return f"{low:g}-{high:g}"
    if high is not None:
        return f"up to {high:g}"
    if low is not None:
        return f"at least {low:g}"
    return "-"


def _status_str(finding) -> str:
    if finding is None:
        return "not assessed"
    if finding.status == "abnormal":
        return f"{finding.direction} / {finding.severity}"
    return "within range"


def build(report, biomarkers, findings, summary, doctor_questions, chat_turns=None) -> bytes:
    pdf = _ReportPDF(format="A4", unit="mm")
    pdf.set_auto_page_break(True, margin=24)
    pdf.set_title(_safe(report.title))
    pdf.add_page()

    # Title + metadata
    _p(pdf, report.title, h=8, size=18, style="B")
    meta = f"{report.report_type.upper()}   |   Status: {report.status}"
    if getattr(report, "analyzed_at", None):
        meta += f"   |   Analyzed: {report.analyzed_at[:10]}"
    _p(pdf, meta, size=10, color=_MUTED)
    _p(pdf, "Educational summary — not a diagnosis. " + DISCLAIMER, h=4, size=8, style="I", color=_MUTED)

    if summary is not None:
        _heading(pdf, "Summary")
        _p(pdf, summary.summary_text)

    _heading(pdf, "Biomarkers")
    finding_by_bm = {f.biomarker_id: f for f in findings}
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*_INK)
    pdf.set_x(pdf.l_margin)
    with pdf.table(col_widths=(38, 22, 24, 22), text_align="LEFT", line_height=6) as table:
        table.row(["Test", "Value", "Reference", "Status"])
        for bm in biomarkers:
            f = finding_by_bm.get(bm.id)
            table.row(
                [
                    _safe(_display(bm.canonical_name, bm.test_name)),
                    _safe(_value_str(bm)),
                    _safe(_ref_str(bm)),
                    _safe(_status_str(f)),
                ]
            )

    explained = [f for f in findings if f.explanation]
    if explained:
        _heading(pdf, "Explanations")
        bm_by_id = {b.id: b for b in biomarkers}
        for f in explained:
            bm = bm_by_id.get(f.biomarker_id)
            label = _display(bm.canonical_name if bm else None, bm.test_name if bm else "Result")
            _p(pdf, label, size=10, style="B")
            _p(pdf, f.explanation)
            pdf.ln(1)

    if doctor_questions:
        _heading(pdf, "Questions for your doctor")
        for i, q in enumerate(doctor_questions, start=1):
            _p(pdf, f"{i}. {q.question_text}")

    if chat_turns:
        _heading(pdf, "Chat (educational)")
        ctx = GuardContext(surface=Surface.export)
        for turn in chat_turns:
            who = "You" if turn.role == "user" else "MedExplain AI"
            # Re-guard generated (assistant) prose before embedding; user text is their own.
            content = turn.content if turn.role == "user" else check_output(turn.content, ctx)
            _p(pdf, who, h=4.5, size=9, style="B", color=_MUTED)
            _p(pdf, content, size=9)
            pdf.ln(1)

    return bytes(pdf.output())
