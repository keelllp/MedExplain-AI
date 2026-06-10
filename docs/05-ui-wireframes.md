# 05 — UI Wireframes & Component Breakdown

> **Document scope.** Phase 1 design (no implementation) for *MedExplain AI*. This document specifies the screen layouts, shadcn/ui component inventory, user actions → API-endpoint mapping, and the empty / loading / error states for all nine required frontend pages. Every field shown maps to the database schema (`03-database-schema.md`) and the API contract (`04-api-spec.md`). The mandatory safety footer (`07-safety-and-compliance.md`) is rendered on every page and is the load-bearing UI element.

---

## 1. Design System

### 1.1 Stack & conventions

| Concern | Choice |
|---|---|
| Styling | TailwindCSS, utility-first, **mobile-first** (base styles target ~360px; `sm:`/`md:`/`lg:` progressively enhance) |
| Components | shadcn/ui (Radix primitives + Tailwind) — `Card`, `Button`, `Input`, `Label`, `Form`, `Tabs`, `Table`, `Dialog`, `Sheet`, `Toast` (Sonner), `Progress`, `Badge`, `Skeleton`, `Alert`, `DropdownMenu`, `Avatar`, `Separator`, `Tooltip`, `Select` |
| Data fetching | TanStack **React Query** — `useQuery` for reads (with `refetchInterval` polling on analyze status), `useMutation` for writes; query keys scoped by `user_id`/`report_id` |
| Charts | **Recharts** (`LineChart`, `ReferenceArea`, `ReferenceLine`, `Tooltip`, `Legend`) wrapped in the shadcn `Chart` container |
| Auth transport | JWT in memory + httpOnly refresh strategy; `Authorization: Bearer <token>` on every protected call; 401 → redirect to `/login` |
| Icons | `lucide-react` |
| Notifications | `Toast` (Sonner) for transient success/error; `Alert` for inline, persistent states |

### 1.2 Responsive behavior

- **Mobile (base):** single column, full-width cards, top nav collapses into a hamburger `Sheet` drawer, tables become stacked key/value rows or horizontally scrollable.
- **Tablet (`md:`):** two-column where useful (e.g., Report Viewer biomarkers + explanation side-by-side).
- **Desktop (`lg:`):** max content width `max-w-6xl mx-auto`, persistent left context where applicable, full data tables.

### 1.3 Global layout

```
┌──────────────────────────────────────────────────────────────┐
│  TOP NAV  (authed only)                                        │
│  [≡] MedExplain AI   Dashboard  Upload  Trends   [Avatar ▾]    │
├──────────────────────────────────────────────────────────────┤
│                                                                │
│                     <page content slot>                       │
│                     max-w-6xl, mx-auto, p-4 md:p-6             │
│                                                                │
├──────────────────────────────────────────────────────────────┤
│  ⚠ DisclaimerFooter  (EVERY page, authed or not)              │
│  MedExplain AI is an educational tool, not a medical device.   │
│  ... Consult a licensed healthcare professional for medical    │
│  advice.                                                       │
└──────────────────────────────────────────────────────────────┘
```

- **`<TopNav/>`** renders only when authenticated. Public pages (Landing, Login, Signup) show a minimal brand-only bar with `Login` / `Sign up` buttons.
- **`<DisclaimerFooter/>`** is a shared layout component mounted in the Next.js root layout. It is **always present on all 9 pages** and shows the full canonical block from the safety doc, ending in the mandatory sentence:
  > Consult a licensed healthcare professional for medical advice.
  This is the *UI* copy of the disclaimer; server-side `ensure_disclaimer()` independently guarantees it inside every generated explanation/chat answer/export, so removing the footer can never strip the disclaimer from content. Every API response carrying explanatory content also carries a top-level `disclaimer` field.
- **Avatar dropdown** (`DropdownMenu`): Profile, Settings (LLM mode toggle), Log out.
- **Global states:** `Skeleton` for first loads, `Toast` for mutation results, an `<ErrorBoundary>` + `Alert` for fetch failures with a Retry action.

---

## 2. Page Wireframes

### 2.1 Landing (`/`) — public

