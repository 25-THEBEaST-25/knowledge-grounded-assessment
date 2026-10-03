# Assessment workflow (SNAPTIX assessment module)

Faculty setup → approval → student answer sheet → OCR/mapping → Orchestrator plan → RAG → TEXT evaluator
(evidence only) → deterministic Assessment Engine → confidence checks → faculty review → stored result + audit trail.

## Run locally

```bash
docker compose up -d                      # PostgreSQL + Qdrant (dev passwords, see docker-compose.yml)
cp backend/.env.example backend/.env      # set GEMINI_API_KEY, FACULTY_API_KEY, STUDENT_API_KEY (long random values)
set -a; source backend/.env; set +a
pip install -r backend/requirements.txt
alembic -c backend/alembic.ini upgrade head
uvicorn backend.app.main:app --reload --port 8000
cd frontend && npm install && npm run dev  # http://localhost:3000/faculty/workflow
```

Without `DATABASE_URL` the app falls back to a local SQLite file (development only). Without `QDRANT_URL`
retrieval is reported as `UNAVAILABLE` and evaluation says so; RAG is never pretended.

## Monday demo (repeatable)

1. `python -m backend.scripts.demo_seed` → prints a **demo** assessment id and writes `demo_assets/demo_answer_sheet.png`
   (synthetic *printed* text, not handwriting).
2. Open `/faculty/workflow`, paste the faculty key into the connection bar, open the demo assessment.
3. Review the extracted Q1(a)/Q1(b), rubric criteria and marks (edit if you like) → **Approve materials**
   (this also indexes the approved material into Qdrant).
4. Upload the sheet with a roll number → it processes in the background; the status badge updates.
5. **Open review**: sheet page, extracted text, rubric criteria with evidence + sources, confidence, warnings.
6. Accept / modify / reject each question (modify/reject need a comment) → **Publish final marks**.
7. Student side: `/student/workflow` with the student key + the same roll number shows published marks only.

## Data flow → tables written

| Stage | Tables |
|---|---|
| Create assessment | `subjects`, `assessments`, `audit_logs` |
| Upload materials | `documents`, `questions`, `subquestions`, `model_answers`, `rubrics`, `rubric_criteria` |
| Approve | approval flags on the above, `documents.index_status`; vectors in Qdrant |
| Upload sheet | `students`, `submissions` |
| OCR + mapping | `student_responses` (text, OCR/mapping confidence, page+bbox, review reasons) |
| Orchestrate | `evaluation_plans`, `evaluation_tasks` |
| Evaluate | `evaluation_results` (raw output, retrieved sources), `evidence` |
| Score (Python engine) | `criterion_scores`, `assessment_results` |
| Faculty review | `human_reviews` (append-only; AI result is never overwritten), `audit_logs` |
| Publish | `assessment_results.published` |

## Safety properties (covered by tests)

LLM never computes marks; criterion/question maxima enforced; duplicate evidence can't double-award
(plus a unique constraint); AI marks stay proposals until faculty review; missing rubric / uncertain mapping /
evaluator failure each force review; student/document text is delimited as untrusted data.

## Known limitations

- Only the TEXT evaluator exists. MATH/CODE/VISUAL/MCQ responses are routed and labelled `NOT_IMPLEMENTED`
  (no marks simulated); they require faculty marking.
- Confidence thresholds (0.90 / 0.75 / OCR 0.80) are provisional, uncalibrated, and model confidence is only a hint.
- Handwriting accuracy is unvalidated: no genuine handwriting sample has been tested.
- Auth is shared per-role API keys with self-declared reviewer/roll, not per-user accounts or SSO.
- Page images are shown unannotated; bbox regions are stored but not overlaid.
- Tests use fakes for Gemini/OCR/embeddings and SQLite; the CI `migrations` job exercises real PostgreSQL DDL,
  but there is no automated test against a live Gemini, Qdrant server or PaddleOCR on real handwriting.
