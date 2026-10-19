"""Tests for evidence verification. No LLM involved, so these run instantly and for free.

Run from the project root:
    .venv/bin/python -m pytest
"""

from caregraph.extract import find_unsupported_facts
from caregraph.schemas import Allergy, DocumentExtraction, LabResult, Medication

DOCUMENT = """\
ALLERGIES
- Penicillin: generalised rash (documented 2019)

DISCHARGE MEDICATIONS
- Lisinopril 10 mg PO once daily - DOSE REDUCED (previously 20 mg) due to AKI

INVESTIGATIONS
Test                 Admission (02-24)   Discharge (03-01)   Reference
Creatinine           1.6                 1.2                 0.7-1.3 mg/dL
Haemoglobin          11.2                12.1                13.0-17.0 g/dL
"""


def make_extraction(
    allergy_evidence: str = "Penicillin: generalised rash",
    medication_evidence: str = "Lisinopril 10 mg PO once daily",
    lab_results: list[LabResult] | None = None,
) -> DocumentExtraction:
    return DocumentExtraction(
        document_type="discharge_summary",
        document_date=None,
        patient_name=None,
        patient_mrn=None,
        diagnoses=[],
        medications=[
            Medication(
                name="Lisinopril",
                dose="10 mg",
                route="PO",
                frequency="once daily",
                status="changed",
                change_detail="previously 20 mg",
                evidence=medication_evidence,
            )
        ],
        allergies=[Allergy(substance="Penicillin", reaction="rash", evidence=allergy_evidence)],
        lab_results=lab_results or [],
        suspicious_content=[],
    )


def lab(value: str, evidence: str) -> LabResult:
    return LabResult(
        test="Creatinine", value=value, unit="mg/dL", date=None, reference_range=None, evidence=evidence
    )


def test_exact_quotes_are_supported():
    extraction = make_extraction(
        allergy_evidence="Penicillin: generalised rash",
        medication_evidence="Lisinopril 10 mg PO once daily",
    )
    assert find_unsupported_facts(extraction, DOCUMENT) == []


def test_formatting_differences_are_forgiven():
    # Different case, extra spaces, and an en dash instead of a hyphen: same content.
    extraction = make_extraction(
        allergy_evidence="PENICILLIN:   generalised rash",
        medication_evidence="Lisinopril 10 mg PO once daily – DOSE REDUCED",
    )
    assert find_unsupported_facts(extraction, DOCUMENT) == []


def test_invented_quote_is_caught():
    # The document says 10 mg. A model that "remembered" a different dose gets flagged.
    extraction = make_extraction(
        allergy_evidence="Penicillin: generalised rash",
        medication_evidence="Lisinopril 20 mg PO once daily",
    )
    unsupported = find_unsupported_facts(extraction, DOCUMENT)
    assert len(unsupported) == 1
    assert unsupported[0].section == "medications"
    assert unsupported[0].label == "Lisinopril"
    assert unsupported[0].reason == "quote not in document"


# Exercise 2: the same safety net, for allergies.
def test_invented_allergy_is_caught():
    extraction = make_extraction(allergy_evidence="Sulfa: hives")
    unsupported = find_unsupported_facts(extraction, DOCUMENT)
    assert len(unsupported) == 1
    assert unsupported[0].section == "allergies"
    assert unsupported[0].label == "Penicillin"


# Exercise 3: a real quote isn't enough - the extracted value must be in it too.
def test_lab_value_matching_its_quote_is_supported():
    extraction = make_extraction(lab_results=[lab("1.6", "Creatinine 1.6 1.2 0.7-1.3 mg/dL")])
    assert find_unsupported_facts(extraction, DOCUMENT) == []


def test_lab_value_missing_from_its_quote_is_caught():
    # The quote is real, but the model put 2.6 in the value field.
    extraction = make_extraction(lab_results=[lab("2.6", "Creatinine 1.6 1.2 0.7-1.3 mg/dL")])
    unsupported = find_unsupported_facts(extraction, DOCUMENT)
    assert len(unsupported) == 1
    assert unsupported[0].section == "lab_results"
    assert unsupported[0].reason == "value not in its quote"


def test_lab_value_must_match_a_whole_number():
    # "1.2" appears inside "11.2" as text, but they're different numbers.
    extraction = make_extraction(lab_results=[lab("1.2", "Haemoglobin 11.2 12.1")])
    unsupported = find_unsupported_facts(extraction, DOCUMENT)
    assert [f.reason for f in unsupported] == ["value not in its quote"]
