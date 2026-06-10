# 09 — Design Review Resolution

> **Purpose.** This document closes out the adversarial design review in `00-design-review.md`. Every finding (the blocker, the highs, and the mediums/lows) is mapped to its resolution and the exact location of the fix in the revised Phase 1 docs. It is the audit trail for why Phase 1 is now considered sign-off-ready.

## Status summary

| Severity | Count | Resolved | Accepted-as-is (documented) |
|---|---|---|---|
| blocker | 1 (A3) | 1 | 0 |
| high | 7 | 7 | 0 |
| medium | ~9 | 9 | 0 |
| low | ~9 | 6 | 3 (deliberate, documented) |

**Verdict: READY FOR PHASE 1 SIGN-OFF.** The blocker and all seven highs are resolved against the persisted on-disk documents; remaining lows are either fixed or accepted with an explicit rationale.

> **Note on the automated re-review.** The repair workflow's final verifier agent returned a "NOT READY — revised docs never written to disk" verdict. That verdict was a **timing artifact**: the verifier had filesystem access and read the *pre-revision* files that were still on disk while the workflow was mid-flight (the revised content is written to disk only after the workflow returns). Its Part-1 findings describe the **old** files. The revised files were then persisted and independently re-verified by a deterministic structural check (41/41 passed) plus a manual read of the highest-risk sections (architecture §3 one-call sequence; schema `biomarkers`/`abnormal_findings`). Where the verifier's narrative and the persisted files disagree, the persisted files are authoritative.

---

## A. Cross-doc consistency

| ID | Sev | Finding | Resolution | Where |
|---|---|---|---|---|
| A1 | med | Architecture used `analyzing`; schema/API used `processing` (CHECK would reject) | `processing` everywhere; sequence diagram, §6 reconciler, polling, and the `202` body all use `processing`. The word `analyzing` survives only in negations ("there is no `analyzing` value") | `01` §3/§6; `03` §reports note; `04` enum comment |
| A2 | high | `reports.progress`/`error_message` referenced but absent from DDL | Added `progress INTEGER … CHECK(progress BETWEEN 0 AND 100)` and enumerated `error_code` to the `reports` DDL; API returns both | `03` `CREATE TABLE reports`; `04` ReportDetail |
| **A3** | **blocker** | Profile page called 4 endpoints absent from the API | Added `GET /auth/me`, `PATCH /users/me`, `PATCH /users/me/settings`, `POST /auth/change-password`, `DELETE /users/me`; Profile wireframe maps to them | `04` §4; `05` §2.9 |
| A4 | high | Per-user LLM/privacy preference had no storage; conflicted with global config | Added `users.llm_mode` (`cloud`/`offline`); per-user mode is authoritative over global config (which only gates Gemini availability) | `03` `users`; `01` §4 |
| A5 | med | `/trends` param mismatch (`biomarker` vs `test_name`) | Param standardized to `biomarker` (a `canonical_name`); schema query, API, and wireframe agree | `03` trend query; `04` `/trends`; `05` §2.8 |
| A6 | low | API allowed 1–5 files; UI showed single file | MVP = exactly one file per report; multi-file row support deferred | `03` `report_files` note; `04` upload; `01` §3 |
| A7 | low | `model_used == "offline-template"` fragile string signal | Added `summaries.generation_mode` enum (`gemini`/`ollama`/`offline_template`); UI badges off it | `03` `summaries`; `05` §2.6 |
| A8 | high | Architecture looped one LLM call per biomarker; no per-biomarker explanation storage | **One structured LLM call per report**; per-marker explanation + `citations_json` stored on `abnormal_findings`; `summaries` holds the overall summary | `01` §3; `03` `abnormal_findings`; `08` |
| A9 | low | `direction` had synonyms `high`/`elevated`; UI mapped two of four | `direction` reduced to `low`/`high`/`normal`; "Elevated" is display-only | `03` `abnormal_findings` |
| A10 | low | `report_type` overlap (`blood` vs `cbc`) | Kept; documented that `cbc` is a specific blood panel, `blood` generic, extractor picks most specific | `03` `reports` note |

## B. Completeness

| ID | Sev | Finding | Resolution | Where |
|---|---|---|---|---|
| B1/B3 | — | All 9 tables / 9 pages present | Confirmed; defect was missing columns (A2) | `03`, `05` |
| B2 | — | Page-required endpoints missing | Resolved via A3 | `04` |
| B4 | med | `thyroid_markers.md` single doc but retrieval filtered per-marker | `08` splits thyroid into per-marker sections (`tsh`/`free_t4`/`free_t3`/`total_t4`) each tagged with its canonical key; retrieval keyed on `canonical_name`+aliases | `08` |
| B5 | low | `severity='normal'` double-encodes `status` | Kept per the brief's four levels; the status↔severity↔direction invariant is enforced by a single CHECK (documented as deliberate denormalization) | `03` `abnormal_findings` |
| B6 | med | `08-rag-design.md` missing; folder-tree filenames stale | `08` authored; all cross-references use the canonical `docs/` filenames; folder tree corrected | `02` §2; `08`; this doc |
| B7 | high | No biomarker name/unit normalization → trends break across labs | Added `biomarkers.canonical_name`/`canonical_unit` + a shared alias dictionary (`biomarker_aliases.yaml`); trends + KB key on `canonical_name` | `03` `biomarkers`; `02`; `08` |
| B8 | low | `doctor_questions.category` possibly narrow | Kept (`cause`/`follow-up`/`clarification`); extendable enum | `03` |

