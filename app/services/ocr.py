from abc import ABC, abstractmethod
from io import BytesIO
from PIL import Image, UnidentifiedImageError
import pytesseract
from app.core.errors import InvalidDocumentError, ProviderError

class OCRProvider(ABC):
    @abstractmethod
    def extract_text(self, content: bytes, filename: str) -> str:
        raise NotImplementedError

class TesseractOCRProvider(OCRProvider):
    def __init__(self, languages: str = "rus+eng") -> None:
        self.languages = languages

    def extract_text(self, content: bytes, filename: str) -> str:
        if filename.lower().endswith(".pdf"):
            raise InvalidDocumentError("PDF rasterization is not enabled; upload a PNG/JPEG image.")
        try:
            image = Image.open(BytesIO(content)).convert("RGB")
        except (UnidentifiedImageError, OSError) as exc:
            raise InvalidDocumentError("File is not a valid image.") from exc
        try:
            return pytesseract.image_to_string(image, lang=self.languages).strip()
        except pytesseract.TesseractNotFoundError as exc:
            raise ProviderError("Tesseract is not installed; install tesseract-ocr and Russian language data.") from exc
        except pytesseract.TesseractError as exc:
            raise ProviderError("OCR provider failed to process this image.") from exc
