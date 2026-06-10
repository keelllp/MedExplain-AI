# API Specification — MedExplain AI

This document defines the complete HTTP API for MedExplain AI: a privacy-first, CPU-only educational assistant that helps users understand medical reports they upload. It is written to be near-implementable on the fixed stack (FastAPI + Python 3.12, Pydantic v2, SQLite, JWT auth) by a single developer. Enums, table names, and safety behavior here mirror `03-database-schema.md`, `01-architecture.md`, and `07-safety-and-compliance.md` exactly; where they appear to conflict, those documents and `00-design-review.md` are authoritative and this spec is kept in sync with them.

---

## 1. Conventions

### 1.1 Base URL and versioning

- All endpoints are served under the prefix **`/api/v1`**. (Examples below sometimes omit the prefix for brevity; the deployed path always includes it — e.g. `POST /api/v1/auth/login`.)
- The API speaks **JSON, UTF-8** only, except `POST /reports/upload` (which accepts `multipart/form-data`) and `POST /export` (which streams `application/pdf`).
- Request bodies must send `Content-Type: application/json` for JSON endpoints; responses set `Content-Type: application/json; charset=utf-8`.

### 1.2 Authentication — JWT bearer

- Auth is a **short-lived JWT access token** obtained from `POST /auth/login`. Protected endpoints require the header `Authorization: Bearer <token>`.
- The token payload carries only `sub` (the user `id`), `iat`, and `exp` — **no PHI, no email, no name** (per `07-safety-and-compliance.md` §5.3). The signing secret comes from the environment (`JWT_SECRET`), never committed.
- Default access-token lifetime: **60 minutes** (configurable). There is no refresh-token flow in the MVP; the client re-authenticates on expiry. Expired/invalid/missing tokens on a protected route → **401** with code `unauthorized`.
- **Owner-scoping is non-negotiable.** Every query for reports, biomarkers, findings, summaries, chat, and trends is filtered by the JWT's `user_id`. A request for a resource owned by another user returns **404** `not_found` (we prefer 404 over 403 for cross-owner resource IDs so existence is not leaked; 403 is reserved for authenticated-but-not-permitted actions such as a disallowed `cloud` mode switch).

#### Public vs. protected route table

| Method | Path | Auth |
|---|---|---|
| `POST` | `/auth/register` | Public |
| `POST` | `/auth/login` | Public |
| `GET` | `/health` | Public |
| `GET` | `/auth/me` | Protected |
| `POST` | `/auth/change-password` | Protected |
| `PATCH` | `/users/me` | Protected |
| `PATCH` | `/users/me/settings` | Protected |
| `DELETE` | `/users/me` | Protected |
| `POST` | `/reports/upload` | Protected |
| `POST` | `/reports/analyze` | Protected |
| `GET` | `/reports` | Protected |
| `GET` | `/reports/{id}` | Protected |
| `POST` | `/chat` | Protected |
| `GET` | `/chat/sessions` | Protected |
| `GET` | `/chat/sessions/{id}` | Protected |
| `GET` | `/chat/sessions/{id}/messages` | Protected |
| `GET` | `/trends` | Protected |
| `POST` | `/export` | Protected |

### 1.3 Standard error envelope

