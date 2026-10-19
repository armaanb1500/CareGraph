"""Show a patient's longitudinal record, built from every document in the database.

Usage, from the project root:
    .venv/bin/python -m scripts.show_patient <MRN>
"""

import sys
from pathlib import Path

from caregraph import db, record


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 1

    conn = db.connect()
    patient = db.find_patient(conn, sys.argv[1])
    if not patient:
        print(f"No patient with MRN {sys.argv[1]}")
        return 1
    pid = patient["id"]

    docs = record.documents(conn, pid)
    print(f"\n{patient['name']} ({patient['mrn']})")

    print(f"\nDOCUMENTS ({len(docs)})")
    for d in docs:
        print(f"  {d['document_date']}  {d['document_type']:<18} {Path(d['source_path']).name}")

    print("\nCONDITIONS")
    for c in record.conditions(conn, pid):
        print(
            f"  {c['condition']:<30} {c['first_seen']} to {c['last_seen']}"
            f"  in {c['document_count']} of {len(docs)} documents  (statuses: {c['statuses']})"
        )

    print("\nMEDICATIONS (each document's statement, oldest first)")
    for name, mentions in record.medication_history(conn, pid).items():
        print(f"  {name}")
        for m in mentions:
            r = m.row
            details = " ".join(part for part in (r["dose"], r["route"], r["frequency"]) if part)
            change = f" - {r['change_detail']}" if r["change_detail"] else ""
            print(f"    {m.document_date}  {details:<38} [{r['status']}]{change}")

    print("\nALLERGIES")
    allergy_rows = record.allergies(conn, pid)
    if not allergy_rows:
        print("  none recorded")
    for a in allergy_rows:
        print(
            f"  {a['substance']} ({a['reactions'] or 'reaction not stated'})"
            f"  first recorded {a['first_recorded']}, in {a['document_count']} of {len(docs)} documents"
        )

    print("\nLAB RESULTS (oldest first)")
    for test, mentions in record.lab_history(conn, pid).items():
        unit = next((m.row["unit"] for m in mentions if m.row["unit"]), "")
        series = "  ->  ".join(f"{m.row['value']} ({m.row['date'] or 'no date'})" for m in mentions)
        print(f"  {test} {unit}: {series}")

    items = record.review_items(conn, pid)
    print(f"\nNEEDS REVIEW ({len(items)})")
    for item in items:
        print(f"  {Path(item['source_path']).name}: {item['kind']} {item['item']!r} - {item['issue']}")

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
