-- CareGraph database schema.
--
-- One patient has many documents; one document has many facts.
-- Every fact points to the document it came from (document_id), so any fact
-- can be traced back to its source - the "evidence-linked" part of CareGraph.
--
-- "IF NOT EXISTS" makes this safe to run every time the app starts.

CREATE TABLE IF NOT EXISTS patients (
    id          INTEGER PRIMARY KEY,           -- SQLite fills this in automatically
    mrn         TEXT NOT NULL UNIQUE,          -- medical record number: how we match documents to patients
    name        TEXT,
    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS documents (
    id             INTEGER PRIMARY KEY,
    patient_id     INTEGER NOT NULL REFERENCES patients(id),
    source_path    TEXT NOT NULL,
    content_hash   TEXT NOT NULL UNIQUE,       -- fingerprint of the text, so the same document isn't stored twice
    document_type  TEXT NOT NULL,
    document_date  TEXT,                       -- YYYY-MM-DD, so sorting as text sorts by date
    raw_text       TEXT NOT NULL,              -- the original, kept so every fact can be checked against it
    model          TEXT NOT NULL,              -- which LLM extracted the facts
    ingested_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- In the fact tables, verification_issue is NULL when the fact passed verification,
-- or holds the reason it failed. Failed facts are kept and flagged, never silently dropped.

CREATE TABLE IF NOT EXISTS diagnoses (
    id                  INTEGER PRIMARY KEY,
    document_id         INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    name                TEXT NOT NULL,
    condition           TEXT NOT NULL,
    status              TEXT NOT NULL,
    evidence            TEXT NOT NULL,
    verification_issue  TEXT
);

CREATE TABLE IF NOT EXISTS medications (
    id                  INTEGER PRIMARY KEY,
    document_id         INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    name                TEXT NOT NULL,
    dose                TEXT,
    route               TEXT,
    frequency           TEXT,
    status              TEXT NOT NULL,
    change_detail       TEXT,
    evidence            TEXT NOT NULL,
    verification_issue  TEXT
);

CREATE TABLE IF NOT EXISTS allergies (
    id                  INTEGER PRIMARY KEY,
    document_id         INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    substance           TEXT NOT NULL,
    reaction            TEXT,
    evidence            TEXT NOT NULL,
    verification_issue  TEXT
);

CREATE TABLE IF NOT EXISTS lab_results (
    id                  INTEGER PRIMARY KEY,
    document_id         INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    test                TEXT NOT NULL,
    value               TEXT NOT NULL,
    unit                TEXT,
    date                TEXT,
    reference_range     TEXT,
    evidence            TEXT NOT NULL,
    verification_issue  TEXT
);

CREATE TABLE IF NOT EXISTS suspicious_content (
    id           INTEGER PRIMARY KEY,
    document_id  INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    quote        TEXT NOT NULL
);

-- Indexes make "find everything for this patient/document" fast as the data grows,
-- like the index at the back of a book.
CREATE INDEX IF NOT EXISTS idx_documents_patient ON documents(patient_id);
CREATE INDEX IF NOT EXISTS idx_diagnoses_document ON diagnoses(document_id);
CREATE INDEX IF NOT EXISTS idx_medications_document ON medications(document_id);
CREATE INDEX IF NOT EXISTS idx_allergies_document ON allergies(document_id);
CREATE INDEX IF NOT EXISTS idx_lab_results_document ON lab_results(document_id);
CREATE INDEX IF NOT EXISTS idx_suspicious_content_document ON suspicious_content(document_id);
