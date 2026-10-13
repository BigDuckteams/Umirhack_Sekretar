"""Обработка документа (раздел `document_processing/` рекомендуемой структуры ТЗ): проверка формата, определение типа,
извлечение и валидация полей.

Определение типа (`dekanat/classify.py`) и извлечение полей (`dekanat/extract/`) уже были в проекте и здесь не дублируются,
а собраны под названием из ТЗ. Новые этапы конвейера — `formats.py` (проверка формата) и `validation.py` (валидация).
"""

from ..classify import Classification, classify
from ..extract import FieldExtractor
from ..extract.locate import boxes_for_words, locate_fragment
from ..extract.values import parse_value
from .formats import SUPPORTED_FORMATS, check_format, detect_format
from .validation import doubt_reason, validate_fields

__all__ = [
    "SUPPORTED_FORMATS", "check_format", "detect_format", "Classification", "classify", "FieldExtractor", "parse_value",
    "validate_fields", "doubt_reason", "locate_fragment", "boxes_for_words",
]
