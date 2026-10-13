"""Необязательный «арбитр» на локальной модели (Ollama). Внешние API не используются.

Модель не пишет ответ: она только решает, содержится ли ответ на вопрос в найденных пунктах Положения
(и в каком именно). Текст ответа всегда собирается из самого Положения — модель не может выдумать норму.
Если Ollama недоступна, сервис работает без неё.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Optional

from ..models import Clause


@dataclass
class Judgement:
    answerable: bool
    clause_number: Optional[str] = None


class LlmClient:
    def __init__(self, url: str = "http://localhost:11434", model: str = "llama3.1:8b", timeout: float = 180.0):
        self.url = url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def available(self) -> bool:
        try:
            with urllib.request.urlopen(f"{self.url}/api/tags", timeout=3) as r:
                names = [m.get("name", "") for m in json.loads(r.read()).get("models", [])]
            return any(n == self.model or n.split(":")[0] == self.model.split(":")[0] for n in names)
        except (urllib.error.URLError, OSError, ValueError):
            return False

    def _generate(self, prompt: str) -> str:
        body = json.dumps({
            "model": self.model, "prompt": prompt, "stream": False, "format": "json",
            "options": {"temperature": 0, "num_predict": 80, "num_ctx": 2048},
        }).encode("utf-8")
        req = urllib.request.Request(f"{self.url}/api/generate", data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return json.loads(r.read()).get("response", "")

    def judge(self, clauses: list[Clause], question: str) -> Optional[Judgement]:
        listing = "\n".join(f"[{c.number}] {c.text}" for c in clauses)
        prompt = (
            "Ты помощник деканата. Отвечай ТОЛЬКО по приведённым пунктам Положения.\n"
            f"Вопрос студента: {question}\n\nПункты Положения:\n{listing}\n\n"
            'Ответь JSON: {"answerable": true или false, "clause": "номер пункта или null"}.\n'
            "answerable=true только если в одном из пунктов ПРЯМО содержится ответ на вопрос. "
            "Если вопрос о том, чего в пунктах нет (цены, адреса, телефоны, даты сессий и т. п.), answerable=false."
        )
        raw = self._generate(prompt)
        try:
            data = json.loads(raw)
        except ValueError:
            return None
        answerable = bool(data.get("answerable"))
        number = data.get("clause")
        valid = {c.number for c in clauses}
        number = str(number) if str(number) in valid else None
        return Judgement(answerable, number)