Every non-2xx response (except streamed-file failures that occur after headers are sent) uses one envelope:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Human-readable, PHI-free summary of what went wrong.",
    "details": [
      { "field": "email", "issue": "value is not a valid email address" }
    ]
  }
}
```

- `code` is a stable, machine-readable string drawn from the canonical set below. `message` is short and **PHI-free** (never echoes raw report content or raw exception text — per `07-safety-and-compliance.md`). `details` is optional and used mainly for `validation_error`.
- HTTP status is set on the response in addition to `code`.

#### Canonical error codes

| `code` | HTTP | Meaning |
|---|---|---|
| `validation_error` | 422 | Request body/query failed Pydantic validation. |
| `unauthorized` | 401 | Missing/invalid/expired token, or bad login credentials. |
| `forbidden` | 403 | Authenticated but action not permitted (e.g. `cloud` mode without a server key). |
| `not_found` | 404 | Resource does not exist or is not owned by the caller. |
| `conflict` | 409 | State conflict (e.g. email already registered, analyze while already processing). |
| `payload_too_large` | 413 | Upload > 20 MB or JSON body > 1 MB. |
| `unsupported_media_type` | 415 | Upload not PDF/JPG/PNG, or magic-byte check failed. |
| `rate_limited` | 429 | Login-attempt guard tripped. |
| `internal_error` | 500 | Unhandled server error (sanitized; no stack trace, no PHI). |

### 1.4 Pagination — `Page[T]`

List endpoints use **offset/limit** pagination and return a uniform envelope:

```json
{
  "items": [],
  "total": 0,
  "limit": 20,
  "offset": 0
}
```

- Query params: `limit` (default `20`, min `1`, max `100`) and `offset` (default `0`, min `0`).
- `total` is the unfiltered-by-page count for the owner-scoped query, so the client can render pagination controls.

### 1.5 Upload and body limits

- **Single-file upload, ≤ 20 MB.** `POST /reports/upload` accepts **exactly one** file (`multipart/form-data`, field name `file`) of type PDF/JPG/PNG (per D-SINGLEFILE). Larger → **413** `payload_too_large`.
- **Magic-byte validation.** The declared `Content-Type` and filename extension are **not** trusted. The server sniffs the leading bytes: `%PDF` for PDF, `FF D8 FF` for JPEG, `89 50 4E 47 0D 0A 1A 0A` for PNG. A mismatch (or any other type) → **415** `unsupported_media_type`. Accepted MIME values stored on `report_files.mime_type`: `application/pdf`, `image/jpeg`, `image/png`.
- **JSON body cap: 1 MB.** Any JSON request body over 1 MB → **413** `payload_too_large` (enforced by middleware before parsing).

### 1.6 Login-attempt guard (per D-RATELIMIT)

- There is **no Redis and no heavy per-IP brute-force machinery.** A **minimal, in-process** login-attempt guard tracks recent failed logins per email in an in-memory structure (valid because the backend runs a **single Uvicorn worker** — see `01-architecture.md`).
- After **5** consecutive failed logins for an email within a rolling **15-minute** window, further attempts return **429** `rate_limited` with a short back-off (e.g. `Retry-After: 60`) until the window clears or a success resets the counter. Owner-scoped data queries are not rate-limited.

### 1.7 The mandatory `disclaimer` field, `Citation` type, and `refused` flag

Three cross-cutting shapes appear throughout (aligned with `07-safety-and-compliance.md`):

- **`disclaimer` (string).** Every response that carries **explanatory prose** (analysis explanations, summaries, chat answers, refusals, export metadata) includes a **top-level `disclaimer` field** holding the canonical sentence: `"Consult a licensed healthcare professional for medical advice."` This is belt-and-suspenders: the same sentence is also embedded inside each explanation string by the server-side `ensure_disclaimer()`. The disclaimer is **server-enforced**, never trusted to the client or the model.
- **`Citation` type.** A knowledge-base source reference attached to an explanation or chat answer. Two shapes exist in the schema; the API normalizes per-marker/explanation citations to the `{ n, doc_title, section, source_path }` form (see `BiomarkerExplanationCitation`) and chat citations to the `{ doc, chunk_id, score }` form (see `ChatCitation`), mirroring the two `citations_json` columns in `03-database-schema.md`.
- **`refused` flag (boolean).** Responses from generation surfaces that can be safety-refused (`POST /chat`) carry `"refused": true|false`. When `true`, the `answer` is the templated safe refusal+reframe (no LLM answer was generated), and `citations` is empty. The input guard is best-effort English-keyword; the **output guard is authoritative** (`07-safety-and-compliance.md` §2).

---

## 2. Endpoint Summary

| # | Method | Path | Purpose | Success |
|---|---|---|---|---|
| 1 | `POST` | `/auth/register` | Create account | 201 |
| 2 | `POST` | `/auth/login` | Obtain JWT | 200 |
| 3 | `GET` | `/auth/me` | Current user (incl. `llm_mode`, `gemini_consent`) | 200 |
| 4 | `POST` | `/auth/change-password` | Change password (re-verify current) | 200 |
| 5 | `PATCH` | `/users/me` | Update profile (`full_name`) | 200 |
| 6 | `PATCH` | `/users/me/settings` | Set `llm_mode` (`cloud` records consent) | 200 |
| 7 | `DELETE` | `/users/me` | Delete account + all data, files, vectors | 204 |
| 8 | `POST` | `/reports/upload` | Upload one PDF/JPG/PNG (≤20 MB) | 201 |
| 9 | `POST` | `/reports/analyze` | Start analysis (async) | 202 |
| 10 | `GET` | `/reports` | List the user's reports (paged) | 200 |
| 11 | `GET` | `/reports/{id}` | Full report (status/progress or results) | 200 |
| 12 | `POST` | `/chat` | Ask a question (RAG, single LLM call) | 200 |
| 13 | `GET` | `/chat/sessions` | List chat sessions (paged) | 200 |
| 14 | `GET` | `/chat/sessions/{id}` | Session metadata | 200 |
| 15 | `GET` | `/chat/sessions/{id}/messages` | Messages in a session (paged) | 200 |
| 16 | `GET` | `/trends?biomarker=<canonical_name>` | Trend series + trend label | 200 |
| 17 | `POST` | `/export` | Stream a PDF report summary | 200 (stream) |

---

## 3. Shared Pydantic v2 Models

Enums are **mirrored exactly** from the revised DDL in `03-database-schema.md`.

```python
from __future__ import annotations
from enum import Enum
from typing import Generic, TypeVar, Optional, Literal
from pydantic import BaseModel, Field, EmailStr, ConfigDict

# ----- Enums (mirror the DDL CHECK constraints) -----

class ReportStatus(str, Enum):
    uploaded   = "uploaded"
    processing = "processing"      # never "analyzing"
    analyzed   = "analyzed"
    failed     = "failed"

class ReportType(str, Enum):
    blood        = "blood"          # generic blood report
    cbc          = "cbc"            # specific panel: complete blood count
    mri          = "mri"
    ct           = "ct"
    xray         = "xray"
    pathology    = "pathology"
    prescription = "prescription"
    discharge    = "discharge"
    other        = "other"

class FindingStatus(str, Enum):
    normal   = "normal"
    abnormal = "abnormal"

class Severity(str, Enum):
    normal   = "normal"
    mild     = "mild"
    moderate = "moderate"
    severe   = "severe"

class Direction(str, Enum):
    low    = "low"
    high   = "high"
    normal = "normal"               # "elevated" is display-only phrasing, never a value

class LLMMode(str, Enum):
    cloud   = "cloud"               # Gemini primary + Ollama fallback (consent + server key required)
    offline = "offline"             # Ollama-only then deterministic template; no network egress

class GenerationMode(str, Enum):
    gemini           = "gemini"
    ollama           = "ollama"
    offline_template = "offline_template"

class DoctorQuestionCategory(str, Enum):
    cause         = "cause"
    follow_up     = "follow-up"
    clarification = "clarification"

class ErrorCode(str, Enum):           # reports.error_code allowed set (sanitized, enumerated)
    ocr_failed        = "ocr_failed"
    extraction_failed = "extraction_failed"
    llm_unavailable   = "llm_unavailable"
    timeout           = "timeout"
    internal_error    = "internal_error"

# ----- Error envelope -----

class ErrorDetail(BaseModel):
    field: Optional[str] = None
    issue: str

class ErrorBody(BaseModel):
    code: str
    message: str
    details: Optional[list[ErrorDetail]] = None

class ErrorResponse(BaseModel):
    error: ErrorBody

