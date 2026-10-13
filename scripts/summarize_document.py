"""Summarize one clinical document with the LLM.

Usage, from the project root:
    .venv/bin/python -m scripts.summarize_document <path-to-document>
"""

import sys
from pathlib import Path

from google.genai import errors

from caregraph.summarize import summarize_document


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 1

    path = Path(sys.argv[1])
    if not path.is_file():
        print(f"No such file: {path}")
        return 1

    try:
        result = summarize_document(path.read_text())
    except errors.APIError as e:
        print(f"Gemini error {e.code}: {e.message}")
        return 1

    print(result.text)
    print(
        f"\n--- model: {result.model} | tokens: {result.input_tokens} in, {result.output_tokens} out, "
        f"{result.thinking_tokens} thinking ---"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
