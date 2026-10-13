"""Фоновые задачи проверки с прогрессом: интерфейс опрашивает статус и показывает реальные этапы, а не «вечный» спиннер."""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from ..pipeline import Cancelled

Work = Callable[[Callable[[str, str, float], None]], dict]


@dataclass
class Job:
    id: str
    created: float = field(default_factory=time.time)
    status: str = "queued"  # queued | running | done | error | cancelled
    stage: str = "queued"
    label: str = "В очереди"
    fraction: float = 0.0
    started: Optional[float] = None
    finished: Optional[float] = None
    result: Optional[dict] = None
    error: Optional[str] = None
    cancel: threading.Event = field(default_factory=threading.Event)

    def snapshot(self, with_result: bool = True) -> dict:
        end = self.finished or time.time()
        out: dict[str, Any] = {
            "id": self.id, "status": self.status, "stage": self.stage, "label": self.label, "fraction": round(self.fraction, 3),
            "elapsed": round(end - (self.started or self.created), 1),
        }
        if self.status == "done" and with_result:
            out["result"] = self.result
        if self.status == "error":
            out["error"] = self.error
        return out


class JobManager:
    def __init__(self, slots: int = 2, max_jobs: int = 40, ttl: float = 900.0):
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._slots = threading.Semaphore(slots)
        self._max = max_jobs
        self._ttl = ttl

    def submit(self, work: Work, describe_error: Callable[[Exception], str]) -> Job:
        job = Job(id=uuid.uuid4().hex[:12])
        with self._lock:
            self._evict()
            self._jobs[job.id] = job
        threading.Thread(target=self._run, args=(job, work, describe_error), daemon=True, name=f"job-{job.id}").start()
        return job

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def cancel(self, job_id: str) -> bool:
        job = self.get(job_id)
        if job is None:
            return False
        job.cancel.set()
        if job.status in ("queued", "running"):
            job.label = "Отменяю…"
        return True

    def _evict(self) -> None:
        now = time.time()
        for jid in [j for j, job in self._jobs.items() if job.finished and now - job.finished > self._ttl]:
            del self._jobs[jid]
        while len(self._jobs) >= self._max:
            oldest = min(self._jobs.values(), key=lambda j: j.created)
            del self._jobs[oldest.id]

    def _run(self, job: Job, work: Work, describe_error: Callable[[Exception], str]) -> None:
        def progress(stage: str, label: str, fraction: float) -> None:
            if job.cancel.is_set():
                raise Cancelled()
            job.stage, job.label, job.fraction = stage, label, max(job.fraction, min(1.0, fraction))

        try:
            while not self._slots.acquire(timeout=0.2):
                if job.cancel.is_set():
                    raise Cancelled()
            try:
                job.status, job.started = "running", time.time()
                job.label = "Начинаю"
                job.result = work(progress)
                if job.cancel.is_set():
                    raise Cancelled()
                job.status, job.stage, job.label, job.fraction = "done", "done", "Готово", 1.0
            finally:
                self._slots.release()
        except Cancelled:
            job.status, job.label = "cancelled", "Отменено"
        except Exception as exc:  # noqa: BLE001 — любую ошибку отдаём пользователю понятным текстом
            job.status, job.error = "error", describe_error(exc)
        finally:
            job.finished = time.time()
