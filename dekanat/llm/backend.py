"""Backend локальной модели. Единственная реализация — Ollama (CPU, без внешних API).

Бизнес-логика не знает про Ollama: она работает через `LLMService` (service.py), а сервис — через интерфейс `LLMBackend`.
Это позволяет в тестах подменять модель, а при желании подключить llama.cpp, не трогая остальной код.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


class LLMError(Exception):
    """Ошибка инференса (плохой ответ сервера, пустой ответ)."""


class LLMUnavailable(LLMError):
    """Модель недоступна: сервер не запущен, модель не установлена, истёк тайм-аут."""


@dataclass(frozen=True)
class LLMConfig:
    """Параметры локальной модели. Читаются из раздела `llm:` в config/settings.yaml."""

    enabled: bool = False
    backend: str = "ollama"
    url: str = "http://localhost:11434"
    model: str = "qwen2.5:3b-instruct"
    timeout: float = 120.0
    threads: int = 0
    cpu_only: bool = True
    num_ctx: int = 4096
    max_input_chars: int = 6000
    max_output_tokens: int = 400
    max_retries: int = 1
    keep_alive: str = "5m"
    cooldown_seconds: float = 60.0

    @classmethod
    def from_settings(cls, settings) -> "LLMConfig":  # settings: dekanat.config.Settings
        g = settings.get
        return cls(
            enabled=settings.use_local_llm,
            backend=str(g("llm.backend", "ollama")).lower(),
            url=str(g("llm.ollama_url", "http://localhost:11434")),
            model=str(g("llm.model", "qwen2.5:3b-instruct")),
            timeout=float(g("llm.timeout", 120)),
            threads=int(g("llm.threads", 0)),
            cpu_only=bool(g("llm.cpu_only", True)),
            num_ctx=int(g("llm.num_ctx", 4096)),
            max_input_chars=int(g("llm.max_input_chars", 6000)),
            max_output_tokens=int(g("llm.max_output_tokens", 400)),
            max_retries=max(0, min(3, int(g("llm.max_retries", 1)))),
            keep_alive=str(g("llm.keep_alive", "5m")),
            cooldown_seconds=float(g("llm.cooldown_seconds", 60)),
        )


class LLMBackend(ABC):
    """Минимальный интерфейс модели: один запрос -> один текст."""

    name = "abstract"

    @abstractmethod
    def available(self) -> bool:
        """Дёшево проверяет, что модель можно вызвать (без загрузки модели в память)."""

    @abstractmethod
    def complete(self, system: str, user: str, *, max_tokens: int, json_mode: bool = True) -> str:
        """Возвращает сырой текст ответа. Бросает LLMUnavailable / LLMError."""


class OllamaBackend(LLMBackend):
    name = "ollama"

    def __init__(self, cfg: LLMConfig):
        self.cfg = cfg
        self.url = cfg.url.rstrip("/")
        # локальный сервер не должен ходить через системный прокси
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def _open(self, req, timeout: float):
        return self._opener.open(req, timeout=timeout)

    def available(self) -> bool:
        try:
            with self._open(urllib.request.Request(f"{self.url}/api/tags"), 3) as r:
                names = [m.get("name", "") for m in json.loads(r.read()).get("models", [])]
        except (urllib.error.URLError, OSError, ValueError):
            return False
        want = self.cfg.model
        return want in names or (":" not in want and f"{want}:latest" in names)

    def _options(self, max_tokens: int) -> dict:
        opts: dict = {"temperature": 0, "num_predict": int(max_tokens), "num_ctx": int(self.cfg.num_ctx)}
        if self.cfg.threads > 0:
            opts["num_thread"] = int(self.cfg.threads)
        if self.cfg.cpu_only:
            opts["num_gpu"] = 0  # ни одного слоя на видеокарте
        return opts

    def complete(self, system: str, user: str, *, max_tokens: int, json_mode: bool = True) -> str:
        body = {
            "model": self.cfg.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "stream": False,
            "options": self._options(max_tokens),
            "keep_alive": self.cfg.keep_alive,
        }
        if json_mode:
            body["format"] = "json"
        req = urllib.request.Request(f"{self.url}/api/chat", data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"})
        try:
            with self._open(req, self.cfg.timeout) as r:
                payload = json.loads(r.read())
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise LLMUnavailable(f"Модель «{self.cfg.model}» не установлена (ollama pull {self.cfg.model})") from exc
            raise LLMError(f"Ollama вернула HTTP {exc.code}") from exc
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            raise LLMUnavailable(f"Ollama недоступна: {exc}") from exc
        except ValueError as exc:
            raise LLMError("Ollama вернула не JSON") from exc
        text = (payload.get("message") or {}).get("content", "")
        if not isinstance(text, str) or not text.strip():
            raise LLMError("Пустой ответ модели")
        return text


class CircuitBreaker:
    """После нескольких подряд ошибок связи на время «остывает»: недоступную модель не долбим на каждое сообщение."""

    def __init__(self, threshold: int = 2, cooldown: float = 60.0):
        self.threshold = threshold
        self.cooldown = cooldown
        self.failures = 0
        self.open_until = 0.0

    def allow(self) -> bool:
        return time.monotonic() >= self.open_until

    def ok(self) -> None:
        self.failures = 0
        self.open_until = 0.0

    def fail(self) -> None:
        self.failures += 1
        if self.failures >= self.threshold:
            self.open_until = time.monotonic() + self.cooldown


def make_backend(cfg: LLMConfig) -> Optional[LLMBackend]:
    """Создаёт backend. Не обращается к сети и не загружает модель."""
    if cfg.backend == "ollama":
        return OllamaBackend(cfg)
    return None
