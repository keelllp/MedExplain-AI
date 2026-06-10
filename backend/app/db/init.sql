-- MedExplain AI — canonical SQLite schema (9 tables)
-- This file is the SINGLE SOURCE OF TRUTH for the database structure.
-- It mirrors docs/03-database-schema.md and is executed idempotently on startup
-- (see app/db/__init__.py :: init_db). No Alembic — for a single-file SQLite DB
-- owned by one developer, editing this file + recreating the local DB is sufficient.
--
-- PRAGMAs (foreign_keys / WAL / busy_timeout) are applied per-connection in
-- app/core/db.py, NOT here, because PRAGMA foreign_keys is a per-connection setting.

-- ---------------------------------------------------------------------------
-- users
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id                  INTEGER PRIMARY KEY,
    -- COLLATE NOCASE makes the UNIQUE constraint case-insensitive, backstopping the
    -- application-level lowercasing so 'User@x' and 'user@x' can never both exist.
    email               TEXT COLLATE NOCASE NOT NULL UNIQUE
                            CHECK (length(email) <= 320 AND email LIKE '%_@_%.__%'),
    password_hash       TEXT NOT NULL,
    full_name           TEXT,
    -- LLM generation policy for this account. Privacy-first default = 'offline'
    -- (Ollama -> deterministic template; no network egress). 'cloud' is honored
    -- only when gemini_consent = 1 AND a server Gemini key is configured.
    llm_mode            TEXT NOT NULL DEFAULT 'offline'
                            CHECK (llm_mode IN ('cloud', 'offline')),
    gemini_consent      INTEGER NOT NULL DEFAULT 0
                            CHECK (gemini_consent IN (0, 1)),
    gemini_consented_at TEXT,
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- ---------------------------------------------------------------------------
-- reports
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS reports (
    id             INTEGER PRIMARY KEY,
    user_id        INTEGER NOT NULL,
    title          TEXT NOT NULL DEFAULT 'Untitled report',
    report_type    TEXT NOT NULL DEFAULT 'other'
                       CHECK (report_type IN (
                           'blood', 'cbc', 'mri', 'ct', 'xray',
                           'pathology', 'prescription', 'discharge', 'other'
                       )),
    status         TEXT NOT NULL DEFAULT 'uploaded'
                       CHECK (status IN ('uploaded', 'processing', 'analyzed', 'failed')),
    progress       INTEGER NOT NULL DEFAULT 0
                       CHECK (progress BETWEEN 0 AND 100),
    -- Sanitized, enumerated failure code only (NEVER raw exception text / PHI).
    error_code     TEXT
                       CHECK (error_code IS NULL OR error_code IN (
                           'ocr_failed', 'extraction_failed',
                           'llm_unavailable', 'timeout', 'internal_error'
                       )),
    ocr_confidence REAL CHECK (ocr_confidence IS NULL OR (ocr_confidence >= 0 AND ocr_confidence <= 1)),
    uploaded_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    analyzed_at    TEXT,
    created_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ---------------------------------------------------------------------------
-- report_files  (MVP: exactly one row per report; schema allows more)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS report_files (
    id                    INTEGER PRIMARY KEY,
    report_id             INTEGER NOT NULL,
    original_filename     TEXT NOT NULL,
    stored_path           TEXT NOT NULL UNIQUE,
    mime_type             TEXT NOT NULL
                              CHECK (mime_type IN (
                                  'application/pdf', 'image/jpeg', 'image/png'
                              )),
    size_bytes            INTEGER NOT NULL CHECK (size_bytes >= 0),
    page_count            INTEGER CHECK (page_count IS NULL OR page_count >= 0),
    raw_ocr_text          TEXT,
    extracted_tables_json TEXT,
    created_at            TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE CASCADE
);

-- ---------------------------------------------------------------------------
-- biomarkers
--   test_name/unit       = raw printed values (display)
--   canonical_name/unit  = normalized keys (trends + KB retrieval); NULL if unmapped
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS biomarkers (
    id                   INTEGER PRIMARY KEY,
    report_id            INTEGER NOT NULL,
    test_name            TEXT NOT NULL,
    canonical_name       TEXT,
    value                REAL,
    value_text           TEXT,
    unit                 TEXT,
    canonical_unit       TEXT,
    reference_low        REAL,
    reference_high       REAL,
    reference_range_text TEXT,
    captured_at          TEXT,
    created_at           TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    CHECK (value IS NOT NULL OR value_text IS NOT NULL),
    CHECK (reference_low IS NULL OR reference_high IS NULL OR reference_low <= reference_high),
    FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE CASCADE
);

-- ---------------------------------------------------------------------------
-- abnormal_findings  (one row per evaluated biomarker)
--   per-biomarker plain-language explanation + citations live here (from the
--   single per-report LLM call, or a guarded template); overall summary -> summaries
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS abnormal_findings (
    id            INTEGER PRIMARY KEY,
    biomarker_id  INTEGER NOT NULL UNIQUE,
    status        TEXT NOT NULL
                      CHECK (status IN ('normal', 'abnormal')),
    severity      TEXT NOT NULL
                      CHECK (severity IN ('normal', 'mild', 'moderate', 'severe')),
    direction     TEXT NOT NULL DEFAULT 'normal'
                      CHECK (direction IN ('low', 'high', 'normal')),
    rule_id       TEXT,
    explanation   TEXT,
    citations_json TEXT,
    created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    -- status <-> severity <-> direction invariant
    CHECK (
        (status = 'normal'   AND severity = 'normal' AND direction = 'normal') OR
        (status = 'abnormal' AND severity IN ('mild', 'moderate', 'severe'))
    ),
    FOREIGN KEY (biomarker_id) REFERENCES biomarkers(id) ON DELETE CASCADE
);

-- ---------------------------------------------------------------------------
-- summaries  (latest-per-report overall summary; regeneration history allowed)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS summaries (
    id              INTEGER PRIMARY KEY,
    report_id       INTEGER NOT NULL,
    summary_text    TEXT NOT NULL,
    generation_mode TEXT NOT NULL DEFAULT 'offline_template'
                        CHECK (generation_mode IN ('gemini', 'ollama', 'offline_template')),
    model_used      TEXT NOT NULL,  -- provenance string is always recorded (e.g. 'offline-template')
    generated_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE CASCADE
);

-- ---------------------------------------------------------------------------
-- doctor_questions
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS doctor_questions (
    id            INTEGER PRIMARY KEY,
    report_id     INTEGER NOT NULL,
    question_text TEXT NOT NULL,
    category      TEXT NOT NULL DEFAULT 'follow-up'
                      CHECK (category IN ('cause', 'follow-up', 'clarification')),
    ordering      INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE CASCADE
);

-- ---------------------------------------------------------------------------
-- chat_sessions  (report_id nullable; ON DELETE SET NULL keeps history)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS chat_sessions (
    id         INTEGER PRIMARY KEY,
    user_id    INTEGER NOT NULL,
    report_id  INTEGER,
    title      TEXT NOT NULL DEFAULT 'New chat',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    FOREIGN KEY (user_id)   REFERENCES users(id)   ON DELETE CASCADE,
    FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE SET NULL
);

-- ---------------------------------------------------------------------------
-- chat_messages
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS chat_messages (
    id             INTEGER PRIMARY KEY,
    session_id     INTEGER NOT NULL,
    role           TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content        TEXT NOT NULL,
    citations_json TEXT,
    created_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
);

-- ---------------------------------------------------------------------------
-- Indexes: every FK + hot query paths (trends key on canonical_name)
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_reports_user_id              ON reports(user_id);
CREATE INDEX IF NOT EXISTS idx_report_files_report_id       ON report_files(report_id);
CREATE INDEX IF NOT EXISTS idx_biomarkers_report_id         ON biomarkers(report_id);
CREATE INDEX IF NOT EXISTS idx_abnormal_findings_biomarker  ON abnormal_findings(biomarker_id);
CREATE INDEX IF NOT EXISTS idx_summaries_report_id          ON summaries(report_id);
CREATE INDEX IF NOT EXISTS idx_doctor_questions_report_id   ON doctor_questions(report_id);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id        ON chat_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_report_id      ON chat_sessions(report_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id     ON chat_messages(session_id);

-- Trend analysis: a given canonical biomarker across a user's reports, by time.
CREATE INDEX IF NOT EXISTS idx_biomarkers_canonical_report  ON biomarkers(canonical_name, report_id);

-- Common dashboard / ordering paths
CREATE INDEX IF NOT EXISTS idx_reports_user_uploaded        ON reports(user_id, uploaded_at);
CREATE INDEX IF NOT EXISTS idx_doctor_questions_report_order ON doctor_questions(report_id, ordering);
CREATE INDEX IF NOT EXISTS idx_chat_messages_session_created ON chat_messages(session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_summaries_report_generated   ON summaries(report_id, generated_at);
