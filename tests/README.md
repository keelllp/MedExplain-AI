# MedExplain AI — tests

Two layers: **Pytest** for the backend (unit / integration / safety, LLM mocked — fast,
offline, provider-independent) and **Playwright** for end-to-end across a live, isolated stack.

## Backend (Pytest)

From `backend/`:

```bash
uv run pytest                       # full suite
uv run pytest -m safety             # safety guard + KB hedging lint only
uv run pytest -m "unit or integration"
```

(Or via the venv directly: `.venv/Scripts/python.exe -m pytest`.) Markers are declared in
`backend/pytest.ini`. `conftest.py` isolates a temp SQLite DB, clears the Gemini key, points
Ollama at a dead port (→ deterministic offline-template path), and pins new-account default to
`offline`, so the suite never makes a network call.

Coverage highlights (the load-bearing modules):
- **Safety** (`tests/safety/`): input REFUSE / ALLOW, output scrub+block, disclaimer
  idempotency, and the **KB hedging lint** (`test_kb_lint.py`) — a hard gate that fails the
  build if any `knowledge_base/*.md` doc contains assertive/diagnostic/imperative/drug-dose phrasing.
- **Pipeline contracts** (`tests/integration/test_pipeline_contracts.py`): **one LLM call per
  report** (D-ONECALL) even with multiple abnormal markers; every analyze explanation carries
  the disclaimer.
- Rule engine, extraction/normalization, trend query/label, auth + owner-scoping, chat
  (refusal + citations + disclaimer), trends (series + selector).

## End-to-end (Playwright)

From `tests/e2e/`:

```bash
npm install            # first time
npx playwright install chromium   # first time (downloads the browser)
npm test               # headless
npm run test:headed    # watch it drive a real browser
npm run report         # open the HTML report after a run
```

Playwright starts its **own isolated stack** (see `playwright.config.ts`) so it never touches
the dev stack on :3000/:8000:
- **Backend** on `127.0.0.1:8123` with its own SQLite DB (`e2e.db`), `offline` LLM mode, no
  Gemini key, and a dead Ollama host → fully deterministic, no egress.
- **Frontend** built (`next build`) into a separate dir (`NEXT_DIST_DIR=.next-e2e`) and served
  with `next start` on `127.0.0.1:3123`, pointed at the 8123 backend. A **production build** is
  used on purpose: `next dev`'s on-demand compilation let the browser interact before React
  hydrated, causing flaky failures.

Specs (`tests/e2e/tests/`): `auth` (sign up / log in / protected-redirect), `account`
(LLM-mode toggle + consent), `upload-analyze` (upload → analyze → view results),
`chat` (diagnosis request is refused with a disclaimer; educational answer is hedged),
`trends` (chart renders for a 2-point series; empty-state for a new account).

Notes: `e2e.db` persists across runs (tests use unique emails, so it's safe to leave or delete).
The fixture PDF is `fixtures/sample-cbc.pdf`. Artifacts (`test-results/`, `playwright-report/`,
`node_modules/`, `e2e.db`) are git-ignored.
