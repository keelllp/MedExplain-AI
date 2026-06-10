# Folder Structure — MedExplain AI

> **Document scope.** Phase 1 design (no implementation). This document defines the complete monorepo layout for *MedExplain AI*, consistent with the System Architecture, Database Schema (9 tables), API surface, Safety design, and the fixed tech stack. It is optimized for a single-developer, CPU-only, local deployment: one single-worker FastAPI process, one SQLite file, one local ChromaDB directory, one uploads folder, a Next.js 15 frontend, and a Docker Compose stack. No microservice splitting.

---

## 1. Key Structural Decisions

Before the tree, three choices that shape it (each stated explicitly per the brief):

| Decision | Choice | Rationale |
|---|---|---|
| **DB access layer** | **SQLAlchemy 2.0 (ORM) + plain SQL init script.** Models live in `backend/app/models/`; schema is created from a hand-written `init.sql` (the canonical DDL from the schema doc) executed on first startup. | ORM gives type-safe queries, relationship loading, and the per-connection `PRAGMA foreign_keys=ON` / `WAL` wiring via a `connect` event listener — exactly what the schema doc requires. Keeping a literal `init.sql` keeps the canonical DDL auditable and lets a dev inspect/seed the DB without Python. |
| **Migrations** | **No Alembic.** Use a single idempotent `init.sql` + a tiny `seed.py`. | For a single-file SQLite DB owned by one developer with a fixed 9-table schema, Alembic is overengineering. Schema changes during Phase 1 are handled by editing `init.sql` and recreating the local DB. (Alembic can be added later if the schema ever needs versioned production migrations — the `db/` folder leaves room.) |
| **Repository pattern** | **Thin `crud/` modules**, one per aggregate, called by services/routers. | Keeps SQL/ORM access in one place per table group without the ceremony of a full repository abstraction layer. Single-dev maintainable. |

---

## 2. Top-Level Repository Tree

