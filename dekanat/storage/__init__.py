"""Хранилище: SQLite + файлы (шаблоны, готовые документы). Единая точка доступа — `Storage`."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from .db import Database, iso, now
from .repos import (
    TICKET_STATUSES,
    TICKET_TYPES,
    AdminRepo,
    AuditRepo,
    EventRepo,
    GeneratedRepo,
    KBRepo,
    TemplateRepo,
    TicketRepo,
    UserSessionRepo,
    session_ref,
    sha256_hex,
)

log = logging.getLogger(__name__)

__all__ = ["Storage", "Database", "iso", "now", "session_ref", "sha256_hex", "TICKET_STATUSES", "TICKET_TYPES"]


def _remove_files(paths: list[str]) -> int:
    n = 0
    for p in paths:
        try:
            Path(p).unlink(missing_ok=True)
            n += 1
        except OSError as exc:  # файл занят/недоступен — не страшно, запись в БД уже удалена
            log.warning("Не удалось удалить файл %s: %s", p, exc)
    return n


class Storage:
    """Все репозитории + политика хранения и удаления персональных данных (privacy.*)."""

    def __init__(self, settings):
        self.settings = settings
        self.db = Database(settings.path("storage.db_path", "data/storage/dekanat.db"))
        self.templates_dir = settings.path("storage.templates_dir", "data/templates")
        self.output_dir = settings.path("storage.output_dir", "data/output")
        self.admins = AdminRepo(self.db)
        self.sessions = UserSessionRepo(self.db)
        self.generated = GeneratedRepo(self.db)
        self.templates = TemplateRepo(self.db)
        self.kb = KBRepo(self.db)
        self.tickets = TicketRepo(self.db)
        self.events = EventRepo(self.db)
        self.audit = AuditRepo(self.db)

    # ------------------------------------------------------------------ политика хранения
    @property
    def session_ttl(self) -> float:
        return float(self.settings.get("privacy.session_ttl_hours", 24)) * 3600

    @property
    def generated_ttl(self) -> float:
        return float(self.settings.get("privacy.generated_ttl_hours", 24)) * 3600

    def purge(self) -> dict:
        """Удаляет просроченное: сессии (с анкетами и данными документов), готовые документы, старые обращения и события, сессии админов."""
        n_sessions, paths = self.sessions.purge_expired()
        paths += self.generated.purge_expired()
        files = _remove_files(paths)
        old_tickets = self.tickets.purge_older_than(float(self.settings.get("privacy.ticket_retention_days", 180)))
        for tid in old_tickets:
            shutil.rmtree(self.ticket_dir(tid), ignore_errors=True)
        tickets = len(old_tickets)
        events = self.events.purge_older_than(float(self.settings.get("privacy.event_retention_days", 365)))
        admin_sessions = self.admins.purge_expired()
        return {"sessions": n_sessions, "files": files, "tickets": tickets, "events": events, "admin_sessions": admin_sessions}

    def ticket_dir(self, ticket_id: int) -> Path:
        return self.output_dir / "tickets" / str(int(ticket_id))

    def delete_session(self, sid: str) -> dict:
        """Полное удаление сессии: анкета, данные документа, готовые файлы."""
        files = _remove_files(self.sessions.delete(sid))
        return {"files": files}

    def delete_user_data(self, sid: str) -> dict:
        """«Удалить мои данные»: анкета, данные документа и готовые файлы стираются сразу."""
        files = _remove_files(self.generated.delete_for_session(sid))
        self.sessions.delete_state(sid)
        self.sessions.delete_document(sid)
        return {"files": files}

    def close(self) -> None:
        self.db.close()