# ----- Pagination -----

T = TypeVar("T")

class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)

# ----- Citations -----

class BiomarkerExplanationCitation(BaseModel):
    """Mirrors abnormal_findings.citations_json shape."""
    n: int
    doc_title: str
    section: str
    source_path: str

class ChatCitation(BaseModel):
    """Mirrors chat_messages.citations_json shape."""
    doc: str
    chunk_id: str
    score: float

# ----- Core domain models -----

DISCLAIMER = "Consult a licensed healthcare professional for medical advice."

class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: EmailStr
    full_name: Optional[str] = None
    llm_mode: LLMMode
    gemini_consent: bool                      # serialized from INTEGER 0/1
    gemini_consented_at: Optional[str] = None # ISO-8601 UTC
    created_at: str
    updated_at: str

class BiomarkerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    test_name: str                       # raw printed name, e.g. "Hb"
    canonical_name: Optional[str] = None # normalized key, e.g. "hemoglobin"
    value: Optional[float] = None        # numeric result (None if qualitative)
    value_text: Optional[str] = None     # qualitative result, e.g. "Positive"
    unit: Optional[str] = None           # raw printed unit, e.g. "g/dL"
    canonical_unit: Optional[str] = None # normalized unit
    reference_low: Optional[float] = None
    reference_high: Optional[float] = None
    reference_range_text: Optional[str] = None
    captured_at: Optional[str] = None

class AbnormalFindingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    biomarker_id: int
    status: FindingStatus
    severity: Severity
    direction: Direction
    rule_id: Optional[str] = None
    explanation: Optional[str] = None        # guarded prose (disclaimer embedded)
    citations: list[BiomarkerExplanationCitation] = []  # parsed from citations_json

class SummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    summary_text: str                    # guarded prose (disclaimer embedded)
    generation_mode: GenerationMode      # authoritative signal for the offline UI badge
    model_used: str                      # free-text provenance, e.g. "ollama/qwen2.5:3b"
    generated_at: str

class DoctorQuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    question_text: str
    category: DoctorQuestionCategory
    ordering: int

class ReportSummaryOut(BaseModel):
    """Row shape for GET /reports list."""
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    report_type: ReportType
    status: ReportStatus
    progress: int = Field(ge=0, le=100)
    error_code: Optional[ErrorCode] = None
    ocr_confidence: Optional[float] = None
    uploaded_at: str
    analyzed_at: Optional[str] = None
```

`gemini_consent` is exposed as a JSON boolean though stored as `INTEGER 0/1`; `bool(0)=False`, `bool(1)=True`.

---

## 4. Endpoints

For every endpoint: **purpose, auth, params, request model, response model + example, validation, errors.**

---

### 4.1 `POST /auth/register`

- **Purpose:** Create a new account. New users default to the privacy-first `llm_mode='offline'`, `gemini_consent=0`.
- **Auth:** Public.

**Request**

```python
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: Optional[str] = Field(default=None, max_length=200)
```

**Response — 201** (`UserOut`)

```json
{
  "id": 1,
  "email": "ada@example.com",
  "full_name": "Ada Lovelace",
  "llm_mode": "offline",
  "gemini_consent": false,
  "gemini_consented_at": null,
  "created_at": "2026-06-09T14:30:00Z",
  "updated_at": "2026-06-09T14:30:00Z"
}
```

- **Validation:** valid email (also satisfies the DDL `email LIKE '%_@_%.__%'` and ≤320 chars); password length 8–128; password hashed with bcrypt/argon2 before storage (never plaintext).
- **Errors:** `409 conflict` (email already registered), `413 payload_too_large` (>1 MB), `422 validation_error`, `500 internal_error`.

---

### 4.2 `POST /auth/login`

- **Purpose:** Verify credentials and return a JWT access token.
- **Auth:** Public.

**Request**

```python
class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
```

**Response — 200**

```python
class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int   # seconds until expiry, e.g. 3600
    user: UserOut
```

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "id": 1, "email": "ada@example.com", "full_name": "Ada Lovelace",
    "llm_mode": "offline", "gemini_consent": false, "gemini_consented_at": null,
    "created_at": "2026-06-09T14:30:00Z", "updated_at": "2026-06-09T14:30:00Z"
  }
}
```

- **Validation:** constant-time hash comparison; identical generic message for unknown email vs. wrong password (no account enumeration).
- **Errors:** `401 unauthorized` (bad credentials), `429 rate_limited` (login-attempt guard tripped — §1.6), `422 validation_error`, `500 internal_error`.

---

### 4.3 `GET /auth/me`

- **Purpose:** Return the authenticated user, including `llm_mode` and `gemini_consent` — backs the Profile page.
- **Auth:** Protected. **Params:** none.
- **Request model:** none.
- **Response — 200** (`UserOut`) — same shape as §4.1.
- **Errors:** `401 unauthorized`, `500 internal_error`.

---

### 4.4 `POST /auth/change-password`

- **Purpose:** Change password after re-verifying the current one.
- **Auth:** Protected.

**Request**

```python
class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)
```

**Response — 200**

```python
class MessageResponse(BaseModel):
    message: str
```

```json
{ "message": "Password updated." }
```

- **Validation:** `current_password` must match the stored hash; `new_password` 8–128 chars and must differ from current (else `422`). On success, existing tokens remain valid until expiry (no server-side session store in MVP).
- **Errors:** `401 unauthorized` (token invalid **or** `current_password` wrong), `422 validation_error`, `413 payload_too_large`, `500 internal_error`.

---

### 4.5 `PATCH /users/me`

- **Purpose:** Update editable profile fields (MVP: `full_name`).
- **Auth:** Protected.

**Request** (all fields optional; at least one required)

```python
class UpdateProfileRequest(BaseModel):
    full_name: Optional[str] = Field(default=None, max_length=200)
```

**Response — 200** (`UserOut`).