```text
medexplain-ai/
├── README.md                      # Project overview, local setup, "educational only" notice
├── docker-compose.yml             # Orchestrates backend, frontend, (optional) ollama services
├── .env.example                   # Template for all env vars (copy → .env, never commit .env)
├── .gitignore                     # Ignores .env, data/, vector_store/, __pycache__, node_modules, etc.
├── .dockerignore                  # Excludes data/, vector_store/, node_modules from build context
├── Makefile                       # Dev task runner: setup / dev / test / lint / seed / index-kb / clean
├── LICENSE
│
├── backend/                       # FastAPI + Python 3.12 (single process, --workers 1 — see §3)
│   ├── pyproject.toml             # Deps + tool config (ruff, black, pytest) — single source of truth
│   ├── requirements.txt           # Pinned runtime deps (generated from pyproject for Docker layer cache)
│   ├── README.md                  # Backend-specific run/test notes
│   ├── pytest.ini                 # Pytest config (testpaths, markers: unit/integration/safety)
│   ├── .env.example               # Backend-only env template (mirrors root, backend keys)
│   └── app/                       # (expanded in §3)
│
├── frontend/                      # Next.js 15 (App Router) + TS + Tailwind + shadcn/ui
│   ├── package.json
│   ├── next.config.ts
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   ├── postcss.config.mjs
│   ├── components.json            # shadcn/ui generator config
│   ├── .env.local.example         # NEXT_PUBLIC_API_BASE_URL, etc.
│   ├── .eslintrc.json
│   └── src/                       # (expanded in §4)
│
├── knowledge_base/                # 9 RAG source docs (markdown) — ingested into ChromaDB at startup
│   ├── README.md                  # Authoring conventions: stable ## headings per the RAG design
│   ├── hemoglobin.md
│   ├── rbc.md
│   ├── wbc.md
│   ├── platelets.md
│   ├── cholesterol.md
│   ├── glucose.md
│   ├── vitamin_d.md
│   ├── iron.md
│   └── thyroid_markers.md
│
├── data/                          # Local runtime state — GIT-IGNORED (created at runtime)
│   ├── .gitkeep
│   ├── medexplain.db              # SQLite database file (9 tables)
│   └── uploads/                   # Uploaded PDF/JPG/PNG — OUTSIDE web root, non-guessable names
│       └── .gitkeep               #   one file per report (MVP); e.g. {user_id}/{uuid4}.pdf — streamed only to owner
│
├── vector_store/                  # ChromaDB local persistent dir — GIT-IGNORED
│   ├── .gitkeep                   # Collection: medexplain_kb (bge-small-en-v1.5, 384-dim)
│   └── chroma.sqlite3             # (created by ChromaDB at runtime; + index segment dirs)
│
├── docker/                        # Build assets for the Compose stack
│   ├── backend.Dockerfile         # Python 3.12-slim; installs PaddleOCR/spaCy/Med models
│   ├── frontend.Dockerfile        # Node 20-alpine multi-stage build of the Next.js app
│   ├── ollama.entrypoint.sh       # Optional: pulls the ONE configured model ($OLLAMA_MODEL, e.g. qwen2.5:3b) on start
│   └── README.md                  # Build/run notes, model-download sizes, CPU expectations
│
├── tests/                         # Cross-cutting + frontend E2E (backend unit tests live in backend/, see §5)
│   ├── e2e/                       # Playwright end-to-end specs (drive the running stack)
│   │   ├── playwright.config.ts
│   │   ├── fixtures/              # Sample reports (sanitized CBC/lipid PDFs+images) for upload flows
│   │   │   ├── sample_cbc.pdf
│   │   │   └── sample_lipid.jpg
│   │   ├── auth.spec.ts           # register → login → JWT-protected route
│   │   ├── upload-analyze.spec.ts # upload → analyze poll → report viewer renders
│   │   ├── chat.spec.ts           # chat-with-report + refusal shows disclaimer
│   │   ├── trends.spec.ts         # multi-report trend chart renders
│   │   ├── account.spec.ts        # profile: change name/password, toggle llm_mode (consent), delete account
│   │   └── export.spec.ts         # PDF export downloads with disclaimer block
│   └── README.md                  # How to run E2E vs backend unit/integration suites
│
└── docs/                          # Design documents (this file lives here)
    ├── 00-design-review.md
    ├── 01-architecture.md
    ├── 02-folder-structure.md     # ← THIS DOCUMENT
    ├── 03-database-schema.md
    ├── 04-api-spec.md
    ├── 05-ui-wireframes.md
    ├── 06-roadmap.md
    ├── 07-safety-and-compliance.md
    ├── 08-rag-design.md
    └── 09-review-resolution.md
```

---

## 3. Backend Expanded — `backend/app/`

A clean, flat-as-possible FastAPI layout. **One single-worker process** (`uvicorn --workers 1`), versioned API under `api/v1/`, business logic in `services/`, table access in `crud/`, ORM models in `models/`, request/response shapes in `schemas/`.

