"""Stage 4: the HTTP API. CareGraph's backend server.

Start it from the project root:
    .venv/bin/uvicorn caregraph.api:app --reload
then open http://127.0.0.1:8000/docs for interactive documentation.

This file only translates between HTTP and the rest of CareGraph. The real work
happens in ingest.py, record.py and summarize.py, which the scripts use too.
"""

import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Response, UploadFile, status
from google.genai import errors
from pydantic import BaseModel

from caregraph import db, record
from caregraph.ingest import ingest_text
from caregraph.llm import LLMUnavailableError
from caregraph.summarize import summarize_document

MAX_UPLOAD_BYTES = 1_000_000  # 1 MB is plenty for a text document

app = FastAPI(
    title="CareGraph",
    description="Clinician-support API: turns clinical documents into an evidence-linked patient record. "
    "It reports what documents say; it does not diagnose or recommend treatment. Synthetic data only.",
    version="0.4.0",
)


# --- Response models ------------------------------------------------------------------
# These describe the JSON each endpoint returns. FastAPI uses them to check our output
# and to generate the documentation page at /docs.


class PatientSummary(BaseModel):
    mrn: str
    name: str | None
    document_count: int


class DocumentInfo(BaseModel):
    id: int
    document_date: str | None
    document_type: str
    source_name: str


class DocumentDetail(DocumentInfo):
    model: str
    raw_text: str


class Condition(BaseModel):
    condition: str
    first_seen: str | None
    last_seen: str | None
    document_count: int
    statuses: list[str]


class MedicationMention(BaseModel):
    document_id: int
    document_date: str | None
    dose: str | None
    route: str | None
    frequency: str | None
    status: str
    change_detail: str | None
    evidence: str
    verification_issue: str | None


class MedicationHistory(BaseModel):
    name: str
    mentions: list[MedicationMention]


class Allergy(BaseModel):
    substance: str
    reactions: str | None
    first_recorded: str | None
    document_count: int


class LabPoint(BaseModel):
    document_id: int
    date: str | None
    value: str
    unit: str | None
    reference_range: str | None
    evidence: str
    verification_issue: str | None


class LabSeries(BaseModel):
    test: str
    results: list[LabPoint]


class ReviewItem(BaseModel):
    source_name: str
    kind: str
    item: str
    issue: str


class PatientRecord(BaseModel):
    mrn: str
    name: str | None
    documents: list[DocumentInfo]
    conditions: list[Condition]
    medications: list[MedicationHistory]
    allergies: list[Allergy]
    lab_results: list[LabSeries]
    needs_review: list[ReviewItem]


class IngestResponse(BaseModel):
    status: str
    message: str
    document_id: int | None


class SummaryResponse(BaseModel):
    document_id: int
    summary: str
    model: str


# --- Dependencies ---------------------------------------------------------------------


def get_conn() -> Iterator[sqlite3.Connection]:
    """Give each request its own database connection, and close it afterwards.

    Endpoints ask for this with `conn: Connection`. FastAPI calls it for them: that's
    "dependency injection". Tests can swap it for an in-memory database.
    """
    conn = db.connect()
    try:
        yield conn
    finally:
        conn.close()


Connection = Annotated[sqlite3.Connection, Depends(get_conn)]


def require_patient(conn: sqlite3.Connection, mrn: str) -> sqlite3.Row:
    patient = db.find_patient(conn, mrn)
    if patient is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No patient with MRN {mrn}")
    return patient


def source_name(source_path: str) -> str:
    # Show only the file name: full paths would reveal how the server's disk is laid out.
    return Path(source_path).name


# --- Endpoints ------------------------------------------------------------------------


@app.get("/health")
def health() -> dict[str, str]:
    """Is the server running? Monitoring tools call this."""
    return {"status": "ok"}


@app.get("/patients")
def list_patients(conn: Connection) -> list[PatientSummary]:
    rows = conn.execute(
        """SELECT p.mrn, p.name, COUNT(d.id) AS document_count
           FROM patients p LEFT JOIN documents d ON d.patient_id = p.id
           GROUP BY p.id ORDER BY p.name"""
    ).fetchall()
    return [PatientSummary(**dict(row)) for row in rows]