- **Validation:** `full_name` ≤200 chars; empty body → `422`. `email` is **not** mutable in the MVP.
- **Errors:** `401 unauthorized`, `422 validation_error`, `413 payload_too_large`, `500 internal_error`.

---

### 4.6 `PATCH /users/me/settings`

- **Purpose:** Set the per-user `llm_mode`. Setting `cloud` is the **consent action** and is permitted only when a **server Gemini key is configured**; on success it sets `gemini_consent=1` and stamps `gemini_consented_at=now` (per D-LLMMODE). Setting `offline` immediately stops all egress. The per-user `llm_mode` is authoritative over any global default.
- **Auth:** Protected.

**Request**

```python
class UpdateSettingsRequest(BaseModel):
    llm_mode: LLMMode
```

**Response — 200** (`UserOut`)

```json
{
  "id": 1, "email": "ada@example.com", "full_name": "Ada Lovelace",
  "llm_mode": "cloud",
  "gemini_consent": true,
  "gemini_consented_at": "2026-06-09T15:02:11Z",
  "created_at": "2026-06-09T14:30:00Z",
  "updated_at": "2026-06-09T15:02:11Z"
}
```

- **Validation:** `llm_mode ∈ {cloud, offline}`. Requesting `cloud` when **no server Gemini key is configured** → `403 forbidden` (code `forbidden`, message: "Cloud mode is not available on this server."). Switching to `cloud` records consent (`gemini_consent=1`, `gemini_consented_at=now`); switching back to `offline` leaves the historical consent timestamp intact but stops egress. Setting the same value is idempotent.
- **Errors:** `401 unauthorized`, `403 forbidden` (no server key), `422 validation_error`, `500 internal_error`.

---

### 4.7 `DELETE /users/me`

- **Purpose:** Permanently delete the account and **all** associated data: DB rows (cascading through `reports → report_files / biomarkers → abnormal_findings / summaries / doctor_questions`, plus `chat_sessions → chat_messages`), the user's **uploaded files on disk**, and their **ChromaDB vectors**. Leaves no orphaned PHI.
- **Auth:** Protected. **Params:** none. **Request model:** none (the JWT identifies the user).
- **Response — 204** No Content (empty body).
- **Validation:** the operation is owner-scoped to the JWT subject; idempotent on the (already-authenticated) caller.
- **Errors:** `401 unauthorized`, `500 internal_error` (any partial-cleanup failure is logged sanitized; the API does not leak which artifact failed).

---

### 4.8 `POST /reports/upload`

- **Purpose:** Upload **exactly one** medical report file and create the `reports` row (`status='uploaded'`, `progress=0`) plus its single `report_files` row (per D-SINGLEFILE). Does **not** start analysis.
- **Auth:** Protected.
- **Content-Type:** `multipart/form-data`.

**Request (form fields)**

| Field | Type | Required | Notes |
|---|---|---|---|
| `file` | binary | yes | Exactly one PDF/JPG/PNG, ≤ 20 MB. |
| `title` | string | no | ≤ 200 chars; defaults to `"Untitled report"`. |
| `report_type` | string | no | One of `ReportType`; defaults to `other`. The extractor may refine this during analysis (picks the most specific, e.g. `cbc` over `blood`). |

**Response — 201**

```python
class ReportUploadResponse(BaseModel):
    report_id: int
    status: ReportStatus          # "uploaded"
    original_filename: str
    mime_type: Literal["application/pdf", "image/jpeg", "image/png"]
    size_bytes: int
```

```json
{
  "report_id": 42,
  "status": "uploaded",
  "original_filename": "cbc_june.pdf",
  "mime_type": "application/pdf",
  "size_bytes": 581234
}
```

- **Validation:** exactly one `file` part (multiple files → `422`); size ≤ 20 MB (else `413`); **magic-byte sniff** must match an accepted type (else `415` — §1.5); stored under a randomized, non-guessable name **outside the web root**; original filename retained only as metadata.
- **Errors:** `401 unauthorized`, `413 payload_too_large`, `415 unsupported_media_type`, `422 validation_error` (missing/extra file, bad `report_type`), `500 internal_error`.

---

### 4.9 `POST /reports/analyze`

- **Purpose:** Kick off the asynchronous analysis pipeline for an uploaded report. Sets `status='processing'`, `progress=0`, enqueues the background job (single semaphore, cap=1), and returns immediately. The client then **polls `GET /reports/{id}`** for `status`/`progress`.
- **Auth:** Protected.

**Request**

```python
class AnalyzeRequest(BaseModel):
    report_id: int = Field(gt=0)
```

**Response — 202**

```python
class AnalyzeAcceptedResponse(BaseModel):
    report_id: int
    status: ReportStatus          # "processing"
    progress: int = Field(ge=0, le=100)  # 0 at enqueue
```

```json
{ "report_id": 42, "status": "processing", "progress": 0 }
```

- **Validation:** report must exist and be owned by the caller (`404` otherwise). Allowed from any non-`processing` status (`uploaded`, `failed`, or re-analyzing an `analyzed` report); an already-`processing` report is rejected with `409 conflict` (code `conflict`, message "Analysis already in progress."). Re-analysis resets `progress=0` and `error_code=NULL`. Progress advances at fixed checkpoints during the job: OCR/text-extraction `25` → extraction+normalization `50` → rules `70` → explanations `100` (per D-PROGRESS).
- **Errors:** `401 unauthorized`, `404 not_found`, `409 conflict`, `422 validation_error`, `500 internal_error`.

---

### 4.10 `GET /reports`

- **Purpose:** List the caller's reports, newest first, for the dashboard.
- **Auth:** Protected.

**Query params**

| Param | Type | Default | Notes |
|---|---|---|---|
| `limit` | int | 20 | 1–100 |
| `offset` | int | 0 | ≥0 |
| `status` | `ReportStatus` | — | Optional filter. |

**Response — 200** (`Page[ReportSummaryOut]`)