```text
backend/app/
├── __init__.py
├── main.py                        # FastAPI app factory: mounts api/v1 routers, CORS, middleware,
│                                  #   startup hooks (init DB, run reconciler, ensure KB index,
│                                  #   warm-load OCR + spaCy/MedSpaCy + bge models once),
│                                  #   global exception handlers; pinned to a single Uvicorn worker
│
├── core/                          # App-wide infrastructure (no business logic)
│   ├── __init__.py
│   ├── config.py                  # Pydantic Settings: paths (DB, uploads, vector_store, KB),
│   │                              #   JWT secret/expiry, Gemini API key (server availability) + quota,
│   │                              #   Ollama host + single OLLAMA_MODEL, CORS origins
│   │                              #   (per-user llm_mode lives in DB and is AUTHORITATIVE over config)
│   ├── security.py                # JWT encode/decode, password hashing (bcrypt via passlib),
│   │                              #   get_current_user dependency, OAuth2 scheme
│   ├── db.py                      # SQLAlchemy engine + SessionLocal; connect-event listener wires
│   │                              #   PRAGMA foreign_keys=ON / journal_mode=WAL / busy_timeout=5000;
│   │                              #   get_db() FastAPI dependency
│   ├── logging.py                 # Logging config — PII-safe (no report text / values / LLM payloads / raw exceptions)
│   ├── concurrency.py             # ONE in-process semaphore (cap=1 concurrent analysis) owning the warm
│   │                              #   models + thread/process executor; in-process job registry,
│   │                              #   login-attempt guard, and daily quota counter (all assume one worker)
│   └── exceptions.py              # Custom exceptions + handlers (404/403 owner-scope, 422, 500)
│
├── models/                        # SQLAlchemy 2.0 ORM models — one file per table (9 tables)
│   ├── __init__.py                # Base (DeclarativeBase) + imports so metadata is complete
│   ├── user.py                    # users (incl. llm_mode, gemini_consent, gemini_consented_at)
│   ├── report.py                  # reports (status: uploaded→processing→analyzed|failed; progress; error_code)
│   ├── report_file.py             # report_files (stored_path, raw_ocr_text, extracted_tables_json)
│   ├── biomarker.py               # biomarkers (test_name/canonical_name, value/value_text, unit/canonical_unit, ref_low/high/text)
│   ├── abnormal_finding.py        # abnormal_findings (status/severity/direction∈low|high|normal, rule_id, explanation, citations_json)
│   ├── summary.py                 # summaries (summary_text, generation_mode, model_used, generated_at)
│   ├── doctor_question.py         # doctor_questions (question_text, category, ordering)
│   ├── chat_session.py            # chat_sessions (nullable report_id, ON DELETE SET NULL)
│   └── chat_message.py            # chat_messages (role, content, citations_json)
│
├── schemas/                       # Pydantic v2 request/response models (API contract)
│   ├── __init__.py
│   ├── auth.py                    # RegisterIn, LoginIn, TokenOut, ChangePasswordIn{current_password,new_password}
│   ├── user.py                    # UserOut (incl. llm_mode, gemini_consent), UserUpdate (full_name), SettingsUpdate (llm_mode)
│   ├── report.py                  # ReportCreateOut, ReportStatusOut (status+progress%+error_code), ReportDetailOut
│   ├── biomarker.py               # BiomarkerOut (raw + canonical), AbnormalFindingOut (explanation + citations)
│   ├── summary.py                 # SummaryOut (generation_mode + disclaimer guaranteed by guard)
│   ├── doctor_question.py         # DoctorQuestionOut
│   ├── chat.py                    # ChatIn, ChatMessageOut, ChatSessionOut, CitationOut
│   ├── trend.py                   # TrendSeriesOut (points + reference band + severity), keyed by canonical_name
│   ├── export.py                  # ExportRequestIn, ExportResultOut
│   └── common.py                  # Shared envelope incl. top-level `disclaimer` field for explanatory responses
│
├── api/                           # HTTP layer only — thin; delegates to services
│   ├── __init__.py
│   └── v1/
│       ├── __init__.py
│       ├── router.py              # Aggregates all v1 routers under /api/v1
│       └── routers/
│           ├── __init__.py
│           ├── auth.py            # POST /auth/register, POST /auth/login, GET /auth/me,
│           │                      #   POST /auth/change-password
│           ├── users.py           # PATCH /users/me (full_name), PATCH /users/me/settings (llm_mode;
│           │                      #   setting 'cloud' records consent → gemini_consent=1 + gemini_consented_at),
│           │                      #   DELETE /users/me (cascades rows + files + vectors)
│           ├── reports.py         # POST /reports/upload (EXACTLY ONE PDF/JPG/PNG ≤20MB), POST /reports/analyze,
│           │                      #   GET /reports/{id}, GET /reports (list), DELETE /reports/{id}
│           ├── chat.py            # POST /chat (single LLM call per message) (+ session/message listing)
│           ├── trends.py          # GET /trends?biomarker=<canonical_name> (series across user's reports)
│           └── export.py          # POST /export (PDF summary; disclaimer block on every page; no raw chat by default)
│
├── services/                      # Business logic / pipeline orchestration (the heart of the app)
│   ├── __init__.py
│   ├── analysis_pipeline.py       # Orchestrates the analyze job: doc→ocr(if needed)→extract→normalize→rules→rag→
│   │                              #   ONE structured LLM call→safety; progress checkpoints (OCR 25→extract 50→rules 70→explanations 100)
│   ├── doc_service.py             # PyMuPDF + pdfplumber: load file, page count, native embedded-text & table extract (preferred)
│   ├── ocr_service.py             # PaddleOCR (lite/mobile): runs ONLY on pages with no text layer; cleanup → text + cell boxes + confidence
│   ├── extraction_service.py      # spaCy + MedSpaCy + regex → {test_name, value, value_text, unit, ref_range}
│   ├── normalization_service.py   # Maps raw test_name/unit → canonical_name/canonical_unit via data/biomarker_aliases.yaml (incl. unit conversion)
│   ├── abnormality_service.py     # Deterministic rule engine: numeric_range + qualitative → status/severity/direction + rule_id
│   ├── rag_service.py             # LlamaIndex over ChromaDB; bge-small embed; per-biomarker retrieval filtered on canonical_name (incl. aliases)
│   ├── llm_service.py             # LLM router (per-user llm_mode authoritative): cloud → Gemini→Ollama→template; offline → Ollama→template; quota guard
│   ├── safety_service.py          # Thin orchestrator binding safety/ guards into every generate()/template/rule-prose path
│   └── export_service.py          # Renders SummaryOut + biomarkers + findings → PDF (disclaimer footer on every page)
│
├── safety/                        # Non-negotiable safety layer (controlling per 07-safety-and-compliance.md)
│   ├── __init__.py
│   ├── guard.py                   # check_input() (Stage A/B keyword + optional Stage C LLM, fail-closed),
│   │                              #   check_output() (authoritative), ensure_disclaimer() (idempotent) — pure functions
│   ├── triggers.yaml              # Config-driven keyword/regex seeds per intent category (dev-tunable)
│   ├── drug_lexicon.txt           # Curated drug-name / RxNorm-style stems for drug+dose detection
│   ├── refusal_templates.py       # Templated refusals (diagnosis/treatment/Rx/dose/self-harm) + reframe
│   └── disclaimer.py              # Canonical disclaimer sentence + full compliance block constants
│
├── llm/                           # LLM provider adapters + prompts (used by services/llm_service.py)
│   ├── __init__.py
│   ├── system_prompt.txt          # Single shared system prompt (Gemini + Ollama load same file)
│   ├── gemini_provider.py         # Gemini client (cloud-mode + consent + server key only; timeout 20s, 1 retry, quota counter)
│   ├── ollama_provider.py         # Ollama client (ONE configured OLLAMA_MODEL; timeout 120–180s; capped output tokens)
│   └── prompt_builder.py          # Assembles SYSTEM + CONTEXT(KB per marker) + REPORT DATA (all abnormal markers) → ONE structured call
│
├── rules/                         # Abnormality rule definitions (data, not code-heavy)
│   ├── __init__.py
│   └── abnormality_rules.yaml     # numeric_range ranges + severity bands + rule_ids (e.g. HGB_LOW_ADULT_M)
│                                  #   AND a qualitative_rules section (expected value sets + rule-defined severity, default 'mild')
│
├── data/                          # Committed reference data files (not runtime state)
│   ├── __init__.py
│   └── biomarker_aliases.yaml     # Synonym→canonical_name + unit→canonical_unit (+conversion factors);
│                                  #   used by BOTH extraction/normalization AND RAG retrieval (D-NORMALIZE)
│
├── crud/                          # Thin DB access — one module per aggregate (called by services/routers)
│   ├── __init__.py
│   ├── user.py                    # create_user, get_by_email, get_by_id, update_profile, set_settings (llm_mode + consent stamp), delete_user (cascade)
│   ├── report.py                  # create, set_status/progress/error_code, get_for_user (owner-scoped), list, delete
│   ├── report_file.py             # add_file, get_files, persist OCR text/tables
│   ├── biomarker.py               # bulk_insert (raw + canonical), list_by_report, trend_query on canonical_name (drives GET /trends)
│   ├── abnormal_finding.py        # upsert finding per biomarker (status/severity/direction, explanation, citations_json)
│   ├── summary.py                 # add_summary (records generation_mode: gemini|ollama|offline_template), get_latest_for_report
│   ├── doctor_question.py         # bulk_insert, list_by_report (ordered)
│   ├── chat_session.py            # create/get/list (owner-scoped, optional report scope)
│   └── chat_message.py            # add_message, list_by_session
│
└── db/                            # Schema + seed + maintenance (NO Alembic — see §1)
    ├── __init__.py
    ├── init.sql                   # Canonical DDL: 9 tables + CHECK constraints + all indexes (incl. biomarkers(canonical_name, report_id))
    ├── seed.py                    # Optional dev seed: a demo user + sample report (idempotent)
    ├── kb_indexer.py              # Idempotent ChromaDB ingest of knowledge_base/*.md (content-hash gated)
    └── reconcile.py               # Startup reconciler: stale 'processing' reports → 'failed' (error_code='timeout'); crash recovery
```