@app.get("/patients/{mrn}")
def get_patient_record(mrn: str, conn: Connection) -> PatientRecord:
    """A patient's longitudinal record: every fact from every document, oldest first.

    Each medication mention and lab result carries its evidence quote and document_id,
    so any fact can be traced to its source with GET /documents/{document_id}.
    """
    patient = require_patient(conn, mrn)
    pid = patient["id"]
    return PatientRecord(
        mrn=patient["mrn"],
        name=patient["name"],
        documents=[
            DocumentInfo(
                id=d["id"],
                document_date=d["document_date"],
                document_type=d["document_type"],
                source_name=source_name(d["source_path"]),
            )
            for d in record.documents(conn, pid)
        ],
        conditions=[
            Condition(
                condition=c["condition"],
                first_seen=c["first_seen"],
                last_seen=c["last_seen"],
                document_count=c["document_count"],
                statuses=c["statuses"].split(","),
            )
            for c in record.conditions(conn, pid)
        ],
        medications=[
            MedicationHistory(
                name=name,
                mentions=[MedicationMention(**_fields(m.row, MedicationMention)) for m in mentions],
            )
            for name, mentions in record.medication_history(conn, pid).items()
        ],
        allergies=[Allergy(**dict(a)) for a in record.allergies(conn, pid)],
        lab_results=[
            LabSeries(test=test, results=[LabPoint(**_fields(m.row, LabPoint)) for m in mentions])
            for test, mentions in record.lab_history(conn, pid).items()
        ],
        needs_review=[
            ReviewItem(source_name=source_name(i["source_path"]), kind=i["kind"], item=i["item"], issue=i["issue"])
            for i in record.review_items(conn, pid)
        ],
    )


@app.get("/documents/{document_id}")
def get_document(document_id: int, conn: Connection) -> DocumentDetail:
    """The original document text: where a clinician goes to check a fact's source."""
    row = conn.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No document with id {document_id}")
    return DocumentDetail(
        id=row["id"],
        document_date=row["document_date"],
        document_type=row["document_type"],
        source_name=source_name(row["source_path"]),
        model=row["model"],
        raw_text=row["raw_text"],
    )


@app.post("/documents", status_code=status.HTTP_201_CREATED)
def upload_document(file: UploadFile, conn: Connection, response: Response) -> IngestResponse:
    """Upload a plain-text clinical document. It's extracted, verified and added to the
    patient's record. Takes a few seconds while the LLM reads it.

    Returns 201 when ingested, 200 when the document is already stored, and 422 when it's
    rejected (e.g. no patient identifier).
    """
    content = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Documents must be under 1 MB")
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only UTF-8 text files are supported for now")

    result = _call_llm(ingest_text, conn, text, source=f"upload:{file.filename}")

    if result.status == "rejected":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, result.message)
    if result.status == "skipped":
        # Nothing new was created, so 201 would be wrong. Return 200 instead.
        response.status_code = status.HTTP_200_OK
    return IngestResponse(status=result.status, message=result.message, document_id=result.document_id)


@app.post("/documents/{document_id}/summary")
def summarize(document_id: int, conn: Connection) -> SummaryResponse:
    """A plain-language summary of one document, generated by the LLM (Stage 1's summarizer)."""
    document = get_document(document_id, conn)
    result = _call_llm(summarize_document, document.raw_text)
    return SummaryResponse(document_id=document_id, summary=result.text, model=result.model)


# --- Helpers --------------------------------------------------------------------------


def _fields(row: sqlite3.Row, model: type[BaseModel]) -> dict:
    """Pick out of a database row just the columns a response model needs."""
    return {name: row[name] for name in model.model_fields if name in row.keys()}


def _call_llm(function, *args, **kwargs):
    """Run something that calls the LLM, turning LLM outages into proper HTTP errors."""
    try:
        return function(*args, **kwargs)
    except LLMUnavailableError as e:
        # 503 tells the caller "temporarily unavailable, try again later".
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e))
    except errors.APIError as e:
        # 502 means "a service we depend on failed".
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"LLM provider error: {e.message}")