```json
{
  "items": [
    {
      "id": 42, "title": "CBC June", "report_type": "cbc",
      "status": "analyzed", "progress": 100, "error_code": null,
      "ocr_confidence": 0.97,
      "uploaded_at": "2026-06-09T14:30:00Z",
      "analyzed_at": "2026-06-09T14:31:12Z"
    },
    {
      "id": 41, "title": "Untitled report", "report_type": "other",
      "status": "failed", "progress": 25, "error_code": "ocr_failed",
      "ocr_confidence": null,
      "uploaded_at": "2026-06-08T09:10:00Z",
      "analyzed_at": null
    }
  ],
  "total": 2, "limit": 20, "offset": 0
}
```

- **Validation:** `limit`/`offset` bounds; invalid `status` → `422`. Owner-scoped via `idx_reports_user_uploaded`.
- **Errors:** `401 unauthorized`, `422 validation_error`, `500 internal_error`.

---

### 4.11 `GET /reports/{id}`

- **Purpose:** Fetch one report. While `processing`/`uploaded` it returns status + `progress` (poll target). When `analyzed` it returns the full payload: biomarkers (incl. `canonical_name`/`canonical_unit`), abnormal findings (incl. guarded `explanation` + parsed `citations`), the **latest** summary (incl. `generation_mode`), and ordered doctor questions. When `failed` it returns the sanitized `error_code`.
- **Auth:** Protected. **Path param:** `id` (int).

**Response model**

```python
class ReportDetailOut(BaseModel):
    id: int
    title: str
    report_type: ReportType
    status: ReportStatus
    progress: int = Field(ge=0, le=100)
    error_code: Optional[ErrorCode] = None
    ocr_confidence: Optional[float] = None
    uploaded_at: str
    analyzed_at: Optional[str] = None
    biomarkers: list[BiomarkerOut] = []
    findings: list[AbnormalFindingOut] = []
    summary: Optional[SummaryOut] = None        # latest summaries row, or None pre-analysis
    doctor_questions: list[DoctorQuestionOut] = []
    disclaimer: str = DISCLAIMER                 # present whenever explanatory prose is returned
```

**Example — analyzed**

```json
{
  "id": 42, "title": "CBC June", "report_type": "cbc",
  "status": "analyzed", "progress": 100, "error_code": null,
  "ocr_confidence": 0.97,
  "uploaded_at": "2026-06-09T14:30:00Z",
  "analyzed_at": "2026-06-09T14:31:12Z",
  "biomarkers": [
    {
      "id": 900, "test_name": "Hb", "canonical_name": "hemoglobin",
      "value": 9.1, "value_text": null, "unit": "g/dL", "canonical_unit": "g/dL",
      "reference_low": 13.0, "reference_high": 17.0,
      "reference_range_text": "13.0-17.0", "captured_at": "2026-06-08T00:00:00Z"
    },
    {
      "id": 901, "test_name": "Urine Protein", "canonical_name": "urine_protein",
      "value": null, "value_text": "Positive", "unit": null, "canonical_unit": null,
      "reference_low": null, "reference_high": null,
      "reference_range_text": "Negative", "captured_at": "2026-06-08T00:00:00Z"
    }
  ],
  "findings": [
    {
      "id": 700, "biomarker_id": 900, "status": "abnormal",
      "severity": "moderate", "direction": "low", "rule_id": "HGB_LOW_ADULT_M",
      "explanation": "Hemoglobin is the protein in red blood cells that carries oxygen. Your value of 9.1 g/dL is below the reference range (Moderate). A low value may be associated with several causes such as iron deficiency, but only a clinician can interpret your specific result. Consult a licensed healthcare professional for medical advice.",
      "citations": [
        { "n": 1, "doc_title": "Hemoglobin", "section": "Why it may be low", "source_path": "kb/hemoglobin.md" }
      ]
    },
    {
      "id": 701, "biomarker_id": 901, "status": "abnormal",
      "severity": "mild", "direction": "normal", "rule_id": "URINE_PROTEIN_UNEXPECTED",
      "explanation": "Urine protein is normally not detected. A result of Positive is unexpected and may be associated with several causes. Consult a licensed healthcare professional for medical advice.",
      "citations": []
    }
  ],
  "summary": {
    "id": 300,
    "summary_text": "This report includes a low hemoglobin result flagged as Moderate and an unexpected urine protein result flagged as Mild... Consult a licensed healthcare professional for medical advice.",
    "generation_mode": "ollama",
    "model_used": "ollama/qwen2.5:3b",
    "generated_at": "2026-06-09T14:31:12Z"
  },
  "doctor_questions": [
    { "id": 50, "question_text": "What might be causing my low hemoglobin?", "category": "cause", "ordering": 0 },
    { "id": 51, "question_text": "Do I need any follow-up tests?", "category": "follow-up", "ordering": 1 }
  ],
  "disclaimer": "Consult a licensed healthcare professional for medical advice."
}
```

**Example — still processing**

```json
{
  "id": 42, "title": "CBC June", "report_type": "cbc",
  "status": "processing", "progress": 50, "error_code": null,
  "ocr_confidence": null, "uploaded_at": "2026-06-09T14:30:00Z", "analyzed_at": null,
  "biomarkers": [], "findings": [], "summary": null, "doctor_questions": [],
  "disclaimer": "Consult a licensed healthcare professional for medical advice."
}
```

**Example — failed**

```json
{
  "id": 41, "title": "Untitled report", "report_type": "other",
  "status": "failed", "progress": 25, "error_code": "ocr_failed",
  "ocr_confidence": null, "uploaded_at": "2026-06-08T09:10:00Z", "analyzed_at": null,
  "biomarkers": [], "findings": [], "summary": null, "doctor_questions": [],
  "disclaimer": "Consult a licensed healthcare professional for medical advice."
}
```

