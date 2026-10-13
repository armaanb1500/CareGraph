"""Stage 1: summarize a single clinical document for a clinician."""

from caregraph.llm import LLMResult, generate

SYSTEM_PROMPT = """\
You are a clinical documentation assistant that supports licensed clinicians.
You summarize medical documents. You do not diagnose, recommend treatment, or give medical advice.

Rules:
- Use only information stated in the document. Never add facts, guesses, or general medical knowledge.
- If something is missing or unclear, write "not stated in the document".
- Copy drug names, doses, dates and lab values exactly as written.
- Write for a busy clinician: short, scannable, no filler.

Use these sections:
1. Overview (one line)
2. Diagnoses
3. Medications (mark each as new, changed, stopped, or continued)
4. Allergies
5. Key results
6. Follow-up actions
"""


def summarize_document(text: str) -> LLMResult:
    # The <document> tags mark exactly where the document starts and ends, so the
    # model treats its contents as data to summarize rather than instructions to follow.
    prompt = f"Summarize this clinical document.\n\n<document>\n{text}\n</document>"
    return generate(prompt, system=SYSTEM_PROMPT)
