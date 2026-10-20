"""Test data builders shared by several test files."""

import sqlite3

from caregraph import db
from caregraph.extract import ExtractionReport
from caregraph.llm import LLMResult
from caregraph.schemas import DocumentExtraction, Medication


def make_report(date: str, lisinopril_dose: str, mrn: str = "SYN-1") -> ExtractionReport:
    """A fake extraction result: one patient, one Lisinopril mention. No LLM involved."""
    extraction = DocumentExtraction(
        document_type="clinical_note",
        document_date=date,
        patient_name="Test Patient",
        patient_mrn=mrn,
        diagnoses=[],
        medications=[
            Medication(
                name="Lisinopril",
                dose=lisinopril_dose,
                route="PO",
                frequency="once daily",
                status="changed",
                change_detail=None,
                evidence=f"Lisinopril {lisinopril_dose}",
            )
        ],
        allergies=[],
        lab_results=[],
        suspicious_content=[],
    )
    llm = LLMResult(text="", model="test-model", input_tokens=0, output_tokens=0, thinking_tokens=0)
    return ExtractionReport(extraction=extraction, unsupported=[], llm=llm)


def save(conn: sqlite3.Connection, report: ExtractionReport, content_hash: str, text: str = "text") -> int:
    """Store a fake report as if it had been ingested. Returns the document id."""
    with conn:
        patient_id = db.get_or_create_patient(conn, "SYN-1", "Test Patient")
        return db.save_document(conn, patient_id, "/secret/server/path/test.txt", content_hash, text, report)