```
┌──────────────────────────────────────────────────────────────┐
│  MedExplain AI                          [ Log in ] [ Sign up ] │
├──────────────────────────────────────────────────────────────┤
│                                                                │
│        Understand your medical reports — in plain English.     │
│        Educational explanations, never a diagnosis.            │
│                                                                │
│              [  Get started  ]   [  Log in  ]                  │
│                                                                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ Upload   │  │ Auto-     │  │ Plain-    │  │ Trends    │      │
│  │ PDF/JPG  │  │ extract   │  │ language  │  │ over time │      │
│  │ /PNG     │  │ biomarkers│  │ + doctor  │  │ (charts)  │      │
│  │          │  │ & flags   │  │ questions │  │           │      │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
│                                                                │
│  ⓘ Local & private. Offline (Ollama) mode keeps data on-device.│
├──────────────────────────────────────────────────────────────┤
│  ⚠ DisclaimerFooter ... Consult a licensed healthcare          │
│     professional for medical advice.                           │
└──────────────────────────────────────────────────────────────┘
```

- **Components:** `Card` (feature tiles), `Button`, `Separator`, `Badge` ("Local & private").
- **Actions → endpoints:**
  - *Get started* → route to `/signup` (no API).
  - *Log in* → route to `/login` (no API).
- **States:** static page; no loading/empty/error.

---

### 2.2 Login (`/login`) — public

```
┌──────────────────────────────────────────────────────────────┐
│  MedExplain AI                                       [ Sign up ]│
├──────────────────────────────────────────────────────────────┤
│                 ┌──────────────────────────────┐               │
│                 │  Log in                       │               │
│                 │  ───────────────────────────  │               │
│                 │  Email                         │               │
│                 │  [_____________________]       │               │
│                 │  Password                      │               │
│                 │  [_____________________] [👁]   │               │
│                 │                                │               │
│                 │  [   Log in   ]                │               │
│                 │  ⓧ Invalid email or password   │  ← Alert      │
│                 │                                │               │
│                 │  No account?  Sign up →        │               │
│                 └──────────────────────────────┘               │
├──────────────────────────────────────────────────────────────┤
│  ⚠ DisclaimerFooter ... Consult a licensed healthcare prof.    │
└──────────────────────────────────────────────────────────────┘
```

- **Components:** `Card`, `Form` + `Input` + `Label`, `Button`, `Alert` (error), `Toast`.
- **Fields map to:** `users.email`, password (never stored client-side beyond submit).
- **Actions → endpoints:**
  - *Log in* → `POST /auth/login` `{email, password}` → returns JWT; store token, route to `/dashboard`. A minimal login-attempt guard applies a small back-off after repeated failures (no heavy per-IP rate limiting).
  - *Sign up →* → route to `/signup`.
- **States:**
  - *Loading:* button shows spinner + disabled while mutation pending.
  - *Error:* `401` → inline `Alert` "Invalid email or password." (never reveals which field).

---

### 2.3 Signup (`/signup`) — public

```
┌──────────────────────────────────────────────────────────────┐
│  MedExplain AI                                       [ Log in ] │
├──────────────────────────────────────────────────────────────┤
│             ┌────────────────────────────────────┐             │
│             │  Create your account                │             │
│             │  ────────────────────────────────   │             │
│             │  Full name (optional)                │             │
│             │  [______________________]            │             │
│             │  Email                               │             │
│             │  [______________________]            │             │
│             │  Password   (min 8 chars)            │             │
│             │  [______________________] [👁]        │             │
│             │  Confirm password                    │             │
│             │  [______________________]            │             │
│             │                                      │             │
│             │  ☐ I understand MedExplain AI is an  │  ← required │
│             │    educational tool, not a doctor.   │             │
│             │                                      │             │
│             │  [   Create account   ]              │             │
│             └────────────────────────────────────┘             │
├──────────────────────────────────────────────────────────────┤
│  ⚠ DisclaimerFooter ... Consult a licensed healthcare prof.    │
└──────────────────────────────────────────────────────────────┘
```

- **Components:** `Card`, `Form`/`Input`/`Label`, `Checkbox` (educational ack — required to enable submit), `Button`, `Alert`, `Toast`.
- **Fields map to:** `users.full_name`, `users.email`, password (hashed server-side per safety doc §5.3). New accounts default to `users.llm_mode = 'offline'` (privacy-first); there is no Gemini egress at signup.
- **Actions → endpoints:**
  - *Create account* → `POST /auth/register` `{email, password, full_name?}` → on success auto-login (or route to `/login`), record onboarding acknowledgment.
- **States:**
  - *Validation:* client-side — email format, password length, passwords match, educational-ack checkbox ticked.
  - *Error:* `409` email exists → inline `Alert` "An account with this email already exists."
  - *Loading:* submit disabled + spinner.

> The educational-only acknowledgment checkbox satisfies the safety doc's "First-run / onboarding" requirement. Cloud/Gemini egress consent is **not** bundled into signup — it is a separate, deliberate per-user action taken later in Profile (the `llm_mode` toggle, §2.9), which sets `gemini_consent=1` and stamps `gemini_consented_at`. Privacy-first default is offline.