### 3a. Backend service-module responsibilities (one line each)

| Module | Responsibility |
|---|---|
| `services/analysis_pipeline.py` | Orchestrates the end-to-end analyze job and writes coarse progress checkpoints to `reports.status`/`progress` (OCR 25 → extraction 50 → rules 70 → explanations 100). |
| `services/doc_service.py` | Loads PDFs/images with PyMuPDF + pdfplumber; extracts native embedded text, page count, and tables — the preferred, OCR-free path for text-native PDFs. |
| `services/ocr_service.py` | Runs PaddleOCR (lite/mobile) **only** on pages with no text layer; image cleanup (deskew/denoise/binarize) → OCR text, cell boxes, and confidence. |
| `services/extraction_service.py` | Turns native-text/OCR/table output into raw structured biomarkers (`test_name, value, value_text, unit, reference range`) via spaCy/MedSpaCy + regex. |
| `services/normalization_service.py` | Normalizes raw `test_name`/`unit` to `canonical_name`/`canonical_unit` (with unit conversion) using `data/biomarker_aliases.yaml`, the shared dictionary also used by RAG retrieval. |
| `services/abnormality_service.py` | Deterministic rule engine supporting `numeric_range` (value vs ref_low/high) and `qualitative` (value_text vs expected set; rule-defined severity) to assign status/severity/direction + `rule_id`. |
| `services/rag_service.py` | Per-biomarker retrieval from ChromaDB (bge-small embeddings) via LlamaIndex, metadata-filtered on `canonical_name` (incl. aliases); returns grounded KB chunks + citations. |
| `services/llm_service.py` | The LLM router honoring the **authoritative per-user `llm_mode`**: cloud (Gemini→Ollama→template, only with consent + server key) vs offline (Ollama→template, no egress); timeouts, retries, daily quota guard; **exactly one structured generation call per report**. |
| `services/safety_service.py` | Binds the `safety/` guards around every prose path — LLM output, offline-template assembly, **and** rule-engine explanation text — so `check_output()` + `ensure_disclaimer()` are unbypassable. |
| `services/export_service.py` | Renders the latest summary, biomarkers, and findings into a PDF with the full disclaimer block on every page; no raw chat embedded by default. |

