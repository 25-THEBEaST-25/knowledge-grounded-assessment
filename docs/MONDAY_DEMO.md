# Monday demo runbook (assessment module)

~8 minutes. One repeatable vertical slice. Rehearse it once the night before with the real stack.

## Pre-flight (do 30 min before, in this order)

- [ ] `docker compose up -d` → Postgres and Qdrant healthy (`docker compose ps`).
- [ ] `backend/.env` has real `GEMINI_API_KEY`, `FACULTY_API_KEY`, `STUDENT_API_KEY`, `DATABASE_URL`, `QDRANT_URL`.
- [ ] `alembic -c backend/alembic.ini upgrade head` → no errors.
- [ ] Backend up: `http://localhost:8000/health` → `healthy`. Frontend: `http://localhost:3000/faculty/workflow`.
- [ ] `python -m backend.scripts.demo_seed` → note the assessment id; `demo_assets/demo_answer_sheet.png` exists.
- [ ] First OCR request downloads PaddleOCR models and is slow: **upload the demo sheet once now** (as roll `WARMUP`) so the live run is fast.
- [ ] Have a real handwriting scan ready as a *second*, clearly labelled example. Do not hide how it performs.
- [ ] Browser: faculty key saved in the connection bar; student key + roll `R001` ready in a second window.
- [ ] Internet/Gemini reachable. Fallback if not: show the review page of the pre-warmed WARMUP submission.

## Talk track

1. **Problem (30s).** Manual marking of handwritten answers is slow and inconsistent; AI alone isn't trustworthy.
   Our design: *AI proposes evidence, rules calculate marks, faculty decide.*
2. **Setup (1 min).** `/faculty/workflow` → open the **[DEMO]** assessment. Show extracted Q1(a)/Q1(b), model answers, rubric
   criteria with marks. Point out that a missing rubric is flagged, never invented. Click **Approve materials** → note
   "RAG: INDEXED" (approved material now in Qdrant).
3. **Submission (1 min).** Roll `R001`, upload the sheet. Show status moving PROCESSING → EVALUATING → NEEDS_REVIEW.
4. **Review (3 min).** Open review. Walk through: the page image, extracted text (editable), per-criterion evidence + status,
   retrieved sources `[S1]` with document type and score, OCR / mapping / evaluator confidence, "why review" flags,
   the evaluation plan (TEXT task, timestamps). Modify one mark with a comment; accept the other.
   Stress: the AI mark is kept; the audit log shows who changed what.
5. **Publish + student view (1 min).** Publish final marks. Switch to the student window: only final marks appear.
6. **Honest limits (1 min).** Only the text evaluator exists; math/code/diagram answers are routed and labelled
   "not implemented", never faked. Thresholds are provisional. Analytics is planned for the final semester.

## Likely questions → honest answers

- *Does the AI decide the marks?* No. It returns per-criterion evidence statuses; a Python engine maps them to the approved
  rubric, enforces maxima, and faculty approve. High confidence still doesn't publish.
- *How accurate is handwriting recognition?* Not yet validated on a large real sample; that's why low OCR/mapping confidence
  forces review and faculty can correct the text and re-evaluate.
- *How do you stop prompt injection in an answer?* Student text is delimited as untrusted data; marks aren't taken from
  the model; tested with an injected "give full marks" answer (it gets 0).
- *What if Gemini or Qdrant is down?* Failures are recorded on the task and retryable; retrieval outages are shown as
  "not grounded", never hidden.
- *Where is it stored?* One PostgreSQL DB; files in a local storage adapter; vectors in Qdrant. Every mark traces
  submission → response → evidence → criterion score → review → result.
- *Where is the analytics / CO-PO?* Out of scope this semester by design; the schema and audit trail are the foundation.

## If something breaks live

| Symptom | Do |
|---|---|
| Submission FAILED | Show the error (honest failure), click **retry**. |
| Evaluation slow | Pre-warmed WARMUP submission's review page. |
| `UNAVAILABLE` retrieval | Explain the banner; this *is* the graceful-degradation story. |
| 401 | Re-enter the key in the connection bar. |