---

### 2.4 Dashboard (`/dashboard`) — authed

```
┌──────────────────────────────────────────────────────────────┐
│  ≡ MedExplain AI   Dashboard  Upload  Trends      [Avatar ▾]   │
├──────────────────────────────────────────────────────────────┤
│  Your reports                              [ + Upload report ] │
│  ────────────────────────────────────────────────────────────│
│  [ Search… ]   Filter: (Type ▾) (Status ▾)                    │
│                                                                │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ Title            Type   Status     Uploaded     Flags    │  │
│  │ ─────────────────────────────────────────────────────── │  │
│  │ CBC – Apr 2026   CBC    ●Analyzed  2026-04-02   ▲3 🟠    │  │
│  │ Lipid panel      Blood  ●Analyzed  2026-03-10   ▲1 🟡    │  │
│  │ MRI knee         MRI    ◔Processing 2026-06-09  …  ⟳     │  │
│  │ Thyroid          Blood  ✕ Failed    2026-06-01  [Retry]  │  │
│  └────────────────────────────────────────────────────────┘  │
│  (rows clickable → Report Viewer)                              │
├──────────────────────────────────────────────────────────────┤
│  ⚠ DisclaimerFooter ... Consult a licensed healthcare prof.    │
└──────────────────────────────────────────────────────────────┘
```

- **Components:** `Table` (or stacked `Card` list on mobile), `Badge` (status: Analyzed/Processing/Failed; flag count + severity color), `Button`, `Input` (search), `DropdownMenu`/`Select` (filters), `Skeleton` (loading rows), `Toast`.
- **Fields map to:** `reports.title`, `reports.report_type`, `reports.status` (enum `uploaded`/`processing`/`analyzed`/`failed`), `reports.uploaded_at`; "Flags" = count of `abnormal_findings.status='abnormal'` for the report, colored by worst `severity`.
- **Actions → endpoints:**
  - *List reports* → `GET /reports` (list endpoint; owner-scoped by JWT `user_id`). React Query `refetchInterval` while any row is `processing`.
  - *Row click* → route `/reports/{id}` → `GET /reports/{id}`.
  - *+ Upload report* → route `/upload`.
  - *Retry* (on failed row) → `POST /reports/analyze {report_id}`.
- **States:**
  - *Empty:* no reports → centered `Card`: "No reports yet. Upload your first medical report." + `[ Upload report ]` CTA.
  - *Loading:* `Skeleton` table rows.
  - *Processing:* status `Badge` with spinner; auto-polls via React Query.
  - *Error:* fetch failure → `Alert` + `[Retry]`. On a `failed` report the friendly message is mapped client-side from the sanitized `reports.error_code` (e.g. `ocr_failed`, `extraction_failed`, `llm_unavailable`, `timeout`, `internal_error`).

---

### 2.5 Upload Report (`/upload`) — authed

```
┌──────────────────────────────────────────────────────────────┐
│  ≡ MedExplain AI   Dashboard  Upload  Trends      [Avatar ▾]   │
├──────────────────────────────────────────────────────────────┤
│  Upload a medical report                                       │
│  ────────────────────────────────────────────────────────────│
│  ┌──────────────────────────────────────────────────────────┐ │
│  │            ⬆  Drag & drop, or  [ Browse files ]           │ │
│  │       PDF, JPG, or PNG · max 20 MB · one file per report  │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                                │
│  Title  [ CBC – Apr 2026__________ ]   Type ( CBC ▾ )          │
│                                                                │
│  Selected: cbc_apr2026.pdf  (2 pages, 1.4 MB)        [ ✕ ]     │
│  Uploading ▓▓▓▓▓▓▓░░░░░  62%            ← Progress (byte upload)│
│                                                                │
│  [ Upload ]    [ Upload & analyze ]                            │
│                                                                │
│  ── after upload ──                                            │
│  ✓ Uploaded.  Analyzing…  ◔ OCR ▓▓▓░░ 25%   ← polling status   │
│  Stages: OCR → Extract → Rules → Explanations                  │
├──────────────────────────────────────────────────────────────┤
│  ⚠ DisclaimerFooter ... Consult a licensed healthcare prof.    │
└──────────────────────────────────────────────────────────────┘
```