> **Safety boundary note (D-GUARD-ALL-PROSE):** every user-facing explanatory string — LLM output, offline-template assembly, **and** rule-engine explanation text — passes through `services/safety_service.py` → `safety/guard.py` (`check_output()` + `ensure_disclaimer()`) before persistence, and every API response carrying explanatory content also includes a top-level `disclaimer` field. The disclaimer is appended server-side by `ensure_disclaimer()`, never trusted to the LLM or the frontend. The input guard's optional LLM stage (Stage C) **fails closed** on any clinical object when the LLM is unavailable; the output guard is the authoritative layer.

---

## 4. Frontend Expanded — `frontend/src/`

Next.js 15 App Router with route groups: `(marketing)` for the public landing page, `(auth)` for login/signup, and `(app)` for authenticated, layout-shared pages. All required pages are present (Landing, Login, Signup, Dashboard, Upload, Report Viewer, Chat, Trends, Profile). The persistent `<DisclaimerFooter/>` is mounted in the shared layouts.

```text
frontend/src/
├── app/                           # App Router
│   ├── layout.tsx                 # Root layout: providers, fonts, global <DisclaimerFooter/>
│   ├── globals.css                # Tailwind base + theme tokens
│   ├── providers.tsx              # React Query client, theme, auth context providers
│   ├── page.tsx                   # "/" — falls into (marketing) landing (or redirect to dashboard if authed)
│   │
│   ├── (marketing)/
│   │   ├── layout.tsx             # Public chrome + disclaimer footer
│   │   └── page.tsx               # LANDING page (value prop + "educational only" notice)
│   │
│   ├── (auth)/
│   │   ├── layout.tsx             # Minimal centered auth layout + disclaimer footer
│   │   ├── login/page.tsx         # LOGIN  (POST /auth/login → store JWT)
│   │   └── signup/page.tsx        # SIGNUP (POST /auth/register; first-run educational-only acknowledgment)
│   │
│   └── (app)/                     # Authenticated area (route-guarded)
│       ├── layout.tsx             # App shell: sidebar/nav + header + persistent <DisclaimerFooter/>
│       ├── dashboard/page.tsx     # DASHBOARD — list of reports (status badges), entry points
│       ├── upload/page.tsx        # UPLOAD REPORT — single-file picker + upload-progress + trigger analyze
│       ├── reports/
│       │   └── [id]/page.tsx      # REPORT VIEWER — biomarkers table, findings (explanation+citations), summary, doctor questions
│       ├── chat/
│       │   ├── page.tsx           # CHAT — general educational chat (no report scope)
│       │   └── [sessionId]/page.tsx # CHAT — specific session (optionally report-scoped)
│       ├── trends/page.tsx        # TREND DASHBOARD — Recharts line charts per canonical biomarker
│       └── profile/page.tsx       # PROFILE — full_name, change password, llm_mode toggle (Cloud/Gemini ↔ Offline/Ollama) + consent, delete account
│
├── components/
│   ├── ui/                        # shadcn/ui primitives (generated) — button, card, dialog, table,
│   │                              #   input, badge, toast, tabs, dropdown-menu, skeleton, etc.
│   ├── layout/
│   │   ├── DisclaimerFooter.tsx   # Mandatory persistent disclaimer (all pages)
│   │   ├── AppSidebar.tsx
│   │   └── AppHeader.tsx
│   ├── reports/
│   │   ├── ReportCard.tsx         # Dashboard report tile + status badge
│   │   ├── StatusBadge.tsx        # uploaded/processing/analyzed/failed
│   │   ├── BiomarkerTable.tsx     # Value vs reference range + severity coloring (down=low, up=high)
│   │   ├── FindingBadge.tsx       # Normal/Mild/Moderate/Severe pill
│   │   ├── SummaryPanel.tsx       # Plain-language summary (with citations + disclaimer; offline badge off generation_mode)
│   │   ├── DoctorQuestions.tsx    # Suggested questions, grouped by category
│   │   └── AnalyzeProgress.tsx    # Polling progress bar (React Query refetchInterval; reads progress%/error_code)
│   ├── upload/
│   │   ├── FileDropzone.tsx       # Single-file PDF/JPG/PNG with client-side type/size guard (≤20MB)
│   │   └── UploadProgress.tsx     # Byte-upload progress (XHR/fetch progress)
│   ├── chat/
│   │   ├── ChatWindow.tsx
│   │   ├── MessageBubble.tsx      # User/assistant turns + citation chips
│   │   └── ChatComposer.tsx
│   ├── trends/
│   │   ├── TrendChart.tsx         # Recharts line + reference band shading + abnormal markers
│   │   └── TrendSelector.tsx      # Pick which canonical biomarker series to view (distinct canonical_name, ≥2 numeric points)
│   ├── account/
│   │   ├── ProfileForm.tsx        # Edit full_name (PATCH /users/me)
│   │   ├── ChangePasswordForm.tsx # POST /auth/change-password
│   │   ├── LlmModeToggle.tsx      # PATCH /users/me/settings — Cloud consent stamps gemini_consented_at
│   │   └── DeleteAccount.tsx      # DELETE /users/me (cascades rows + files + vectors)
│   └── common/
│       ├── ConfirmDialog.tsx
│       ├── EmptyState.tsx
│       └── ErrorBoundary.tsx
│
├── lib/
│   ├── api/
│   │   ├── client.ts              # fetch wrapper: base URL, JWT header injection, error normalization
│   │   ├── auth.ts                # register / login / me / change-password calls
│   │   ├── users.ts               # update profile / update settings (llm_mode) / delete account
│   │   ├── reports.ts             # upload / analyze / get / list / delete
│   │   ├── chat.ts                # send message / list sessions+messages
│   │   ├── trends.ts              # get trend series (by canonical_name biomarker param)
│   │   └── export.ts              # request PDF export (download)
│   ├── hooks/                     # React Query hooks (one per resource)
│   │   ├── useAuth.ts             # incl. useMe (current user: llm_mode, gemini_consent)
│   │   ├── useAccount.ts          # update profile / settings / change password / delete
│   │   ├── useReports.ts          # incl. useReportStatus with refetchInterval polling
│   │   ├── useChat.ts
│   │   ├── useTrends.ts
│   │   └── useExport.ts
│   ├── auth/
│   │   ├── token.ts               # JWT storage (httpOnly-cookie-friendly) + read/clear
│   │   └── guard.ts               # client-side route guard helper / middleware support
│   ├── types/                     # Shared TS types mirroring backend schemas (api contract)
│   │   ├── user.ts
│   │   ├── report.ts
│   │   ├── chat.ts
│   │   └── trend.ts
│   └── utils/
│       ├── format.ts              # units, dates, value formatting
│       └── severity.ts            # severity → color/label mapping
│
├── middleware.ts                  # Next.js middleware: redirect unauthenticated users from (app) routes
└── public/                        # Static assets (logo, favicon) — NOT user uploads
    └── logo.svg
```

