"""Локальная языковая модель: интерфейс, backend (Ollama, CPU), строгие промпты и проверка ответов."""

from .backend import LLMBackend, LLMConfig, LLMError, LLMUnavailable, OllamaBackend
from .schemas import ExtractedField, IntentResult, Judgement, NormalizedAnswer, SchemaError
from .service import TASKS, LLMService

__all__ = [
    "LLMService", "LLMBackend", "LLMConfig", "LLMError", "LLMUnavailable", "OllamaBackend", "SchemaError",
    "Judgement", "IntentResult", "NormalizedAnswer", "ExtractedField", "TASKS",
]
