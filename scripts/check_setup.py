"""Stage 0 sanity check: is everything installed, and does the API key work?

Run from the project root:
    .venv/bin/python -m scripts.check_setup
"""

import sys

from caregraph.config import PROJECT_ROOT, get_settings


def ok(msg: str) -> None:
    print(f"  [ok]   {msg}")


def fail(msg: str) -> None:
    print(f"  [fail] {msg}")


def main() -> int:
    print("CareGraph setup check\n")

    # 1. Recent enough Python?
    v = sys.version_info
    if v < (3, 11):
        fail(f"Python {v.major}.{v.minor} found, need 3.11 or newer")
        return 1
    ok(f"Python {v.major}.{v.minor}")

    # 2. Running inside the project's virtual environment?
    if sys.prefix == sys.base_prefix:
        fail("Not using .venv - run with .venv/bin/python or activate it first")
        return 1
    ok("Virtual environment active")

    # 3. Does .env exist and hold a real key?
    if not (PROJECT_ROOT / ".env").exists():
        fail(".env missing - copy .env.example to .env")
        return 1
    settings = get_settings()
    if not settings.has_gemini_key:
        fail("GEMINI_API_KEY is not set in .env")
        return 1
    ok(f"Gemini API key found (ends in ...{settings.gemini_api_key[-4:]})")

    # 4. Can we reach Gemini with that key?
    from google import genai

    client = genai.Client(api_key=settings.gemini_api_key)
    try:
        models = [
            m.name.removeprefix("models/")
            for m in client.models.list()
            if "generateContent" in (m.supported_actions or [])
        ]
    except Exception as e:
        fail(f"Could not reach Gemini: {e}")
        return 1
    ok(f"Connected to Gemini ({len(models)} text models available)")

    # 5. Is the model named in .env one of them?
    if settings.gemini_model not in models:
        fail(f"Model '{settings.gemini_model}' is not available to your key")
        flash = [m for m in models if "flash" in m]
        print("         Try one of these in GEMINI_MODEL: " + ", ".join(flash[:6]))
        return 1
    ok(f"Model '{settings.gemini_model}' is available")

    print("\nAll good - you're ready for Stage 1.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
