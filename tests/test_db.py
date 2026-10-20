"""Tests for storing and reading the patient record. Uses an in-memory database: fast,
starts empty every time, and never touches data/caregraph.db. No LLM calls.
"""

import sqlite3
from pathlib import Path

import pytest

from caregraph import db, ingest, record
from helpers import make_report, save


def test_medication_history_spans_documents_in_date_order(conn):
    # Saved out of order on purpose: the record must still read oldest first.
    save(conn, make_report("2026-03-09", "20 mg"), content_hash="b")
    save(conn, make_report("2026-03-02", "10 mg"), content_hash="a")

    patient_id = db.find_patient(conn, "SYN-1")["id"]
    history = record.medication_history(conn, patient_id)

    assert list(history) == ["Lisinopril"]
    assert [(m.document_date, m.row["dose"]) for m in history["Lisinopril"]] == [
        ("2026-03-02", "10 mg"),
        ("2026-03-09", "20 mg"),
    ]


def test_same_patient_is_reused(conn):
    first = db.get_or_create_patient(conn, "SYN-1", "Test Patient")
    second = db.get_or_create_patient(conn, "SYN-1", "Test Patient")
    assert first == second


def test_database_refuses_the_same_document_twice(conn):
    save(conn, make_report("2026-03-02", "10 mg"), content_hash="same")
    # The UNIQUE constraint on content_hash is a second line of defence behind document_exists().
    with pytest.raises(sqlite3.IntegrityError):
        save(conn, make_report("2026-03-02", "10 mg"), content_hash="same")


def test_failed_save_leaves_nothing_behind(conn):
    report = make_report("2026-03-02", "10 mg")
    # Sneak an invalid value past Pydantic so the *last* insert in save_document fails.
    report.extraction.suspicious_content.append(None)

    with pytest.raises(sqlite3.IntegrityError):
        save(conn, report, content_hash="a")

    # The transaction rolled back, so the document and medication inserted before the
    # failure are gone too. No half-saved documents.
    assert conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM medications").fetchone()[0] == 0


def test_ingest_rejects_an_mrn_that_is_not_in_the_document(conn, tmp_path: Path, monkeypatch):
    document = tmp_path / "note.txt"
    document.write_text("Patient MRN: SYN-1\nLisinopril 10 mg")

    # monkeypatch swaps the real LLM extraction for a fake that "hallucinates" a different
    # MRN. This tests our safety check without calling Gemini. Swapping in fakes like this
    # is called mocking.
    monkeypatch.setattr(ingest, "extract_document", lambda text: make_report("2026-03-02", "10 mg", mrn="SYN-999"))

    result = ingest.ingest_file(conn, document)

    assert result.status == "rejected"
    assert conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 0