> **Note on uploads vs `public/`.** User-uploaded reports are **never** placed in `frontend/public/` or any web-served directory. They live only in `data/uploads/` (backend, outside web root) and are streamed to the authenticated owner via the API — per `07-safety-and-compliance.md`'s file-handling rule.

---

## 5. Tests Layout

Backend unit/integration tests live **inside `backend/`** (so they share the Python env and import `app.*` directly); frontend end-to-end tests live in the top-level `tests/e2e/` (Playwright drives the running stack).

```text
backend/tests/
├── __init__.py
├── conftest.py                    # Fixtures: temp SQLite DB, test client, mocked LLM, sample OCR payloads
├── unit/
│   ├── test_security.py           # JWT encode/decode, password hashing, no-PHI-in-token
│   ├── test_normalization.py      # raw test_name/unit → canonical_name/canonical_unit via biomarker_aliases.yaml
│   ├── test_abnormality_rules.py  # numeric_range + qualitative → status/severity/direction (low|high|normal)
│   ├── test_extraction.py         # regex/NLP biomarker parsing on fixture native-text/OCR text
│   └── test_trend_query.py        # crud.biomarker trend query on canonical_name: ordering + reference band
├── integration/
│   ├── test_auth_api.py           # register/login/me/change-password happy + error paths
│   ├── test_account_api.py        # PATCH /users/me, PATCH /users/me/settings (consent stamp), DELETE /users/me (cascade)
│   ├── test_reports_api.py        # upload (one file) → analyze (mocked pipeline) → get; owner-scope 403/404; error_code on failure
│   ├── test_chat_api.py           # /chat returns disclaimer; citations populated
│   ├── test_trends_api.py         # GET /trends?biomarker=<canonical_name> series shape
│   └── test_export_api.py         # PDF contains full disclaimer block on every page; no raw chat by default
└── safety/
    └── test_safety_guard.py       # The §7 safety checklist: input refuse/allow, Stage C fail-closed,
                                   #   output rewrite/block, all-prose-guarded (LLM/template/rule-engine),
                                   #   KB hedging lint, disclaimer idempotency, provider parity, offline no-egress
```

