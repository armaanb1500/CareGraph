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

## Project layout

```
caregraph/        the application code (a Python package)
  config.py       loads settings from .env
scripts/          one-off tools you run by hand
data/synthetic/   fake patient documents for development
data/private/     real data (e.g. your own records) - git-ignored, local model only
docs/             learning log and design notes
```

## Roadmap

| Stage | Build | Status |
|---|---|---|
| 0 | Project setup | in progress |
| 1 | First LLM call on a synthetic discharge summary | |
| 2 | Structured extraction (meds, diagnoses, allergies, labs) | |
| 3 | Database for patients, documents, facts | |
| 4 | FastAPI backend | |
| 5 | OCR for scans and images | |
| 6 | RAG with citations | |
| 7 | "What changed between visits?" timelines | |
| 8 | Conflict detection | |
| 9 | Clinician web UI | |
| 10 | Guardrails, evals, auth, audit log, de-identification, FHIR | |