- **Components:** dropzone `Card`, `Input` (title), `Select` (report_type — enum from schema: blood/cbc/mri/ct/xray/pathology/prescription/discharge/other; `cbc` is the specific blood panel, `blood` is generic), `Button`, `Progress` (upload bytes **and** analyze stage %), `Badge` (stage), `Alert`, `Toast`.
- **Single file per report (MVP):** the dropzone accepts **exactly one** PDF/JPG/PNG (≤20 MB); selecting a new file replaces the prior selection. There is no multi-file upload.
- **Fields map to:** `report_files.original_filename`, `mime_type` (`application/pdf`/`image/jpeg`/`image/png` only), `size_bytes`, `page_count`; `reports.title`, `reports.report_type`. The MVP creates exactly one `report_files` row.
- **Actions → endpoints:**
  - *Upload* → `POST /reports/upload` (multipart, JWT, exactly one file) → `201 {report_id}`. Browser/XHR drives the byte-upload `Progress` bar.
  - *Upload & analyze* → `POST /reports/upload` then `POST /reports/analyze {report_id}` → `202 {report_id, status:"processing"}`.
  - *Poll status* → `GET /reports/{id}` with React Query `refetchInterval ~2s` while status ∈ {uploaded, processing}; stops at `analyzed`/`failed`. Stage % from `reports.progress` checkpoints (OCR 25 → extract 50 → rules 70 → explanations 100).
  - *On `analyzed`* → auto-route or `[ View report ]` toast action → `/reports/{id}`.
- **States:**
  - *Validation/error:* wrong type or >20 MB → inline `Alert`, no submit. Upload `4xx/5xx` → `Toast` error + retry.
  - *Uploading:* byte `Progress`.
  - *Analyzing:* spinner + stage `Progress`/`Badge` via polling (no WebSockets — matches `01-architecture.md`). Status value is `processing` (never `analyzing`).
  - *Failed analysis:* `Alert` "Analysis failed: {friendly message}" + `[ Retry ]` → `POST /reports/analyze`. The friendly message is derived client-side from the sanitized enumerated `reports.error_code` — raw exception text is never returned or shown.

---

### 2.6 Report Viewer (`/reports/{id}`) — authed

```
┌──────────────────────────────────────────────────────────────┐
│  ≡ MedExplain AI   Dashboard  Upload  Trends      [Avatar ▾]   │
├──────────────────────────────────────────────────────────────┤
│  ◀ Back   CBC – Apr 2026                       [ ⤓ Export PDF ]│
│  Type: CBC · Status: Analyzed · Uploaded 2026-04-02            │
│  OCR confidence: 0.94 · Analyzed 2026-04-02 14:31Z            │
│  ───────────────────────────────────────────────────────────  │
│  [ Summary ] [ Biomarkers ] [ Doctor questions ] [ Files ]     │ ← Tabs
│                                                                │
│  ▼ SUMMARY (overall)                                          │
│  ┌───────────────────────────────────────────────────────────┐│
│  │ Your CBC shows a low hemoglobin and a mildly low platelet  ││
│  │ count; other values are within their reference ranges.    ││
│  │ These results can be associated with several causes — only ││
│  │ a clinician can interpret them for you.                    ││
│  │  [ Offline summary ]   ← badge iff generation_mode=        ││
│  │                          'offline_template'  [ Regenerate ]││
│  │ Consult a licensed healthcare professional for medical     ││
│  │ advice.                                                    ││
│  └───────────────────────────────────────────────────────────┘│
│                                                                │
│  ▼ BIOMARKERS                                                 │
│  ┌───────────────────────────────────────────────────────────┐│
│  │ Test          Value     Unit    Reference     Severity     ││
│  │ ───────────────────────────────────────────────────────── ││
│  │ Hemoglobin    9.1       g/dL    13.0–17.0     [Moderate]🟠▼││
│  │ WBC           7.2       10³/µL  4.0–11.0      [Normal]🟢   ││
│  │ Platelets     140       10³/µL  150–400       [Mild]🟡 ▼  ││
│  │ Glucose       142       mg/dL   70–99         [Mild]🟡 ▲  ││
│  │ Urine Protein Positive  –       Negative      [Mild]🟡    ││
│  └───────────────────────────────────────────────────────────┘│
│                                                                │
│  ▼ Hemoglobin — expanded explanation                           │
│  ┌───────────────────────────────────────────────────────────┐│
│  │ Hemoglobin is the protein in red blood cells that carries  ││
│  │ oxygen. Your value (9.1 g/dL) is below the reference range ││
│  │ (Moderate). A low value *may be associated with* iron      ││
│  │ deficiency, among other causes — only a clinician can      ││
│  │ interpret your result. [1]                                 ││
│  │ Sources: [1] Hemoglobin › Why it may be low                ││
│  │ ─────────────────────────────────────────────────────────  ││
│  │ Consult a licensed healthcare professional for medical     ││
│  │ advice.                                                    ││
│  └───────────────────────────────────────────────────────────┘│
│                                                                │
│  ▼ DOCTOR QUESTIONS                                           │
│   1. What might be causing my low hemoglobin?   (cause)        │
│   2. Do I need any follow-up tests?             (follow-up)    │
│   3. Should we recheck this value?              (follow-up)    │
│                                                                │
│  [ 💬 Chat about this report ]                                 │
├──────────────────────────────────────────────────────────────┤
│  ⚠ DisclaimerFooter ... Consult a licensed healthcare prof.    │
└──────────────────────────────────────────────────────────────┘
```

