"""Tests for the HTTP API. TestClient sends requests straight to the app, with no server
running. The database is swapped for an in-memory one, and the LLM for a fake.
"""

import pytest
from fastapi.testclient import TestClient

from caregraph import ingest
from caregraph.api import MAX_UPLOAD_BYTES, app, get_conn
from helpers import make_report, save


@pytest.fixture
def client(conn):
    # dependency_overrides: whenever an endpoint asks for get_conn, hand it our in-memory
    # test database instead of the real one.
    app.dependency_overrides[get_conn] = lambda: conn
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_unknown_patient_is_404(client):
    assert client.get("/patients/NOPE").status_code == 404


def test_every_fact_links_to_its_source_document(client, conn):
    save(conn, make_report("2026-03-02", "10 mg"), content_hash="a", text="Lisinopril 10 mg")

    record = client.get("/patients/SYN-1").json()
    mention = record["medications"][0]["mentions"][0]
    assert mention["dose"] == "10 mg"

    # Follow the link from the fact to its source document.
    document = client.get(f"/documents/{mention['document_id']}").json()
    assert document["raw_text"] == "Lisinopril 10 mg"


def test_server_file_paths_are_not_exposed(client, conn):
    save(conn, make_report("2026-03-02", "10 mg"), content_hash="a")
    response_text = client.get("/patients/SYN-1").text
    assert "test.txt" in response_text
    assert "/secret/server/path" not in response_text


def test_upload_is_rejected_when_the_mrn_is_not_in_the_document(client, monkeypatch):
    monkeypatch.setattr(ingest, "extract_document", lambda text: make_report("2026-03-02", "10 mg", mrn="SYN-999"))

    response = client.post("/documents", files={"file": ("note.txt", b"MRN: SYN-1\nLisinopril 10 mg")})

    assert response.status_code == 422
    assert "SYN-999" in response.json()["detail"]


def test_upload_then_reupload(client, monkeypatch):
    monkeypatch.setattr(ingest, "extract_document", lambda text: make_report("2026-03-02", "10 mg"))
    document = ("note.txt", b"MRN: SYN-1\nLisinopril 10 mg")

    first = client.post("/documents", files={"file": document})
    assert first.status_code == 201
    assert first.json()["document_id"] is not None

    second = client.post("/documents", files={"file": document})
    assert second.status_code == 200
    assert second.json()["status"] == "skipped"


def test_oversized_upload_is_refused(client):
    too_big = b"x" * (MAX_UPLOAD_BYTES + 1)
    response = client.post("/documents", files={"file": ("big.txt", too_big)})
    assert response.status_code == 413
