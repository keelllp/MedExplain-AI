The review is written to `C:\Users\PC\OneDrive\Documents\Projects\Medical report interpreter\docs\00-design-review.md`. Below is the full document content (verbatim).

# 00 — Phase 1 Design Review (Consistency, Feasibility & Safety Critique)

> **Reviewer stance.** Adversarial. The goal is to surface real defects before implementation, not to validate the design. Findings are prioritized; each names exact files/columns/endpoints. A blunt sign-off verdict is at the end.
>
> **Note on team memory:** no `.mcp.json` token was reachable from this environment, so no prior-decision context was retrieved. Findings are based solely on the six design docs provided.

## Severity legend
- **blocker** — must fix before Phase 1 sign-off; broken contract, missing requirement, or safety hole.
- **high** — fix before build; will cause rework or a user-visible defect.
- **medium** — fix during build; under-specified or internally inconsistent.
- **low** — polish.

## A. Cross-Doc Consistency
- **A1 (medium):** Architecture doc still uses `analyzing` (diagrams, §6 reconciler, polling text) while schema/API/UI use `processing`; the schema CHECK would reject `analyzing`.
- **A2 (high):** `reports.progress` and `reports.error_message` are required by the API (`ReportListItem.progress`, `ReportDetail.progress/error_message`) and architecture §6, but **do not exist in the `reports` DDL**. Progress UX and crash-recovery are non-functional without them.
- **A3 (blocker):** Profile page (`05-ui-wireframes.md` §2.9) calls four endpoints absent from the API spec: `PATCH /users/me`, `PATCH /users/me/settings`, `POST /auth/change-password`, `DELETE /users/me`. The LLM toggle (safety §5.1) and account deletion (safety §5.2) depend on them.
- **A4 (high):** Per-user LLM/privacy preference (UI/architecture/safety) has **no `users` column**; also conflicts with the global `core/config.py LLM_PROVIDER`.
- **A5 (medium):** `/trends` param mismatch — API spec reads `biomarker`, wireframe sends `test_name`. Silent wrong-data bug.
- **A6 (low):** API allows 1–5 multi-file upload; upload UI shows single file ("one report"). Reconcile.
- **A7 (low):** `summaries.model_used == "offline-template"` is a UI signal but a free-text column with no enum; exact-string branch is fragile.
- **A8 (medium):** Architecture sequence inserts `summaries`/`doctor_questions` **per biomarker in a loop**, but schema/API model **one summary per report** — and there is **no table for per-biomarker RAG explanations** shown in the Report Viewer.
- **A9 (low):** `direction` enum has synonyms `high`/`elevated`; UI maps only two of four.
- **A10 (low):** `report_type` overlaps (`blood` vs `cbc`).

## B. Completeness
- **B1:** All 9 tables present (defect is missing columns — A2).
- **B2:** 8 brief-required endpoints present; gap is page-required endpoints (A3).
- **B3:** All 9 pages present (minor chat routing reconcile, low).
- **B4 (medium):** `thyroid_markers.md` is one doc covering TSH/T3/T4, but per-biomarker retrieval filters `metadata.biomarker == "TSH"` etc. → silent retrieval misses for thyroid and any synonym (Hgb/Hemoglobin).
- **B5:** 4 severity levels + status present; `severity='normal'` double-encodes status (low).
- **B6 (medium):** Referenced `05-rag-design.md` and `06-frontend-design.md` were **not provided**; the most retrieval-critical decisions (B4, A8) are unreviewed. Folder-tree filenames don't match delivered files (`04-api-design.md` vs `04-api-spec.md`).
- **B7 (high):** No biomarker name/unit normalization design. Trends join on exact `test_name`; `Hemoglobin`/`HGB`/`Hb` and `10^3/uL`/`K/uL` won't group → trends silently break.
- **B8 (low):** `doctor_questions.category` enum may be too narrow.

## C. Feasibility (CPU-only laptop)
- **C1 (high):** PaddleOCR + PaddlePaddle + MedSpaCy + Torch + bge-small in one backend image ≈ 3–6 GB; OCR realistically 5–30s/page on CPU; `estimated_seconds: 40` is optimistic. Fix: warm-load models at startup, use mobile/lite OCR models, and prefer PyMuPDF/pdfplumber native text first (OCR only on image pages — biggest latency win).
- **C2 (high):** Gemini free tier is RPM/TPM-limited; one LLM call per biomarker = 10–15 calls/report → 429s. Daily-count guard ignores RPM/TPM. Fix: **one call per report**.
- **C4 (medium):** Thread executor still starves the event loop on CPU spikes (laggy polls); process executor multiplies model memory. Commit to one dedicated worker process owning the models.
- **C5 (high):** In-process semaphore/rate-limiter/job-registry desync if >1 Uvicorn worker. **Pin `--workers 1`** and state it.
- **C6 (medium):** 90s Ollama timeout optimistic for a 4B CPU model (~single-digit tok/s). Default the smallest model; cap output tokens; 120–180s timeout.
- **C7 (low):** ChromaDB/LlamaIndex over tens of chunks is borderline but allowed.

