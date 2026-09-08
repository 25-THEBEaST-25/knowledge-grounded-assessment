![Python](https://img.shields.io/badge/Python-3.13-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688)
![Next.js](https://img.shields.io/badge/Next.js-Frontend-black)
![License](https://img.shields.io/badge/License-MIT-green)

# SNAPTIX — AI-Assisted Academic Assessment Platform

> Handwritten answer sheets evaluated by OCR and AI, with explainable, rubric-aware feedback for faculty and students.

---

## What this actually is, right now

This README describes the current state of the repository honestly. Where an earlier
version of this document claimed features that don't exist yet (RAG, multi-agent
evaluation, diagram/code grading, full OBE automation), those claims have been moved to
[**Roadmap**](#roadmap--not-yet-implemented) below and to the in-app
`/roadmap` page, which exists specifically so a demo never has to gloss over the gap
between what's built and what's planned.

### Implemented and verified

- **Handwritten answer evaluation pipeline**: upload an image → PaddleOCR extracts text
  (with reading-order line sorting and configurable preprocessing for small/low-contrast
  scans) → deterministic regex-based question segmentation → one Gemini call per
  question, scoring conceptual understanding, accuracy, precision and terminology
  against the faculty's model answer and rubric.
- **Score integrity**: every score is hard-clamped server-side to the rubric's
  authoritative maximum, regardless of what the model returns. The student-answer text
  is explicitly delimited in the prompt as untrusted data — a prompt-injection attempt
  embedded in a scanned answer cannot award itself marks.
- **Safe failure modes**: a missing `GEMINI_API_KEY`, a Gemini rate limit, a provider
  outage, or an unavailable OCR engine all return a clear error to the client (503/500
  with a safe message) — never a stack trace, a provider error string, or a fabricated
  result. Transient provider failures (429, 5xx, DEADLINE_EXCEEDED-style timeouts) get a
  small bounded retry with exponential backoff first; permanent errors (bad key,
  malformed request) are never retried.
- **Faculty portal** (`/faculty`): dashboard, an assessment workflow (create → add
  questions/rubric → upload a real answer sheet → evaluate → publish), the standalone
  Answer Evaluation tool, a student roster, analytics (score distribution, weakest
  questions, CO/PO attainment), and reports.
- **Student portal** (`/student`): dashboard, results with full per-question breakdowns,
  an AI feedback feed, a learning-gaps view, and a profile page.
- **Demo data, clearly labelled**: most numbers in both portals come from a hand-authored
  sample dataset (`frontend/app/lib/demoData.ts`) rather than a live database, and every
  such widget carries a visible "Demo data" badge. The one thing that is never demo data
  is the handwritten evaluation pipeline itself — every score you get from it is a real
  OCR + Gemini result.

### Known limitations (see [Roadmap](#roadmap--not-yet-implemented) for detail)

No database, no authentication, no RAG/knowledge retrieval, no multi-agent evaluation, no
diagram or code grading, and no fully-automated OBE pipeline exist yet. Faculty-created
assessments are persisted in the browser's `localStorage`, not a shared server database —
they are real, but private to the device that created them.

---

## Architecture

```
frontend/  Next.js 16 (App Router) + Tailwind CSS
  app/faculty/    Faculty portal
  app/student/    Student portal
  app/lib/        Domain model, demo dataset, local-assessment storage,
                  the one real backend API client, and the useClientData
                  hook that safely reads browser-only data without a
                  hydration mismatch
  app/components/ Shared UI (AppShell, sidebar, ui/ kit) + the handwritten
                  evaluation panel

backend/   FastAPI + PaddleOCR + google-genai (Gemini)
  app/api/        evaluation.py (generic text grading), handwritten.py
                  (OCR / segment / full pipeline)
  app/services/   ocr_service, segmentation_service, pipeline_service,
                  evaluation_service
  tests/          49 tests — segmentation, score integrity, prompt
                  injection, image safety, OCR preprocessing, Gemini
                  provider-failure handling, API wiring
```

---

## Setup

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Python 3.10–3.13
pip install -r requirements.txt
cp .env.example .env                                  # then set GEMINI_API_KEY
```

Run from the **repository root** (imports are `backend.app...`):

```bash
set -a; source backend/.env; set +a
uvicorn backend.app.main:app --reload --port 8000
```

Swagger UI: http://localhost:8000/docs · Health check: http://localhost:8000/health

PaddleOCR downloads its models (~/.paddlex/official_models) on first use; the first OCR
request takes noticeably longer than subsequent ones.

**Environment variables** (`backend/.env.example` is the authoritative list):

| Variable | Default | Purpose |
| --- | --- | --- |
| `GEMINI_API_KEY` | — | Required for `/evaluation/evaluate` and `/handwritten/evaluate` |
| `GEMINI_MODEL` | `gemini-3.6-flash` | Override if unavailable in your region/project |
| `GEMINI_TIMEOUT_MS` | `60000` | Per-request timeout before failing as unavailable |
| `GEMINI_MAX_RETRIES` | `2` | Bounded retries (exponential backoff) for transient 429/5xx/timeout failures; permanent errors are never retried |
| `OCR_LANG` / `OCR_DEVICE` | `en` / `cpu` | PaddleOCR config |
| `OCR_UPSCALE` / `OCR_TARGET_LONG_SIDE` | `true` / `2000` | Upscale small scans before OCR |
| `OCR_AUTOCONTRAST` | `true` | Widen contrast on faint/washed-out scans |
| `OCR_DENOISE` | `false` | Opt-in median filter; off by default (unvalidated against real handwriting) |
| `REVIEW_CONFIDENCE_THRESHOLD` | `0.6` | Below this combined confidence, a result is flagged `needs_review` |
| `CORS_ORIGINS` | `http://localhost:3000` | Allowed frontend origin(s) |

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000 — you'll land on a Faculty/Student portal picker. Set
`NEXT_PUBLIC_API_URL` if the backend isn't on `http://localhost:8000`.

### Tests

```bash
# Backend — from repo root; PaddleOCR and Gemini are faked, no key needed
pip install pytest httpx
pytest                          # 49 tests

# Frontend — from frontend/
npm run lint
npm run build
```

---

## API endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Liveness |
| POST | `/evaluation/evaluate` | Text answer → Gemini evaluation (generic, no OCR) |
| POST | `/handwritten/ocr` | Image → PaddleOCR text + per-line confidence |
| POST | `/handwritten/segment` | Text → question-wise segments |
| POST | `/handwritten/evaluate` | Image → OCR → segmentation → per-question evaluation |

Curl examples and the full request/response shape are in `backend/README.md`.

---

## Demo flow (Wednesday walkthrough)

1. **Faculty** (`/faculty`) — dashboard shows the class overview; note the "Demo data"
   badges on anything not backed by a real evaluation.
2. **Create an assessment** (`/faculty/assessments` → New assessment) — title, subject,
   questions with model answers and rubric criteria. Saved to this browser only (labelled
   as such).
3. **Evaluate a real answer sheet** — open the new assessment, pick a student, upload an
   image, click Evaluate. This is a real `POST /handwritten/evaluate` call: real OCR,
   real segmentation, real Gemini scoring. Requires the backend running and
   `GEMINI_API_KEY` configured.
4. **Publish** the assessment, then switch to the **Student portal** — the same result
   appears under My Results, tagged "Real evaluation" rather than "Demo data", with the
   full per-question breakdown, AI feedback, and a computed strong/weak-area summary.
5. **Learning Gaps and Analytics** — built from the same underlying per-question,
   per-topic data; explicitly labelled where the dataset behind them is the sample
   dataset rather than live submissions.
6. **`/roadmap`** — the honest list of what's implemented vs. planned, worth having open
   if a reviewer asks about RAG, multi-agent evaluation, or OBE automation.

---

## Roadmap / not yet implemented

- **Real persistence (PostgreSQL)** — everything faculty-created today lives in browser
  `localStorage`. A shared database is the prerequisite for multi-device, multi-user use.
- **Authentication & roles** — there is no login yet; the Faculty/Student split is a
  navigation choice, not an access-controlled account system.
- **Knowledge-grounded retrieval (RAG)** — no Qdrant, LlamaIndex, or embedding pipeline
  exists. Evaluation grades directly against the supplied rubric and model answer.
- **Multi-agent evaluation** — no LangGraph or agent orchestration exists. Evaluation is
  one Gemini call per question, not separate Concept/Accuracy/Diagram/Code/Consensus
  agents.
- **Diagram evaluation** and **Code evaluation** — no service exists for either yet.
- **Full OBE automation** — the CO/PO attainment and CO→PO matrix in Analytics are a
  demo illustration of the intended surface with a transparent, inspectable formula, not
  an accreditation-derived automated pipeline.
- **CI/CD** — tests run locally; nothing runs them automatically on push yet.

See `/roadmap` in the running app for the same list alongside what **is** implemented.

---

## Team

- Aryan Wesavkar
- Siddhant Jadhav
- Sidhan Mahulkar
- Prathamesh Mane

Department of Computer Engineering, K.C. College of Engineering & Management Studies & Research

Bachelor of Engineering Major Project.

## License

MIT.
