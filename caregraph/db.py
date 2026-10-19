"""Storing patients, documents and extracted facts in SQLite.

SQLite keeps the whole database in one file (data/caregraph.db) and comes built into
Python. The tables are defined in schema.sql.

Every query uses ? placeholders instead of building SQL strings with f-strings.
The database then treats the values purely as data, so text inside a document can
never be run as SQL. Building SQL by gluing strings together is how "SQL injection"
attacks happen.
"""

import sqlite3
from pathlib import Path

from caregraph.config import get_settings
from caregraph.extract import ExtractionReport

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    """Open the database (creating it and its tables if needed).

    Pass ":memory:" for a throwaway in-memory database, which is what the tests use.
    """
    if path is None:
        path = get_settings().database_path
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row  # rows behave like dicts: row["name"]
    conn.execute("PRAGMA foreign_keys = ON")  # SQLite doesn't enforce REFERENCES unless asked
    conn.executescript(SCHEMA_PATH.read_text())
    return conn


def find_patient(conn: sqlite3.Connection, mrn: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM patients WHERE mrn = ?", (mrn,)).fetchone()


def get_or_create_patient(conn: sqlite3.Connection, mrn: str, name: str | None) -> int:
    existing = find_patient(conn, mrn)
    if existing:
        return existing["id"]
    cursor = conn.execute("INSERT INTO patients (mrn, name) VALUES (?, ?)", (mrn, name))
    return cursor.lastrowid


def document_exists(conn: sqlite3.Connection, content_hash: str) -> bool:
    row = conn.execute("SELECT 1 FROM documents WHERE content_hash = ?", (content_hash,)).fetchone()
    return row is not None


def save_document(
    conn: sqlite3.Connection,
    patient_id: int,
    source_path: str,
    content_hash: str,
    text: str,
    report: ExtractionReport,
) -> int:
    """Insert a document and all of its extracted facts. Returns the new document's id.

    Call this inside `with conn:` so that either everything is saved or nothing is.
    """
    x = report.extraction
    document_id = conn.execute(
        """INSERT INTO documents
           (patient_id, source_path, content_hash, document_type, document_date, raw_text, model)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (patient_id, source_path, content_hash, x.document_type, x.document_date, text, report.llm.model),
    ).lastrowid

    # Look up each fact's verification problem (if any) by its section and quote.
    issues = {(f.section, f.evidence): f.reason for f in report.unsupported}

    conn.executemany(
        """INSERT INTO diagnoses (document_id, name, condition, status, evidence, verification_issue)
           VALUES (?, ?, ?, ?, ?, ?)""",
        [
            (document_id, d.name, d.condition, d.status, d.evidence, issues.get(("diagnoses", d.evidence)))
            for d in x.diagnoses
        ],
    )
    conn.executemany(
        """INSERT INTO medications (document_id, name, dose, route, frequency, status, change_detail,
                                    evidence, verification_issue)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (document_id, m.name, m.dose, m.route, m.frequency, m.status, m.change_detail, m.evidence,
             issues.get(("medications", m.evidence)))
            for m in x.medications
        ],
    )
    conn.executemany(
        """INSERT INTO allergies (document_id, substance, reaction, evidence, verification_issue)
           VALUES (?, ?, ?, ?, ?)""",
        [
            (document_id, a.substance, a.reaction, a.evidence, issues.get(("allergies", a.evidence)))
            for a in x.allergies
        ],
    )
    conn.executemany(
        """INSERT INTO lab_results (document_id, test, value, unit, date, reference_range, evidence,
                                    verification_issue)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (document_id, r.test, r.value, r.unit, r.date, r.reference_range, r.evidence,
             issues.get(("lab_results", r.evidence)))
            for r in x.lab_results
        ],
    )
    conn.executemany(
        "INSERT INTO suspicious_content (document_id, quote) VALUES (?, ?)",
        [(document_id, quote) for quote in x.suspicious_content],
    )
    return document_id
