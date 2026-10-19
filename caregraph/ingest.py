"""Stage 3: the ingestion pipeline. A document file goes in; facts land in the patient's record.

    read file -> fingerprint -> already stored? -> extract (LLM) -> check patient ID -> save
"""

import hashlib
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from caregraph import db
from caregraph.extract import extract_document, normalize


@dataclass
class IngestResult:
    path: Path
    status: Literal["ingested", "skipped", "rejected"]
    message: str


def ingest_file(conn: sqlite3.Connection, path: Path) -> IngestResult:
    text = path.read_text()

    # A SHA-256 hash is a fingerprint of the text: identical text always gives the same
    # hash. Checking it first makes ingestion safe to re-run ("idempotent"), and saves an
    # LLM call for documents we already have.
    content_hash = hashlib.sha256(text.encode()).hexdigest()
    if db.document_exists(conn, content_hash):
        return IngestResult(path, "skipped", "already in the database")

    report = extract_document(text)
    x = report.extraction

    # Filing a document under the wrong patient is one of the worst errors a record system
    # can make. The MRN comes from the LLM, so check it really is in the document.
    if not x.patient_mrn:
        return IngestResult(path, "rejected", "no MRN found, so it can't be matched to a patient")
    if normalize(x.patient_mrn) not in normalize(text):
        return IngestResult(path, "rejected", f"extracted MRN {x.patient_mrn!r} isn't in the document")

    notes = []
    existing = db.find_patient(conn, x.patient_mrn)
    if existing and x.patient_name and existing["name"] and normalize(existing["name"]) != normalize(x.patient_name):
        notes.append(f"name {x.patient_name!r} differs from the record's {existing['name']!r}")
    if report.unsupported:
        notes.append(f"{len(report.unsupported)} fact(s) failed verification")
    if x.suspicious_content:
        notes.append(f"{len(x.suspicious_content)} suspicious passage(s) flagged")

    # `with conn:` is a transaction: if anything inside fails, every insert is undone,
    # so a document is never left half-saved.
    with conn:
        patient_id = db.get_or_create_patient(conn, x.patient_mrn, x.patient_name)
        db.save_document(conn, patient_id, str(path), content_hash, text, report)

    facts = len(x.diagnoses) + len(x.medications) + len(x.allergies) + len(x.lab_results)
    message = f"{x.document_type} dated {x.document_date}, {facts} facts, patient {x.patient_mrn}"
    if notes:
        message += " | needs review: " + "; ".join(notes)
    return IngestResult(path, "ingested", message)
