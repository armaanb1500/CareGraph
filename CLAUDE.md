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
- Python: `.venv/bin/python` (Python 3.14). Run scripts as modules from the root,
  e.g. `.venv/bin/python -m scripts.check_setup`.
- Gemini free tier is often overloaded (503); `llm.generate()` retries and falls back
  through `GEMINI_FALLBACK_MODELS`.
