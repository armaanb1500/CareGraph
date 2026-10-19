"""Extract structured facts from one clinical document and verify their evidence.

Usage, from the project root:
    .venv/bin/python -m scripts.extract_document <path-to-document>
    .venv/bin/python -m scripts.extract_document <path-to-document> --json
"""

import argparse
import sys
from pathlib import Path

from google.genai import errors

from caregraph.extract import ExtractionReport, extract_document
from caregraph.llm import LLMUnavailableError


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract structured facts from a clinical document.")
    parser.add_argument("path", type=Path, help="the document to read")
    parser.add_argument("--json", action="store_true", help="print the raw extracted JSON instead")
    args = parser.parse_args()

    if not args.path.is_file():
        print(f"No such file: {args.path}")
        return 1

    try:
        report = extract_document(args.path.read_text())
    except LLMUnavailableError as e:
        print(e)
        return 1
    except errors.APIError as e:
        print(f"Gemini error {e.code}: {e.message}")
        return 1
    except KeyboardInterrupt:
        print("\nCancelled.")
        return 130

    if args.json:
        print(report.extraction.model_dump_json(indent=2))
    else:
        print_report(report)
    return 0


def print_report(report: ExtractionReport) -> None:
    x = report.extraction
    reasons = {(f.section, f.evidence): f.reason for f in report.unsupported}

    def mark(section: str, evidence: str) -> str:
        reason = reasons.get((section, evidence))
        return f"  ✗ ({reason})" if reason else "  ✓"

    print(f"\n{x.document_type}, dated {x.document_date} | {x.patient_name} ({x.patient_mrn})")

    print("\nDIAGNOSES")
    for d in x.diagnoses:
        print(f"{mark('diagnoses', d.evidence)} {d.name} [{d.status}] -> {d.condition}")

    print("\nMEDICATIONS")
    for m in x.medications:
        details = " ".join(part for part in (m.dose, m.route, m.frequency) if part)
        change = f" ({m.change_detail})" if m.change_detail else ""
        print(f"{mark('medications', m.evidence)} {m.name} {details} [{m.status}]{change}")

    print("\nALLERGIES")
    for a in x.allergies:
        print(f"{mark('allergies', a.evidence)} {a.substance} ({a.reaction or 'reaction not stated'})")

    print("\nLAB RESULTS")
    for r in x.lab_results:
        ref = f" (ref {r.reference_range})" if r.reference_range else ""
        print(f"{mark('lab_results', r.evidence)} {r.date or 'no date'}  {r.test} {r.value} {r.unit or ''}{ref}")

    if x.suspicious_content:
        print("\n⚠ SUSPICIOUS CONTENT (possible instructions aimed at the AI)")
        for quote in x.suspicious_content:
            print(f"{mark('suspicious_content', quote)} {quote!r}")

    total = len(x.diagnoses) + len(x.medications) + len(x.allergies) + len(x.lab_results)
    print(
        f"\n--- {total} facts, {len(report.unsupported)} failed verification"
        f" | model: {report.llm.model} | tokens: {report.llm.input_tokens} in, {report.llm.output_tokens} out ---"
    )


if __name__ == "__main__":
    sys.exit(main())