```text
tests/e2e/                         # (shown in §2) Playwright specs that exercise the live UI + API
```

> **Why split this way.** Backend tests need `app` imports and a Python toolchain → they sit next to the code. Playwright E2E is a separate Node toolchain and a cross-cutting black-box of the whole stack → it sits at the repo root in `tests/e2e/`. The `pytest.ini` `testpaths` points at `backend/tests`; Playwright config points at `tests/e2e`.

---

## 6. Where Persistent State Lives (summary)

| Artifact | Location | Git status | Notes |
|---|---|---|---|
| SQLite database (9 tables) | `data/medexplain.db` | ignored | Single file; created from `backend/app/db/init.sql` on first startup. |
| Uploaded reports (PDF/JPG/PNG) | `data/uploads/{user_id}/{uuid}.ext` | ignored | Outside web root; non-guessable names; one file per report (MVP); streamed only to owner. |
| ChromaDB vector store | `vector_store/` (collection `medexplain_kb`) | ignored | `bge-small-en-v1.5`, 384-dim; ingested by `db/kb_indexer.py`. |
| Knowledge base (9 markdown docs) | `knowledge_base/*.md` | committed | Source of truth for RAG; re-embedded only when content hash changes; linted for hedged language. |
| Abnormality rules | `backend/app/rules/abnormality_rules.yaml` | committed | Drives the deterministic engine: `numeric_range` ranges/severity bands + a `qualitative_rules` section. |
| Biomarker alias / normalization dictionary | `backend/app/data/biomarker_aliases.yaml` | committed | Synonym→canonical_name + unit→canonical_unit (+conversion); shared by extraction and RAG. |
| Safety triggers / lexicons / system prompt | `backend/app/safety/triggers.yaml`, `safety/drug_lexicon.txt`, `llm/system_prompt.txt` | committed | Dev-tunable without code changes. |
| Secrets (Gemini key, JWT secret) | `.env` (from `.env.example`) | ignored | Injected by Docker Compose at runtime; never committed. The server Gemini key only decides whether cloud is *available*; per-user `llm_mode` is authoritative. |
| Dockerfiles | `docker/backend.Dockerfile`, `docker/frontend.Dockerfile` | committed | Referenced by `docker-compose.yml`. |

