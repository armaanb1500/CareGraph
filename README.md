# CareGraph

Healthcare record intelligence: turns unstructured medical documents (discharge
summaries, prescriptions, lab reports, clinical notes) into a searchable,
longitudinal patient record for authorized healthcare professionals.

> **Clinician-support tool only.** CareGraph surfaces evidence from a patient's
> documents with citations. It does not diagnose or prescribe.
> Development uses synthetic data only.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env        # then paste your Gemini API key into .env
.venv/bin/python -m scripts.check_setup
```

## Try it

```bash
.venv/bin/python -m scripts.ingest data/synthetic/patient_001
.venv/bin/python -m scripts.show_patient SYN-000123
```

Or run the API server and open http://127.0.0.1:8000/docs to try every endpoint in your browser:

```bash
.venv/bin/uvicorn caregraph.api:app --reload
```

## Project layout

```
caregraph/        the application code (a Python package)
  config.py       loads settings from .env
  llm.py          talks to Gemini (retries, fallback models)
  extract.py      structured extraction + evidence verification
  schema.sql      database tables
  db.py           saving to the database
  ingest.py       document -> extraction -> patient record
  record.py       reading a patient's record over time
  api.py          the HTTP API (FastAPI)
scripts/          tools you run by hand
tests/            automated tests (.venv/bin/python -m pytest)
data/synthetic/   fake patient documents for development
data/caregraph.db the database (git-ignored; delete it to rebuild from documents)
data/private/     real data (e.g. your own records) - git-ignored, local model only
docs/             learning log and design notes
```

## Roadmap

| Stage | Build | Status |
|---|---|---|
| 0 | Project setup | done |
| 1 | First LLM call on a synthetic discharge summary | done |
| 2 | Structured extraction (meds, diagnoses, allergies, labs) | done |
| 3 | Database for patients, documents, facts | done |
| 4 | FastAPI backend | done |
| 5 | OCR for scans and images | |
| 6 | RAG with citations | |
| 7 | "What changed between visits?" timelines | |
| 8 | Conflict detection | |
| 9 | Clinician web UI | |
| 10 | Guardrails, evals, auth, audit log, de-identification, FHIR | |
