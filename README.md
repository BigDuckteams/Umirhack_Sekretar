# Онлайн-деканат — цифровой секретарь документов

Engineering starter: **image → OCR → structured extraction → policy retrieval → cited guidance → human review**. Built around the uploaded case brief. MWS-Vision-Bench is an external document-vision regression suite, not a substitute for institution-specific policy QA.

## Architecture

```text
FastAPI → upload validation → OCR provider → field extraction → policy retrieval
        → answer + clause citations/abstention → SQLite audit store
```

Senior-oriented choices: separable services, typed API contracts, explicit confidence/evidence, abstention on missing evidence, traceable policy citations, request IDs, structured logs, health checks, tests, Docker, CI, threat model, and an evaluation plan.

## Quick start

Requirements: Python 3.11+, Tesseract OCR with Russian language data.

```bash
# Ubuntu/Debian
sudo apt-get update && sudo apt-get install -y tesseract-ocr tesseract-ocr-rus
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -e ".[dev]"
cp .env.example .env
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs`.

## API
- `GET /health/live`
- `GET /health/ready`
- `GET /v1/policies`
- `POST /v1/consultations` — multipart `question` + `file` (PNG/JPG/JPEG/WEBP)
- `GET /v1/consultations/{id}`

Example:
```bash
curl -X POST http://127.0.0.1:8000/v1/consultations \\
  -F 'question=Какие поля нужно проверить для перевода?' \\
  -F 'file=@document.jpg'
```

The response includes OCR text, fields with confidence/evidence, an answer, citations, warnings, and `needs_human_review`. The included policy is fictional demo content. This baseline must not be used for real administrative decisions.

## MWS-Vision-Bench

```bash
pip install -e ".[benchmark]"
python scripts/evaluate_mws.py --limit 20 --output artifacts/mws_sample.jsonl
```

The adapter reports an OCR-only character error rate on full-page OCR samples; it is **not** the official overall benchmark score. The public dataset has 1,302 questions across document parsing, full-page OCR, key-information extraction, reasoning VQA, and text grounding. Dataset: https://huggingface.co/datasets/MTSAIR/MWS-Vision-Bench ; official code: https://github.com/mts-ai/MWS-Vision-Bench. Review upstream license/attribution before redistribution.

## Quality checks
```bash
ruff check .
pytest
```

## Before production
- Add institutional SSO/OIDC, RBAC, rate limiting, TLS and malware scanning.
- Add policy versioning, effective dates and an approval workflow.
- Define retention/deletion; OCR text can contain personal data.
- Add PII redaction, encrypted storage/backups and audit access control.
- Validate on organizers' synthetic documents and labelled policy questions.
- Add PDF rasterization, background jobs, load tests and security scans.
- Keep final decisions with authorized staff.

## Limitations
Starter, not a validated production product: Tesseract OCR, heuristic extraction, lexical TF-IDF retrieval, no authentication, no PDF rasterization, and no model-backed reasoning. Accuracy claims require evaluation on the actual case data.
