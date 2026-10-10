from contextlib import asynccontextmanager
from datetime import datetime, timezone
import logging
import uuid
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from app.config import get_settings
from app.core.errors import InvalidDocumentError, ProviderError
from app.core.logging import configure_logging
from app.schemas import ConsultationResponse, HealthResponse
from app.services.answer import build_grounded_answer
from app.services.audit import AuditStore
from app.services.extraction import extract_fields
from app.services.ocr import TesseractOCRProvider
from app.services.policy import PolicyRetriever

configure_logging()
logger = logging.getLogger(__name__)
settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    app.state.audit = AuditStore(settings.database_path)
    app.state.ocr = TesseractOCRProvider(settings.ocr_languages)
    app.state.policies = PolicyRetriever(settings.policy_path)
    yield

app = FastAPI(title="Онлайн-деканат API", version="0.1.0", description="OCR + extraction + cited policy guidance. Final decisions require staff review.", lifespan=lifespan)

@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["x-request-id"] = request_id
    return response

@app.exception_handler(InvalidDocumentError)
async def invalid_document_handler(request: Request, exc: InvalidDocumentError):
    return JSONResponse(status_code=422, content={"detail": str(exc), "request_id": request.state.request_id})

@app.exception_handler(ProviderError)
async def provider_error_handler(request: Request, exc: ProviderError):
    logger.exception("provider_error request_id=%s", request.state.request_id)
    return JSONResponse(status_code=503, content={"detail": str(exc), "request_id": request.state.request_id})

@app.get("/health/live", response_model=HealthResponse, tags=["health"])
def live():
    return HealthResponse(status="ok", app=settings.app_name)

@app.get("/health/ready", response_model=HealthResponse, tags=["health"])
def ready(request: Request):
    if not request.app.state.audit.ready():
        raise HTTPException(status_code=503, detail="audit store unavailable")
    return HealthResponse(status="ready", app=settings.app_name)

@app.get("/v1/policies", tags=["policies"])
def list_policies(request: Request):
    chunks = request.app.state.policies.chunks
    return {"count": len(chunks), "policies": [{"policy_id": c.policy_id, "clause": c.clause, "title": c.title, "source": c.source} for c in chunks]}

@app.post("/v1/consultations", response_model=ConsultationResponse, tags=["consultations"])
async def create_consultation(request: Request, question: str = Form(..., min_length=3), file: UploadFile = File(...)):
    question = question.strip()
    if len(question) > settings.max_question_chars:
        raise HTTPException(status_code=413, detail="question exceeds configured character limit")
    filename = file.filename or "upload.bin"
    suffix = "." + filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise HTTPException(status_code=415, detail="Only PNG/JPG/JPEG/WEBP images are supported.")
    content = await file.read(settings.max_upload_bytes + 1)
    if not content:
        raise HTTPException(status_code=400, detail="uploaded file is empty")
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="file exceeds configured size limit")
    if not content.startswith((b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"RIFF")):
        raise HTTPException(status_code=415, detail="file signature does not match accepted image formats")
    ocr_text = request.app.state.ocr.extract_text(content, filename)
    fields = extract_fields(ocr_text)
    retrieved = request.app.state.policies.search(question + "\n" + ocr_text[:1000], settings.top_k_policy_chunks)
    answer, citations, needs_review, warnings = build_grounded_answer(question, ocr_text, fields, retrieved)
    consultation_id = str(uuid.uuid4())
    result = ConsultationResponse(consultation_id=consultation_id, created_at=datetime.now(timezone.utc), status="needs_review" if needs_review else "completed", ocr_text=ocr_text, extracted_fields=fields, answer=answer, citations=citations, needs_human_review=needs_review, warnings=warnings)
    request.app.state.audit.save(consultation_id, question, result.model_dump(mode="json"))
    logger.info("consultation_created request_id=%s consultation_id=%s ocr_chars=%d citations=%d", request.state.request_id, consultation_id, len(ocr_text), len(citations))
    return result

@app.get("/v1/consultations/{consultation_id}", tags=["consultations"])
def get_consultation(consultation_id: str, request: Request):
    result = request.app.state.audit.get(consultation_id)
    if result is None:
        raise HTTPException(status_code=404, detail="consultation not found")
    return result
