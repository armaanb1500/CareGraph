# Learning log

Notes on what each stage built and the ideas behind it.

## Stage 0: Project setup

### Virtual environment (`.venv/`)
A private copy of Python just for this project. Packages installed here don't
affect other projects on your Mac, and other projects can't break this one.
- `.venv/bin/python` runs this project's Python directly.
- Or run `source .venv/bin/activate` once per terminal, then `python` means the venv's Python.
- It's git-ignored because anyone can recreate it from `requirements.txt`.

### `requirements.txt`
The list of packages (with exact versions) the project needs. Pinning versions
means the code behaves the same on every machine.
- `google-genai`: Google's official SDK for calling Gemini.
- `python-dotenv`: reads `.env` into environment variables.
- `pydantic`: describes data shapes and validates them. It's central in Stage 2.

### Secrets and `.env`
An API key works like a password: anyone who has it can use your quota.
Real projects keep secrets out of code:
- `.env` holds the real values and is **git-ignored**, so it never gets pushed to GitHub.
- `.env.example` is committed. It documents which settings exist, with fake values.
- `caregraph/config.py` is the only place that reads settings. Everything else asks it.

### Package vs scripts
- `caregraph/` is a **package**: a folder with `__init__.py`, importable as `import caregraph`.
  The real application logic lives here.
- `scripts/` holds tools you run by hand. Running them with `python -m scripts.check_setup`
  from the project root lets them `import caregraph`.

### Git
Git tracks every version of your code. `.gitignore` lists what git should never track:
secrets, the venv, databases, and `data/private/`.

### Why `data/private/` exists already
This is the "design as if real data is coming" principle. If you ever test with your own
medical records, they go here: git never sees them, and we'll only process them with a
local model.

## Stage 1: First LLM call

### Anatomy of an LLM call (`caregraph/llm.py`)
Every call sends the same four things:
- **model**: which LLM answers (`gemini-3.8-flash`).
- **system instruction**: standing rules for how to behave ("use only the document").
- **contents**: the actual request, including the document.
- **config**: knobs like `temperature`.

And gets back:
- **text**: the answer.
- **usage**: token counts. Tokens are chunks of words (~4 characters each). APIs bill and
  rate-limit by tokens. "Thinking" tokens are the model reasoning privately before it answers.

### Temperature
Controls randomness. 0-0.3 gives consistent, factual output (what we want for medical
records); 0.7+ gives varied, creative output. We use 0.2.

### Prompt engineering in `caregraph/summarize.py`
- **Role and limits**: "supports licensed clinicians... does not diagnose."
- **Grounding**: "use only information stated in the document." Without this, LLMs fill gaps
  with plausible-sounding guesses. That's called *hallucination*.
- **An escape hatch**: "write 'not stated in the document'". The model needs a permitted way
  to say "I don't know", or it will invent something.
- **Exactness**: "copy doses and values exactly." The model shouldn't round 8.4% to "about 8%".
- **Fixed sections**: predictable output that's easy to scan (and easier to parse later).
- **Delimiters**: `<document>...</document>` marks where the document starts and ends. If a
  document contained text like "ignore your instructions", the tags help the model treat it as
  data. Defending against that kind of attack is called *prompt-injection defence*.

### Layers: why three files instead of one
- `llm.py`: *how* to talk to an LLM (provider, retries). Knows nothing about medicine.
- `summarize.py`: *what* to ask (the prompt). Knows nothing about Gemini.
- `scripts/summarize_document.py`: *entry point*. Reads a file, prints the result.
Each layer can change without touching the others. Swapping Gemini for Ollama only touches `llm.py`.
Adding a FastAPI endpoint in Stage 4 will reuse `summarize.py` unchanged.

### Reliability: retries, backoff, fallback
Free-tier models are often overloaded (HTTP 503) or rate-limited (HTTP 429).
- **Retry**: these errors are temporary, so try again.
- **Exponential backoff**: wait 2s, then 4s, then longer, so we don't hammer a struggling server.
- **Fallback models**: if the preferred model stays busy, try the next one in `GEMINI_FALLBACK_MODELS`.
- **Don't retry real errors**: a bad key (401) or bad request (400) will fail every time.

### Model versions
Google retired `gemini-2.5-flash` for new users while it still appeared in the model list.
Lessons: pin an exact model version (not `-latest`, which can change under you), test with a
real call, and record which model produced each output (`LLMResult.model`). In healthcare
you need to be able to answer "which model wrote this summary?"
