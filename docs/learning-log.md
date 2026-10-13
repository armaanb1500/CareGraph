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