- **Components:** `Tabs` (Summary / Biomarkers / Doctor questions / Files), `Table` (biomarkers), `Badge` (severity, color-coded; "Offline summary"), `Accordion`/`Collapsible` (per-biomarker explanation), `Card`, `Button` (Export, Chat, Regenerate), `Tooltip` (citation hover), `Separator`, `Skeleton`.
- **Severity Badge color map:**

  | Severity | Badge color |
  |---|---|
  | Normal | 🟢 green (`bg-emerald-100 text-emerald-800`) |
  | Mild | 🟡 amber (`bg-amber-100 text-amber-800`) |
  | Moderate | 🟠 orange (`bg-orange-100 text-orange-800`) |
  | Severe | 🔴 red (`bg-red-100 text-red-800`) |

- **Direction arrows:** ▼ down = `direction='low'`, ▲ up = `direction='high'`; `normal` shows no arrow. The word "Elevated" is display-only phrasing for some high results and is never a stored value (only `low`/`high`/`normal` exist in `abnormal_findings.direction`).
- **Biomarker examples (numeric vs. qualitative):** *Glucose* is a **numeric** test handled by a `numeric_range` rule — e.g. 142 mg/dL against 70–99 yields direction `high` (▲), severity `Mild`. *Urine Protein* is a genuinely **qualitative** test handled by a `qualitative` rule — expected `Negative`, observed `Positive` ⇒ status `abnormal`, severity rule-defined (default `Mild`); it has no numeric direction arrow.
- **Fields map to:**
  - Metadata → `reports.title`, `report_type`, `status`, `ocr_confidence`, `uploaded_at`, `analyzed_at`.
  - Biomarkers table → `biomarkers.test_name` (raw printed name), `value`/`value_text`, `unit` (raw printed unit), `reference_range_text` (or `reference_low–reference_high`); Severity `Badge` ← `abnormal_findings.severity`; arrow ← `abnormal_findings.direction` (▼ low / ▲ high).
  - **Overall summary** (Summary tab) → latest `summaries` row: `summaries.summary_text`. The "Offline summary" badge keys off `summaries.generation_mode = 'offline_template'` (not a fragile string match on `model_used`).
  - **Per-finding explanation** (expanded card) → `abnormal_findings.explanation` + `abnormal_findings.citations_json` (a JSON array of `{n, doc_title, section, source_path}`) → rendered as "Sources: [n] {doc_title} › {section}". Normal biomarkers carry a short deterministic templated note; abnormal ones carry the LLM-generated explanation from the single structured analysis call.
  - Doctor questions → `doctor_questions.question_text`, `category`, ordered by `ordering`.
  - Files tab → `report_files.original_filename`, `page_count`, `mime_type`, `raw_ocr_text` (view OCR; may be empty for text-native PDFs).
- **Actions → endpoints:**
  - *Load report* → `GET /reports/{id}` (returns biomarkers, findings with `explanation`+`citations_json`, latest summary, questions — payload already disclaimer-stamped and carries a top-level `disclaimer` field).
  - *Export PDF* → `POST /export {report_id}` → returns/downloads PDF (full disclaimer block on every page per `07-safety-and-compliance.md` §6.2; no raw chat embedded by default). Button shows spinner while generating.
  - *Chat about this report* → route `/chat?report_id={id}` → starts `chat_sessions` scoped to this report.
  - *Row expand* → reveals stored per-finding explanation + citations (no extra call; from `GET /reports/{id}`).
  - *Regenerate* (offline-summary case) → `POST /reports/analyze {report_id}` (re-runs analysis).
- **States:**
  - *Still processing:* if `status=processing`, show analyzing spinner + `Progress` and poll `GET /reports/{id}` (reuses Upload polling).
  - *Failed:* `Alert` "Analysis failed" (message mapped client-side from sanitized `error_code`) + `[ Re-analyze ]` → `POST /reports/analyze`.
  - *Offline-template explanations:* if the latest `summaries.generation_mode = 'offline_template'`, show a `Badge` "Offline summary" + `[ Regenerate ]` (re-runs analyze) per the architecture doc's degradation path.
  - *Loading:* `Skeleton` table + cards.

