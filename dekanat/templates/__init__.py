"""Формирование документов: DOCX-шаблоны с плейсхолдерами и автозаполнение."""

from .docx_templates import (
    STANDARD_KEYS,
    FillResult,
    PlaceholderInfo,
    TemplateError,
    TemplateExists,
    TemplateInfo,
    TemplateNotFound,
    TemplateStore,
    convert_to_template,
    fill_docx,
    find_placeholders,
    validate_docx,
)

__all__ = [
    "STANDARD_KEYS", "FillResult", "PlaceholderInfo", "TemplateError", "TemplateExists", "TemplateInfo", "TemplateNotFound",
    "TemplateStore", "convert_to_template", "fill_docx", "find_placeholders", "validate_docx",
]
