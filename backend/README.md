# Backend (FastAPI)

## Setup

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Python 3.10 - 3.13
pip install -r requirements.txt
cp .env.example .env                                  # set GEMINI_API_KEY
```

Run from the **repository root** (imports are `backend.app...`):

```bash
set -a; source backend/.env; set +a
uvicorn backend.app.main:app --reload --port 8000
```

Swagger UI: http://localhost:8000/docs

PaddleOCR downloads its models (~/.paddlex/official_models) on the first OCR
request; the first call takes a few seconds longer.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | liveness |
| POST | `/evaluation/evaluate` | text answer -> Gemini evaluation (baseline evaluator) |
| POST | `/handwritten/ocr` | image -> PaddleOCR text + per-line confidence |
| POST | `/handwritten/segment` | text -> question-wise segments |
| POST | `/handwritten/evaluate` | image -> OCR -> segmentation -> per-question evaluation |

### Vertical slice

```
handwritten answer image -> PaddleOCR -> extracted text -> question-wise segmentation
  -> evaluate_answer() per question -> marks + feedback + strengths + missing concepts + confidence
```

```bash
# Step 1 only
curl -F "image=@answer_sheet.jpg" http://localhost:8000/handwritten/ocr

# Step 2 only
curl -H 'Content-Type: application/json' -d '{"text":"Q1. ...\nQ2. ...","expected_question_ids":["Q1","Q2"]}' \
  http://localhost:8000/handwritten/segment

# Full pipeline
curl -F "image=@answer_sheet.jpg" \
  -F 'questions=[{"question_id":"Q1","question":"Define photosynthesis.","model_answer":"Photosynthesis converts light energy into chemical energy (glucose) using CO2 and water, releasing O2.","rubric":{"max_score":10,"criteria":{"concept":4,"accuracy":3,"precision":2,"terminology":1}}}]' \
  http://localhost:8000/handwritten/evaluate
```

Response (abridged):

```json
{
  "extracted_text": "Q1. Photosynthesis ...",
  "ocr_confidence": 0.91,
  "segments": [{"question_id": "Q1", "text": "Photosynthesis ...", "detected": true}],
  "results": [{
    "question_id": "Q1", "score": 7, "max_score": 10,
    "strengths": ["..."], "missing_concepts": ["..."], "feedback": "...",
    "confidence": 0.85, "ocr_confidence": 0.91, "combined_confidence": 0.81,
    "needs_review": false
  }],
  "total_score": 7, "total_max_score": 10, "overall_confidence": 0.81, "needs_review": false
}
```

- Questions listed in `questions` but not found on the sheet are returned with
  `answer_detected: false`, `score: 0` and `needs_review: true`.
- `combined_confidence = evaluator_confidence * (0.5 + 0.5 * ocr_confidence)`;
  `needs_review` when below `REVIEW_CONFIDENCE_THRESHOLD` (default 0.6).
- Segmentation recognises `Q1`, `Q.1`, `Question 1`, `Ans 1`, `1.`, `1)`, `(1)`,
  `Q1(a)` and common OCR mis-reads (`Ql`, `0.1`).

## Tests

```bash
pip install pytest httpx
pytest            # from repo root; PaddleOCR and Gemini are faked, no key needed
```

## Notes

- `OCR_ENABLE_MKLDNN` defaults to `false`: PaddlePaddle 3.3.1 raises
  `ConvertPirAttribute2RuntimeAttribute not support` on the default PP-OCRv6
  models when oneDNN is enabled.
- If `paddleocr` is not installed the API still boots; `/handwritten/*` OCR
  endpoints return HTTP 503 with an explanatory message.
- A missing/invalid `GEMINI_API_KEY`, a Gemini rate limit (429), a provider
  error, or a network/timeout failure (`GEMINI_TIMEOUT_MS`, default 30s) all
  return HTTP 503 with a safe message from both `/evaluation/evaluate` and
  `/handwritten/evaluate` -- never a stack trace or the provider's raw error.
- OCR preprocessing (`OCR_UPSCALE`, `OCR_TARGET_LONG_SIDE`, `OCR_AUTOCONTRAST`,
  `OCR_DENOISE`) is applied only to the copy of the image handed to the OCR
  engine; see `ocr_service.preprocess_for_ocr` for what each does and why
  `OCR_DENOISE` defaults off.