> Every per-finding explanation card and the overall summary end with the mandatory sentence, mirroring the server-side `check_output()` + `ensure_disclaimer()` guarantee.

---

### 2.7 Chat (`/chat`) — authed

```
┌──────────────────────────────────────────────────────────────┐
│  ≡ MedExplain AI   Dashboard  Upload  Trends      [Avatar ▾]   │
├───────────────┬────────────────────────────────────────────── │
│ Sessions      │  Chat — about: CBC – Apr 2026   (report-scoped)│
│ ───────────   │  ─────────────────────────────────────────────│
│ + New chat    │  ┌──────────────────────────────────────────┐ │
│ ● CBC – Apr   │  │ 🧑 What does my low hemoglobin mean?       │ │
│   General Q&A │  └──────────────────────────────────────────┘ │
│ ● Lipid chat  │  ┌──────────────────────────────────────────┐ │
│               │  │ 🤖 Hemoglobin carries oxygen in the blood. │ │
│               │  │ A low value *may be associated with* iron  │ │
│               │  │ deficiency, among other causes. [1][2]     │ │
│               │  │ ┌──────────┐┌────────────────────┐         │ │
│               │  │ │[1] Hemo… ││[2] Iron › Low causes│  ←chips │ │
│               │  │ └──────────┘└────────────────────┘         │ │
│               │  │ Consult a licensed healthcare professional │ │
│               │  │ for medical advice.                        │ │
│               │  └──────────────────────────────────────────┘ │
│               │  ┌──────────────────────────────────────────┐ │
│               │  │ 🤖 I'm not able to diagnose… (refusal)     │ │ ← guard
│               │  └──────────────────────────────────────────┘ │
│               │  ───────────────────────────────────────────  │
│               │  [ Ask an educational question…       ] [Send]│
│               │  ⓘ I can't diagnose, prescribe, or give doses. │
├───────────────┴────────────────────────────────────────────── │
│  ⚠ DisclaimerFooter ... Consult a licensed healthcare prof.    │
└──────────────────────────────────────────────────────────────┘
```

- **Components:** message thread (`ScrollArea` + role-styled bubbles), citation **chips** (`Badge` + `Tooltip` → "{doc_title} › {section}"), `Input`/`Textarea` + `Button` (Send), session list (`Sheet` on mobile / sidebar on desktop), `Skeleton`, `Toast`, inline `Alert` (refusal hint).
- **Fields map to:**
  - Sessions → `chat_sessions.title`, `report_id` (NULL = "General Q&A", set = "about: {report title}").
  - Messages → `chat_messages.role` (user/assistant), `content`, `citations_json` (rendered as chips).
- **Actions → endpoints:**
  - *Load sessions* → `GET /chat/sessions` (owner-scoped).
  - *Load thread* → `GET /chat/sessions/{id}/messages`.
  - *Send message* → `POST /chat {session_id?, report_id?, message}` → one LLM call per user message; returns the assistant turn (already passed through the input/output safety guards + `ensure_disclaimer()`, with a top-level `disclaimer` field; or a templated refusal). Append both user + assistant messages.
  - *New chat* → creates a `chat_sessions` row (general if no `report_id`, scoped if arriving from Report Viewer `?report_id=`).
- **States:**
  - *Empty thread:* prompt suggestions ("What does low hemoglobin mean?", "What questions should I ask my doctor?").
  - *Sending/typing:* assistant bubble shows animated "typing…" `Skeleton`; respects long Ollama timeouts (120–180s) with a "Thinking… (offline model can be slow)" hint.
  - *Refusal:* assistant bubble renders the templated refusal (diagnosis/Rx/dose) with reframe + disclaimer — visually identical bubble, no special error styling.
  - *Error:* network/LLM-down → `Toast` + assistant bubble showing graceful offline-template note; never blank.

> The assistant input footer hint and every assistant bubble ending in the mandatory sentence reinforce the safety contract at the UI level.

---

### 2.8 Trend Dashboard (`/trends`) — authed

