"""Ingest documents into the CareGraph database.

Usage, from the project root:
    .venv/bin/python -m scripts.ingest <file-or-folder> [<file-or-folder> ...]

Folders are scanned for .txt files. Documents already in the database are skipped,
so it's safe to run again.
"""

import argparse
import sys
from pathlib import Path

from google.genai import errors

from caregraph import db
from caregraph.ingest import ingest_file
from caregraph.llm import LLMUnavailableError

SYMBOLS = {"ingested": "+", "skipped": "=", "rejected": "!"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest clinical documents into CareGraph.")
    parser.add_argument("paths", nargs="+", type=Path, help="document files or folders")
    args = parser.parse_args()

    files = []
    for path in args.paths:
        if path.is_dir():
            files.extend(sorted(path.glob("*.txt")))
        elif path.is_file():
            files.append(path)
        else:
            print(f"No such file or folder: {path}")
            return 1

    conn = db.connect()
    counts = {"ingested": 0, "skipped": 0, "rejected": 0}
    try:
        for file in files:
            print(f"\n{file}")
            result = ingest_file(conn, file)
            counts[result.status] += 1
            print(f"  [{SYMBOLS[result.status]}] {result.status}: {result.message}")
    except (LLMUnavailableError, errors.APIError) as e:
        print(f"\nStopped: {e}\nDocuments ingested so far are saved; re-run to continue.")
        return 1
    except KeyboardInterrupt:
        print("\nCancelled. Documents ingested so far are saved; re-run to continue.")
        return 130
    finally:
        conn.close()

    print(f"\nDone: {counts['ingested']} ingested, {counts['skipped']} skipped, {counts['rejected']} rejected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
