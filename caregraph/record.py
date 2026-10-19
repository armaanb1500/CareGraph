"""Reading a patient's longitudinal record: facts from all their documents, in date order.

Facts live in separate tables that point at documents, and documents point at patients.
A JOIN follows those links, so "all medications for patient 1" means:
    medications -> (document_id) -> documents -> (patient_id) -> patient 1

This module only reports what the documents say. It doesn't decide what's true.
"""

import sqlite3
from dataclasses import dataclass
from itertools import groupby


@dataclass
class Mention:
    """One fact, as stated in one document."""

    document_date: str | None
    document_type: str
    source_path: str
    row: sqlite3.Row  # the fact's own columns, e.g. row["dose"]


def documents(conn: sqlite3.Connection, patient_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT id, document_date, document_type, source_path, model
           FROM documents WHERE patient_id = ?
           ORDER BY document_date""",
        (patient_id,),
    ).fetchall()


def conditions(conn: sqlite3.Connection, patient_id: int) -> list[sqlite3.Row]:
    """One row per condition, however many times and places it was mentioned.

    GROUP BY collapses all mentions of a condition into one row; MIN/MAX/COUNT then
    summarise each group. lower() makes "Hypertension" and "hypertension" one group.
    """
    return conn.execute(
        """SELECT dx.condition,
                  MIN(doc.document_date)          AS first_seen,
                  MAX(doc.document_date)          AS last_seen,
                  COUNT(DISTINCT doc.id)          AS document_count,
                  GROUP_CONCAT(DISTINCT dx.status) AS statuses
           FROM diagnoses dx
           JOIN documents doc ON doc.id = dx.document_id
           WHERE doc.patient_id = ?
           GROUP BY lower(dx.condition)
           ORDER BY first_seen, dx.condition""",
        (patient_id,),
    ).fetchall()


def medication_history(conn: sqlite3.Connection, patient_id: int) -> dict[str, list[Mention]]:
    """Each medication's mentions across documents, oldest first."""
    rows = conn.execute(
        """SELECT med.*, doc.document_date, doc.document_type, doc.source_path
           FROM medications med
           JOIN documents doc ON doc.id = med.document_id
           WHERE doc.patient_id = ?
           ORDER BY lower(med.name), doc.document_date""",
        (patient_id,),
    ).fetchall()
    return _group(rows, key="name")


def lab_history(conn: sqlite3.Connection, patient_id: int) -> dict[str, list[Mention]]:
    """Each lab test's results over time, oldest first."""
    rows = conn.execute(
        """SELECT lab.*, doc.document_date, doc.document_type, doc.source_path
           FROM lab_results lab
           JOIN documents doc ON doc.id = lab.document_id
           WHERE doc.patient_id = ?
           ORDER BY lower(lab.test), lab.date""",
        (patient_id,),
    ).fetchall()
    return _group(rows, key="test")


def allergies(conn: sqlite3.Connection, patient_id: int) -> list[sqlite3.Row]:
    """Each allergy, and how many of the patient's documents record it."""
    return conn.execute(
        """SELECT al.substance,
                  GROUP_CONCAT(DISTINCT al.reaction) AS reactions,
                  MIN(doc.document_date)             AS first_recorded,
                  COUNT(DISTINCT doc.id)             AS document_count
           FROM allergies al
           JOIN documents doc ON doc.id = al.document_id
           WHERE doc.patient_id = ?
           GROUP BY lower(al.substance)
           ORDER BY al.substance""",
        (patient_id,),
    ).fetchall()


def review_items(conn: sqlite3.Connection, patient_id: int) -> list[sqlite3.Row]:
    """Everything a human should look at: failed verifications and suspicious passages.

    UNION ALL stacks the results of several SELECTs into one list.
    """
    return conn.execute(
        """SELECT doc.source_path, 'diagnosis' AS kind, dx.name AS item, dx.verification_issue AS issue
           FROM diagnoses dx JOIN documents doc ON doc.id = dx.document_id
           WHERE doc.patient_id = ? AND dx.verification_issue IS NOT NULL
           UNION ALL
           SELECT doc.source_path, 'medication', med.name, med.verification_issue
           FROM medications med JOIN documents doc ON doc.id = med.document_id
           WHERE doc.patient_id = ? AND med.verification_issue IS NOT NULL
           UNION ALL
           SELECT doc.source_path, 'allergy', al.substance, al.verification_issue
           FROM allergies al JOIN documents doc ON doc.id = al.document_id
           WHERE doc.patient_id = ? AND al.verification_issue IS NOT NULL
           UNION ALL
           SELECT doc.source_path, 'lab result', lab.test || ' ' || lab.value, lab.verification_issue
           FROM lab_results lab JOIN documents doc ON doc.id = lab.document_id
           WHERE doc.patient_id = ? AND lab.verification_issue IS NOT NULL
           UNION ALL
           SELECT doc.source_path, 'suspicious text', sc.quote, 'possible instruction aimed at the AI'
           FROM suspicious_content sc JOIN documents doc ON doc.id = sc.document_id
           WHERE doc.patient_id = ?""",
        (patient_id,) * 5,
    ).fetchall()


def _group(rows: list[sqlite3.Row], key: str) -> dict[str, list[Mention]]:
    """Group rows that are already sorted by `key`, ignoring upper/lower case.

    Each group is labelled with the spelling from its first row.
    """
    grouped = {}
    for _, group in groupby(rows, key=lambda r: r[key].lower()):
        group = list(group)
        grouped[group[0][key]] = [
            Mention(r["document_date"], r["document_type"], r["source_path"], r) for r in group
        ]
    return grouped
