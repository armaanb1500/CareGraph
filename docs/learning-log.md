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

## Stage 1: First LLM call

### Anatomy of an LLM call (`caregraph/llm.py`)
Every call sends the same four things:
- **model**: which LLM answers (`gemini-3.8-flash`).
- **system instruction**: standing rules for how to behave ("use only the document").
- **contents**: the actual request, including the document.
- **config**: knobs like `temperature`.

And gets back:
- **text**: the answer.
- **usage**: token counts. Tokens are chunks of words (~4 characters each). APIs bill and
  rate-limit by tokens. "Thinking" tokens are the model reasoning privately before it answers.

### Temperature
Controls randomness. 0-0.3 gives consistent, factual output (what we want for medical
records); 0.7+ gives varied, creative output. We use 0.2.

### Prompt engineering in `caregraph/summarize.py`
- **Role and limits**: "supports licensed clinicians... does not diagnose."
- **Grounding**: "use only information stated in the document." Without this, LLMs fill gaps
  with plausible-sounding guesses. That's called *hallucination*.
- **An escape hatch**: "write 'not stated in the document'". The model needs a permitted way
  to say "I don't know", or it will invent something.
- **Exactness**: "copy doses and values exactly." The model shouldn't round 8.4% to "about 8%".
- **Fixed sections**: predictable output that's easy to scan (and easier to parse later).
- **Delimiters**: `<document>...</document>` marks where the document starts and ends. If a
  document contained text like "ignore your instructions", the tags help the model treat it as
  data. Defending against that kind of attack is called *prompt-injection defence*.

### Layers: why three files instead of one
- `llm.py`: *how* to talk to an LLM (provider, retries). Knows nothing about medicine.
- `summarize.py`: *what* to ask (the prompt). Knows nothing about Gemini.
- `scripts/summarize_document.py`: *entry point*. Reads a file, prints the result.
Each layer can change without touching the others. Swapping Gemini for Ollama only touches `llm.py`.
Adding a FastAPI endpoint in Stage 4 will reuse `summarize.py` unchanged.

### Reliability: retries, backoff, fallback
Free-tier models are often overloaded (HTTP 503) or rate-limited (HTTP 429).
- **Retry**: these errors are temporary, so try again.
- **Exponential backoff**: wait 2s, then 4s, then longer, so we don't hammer a struggling server.
- **Fallback models**: if the preferred model stays busy, try the next one in `GEMINI_FALLBACK_MODELS`.
- **Don't retry real errors**: a bad key (401) or bad request (400) will fail every time.
- **Timeouts**: a congested server can hang for 90 seconds before failing. Any call over a
  network needs a timeout (we use 40s), or your program can wait forever. A slow model is
  skipped straight away rather than retried.
- **Visible progress**: "(asking gemini-3.8-flash...)" means a slow call never looks like a freeze.
- **Custom exceptions**: `LLMUnavailableError` lets the script show one clear message instead
  of a 60-line traceback.

### Model versions
Google retired `gemini-2.5-flash` for new users while it still appeared in the model list.
Lessons: pin an exact model version (not `-latest`, which can change under you), test with a
real call, and record which model produced each output (`LLMResult.model`). In healthcare
you need to be able to answer "which model wrote this summary?"

## Stage 2: Structured extraction

### Why structured data
Prose (Stage 1) is for humans. Programs need data in a fixed shape: a list of medications,
each with a name, dose and status. Only structured data can be stored in a database (Stage 3),
compared across visits (Stage 7), and checked for conflicts (Stage 8).

### Schemas with Pydantic (`caregraph/schemas.py`)
A Pydantic model describes a data shape: which fields exist and what type each one is.
It does two jobs here:
- **Instructions**: the schema is sent to Gemini (`response_schema=...`), which then returns JSON in
  exactly that shape. Field `description`s are read by the model, so they work like extra prompt text.
- **Validation**: `schema.model_validate_json(...)` checks the reply. A missing field or an
  unexpected value raises a `ValidationError` instead of bad data getting through.

Design choices worth noticing:
- `Literal["new", "changed", ...]` limits a field to a fixed set of values, so the model can't
  invent a status like "probably continued".
- `not_stated` is offered in every status list. That's the escape hatch from Stage 1, in schema form.
- Lab `value` is a string, not a number, so "8.4%" and "<5" survive exactly as written.
- Separate `dose`, `route` and `frequency` fields. In a quick test, a vaguer schema put "PRN"
  (which means "as needed", a frequency) into the dose field.

