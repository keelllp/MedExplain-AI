# MedExplain AI — Backend

FastAPI (Python 3.12) backend for MedExplain AI, a local, CPU-only **educational**
medical-report interpreter. It does **not** diagnose, treat, prescribe, or advise on
dosages. See `../docs/` for the full design (architecture, schema, API, safety).

> **Phase 2 (Backend Skeleton)** is implemented: app factory, config, SQLite init
> from the canonical `app/db/init.sql`, JWT auth, account/settings endpoints, the
> Pydantic schema layer, and the full stubbed endpoint surface (reports/chat/trends/
> export return `501` until later phases). OCR/NLP/RAG/LLM land in Phases 3–5.

## Quick start (local, no Docker)

Dependencies are managed with [uv](https://docs.astral.sh/uv/). uv also fetches the
pinned Python (3.12 — see `.python-version`), so you don't need it preinstalled.

```bash
cd backend
uv sync                       # creates .venv + installs from uv.lock (Python 3.12)

cp .env.example .env          # optional; safe dev defaults exist without it

# run the API (single worker — the app assumes one process; see docs/01 §6)
uv run uvicorn app.main:app --reload --port 8000 --workers 1
```

> Prefer pip? `python -m venv .venv && pip install -r requirements.txt` still works —
> `requirements.txt` is exported from `uv.lock` (runtime deps only).

- API docs:   http://localhost:8000/docs
- OpenAPI:     http://localhost:8000/api/v1/openapi.json
- Health:      http://localhost:8000/health

The SQLite database is created automatically at `../data/medexplain.db` on first
start (from `app/db/init.sql`). Optional demo user:

```bash
uv run python -m app.db.seed   # creates demo@medexplain.local / demo-password-123
```

## Tests

```bash
cd backend
uv run pytest               # 21 tests (unit + integration)
uv run pytest -m unit       # or -m integration
```

Verified on Python **3.10** and **3.12** (the pinned target). `pytest.ini` sets
`pythonpath = .` so `import app` resolves regardless of how pytest is invoked.

## Layout (Phase 2)

```
app/
├── main.py            # app factory + lifespan (init DB, reconcile)
├── core/              # config, db (engine + PRAGMAs), security (JWT/bcrypt), logging, exceptions
├── models/            # SQLAlchemy ORM for the 9 tables
├── schemas/           # Pydantic v2 request/response models (enums mirror DB CHECKs)
├── crud/              # thin data access (user implemented; others added per phase)
├── api/
│   ├── deps.py        # get_current_user (JWT bearer)
│   └── v1/routers/    # auth, users (real) + reports/chat/trends/export (501 stubs)
└── db/                # init.sql (canonical DDL), reconcile.py, seed.py
```

## Configuration

All env vars are prefixed `MEDEXPLAIN_` (see `.env.example`). Notable:

| Var | Default | Notes |
|---|---|---|
| `MEDEXPLAIN_JWT_SECRET` | dev placeholder | **App refuses to boot in `prod` with the default.** |
| `MEDEXPLAIN_ENV` | `dev` | `dev` or `prod`. |
| `MEDEXPLAIN_DB_PATH` | `data/medexplain.db` | Relative paths resolve against the repo root. |
| `MEDEXPLAIN_CORS_ORIGINS` | `http://localhost:3000` | Comma-separated. |
| `MEDEXPLAIN_GEMINI_API_KEY` | _(empty)_ | When empty, `cloud` LLM mode is unavailable (offline-only). |

> **Note — OneDrive / cloud-synced folders.** This repo currently lives under a
> OneDrive-synced path. SQLite uses WAL mode, and live cloud-sync of the `.db`/`-wal`/
> `-shm` files can cause `database is locked` errors or corruption. The default DB lives
> in `data/` (git-ignored). If you hit lock errors, exclude `data/` from OneDrive sync
> or set `MEDEXPLAIN_DB_PATH` to a local (non-synced) path.
