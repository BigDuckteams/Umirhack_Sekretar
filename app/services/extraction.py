import re
from app.schemas import ExtractedField

def _field(value: str | None, evidence: str | None, confidence: float) -> ExtractedField:
    return ExtractedField(value=value, evidence=evidence, confidence=confidence if value else 0.0)

def extract_fields(text: str) -> dict[str, ExtractedField]:
    normalized = re.sub(r"[ \t]+", " ", text)
    patterns: dict[str, tuple[str, float]] = {
        "full_name": (r"(?:ФИО|Ф\.?\s*И\.?\s*О\.?)\s*[:\-]\s*([А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+){1,2})", 0.72),
        "institution": (r"((?:ФГБОУ|ГБОУ|АНО|ООО|университет|институт|колледж)[^\n,;]{2,100})", 0.55),
        "document_number": (r"(?:№|номер)\s*([А-Яа-яЁёA-Za-z0-9\-\/]{2,30})", 0.65),
        "issue_date": (r"(\b\d{1,2}[./]\d{1,2}[./]\d{2,4}\b|\b\d{1,2}\s+[А-Яа-яЁё]+\s+\d{4}\s*г?\.?)", 0.55),
    }
    result: dict[str, ExtractedField] = {}
    for name, (pattern, confidence) in patterns.items():
        match = re.search(pattern, normalized, flags=re.IGNORECASE)
        result[name] = _field(match.group(1).strip(), match.group(0), confidence) if match else _field(None, None, 0)
    stamp = re.search(r"\b(печать|штамп)\b", text, re.IGNORECASE)
    result["stamp_mentioned"] = _field("yes" if stamp else None, stamp.group(0) if stamp else None, 0.35)
    return result