### Evidence and verification (`caregraph/extract.py`)
Every fact must include an `evidence` quote copied from the document. Then `find_unsupported_facts`
(plain Python, no AI) checks that each quote really appears in the document text.
- This is **"trust, but verify"**: the LLM does the hard reading, deterministic code checks its work.
- `_normalize` ignores formatting (case, extra spaces, dash and quote styles) but not content.
- **Second check for labs**: the extracted value must also appear in its own quote, as a whole
  number ("1.2" doesn't count inside "11.2"). A real quote can no longer vouch for a wrong value.
- **Remaining gaps**: doses aren't value-checked yet, and nothing catches a fact the model *left out*.

### Defence against prompt injection, layer 2
`suspicious_content` gives the model a specific place to put text that looks like instructions.
On the attack file, the model kept the penicillin allergy *and* flagged the planted note. A
flagged item can then be shown to a human reviewer instead of being silently obeyed or ignored.

### Temperature 0 for extraction
Extraction should give the same answer every time, so `generate_structured` defaults to 0.

### Generic functions
`def generate_structured[T: BaseModel](prompt, schema: type[T]) -> tuple[T, LLMResult]` means:
"pass in any Pydantic model class, get back an instance of that same class." Your editor then
knows that extracting with `DocumentExtraction` returns a `DocumentExtraction`.

### Automated tests (`tests/`)
Tests are code that checks your code. `pytest` finds every `test_*` function and runs it;
`assert` fails the test if something isn't true. Because evidence verification involves no AI,
its tests are instant, free, and give the same result every time. Run them with
`.venv/bin/python -m pytest` after every change.

### What the Stage 2 exercises taught
- **Conflicting prompt rules**: "include every mention" and "merge duplicates" pulled against each
  other, and the small model couldn't do both. Adding more rules made it worse, not better.
- **Vague fields give random answers**: "active" vs "not_stated" flipped between runs even at
  temperature 0, because "active" had no definition. Defining each status by something *visible
  in the document* ("listed among the discharge diagnoses") made it consistent.
- **Omission is a separate failure**: one run silently dropped hyperlipidaemia. Verification
  catches invented facts, not missing ones. Testing several runs is how you notice.
- **Give each job to the right worker**: the LLM now records every mention plus a standard
  `condition` name; *code* groups mentions by that name. Grouping is predictable logic, so it
  belongs in code, where it's testable and works across documents too. Real systems do this
  with standard medical codes (SNOMED CT, ICD-10).
- **Test-driven development**: write the test, watch it fail (red), write the code, watch it pass
  (green). A failing test proves the bug was real. And while writing one test, a test was itself
  wrong ("1.2" never appeared inside the quote it used). Tests need checking too.

## Stage 3: The patient record database

### Relational databases in one picture
```
patients 1 ──< documents 1 ──< diagnoses / medications / allergies / lab_results / suspicious_content
```
"1 ──<" means one-to-many: a patient has many documents, a document has many facts.
- **Table**: like a spreadsheet tab with fixed columns. **Row**: one record.
- **Primary key** (`id`): a unique number for each row, filled in by SQLite.
- **Foreign key** (`REFERENCES`): a column pointing at another table's row, e.g. `medications.document_id`.
  SQLite only enforces these after `PRAGMA foreign_keys = ON`.
- **Constraints**: `NOT NULL` (must have a value), `UNIQUE` (no two rows share it),
  `ON DELETE CASCADE` (deleting a document deletes its facts too).
- **Indexes**: let the database jump straight to "all facts for document 7" instead of scanning
  every row, like the index at the back of a book.

### Why we keep `raw_text` and `model`
Every fact can be re-checked against its original document, and we can say which model extracted
it. Later, with a better model, we can re-extract everything from the stored originals.

### Parameterized queries and SQL injection
`conn.execute("SELECT * FROM patients WHERE mrn = ?", (mrn,))`: the `?` is filled in by the database
as *pure data*. If you built the SQL with an f-string instead, a document containing
`'; DROP TABLE patients; --` could become part of the command. Never build SQL from strings.
It's the same idea as the `<document>` tags: keep data and instructions separate.

### Transactions
`with conn:` groups inserts into one all-or-nothing unit. If the 30th insert fails, the 29 before it
are undone (a "rollback"), so there's never a half-saved document. `test_failed_save_leaves_nothing_behind`
proves it.

### Idempotency
Running ingestion twice must not create duplicates. A SHA-256 hash (a fingerprint of the text) is
checked before calling the LLM, and `UNIQUE` on `content_hash` backs it up in the database itself.

### Patient matching
Filing a document under the wrong patient is one of the most dangerous errors a record system
can make. The MRN comes from the LLM, so ingestion checks it appears in the document, and warns
if the name differs from the existing record. Real hospitals use a Master Patient Index that
matches on several identifiers (name, date of birth, MRN) because MRNs differ between organisations.

### SQL for the record view (`caregraph/record.py`)
- **JOIN** follows foreign keys: medications → documents → patient.
- **GROUP BY** collapses many rows into one per group; **MIN / MAX / COUNT / GROUP_CONCAT** summarise each group.
- **UNION ALL** stacks several queries into one result (the "needs review" list).
- Dates are stored as `YYYY-MM-DD` text, so sorting alphabetically also sorts by date.

### Testing a database
- **Fixtures** (`@pytest.fixture`): setup code shared by tests; here, a fresh in-memory database.
- **`":memory:"`**: a database that exists only while the test runs.
- **Mocking** (`monkeypatch`): swap the real LLM for a fake that returns a "hallucinated" MRN,
  to test the safety check without calling Gemini.

### Imperfections the first real record showed (to fix in later stages)
1. **The same fact, reported twice**: HbA1c 8.4% was measured in February (discharge summary) and then
   *mentioned again* in April's lab report comment. The record shows it twice, once as "8.4%" and once
   as "8.4". Telling a new measurement from a restated one is a Stage 7 problem.
2. **Statuses pile up**: hypertension shows `not_stated, past_history, current`. The record lists what
   each document said; it doesn't yet say what the *latest* position is. That's Stage 7 too.
3. **A contradiction we can't see**: the GP note says "ALLERGIES: NKDA" (no known drug allergies), but
   the hospital recorded a penicillin allergy. Our schema has no way to express "no allergies", so the
   conflict is invisible. Stage 8 will make it visible.
4. **Names must match exactly**: "Fasting glucose" and "Glucose, fasting" would split into two lab series.
   Conditions already solve this with a standard `condition` name; labs will need the same.