- **Notes:** `direction` is one of `low|high|normal` only — the qualitative urine-protein finding uses `direction='normal'` with `status='abnormal'`, `severity='mild'` (rule-defined; per D-QUALITATIVE/D-DIRECTION). The `summary` is the single latest `summaries` row; the offline badge keys off `summary.generation_mode == 'offline_template'`. Both `explanation` and `summary_text` already contain the disclaimer (server-side `ensure_disclaimer()`), and the top-level `disclaimer` field is always present.
- **Errors:** `401 unauthorized`, `404 not_found` (missing or not owned), `500 internal_error`.

---

### 4.12 `POST /chat`

- **Purpose:** Ask one educational question. Performs **one** RAG-grounded LLM call per message (separate from report analysis). Optionally scoped to a report (`report_id` set → chat-with-report RAG; null → general educational chat). Persists the user turn and assistant turn to `chat_messages`; creates a `chat_sessions` row when `session_id` is omitted. The answer is routed by the user's `llm_mode` and passed through the **authoritative output guard** before return.
- **Auth:** Protected.

**Request**

```python
class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: Optional[int] = Field(default=None, gt=0)  # omit to start a new session
    report_id: Optional[int] = Field(default=None, gt=0)   # scope RAG to this report
```

**Response — 200**

```python
class ChatResponse(BaseModel):
    session_id: int
    message_id: int            # id of the persisted assistant turn
    answer: str                # guarded prose (disclaimer embedded)
    citations: list[ChatCitation] = []
    refused: bool = False
    generation_mode: GenerationMode
    disclaimer: str = DISCLAIMER
```

**Example — normal answer**

```json
{
  "session_id": 12,
  "message_id": 88,
  "answer": "Hemoglobin is the protein in red blood cells that carries oxygen. A value below the reference range may be associated with causes such as iron deficiency, among others. Consult a licensed healthcare professional for medical advice.",
  "citations": [
    { "doc": "Hemoglobin", "chunk_id": "hemoglobin#low-causes", "score": 0.82 }
  ],
  "refused": false,
  "generation_mode": "gemini",
  "disclaimer": "Consult a licensed healthcare professional for medical advice."
}
```

**Example — safety refusal** (input guard caught a diagnosis request; `refused=true`, no LLM answer generated, empty citations)

```json
{
  "session_id": 12,
  "message_id": 90,
  "answer": "I'm not able to tell you what disease you have — I'm an educational assistant, not a doctor, and I can't diagnose conditions. Here's what I can help with instead: I can explain what a marker is and what an out-of-range value can generally be associated with, and suggest questions to ask your doctor. Consult a licensed healthcare professional for medical advice.",
  "citations": [],
  "refused": true,
  "generation_mode": "offline_template",
  "disclaimer": "Consult a licensed healthcare professional for medical advice."
}
```

**Example — offline degradation** (user in `offline` mode, Ollama unavailable → deterministic template floor)

```json
{
  "session_id": 12,
  "message_id": 91,
  "answer": "Based on the knowledge base, hemoglobin carries oxygen in the blood, and a low value can be associated with several general causes. I'm currently running in offline mode without a language model available, so this is a brief templated explanation. Consult a licensed healthcare professional for medical advice.",
  "citations": [
    { "doc": "Hemoglobin", "chunk_id": "hemoglobin#what-it-is", "score": 0.79 }
  ],
  "refused": false,
  "generation_mode": "offline_template",
  "disclaimer": "Consult a licensed healthcare professional for medical advice."
}
```

- **Validation:** `message` 1–4000 chars (and the 1 MB JSON cap). If `session_id` is given it must exist and be owned by the caller (else `404`); if `report_id` is given it must exist, be owned, and ideally be `analyzed` (else `404`/`409`). The input guard (best-effort, English-keyword) may short-circuit to a refusal; the output guard (`check_output()` + `ensure_disclaimer()`) is authoritative and runs on **every** path including the template floor.
- **Errors:** `401 unauthorized`, `404 not_found` (session/report not owned), `409 conflict` (report not analyzable), `413 payload_too_large`, `422 validation_error`, `429 rate_limited` (only if a generation rate guard is configured; not required by MVP), `500 internal_error`.

---

### 4.13 `GET /chat/sessions`

- **Purpose:** List the caller's chat sessions, newest activity first.
- **Auth:** Protected.

**Query params:** `limit` (default 20, 1–100), `offset` (default 0), optional `report_id` filter (int; pass to list sessions tied to a report).

**Response model**

```python
class ChatSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    report_id: Optional[int] = None   # null = general chat
    title: str
    created_at: str
    updated_at: str
```

**Response — 200** (`Page[ChatSessionOut]`)

```json
{
  "items": [
    { "id": 12, "report_id": 42, "title": "Questions about my CBC", "created_at": "2026-06-09T15:00:00Z", "updated_at": "2026-06-09T15:06:00Z" },
    { "id": 7, "report_id": null, "title": "New chat", "created_at": "2026-06-01T10:00:00Z", "updated_at": "2026-06-01T10:02:00Z" }
  ],
  "total": 2, "limit": 20, "offset": 0
}
```

- **Errors:** `401 unauthorized`, `422 validation_error`, `500 internal_error`.

---

### 4.14 `GET /chat/sessions/{id}`

- **Purpose:** Fetch one chat session's metadata.
- **Auth:** Protected. **Path param:** `id` (int).
- **Request model:** none.
- **Response — 200** (`ChatSessionOut`).

```json
{ "id": 12, "report_id": 42, "title": "Questions about my CBC", "created_at": "2026-06-09T15:00:00Z", "updated_at": "2026-06-09T15:06:00Z" }
```

- **Errors:** `401 unauthorized`, `404 not_found` (missing or not owned), `500 internal_error`.

---

### 4.15 `GET /chat/sessions/{id}/messages`

- **Purpose:** Fetch the messages in a session, oldest first (chronological for rendering).
- **Auth:** Protected. **Path param:** `id` (int). **Query params:** `limit` (default 50, 1–100), `offset` (default 0).

