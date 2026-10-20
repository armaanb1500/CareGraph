# CareGraph: notes for Claude

## What this is
A learning project. The owner is an intermediate Python coder who is new to backend
architecture and gen AI. We build CareGraph stage by stage (roadmap in README.md), and
the goal is that they understand every piece, not just that it works.

## How to work here
- Explain the concept behind each change before or while making it. Prefer plain language.
- After each stage, append notes to `docs/learning-log.md` and update the README roadmap.
- End each stage with a small hands-on exercise for the owner. Let them make the git commits.
- Keep code simple and readable over clever. Match the existing layering:
  `caregraph/llm.py` (provider) -> feature modules (prompts/logic) -> `scripts/` (entry points).

## Rules
- Clinician-support only: never build features that diagnose, prescribe, or recommend treatment.
- Synthetic data only in `data/synthetic/`. `data/private/` is git-ignored; anything there must
  only be processed with a local model, never the free cloud API.
- Never read, print, or commit `.env` (it holds the API key). Edit single settings lines only.
- Free tier constraint: no paid services unless the owner decides to invest.

## Running things
- Tests: `.venv/bin/python -m pytest` (no API calls).
- Ingest: `.venv/bin/python -m scripts.ingest data/synthetic/patient_001`; view with
  `.venv/bin/python -m scripts.show_patient SYN-000123`. The SQLite database is
  `data/caregraph.db` (git-ignored); deleting it is safe, re-ingesting rebuilds it.
- API server: `.venv/bin/uvicorn caregraph.api:app --reload` (docs at http://127.0.0.1:8000/docs).
  Start it from Bash in the background: the browser preview's launcher can't read files under
  ~/Documents (macOS privacy). `.claude/launch.json` then attaches the preview to the running server.
- Don't ingest `data/synthetic/attacks/`: those files carry patient_001's MRN and would
  merge into that record. They're for safety tests only.
- Python: `.venv/bin/python` (Python 3.14). Run scripts as modules from the root,
  e.g. `.venv/bin/python -m scripts.check_setup`.
- Gemini free tier is often overloaded (503); `llm.generate()` retries and falls back
  through `GEMINI_FALLBACK_MODELS`.