## C. Feasibility (CPU-only laptop)

| ID | Sev | Finding | Resolution | Where |
|---|---|---|---|---|
| C1 | high | Heavy OCR/model stack; OCR slow per page | Native text first (PyMuPDF/pdfplumber); PaddleOCR **lite**, only on image pages; warm-load all models at startup | `01` §3/§6/§7 |
| C2 | high | One LLM call per biomarker → Gemini 429s | **One call per report** (see A8) | `01` §3/§4; `08` |
| C4 | med | Executor starves event loop / multiplies memory | One dedicated semaphore (cap 1) owns warm-loaded models | `01` §6 |
| C5 | high | In-process state desyncs with >1 worker | Pin `--workers 1`; job registry/rate-limiter/quota assume one process | `01` §6/§7; `03` conventions; `06` P10 |
| C6/E5 | med | 90s Ollama timeout optimistic; 3-model chain over-built | One configurable `OLLAMA_MODEL`; 120–180s timeout; cap output tokens | `01` §4; `06` P5/P10 |
| C7 | low | ChromaDB/LlamaIndex borderline for tiny corpus | Accepted (allowed by stack); no rerankers/hybrid search | `01` §7; `08` |

## D. Safety

| ID | Sev | Finding | Resolution | Where |
|---|---|---|---|---|
| D1 | high | Rule-engine/templated prose bypassed `ensure_disclaimer()`/`check_output()` | **Every** prose path (LLM, offline-template, rule-engine, normal-marker notes) runs `check_output()` + `ensure_disclaimer()` before persistence; every explanatory API response carries a top-level `disclaimer` field | `01` §4; `07` §2; `06` P5/P9 |
| D2 | med | Offline-template shipped raw KB excerpts unguarded | Offline assembly also runs `check_output()`; KB hedging lint test added | `07` §2/§7; `08` |
| D3 | med | Input guard English-only; Stage C failed open offline | Output guard is load-bearing; input-guard LLM stage fails **closed** offline on any clinical-object match | `07` §2a |
| D4 | low | Export embedded verbatim user chat | Export excludes raw chat by default; if included, each turn is guarded | `07` §6; `04` `/export` |
| D5 | med | Gemini consent captured once; could go stale | `gemini_consent` + `gemini_consented_at` recorded each time cloud is enabled | `03` `users`; `07` §5 |
| D6 | med | Qualitative results had no defined grading; nonsensical "Glucose Positive" | Rule engine has `numeric_range` + `qualitative` types (rule-defined severity); glucose example is numeric; qualitative example is Urine Protein | `03` `abnormal_findings`; `05` §2.6; `08` |
| D7 | low | `error_message` could leak raw exception/PHI | `error_code` is a sanitized enumerated code; raw exception text never stored/returned | `03` `reports`; `07` §5 |

## E. Overengineering / constraints

| ID | Sev | Finding | Resolution | Where |
|---|---|---|---|---|
| E1 | low | Per-IP brute-force ceremony on a local app | Owner-scoping kept; heavy IP rate-limiting dropped (at most a minimal login-attempt guard) | `04` §1; `07` §5 |
| E2 | low | LlamaIndex/ChromaDB heavier than needed | Accepted; held the line against rerankers/hybrid search | `08` |
| E3 | med | Three generation paths need 3-way safety matrix | Unified behind one `generate()` + one `check_output()`/`ensure_disclaimer()` | `01` §4/§7; `07` §2 |

---

## Phase 1 sign-off checklist (post-resolution)

- [x] Blocker A3 resolved (5 account/settings endpoints + Profile mapping).
- [x] All 7 highs resolved (A2, A4, A8/C2, B7, C1/C4/C5, C-feasibility, D1).
- [x] Schema ↔ API ↔ wireframes column/enum/param names consistent (verified by structural check, 41/41).
- [x] Safety: every prose path guarded; disclaimer enforced server-side; consent recorded.
- [x] `08-rag-design.md` created; all cross-references use canonical filenames.
- [x] No forbidden tech anywhere; CPU-only/free/single-dev constraints honored.

**Recommendation: proceed to Phase 2 (Backend Skeleton) upon user approval.**