**Response model**

```python
class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    role: Literal["user", "assistant"]
    content: str                       # assistant turns are guarded prose
    citations: list[ChatCitation] = [] # populated on assistant turns from citations_json
    created_at: str
```

**Response — 200** (`Page[ChatMessageOut]`)

```json
{
  "items": [
    { "id": 87, "role": "user", "content": "What does low hemoglobin mean?", "citations": [], "created_at": "2026-06-09T15:05:40Z" },
    { "id": 88, "role": "assistant",
      "content": "Hemoglobin is the protein in red blood cells that carries oxygen... Consult a licensed healthcare professional for medical advice.",
      "citations": [ { "doc": "Hemoglobin", "chunk_id": "hemoglobin#low-causes", "score": 0.82 } ],
      "created_at": "2026-06-09T15:05:43Z" }
  ],
  "total": 2, "limit": 50, "offset": 0
}
```

- **Validation:** session must exist and be owned by the caller. Ordered via `idx_chat_messages_session_created`.
- **Errors:** `401 unauthorized`, `404 not_found`, `422 validation_error`, `500 internal_error`.

---

### 4.16 `GET /trends`

- **Purpose:** Return a time-ordered numeric series for **one biomarker** across all of the caller's reports, for the Trend Dashboard, plus a deterministic trend label. The query parameter is **`biomarker`** — a **`canonical_name`** string (per D-TRENDS-PARAM), so synonyms (Hb/HGB/Hemoglobin) collapse onto one series.
- **Auth:** Protected.

**Query params**

| Param | Type | Required | Notes |
|---|---|---|---|
| `biomarker` | string | yes | A `canonical_name`, e.g. `hemoglobin`. The selector lists distinct `canonical_name` values with ≥2 numeric points. |

**Response model**

```python
class TrendPoint(BaseModel):
    report_id: int
    point_time: str                  # COALESCE(captured_at, uploaded_at), ISO-8601
    value: float                     # numeric points only (value IS NOT NULL)
    unit: Optional[str] = None
    canonical_unit: Optional[str] = None
    reference_low: Optional[float] = None
    reference_high: Optional[float] = None
    severity: Optional[Severity] = None
    direction: Optional[Direction] = None

class TrendResponse(BaseModel):
    biomarker: str                   # the canonical_name queried
    points: list[TrendPoint]
    trend: Literal["improving", "worsening", "stable", "insufficient_data"]
    disclaimer: str = DISCLAIMER
```

**Response — 200**

```json
{
  "biomarker": "hemoglobin",
  "points": [
    { "report_id": 30, "point_time": "2026-03-01T00:00:00Z", "value": 8.4, "unit": "g/dL", "canonical_unit": "g/dL", "reference_low": 13.0, "reference_high": 17.0, "severity": "severe", "direction": "low" },
    { "report_id": 42, "point_time": "2026-06-08T00:00:00Z", "value": 9.1, "unit": "g/dL", "canonical_unit": "g/dL", "reference_low": 13.0, "reference_high": 17.0, "severity": "moderate", "direction": "low" }
  ],
  "trend": "improving",
  "disclaimer": "Consult a licensed healthcare professional for medical advice."
}
```

- **Query (mirrors `03-database-schema.md`):** `WHERE r.user_id=:user_id AND b.canonical_name=:biomarker AND b.value IS NOT NULL ORDER BY point_time ASC`, joining `reports` and left-joining `abnormal_findings`, resolved by `idx_biomarkers_canonical_report`.
- **Trend label (deterministic, not LLM):** computed purely from the series relative to the reference band — e.g. distance-from-nearest-bound of the first vs. last numeric point. Moving toward the in-range band → `improving`; away from it → `worsening`; negligible change → `stable`; fewer than 2 numeric points → `insufficient_data`. This is a directional indicator, **not** a clinical judgment, so it carries the `disclaimer` and never asserts health status.
- **Validation:** `biomarker` required and non-empty (`422` if missing). An unknown/never-seen canonical name returns `200` with empty `points` and `trend="insufficient_data"`.
- **Errors:** `401 unauthorized`, `422 validation_error`, `500 internal_error`.

---

### 4.17 `POST /export`

- **Purpose:** Generate and **stream** a PDF summary of a report (analysis, findings, summary, doctor questions). Per D-EXPORT-CHAT the PDF **excludes raw chat by default**; the full disclaimer block appears on **every page**.
- **Auth:** Protected.
- **Produces:** `application/pdf` (streamed; `Content-Disposition: attachment; filename="medexplain-report-{id}.pdf"`).

**Request**

```python
class ExportRequest(BaseModel):
    report_id: int = Field(gt=0)
    include_chat: bool = False        # default False (D-EXPORT-CHAT); if True, each included
                                      # chat turn is re-run through check_output() before embedding
```

**Response — 200:** binary PDF stream (not JSON). On success the response body is the file; no JSON envelope.

- **Validation:** report must exist, be owned by the caller, and be `analyzed` (else `404`/`409 conflict` "Report is not analyzed yet."). If `include_chat=true`, only guarded chat turns are embedded (each re-passed through `check_output()`); the disclaimer block is asserted present on every page before the file is returned.
- **Errors (JSON envelope, before streaming begins):** `401 unauthorized`, `404 not_found`, `409 conflict` (not analyzed), `422 validation_error`, `413 payload_too_large`, `500 internal_error`. (A failure after streaming has started terminates the stream; clients should treat a truncated download as a failed export.)

---

## 5. Schema ↔ API Consistency Cross-Reference

Every API field traces back to a column/enum in `03-database-schema.md`.

