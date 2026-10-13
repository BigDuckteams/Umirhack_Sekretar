"""Совместимость: «арбитр» теперь живёт в `LLMService.judge_clauses` (dekanat/llm). Здесь остался только тип результата.

Прямой клиент Ollama отсюда убран намеренно: все вызовы модели обязаны идти через `LLMService`,
который уважает переключатель USE_LOCAL_LLM."""

from ..llm.schemas import Judgement

__all__ = ["Judgement"]
