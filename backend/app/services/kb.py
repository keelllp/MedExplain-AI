"""Knowledge-base retrieval (deterministic, canonical-name keyed).

For a known biomarker we know exactly which KB doc + section is relevant, so a keyed
lookup is more accurate than vector search. Returns the "what it measures" section plus
the directional ("why a value may be low/high") section, with citation metadata. The
optional semantic ChromaDB+bge index (rag extra) is reserved for free-text chat (Phase 7).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from app.core.config import settings

# canonical_name -> KB markdown file stem (knowledge_base/<stem>.md)
KB_MAP = {
    "hemoglobin": "hemoglobin", "hematocrit": "hemoglobin",
    "rbc": "rbc", "wbc": "wbc", "platelets": "platelets",
    "glucose": "glucose", "hba1c": "glucose",
    "cholesterol_total": "cholesterol", "hdl_cholesterol": "cholesterol",
    "ldl_cholesterol": "cholesterol", "triglycerides": "cholesterol",
    "vitamin_d": "vitamin_d",
    "iron": "iron", "ferritin": "iron",
    "tsh": "thyroid", "free_t4": "thyroid", "free_t3": "thyroid",
    "creatinine": "creatinine",
}


@dataclass
class Chunk:
    text: str
    doc_title: str
    section: str
    source_path: str


@lru_cache
def _load_docs() -> dict:
    docs: dict[str, dict] = {}
    kb_dir = settings.knowledge_base_path
    for stem in set(KB_MAP.values()):
        path = kb_dir / f"{stem}.md"
        if path.exists():
            docs[stem] = _parse(path.read_text(encoding="utf-8"), f"knowledge_base/{stem}.md")
    return docs


def _parse(md: str, source_path: str) -> dict:
    title_match = re.search(r"^#\s+(.+)$", md, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else source_path
    sections: dict[str, str] = {}
    for part in re.split(r"^##\s+", md, flags=re.MULTILINE)[1:]:
        lines = part.splitlines()
        if not lines or not lines[0].strip():  # skip a bare/edited '## ' heading
            continue
        sections[lines[0].strip()] = "\n".join(lines[1:]).strip()
    return {"title": title, "sections": sections, "source_path": source_path}


def _section_starting(sections: dict[str, str], prefix: str) -> tuple[str, str] | None:
    for heading, body in sections.items():
        if heading.lower().startswith(prefix):
            return heading, body
    return None


def loaded_docs() -> dict:
    """Public accessor for the parsed KB docs (used by the optional semantic index)."""
    return _load_docs()


def retrieve(canonical_name: str | None, direction: str | None = None) -> list[Chunk]:
    """Return the relevant KB chunks for a biomarker: 'what it measures' + the directional
    section. Empty list if the marker has no KB doc."""
    if not canonical_name:
        return []
    stem = KB_MAP.get(canonical_name)
    if stem is None:
        return []
    doc = _load_docs().get(stem)
    if doc is None:
        return []

    chunks: list[Chunk] = []
    what = _section_starting(doc["sections"], "what it measures")
    if what:
        chunks.append(Chunk(what[1], doc["title"], what[0], doc["source_path"]))

    if direction == "low":
        sec = _section_starting(doc["sections"], "why a value may be low")
    elif direction == "high":
        sec = _section_starting(doc["sections"], "why a value may be high")
    else:
        sec = None
    if sec:
        chunks.append(Chunk(sec[1], doc["title"], sec[0], doc["source_path"]))

    return chunks