| API model / field | DB table.column | Enum / constraint mirrored |
|---|---|---|
| `UserOut.email` | `users.email` | UNIQUE, `email LIKE '%_@_%.__%'`, ≤320 |
| `UserOut.full_name` | `users.full_name` | — |
| `UserOut.llm_mode` | `users.llm_mode` | `LLMMode ∈ {cloud, offline}`; default `offline` |
| `UserOut.gemini_consent` (bool) | `users.gemini_consent` (INTEGER 0/1) | `CHECK IN (0,1)` |
| `UserOut.gemini_consented_at` | `users.gemini_consented_at` | nullable ISO-8601 |
| `ReportSummaryOut/ReportDetailOut.status` | `reports.status` | `ReportStatus ∈ {uploaded, processing, analyzed, failed}` |
| `…report_type` | `reports.report_type` | `ReportType` 9-value enum; `cbc` more specific than `blood` |
| `…progress` | `reports.progress` | `CHECK BETWEEN 0 AND 100`; checkpoints 25/50/70/100 |
| `…error_code` | `reports.error_code` | `ErrorCode` ∈ {ocr_failed, extraction_failed, llm_unavailable, timeout, internal_error}; sanitized, no PHI |
| `…ocr_confidence` | `reports.ocr_confidence` | `0 ≤ x ≤ 1`, nullable |
| `ReportUploadResponse.mime_type` | `report_files.mime_type` | `CHECK IN ('application/pdf','image/jpeg','image/png')` |
| `…size_bytes` | `report_files.size_bytes` | `≥ 0`, ≤ 20 MB at API |
| `BiomarkerOut.test_name` / `unit` | `biomarkers.test_name` / `unit` | raw printed values |
| `BiomarkerOut.canonical_name` / `canonical_unit` | `biomarkers.canonical_name` / `canonical_unit` | normalized keys; nullable |
| `BiomarkerOut.value` / `value_text` | `biomarkers.value` / `value_text` | `CHECK (value OR value_text NOT NULL)` |
| `BiomarkerOut.reference_low/high/_text` | `biomarkers.reference_low/high/reference_range_text` | `low ≤ high` |
| `AbnormalFindingOut.status` | `abnormal_findings.status` | `FindingStatus ∈ {normal, abnormal}` |
| `AbnormalFindingOut.severity` | `abnormal_findings.severity` | `Severity ∈ {normal, mild, moderate, severe}` |
| `AbnormalFindingOut.direction` | `abnormal_findings.direction` | `Direction ∈ {low, high, normal}` (no `elevated`) |
| `AbnormalFindingOut.explanation` | `abnormal_findings.explanation` | guarded prose |
| `AbnormalFindingOut.citations` | `abnormal_findings.citations_json` | `[{n, doc_title, section, source_path}]` |
| `SummaryOut.summary_text` | `summaries.summary_text` | guarded prose (overall summary) |
| `SummaryOut.generation_mode` | `summaries.generation_mode` | `GenerationMode ∈ {gemini, ollama, offline_template}`; drives offline badge |
| `SummaryOut.model_used` | `summaries.model_used` | free-text provenance |
| `DoctorQuestionOut.category` | `doctor_questions.category` | `∈ {cause, follow-up, clarification}` |
| `DoctorQuestionOut.ordering` | `doctor_questions.ordering` | display order |
| `ChatSessionOut.report_id` | `chat_sessions.report_id` | nullable (general vs. report chat) |
| `ChatMessageOut.role` | `chat_messages.role` | `∈ {user, assistant}` |
| `ChatMessageOut.citations` / `ChatCitation` | `chat_messages.citations_json` | `[{doc, chunk_id, score}]` |
| `TrendPoint.*` | `biomarkers` ⋈ `reports` ⋈ `abnormal_findings` | trend query filters `canonical_name`, `value IS NOT NULL` |

## 6. Safety-Alignment Note

This API is the transport for the safety guarantees defined authoritatively in `07-safety-and-compliance.md`; it does not relax them.

- **Disclaimer is server-enforced and double-surfaced.** Every response carrying explanatory prose (`GET /reports/{id}`, `POST /chat`, `GET /trends`, and the embedded export metadata) includes a top-level `disclaimer` field **and** the same canonical sentence is embedded inside each `explanation`/`summary_text`/`answer` string by `ensure_disclaimer()` before persistence. No prose path bypasses the guard: LLM output, offline-template assembly, and rule-engine explanation text all pass `check_output()` + `ensure_disclaimer()` (D-GUARD-ALL-PROSE).
- **Output guard is authoritative; input guard is best-effort.** `POST /chat` returns a `refused` flag; when `true`, the body is the templated, guarded refusal+reframe and **no** LLM answer was generated. The input guard is English-keyword best-effort and its optional LLM stage **fails closed** on clinical objects (D-INPUT-GUARD-FAILCLOSED); the output guard is the load-bearing layer.
- **Per-user `llm_mode` governs egress.** `PATCH /users/me/settings` is the consent action: `cloud` is permitted only when a server Gemini key is configured and records `gemini_consent=1` + `gemini_consented_at=now`; `offline` (default) performs no network egress (D-LLMMODE). `generation_mode` on summaries/chat answers reports which path produced the prose, and the UI offline badge keys off `generation_mode='offline_template'` (D-GENMODE).
- **No PHI in errors or tokens.** The `ErrorResponse` envelope, `reports.error_code`, and JWT payloads are all sanitized: enumerated codes and PHI-free messages only — never raw exception text or report content.
- **Owner-scoping and account deletion.** Every query is filtered by the JWT `user_id`; cross-owner IDs return `404`. `DELETE /users/me` cascades all rows and additionally removes on-disk files and ChromaDB vectors, leaving no orphaned PHI.
- **Export carries the full disclaimer block on every page and excludes raw chat by default** (D-EXPORT-CHAT).

Cross-references in this document use the canonical filenames defined in `00-design-review.md`: `01-architecture.md`, `02-folder-structure.md`, `03-database-schema.md`, `05-ui-wireframes.md`, `06-roadmap.md`, `07-safety-and-compliance.md`, `08-rag-design.md`, `09-review-resolution.md`.
