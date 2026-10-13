"""Stage 0 sanity check: is everything installed, and does the API key work?

Run from the project root:
    .venv/bin/python -m scripts.check_setup
"""

import sys

from google import genai
from google.genai import errors, types

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
    client = genai.Client(
        api_key=settings.gemini_api_key,
        http_options=types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=1)),
    )
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

    # 5. Do the configured models actually answer? Being listed isn't enough:
    #    retired models can stay in the list but refuse new users.
    names = [settings.gemini_model, *settings.gemini_fallback_models]
    answered = [name for name in names if model_responds(client, name, models)]
    if not answered:
        return 1

    print("\nAll good - CareGraph can reach the LLM.")
    return 0


def model_responds(client: genai.Client, name: str, available: list[str]) -> bool:
    try:
        client.models.generate_content(model=name, contents="Reply with OK")
    except errors.APIError as e:
        if e.code in (429, 503):
            print(f"  [busy] Model '{name}' exists but is overloaded or rate-limited right now")
        else:
            fail(f"Model '{name}' didn't respond: {e.message}")
            flash = [m for m in available if m.startswith("gemini-") and m.endswith("flash")]
            print("         Models you could try: " + ", ".join(flash[-4:]))
        return False
    ok(f"Model '{name}' responded")
    return True


if __name__ == "__main__":
    sys.exit(main())