## D. Safety Gaps
- **D1 (high):** `abnormal_findings.explanation` and templated `doctor_questions` are user-facing prose that **never pass through `ensure_disclaimer()`/`check_output()`** — the "no prose bypasses the guard" claim is false. Either route them through the guard or narrow the claim to envelope level.
- **D2 (medium):** Offline-template path ships **raw KB excerpts** without the output guard's hedging; safety then rests on KB authoring. Run `check_output()` over the offline assembly and add a KB hedging lint/test.
- **D3 (medium):** Input guard is English-only regex/keyword; obfuscated/non-English/typo'd diagnosis requests pass; Stage C fails open offline for "low-risk" phrasings. Make the output guard the load-bearing layer and fail closed offline on any clinical-object match.
- **D4 (low):** `export include_chat` embeds verbatim user turns (may contain diagnostic strings) under the MedExplain header.
- **D5 (medium):** Gemini egress consent captured once at signup; switching to Gemini later in Profile re-uses stale consent; no `consented_at` record.
- **D6 (medium):** Qualitative `value_text` results (UI shows `Glucose Positive [Mild]`) have no numeric value/range, so the comparator can't assign severity — undefined rule + nonsensical example + implicit clinical grading.
- **D7 (low):** `error_message` (returned to client and, per A2, stored) could capture raw exception text containing PHI; must be a sanitized enumerated code.

## E. Overengineering / Constraints
- **E1 (low/pervasive):** Full multi-tenant isolation + anti-enumeration + per-IP brute-force limiting on a "single local user" app — pick one framing; owner-scoping is cheap to keep, the IP rate-limiter ceremony can go.
- **E2 (low):** LlamaIndex/ChromaDB heavier than needed for the corpus but allowed; hold the line against rerankers/hybrid search.
- **E3 (medium):** Three generation paths (Gemini/Ollama/offline) all need safety parity and a 3-way test matrix; unify them behind one `generate()` + one `check_output()`/`ensure_disclaimer()`.
- **E5 (low):** Pulling **three** Ollama models and running a runtime fallback chain is over-built; pull one configurable model.

## F. Top Risks (ranked)
1. **A3 (blocker)** — Profile page hits 4 non-existent endpoints (incl. safety-required toggle + privacy-required deletion).
2. **C2 + A8 (high)** — One LLM call per biomarker blows Gemini RPM / is minutes-per-report on Ollama; also a data-model gap.
3. **A2 (high)** — `reports.progress`/`error_message` missing from schema; progress + crash recovery non-functional.
4. **B7 (high)** — No name/unit normalization; trends (feature #8) silently break across labs.
5. **A4 + D5 (high)** — Per-user privacy preference has no storage; consent can drift.
6. **C1 + C4 + C5 (high)** — Heavy image, executor ambiguity, multi-worker desync.
7. **D1 (high)** — Rule-engine/templated prose bypasses the disclaimer guard.
8. **B4 (medium)** — Thyroid/synonym retrieval misses.
9. **D2 + D3 (medium)** — Unguarded offline excerpts; English-only/best-effort input guard.
10. **D6 (medium)** — Qualitative results graded with no defined rule.

## G. Verdict
**NOT ready for sign-off.** One blocker, several highs, and several overstated guarantees. The safety skeleton (centralized two-stage guard + mandatory disclaimer) and the schema/API cross-referencing are genuinely strong, but the per-biomarker LLM fan-out, missing schema columns/endpoints, and absent normalization layer would surface immediately in build.

**Must-fix:** A3 (add 4 account/settings endpoints) · C2+A8 (one LLM call per report; fix per-biomarker explanation storage) · A2 (add `progress`/`error_message` columns) · B7 (canonical name/unit normalization dictionary) · A4+D5 (`users.llm_mode` + consent) · C5 (pin single Uvicorn worker) · D1 (guard or narrow the disclaimer claim). **Should-fix:** A1, A5, A8, B4 (+ produce `05-rag-design.md` per B6), C1/C4/C6, D2/D3/D6/D7. Fix the blocker + seven highs and produce the RAG doc, and Phase 1 is sign-off-ready.