```
┌──────────────────────────────────────────────────────────────┐
│  ≡ MedExplain AI   Dashboard  Upload  Trends      [Avatar ▾]   │
├──────────────────────────────────────────────────────────────┤
│  Trends over time                                              │
│  Biomarker: ( Hemoglobin ▾ )        Range: ( All time ▾ )      │
│  ───────────────────────────────────────────────────────────  │
│  Trend: ▼ Decreasing   Latest: 9.1 g/dL [Moderate]🟠          │
│  ┌───────────────────────────────────────────────────────────┐│
│  │ g/dL                                                       ││
│  │ 17 ┤········· reference high ·····························  ││ ← ReferenceArea
│  │ 15 ┤      ●───────●                                        ││   (green band
│  │ 13 ┤·············  ●  ··········· reference low ·········  ││    13.0–17.0)
│  │ 11 ┤                     ●                                 ││
│  │  9 ┤                            ● (9.1, Moderate 🟠)       ││
│  │    └────┬───────┬───────┬───────┬──────────────────────►  ││
│  │      Jan'26  Feb'26  Mar'26  Apr'26                        ││
│  └───────────────────────────────────────────────────────────┘│
│  Points outside the reference band are marked by severity color.│
│                                                                │
│  ⓘ This chart shows your own values over time. It is not a     │
│     diagnosis. Consult a licensed healthcare professional…     │
├──────────────────────────────────────────────────────────────┤
│  ⚠ DisclaimerFooter ... Consult a licensed healthcare prof.    │
└──────────────────────────────────────────────────────────────┘
```

- **Components:** `Select` (biomarker selector — lists distinct `canonical_name` values with ≥2 numeric points), `Select` (time range), Recharts `LineChart` (`Line` for values, `ReferenceArea` for the reference band `reference_low–reference_high`, `ReferenceLine`, colored `dot` markers by severity, `Tooltip`, `Legend`) inside shadcn `Chart`, `Badge` (trend label + latest severity), `Card`, `Skeleton`, `Alert`.
- **Canonical grouping:** the selector and the series group on `biomarkers.canonical_name`, so synonyms printed differently across labs (`Hb`, `HGB`, `Hemoglobin`) collapse onto one trend line.
- **Fields map to (drives `GET /trends`):** each point = `{point_time (COALESCE(captured_at, uploaded_at)), value, unit, canonical_unit, reference_low, reference_high, severity, direction}` per the trend query. Trend label (Increasing/Decreasing/Stable) computed from the series; latest-point severity `Badge` from `abnormal_findings`. The ▼/▲ trend glyph follows the same convention (down = decreasing/low, up = increasing/high).
- **Actions → endpoints:**
  - *Select biomarker* → `GET /trends?biomarker=hemoglobin` — the query param is `biomarker`, a `canonical_name` string (not `test_name`); owner-scoped, numeric points only, ordered by `point_time`.
  - *Hover point* → `Tooltip` shows value, unit, date, severity (no API call).
  - *Point click* (optional) → route to that report `/reports/{id}`.
- **States:**
  - *Empty (no trendable history):* if a user has <2 numeric points for any canonical biomarker → `Card`: "Not enough data yet. Upload at least two reports with the same test to see trends." + `[ Upload report ]`.
  - *Loading:* chart `Skeleton`.
  - *Error:* `Alert` + `[Retry]`.

> The chart explicitly does **not** color "in-range" as "healthy" — only range/severity facts are shown, honoring the safety doc's no-reassurance rule.

---

### 2.9 Profile (`/profile`) — authed

```
┌──────────────────────────────────────────────────────────────┐
│  ≡ MedExplain AI   Dashboard  Upload  Trends      [Avatar ▾]   │
├──────────────────────────────────────────────────────────────┤
│  Profile & settings                                            │
│  ───────────────────────────────────────────────────────────  │
│  [ Account ]  [ Privacy & LLM ]  [ Security ]        ← Tabs    │
│                                                                │
│  ▼ ACCOUNT                                                     │
│   Full name  [ Jane Doe________ ]                              │
│   Email      jane@example.com   (read-only)                    │
│   Member since 2026-01-10                                      │
│   [ Save changes ]                                             │
│                                                                │
│  ▼ PRIVACY & LLM                                               │
│   Explanation mode:  ( ○ Cloud (Gemini)  ◉ Offline (Ollama) ) │
│   ⚠ Cloud mode sends your report text to Google (consent).    │
│      Offline mode keeps everything on your device (default).   │
│   Consent recorded: 2026-01-12 09:40Z  (cloud only)            │
│   [ Save preference ]                                          │
│                                                                │
│  ▼ SECURITY                                                    │
│   Change password  [ current ][ new ][ confirm ]  [ Update ]   │
│   [ Log out ]      [ ⚠ Delete account & all data ]             │
├──────────────────────────────────────────────────────────────┤
│  ⚠ DisclaimerFooter ... Consult a licensed healthcare prof.    │
└──────────────────────────────────────────────────────────────┘
```