---

## 7. Docker Compose Service Map (for context)

```text
docker-compose.yml services:
├── backend     # build: docker/backend.Dockerfile
│               # command: uvicorn ... --workers 1   (single worker is load-bearing — see §3 / 01-architecture.md)
│               # mounts: ./data, ./vector_store, ./knowledge_base; reads .env (Gemini key, JWT secret)
│               # exposes: 8000 (FastAPI/Uvicorn)
├── frontend    # build: docker/frontend.Dockerfile
│               # env: NEXT_PUBLIC_API_BASE_URL → backend; exposes: 3000
└── ollama      # optional profile ("offline"): official ollama image, CPU-only
                # entrypoint pulls the ONE configured model ($OLLAMA_MODEL, e.g. qwen2.5:3b); exposes: 11434
```

> Gemini is a **cloud** provider reached over the network (no container) and is contacted only for users in `cloud` mode with consent and a configured server key. Ollama runs as an **optional** Compose profile and pulls a **single** configured model (`OLLAMA_MODEL`) — not a runtime multi-model chain — so users in offline mode download just one model and Gemini-only users download none. The backend is pinned to a **single Uvicorn worker** so the in-process semaphore (cap=1), job registry, login-attempt guard, and quota counter stay consistent. No Kubernetes, no message broker, no separate vector-DB service — ChromaDB and SQLite are embedded in the backend process and persist to mounted host directories.

---

## 8. Root File Responsibilities (one line each)

| File | Responsibility |
|---|---|
| `README.md` | Project overview, local quickstart, and the prominent "educational tool, not a medical device" notice. |
| `docker-compose.yml` | Defines the `backend` (single worker), `frontend`, and optional `ollama` (one model) services and their volume mounts/env. |
| `.env.example` | Documents every required env var (Gemini server key, JWT secret/expiry, paths, `OLLAMA_MODEL`, CORS). |
| `.gitignore` | Excludes `.env`, `data/`, `vector_store/`, `__pycache__/`, `node_modules/`, build artifacts. |
| `.dockerignore` | Keeps runtime state and `node_modules` out of the Docker build context. |
| `Makefile` | Single entry point for dev tasks: `setup`, `dev`, `test`, `lint`, `seed`, `index-kb`, `clean`. |
| `LICENSE` | Open-source license for the project. |