- **Components:** `Tabs` (Account / Privacy & LLM / Security), `Form`/`Input`/`Label`, `RadioGroup` or `Switch` (LLM mode toggle — the "one toggle away" requirement from `07-safety-and-compliance.md` §5.1), `Button`, `Dialog` (confirm destructive delete; confirm cloud-mode consent), `Alert`, `Toast`, `Avatar`.
- **Fields map to:** `users.full_name` (editable), `users.email` (read-only identity), `users.created_at` ("Member since"); `users.llm_mode` (`cloud` ⇄ `offline`, default `offline`), `users.gemini_consent`, `users.gemini_consented_at` ("Consent recorded", shown only in cloud mode). The per-user `llm_mode` is authoritative over any global default and backs the architecture's LLM router; cloud is honored only when consent is granted and a server Gemini key is configured.
- **Actions → endpoints:**
  - *Load current user* → `GET /auth/me` (returns `full_name`, `email`, `llm_mode`, `gemini_consent`, `created_at`).
  - *Save changes* (name) → `PATCH /users/me {full_name}`.
  - *Save preference* (LLM mode) → `PATCH /users/me/settings {llm_mode}`. Setting `cloud` is the consent action: the server sets `gemini_consent=1` and stamps `gemini_consented_at=now`; a `Dialog` first surfaces the egress notice. Switching back to `offline` immediately stops all egress and the entire pipeline stays on-device.
  - *Update password* → `POST /auth/change-password {current_password, new_password}` (re-verifies the current password server-side).
  - *Log out* → clear JWT, route `/login` (client-side).
  - *Delete account & all data* → `Dialog` confirm → `DELETE /users/me` (cascades reports/files/biomarkers/chats + removes files & vectors per `07-safety-and-compliance.md` §5.3).
- **States:**
  - *Loading:* `Skeleton` field rows.
  - *Save success/failure:* `Toast`.
  - *Cloud-mode confirm:* `Dialog` surfaces "Cloud mode sends your report text to Google" and records consent on accept.
  - *Delete:* `Dialog` requires typed confirmation; on success route to Landing.

---

## 3. State Conventions Summary (cross-page)

| State | Pattern | Component(s) |
|---|---|---|
| First load | Skeleton placeholders matching final layout | `Skeleton` |
| Upload in progress | Determinate byte progress bar | `Progress` |
| Analysis in progress | Polling `GET /reports/{id}` every ~2s; stage bar OCR→Extract→Rules→Explanations (status = `processing`) | `Progress`, `Badge`, spinner |
| Empty (no reports) | Centered CTA card | `Card`, `Button` |
| Empty (no trend data) | "Upload ≥2 reports with same test" CTA | `Card`, `Button` |
| Mutation success | Transient confirmation | `Toast` (Sonner) |
| Recoverable error | Inline message (mapped from sanitized `error_code`) + Retry | `Alert`, `Button` |
| Auth failure (401) | Redirect to `/login` | router guard |
| LLM unavailable | Offline-template badge (from `generation_mode='offline_template'`) + Regenerate; chat never blank | `Badge`, graceful bubble |
| Safety refusal | Templated reframe bubble/card with disclaimer | normal bubble + `Alert` hint |

---

## 4. Safety-Footer Enforcement Matrix (UI ↔ server)

| Surface | UI shows disclaimer | Server guarantees disclaimer |
|---|---|---|
| All 9 pages | `<DisclaimerFooter/>` in root layout | — |
| Overall summary (Report Viewer) | rendered at end of the Summary card | `check_output()` + `ensure_disclaimer()` in `summaries.summary_text`; response `disclaimer` field |
| Per-finding explanation (Report Viewer) | rendered at end of each card | `check_output()` + `ensure_disclaimer()` on `abnormal_findings.explanation`; response `disclaimer` field |
| Chat answer | rendered at end of each assistant bubble | `check_output()` + `ensure_disclaimer()` on `/chat` response; response `disclaimer` field |
| Refusal (chat) | rendered in templated refusal bubble | input-guard template includes it (and re-asserted by `ensure_disclaimer()`) |
| Exported PDF | n/a (file) | full block footer on every page on `POST /export`; no raw chat embedded by default |
| Trend Dashboard | chart caption + footer | trend is data-only (no generated prose) |

The UI footer is presentational; the **server-side output guard is authoritative**, so no user-facing generated/templated/rule-engine prose can ship without the mandatory sentence even if the frontend changes. Cross-document references in this file use the canonical names defined in `00-design-review.md` (`01-architecture.md`, `03-database-schema.md`, `04-api-spec.md`, `07-safety-and-compliance.md`, `08-rag-design.md`).
