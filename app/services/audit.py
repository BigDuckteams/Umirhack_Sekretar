import json
import sqlite3
from pathlib import Path
from threading import Lock
from typing import Any

class AuditStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = Lock()
        with self._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS consultations (consultation_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, status TEXT NOT NULL, question TEXT NOT NULL, response_json TEXT NOT NULL)")

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def save(self, consultation_id: str, question: str, response: dict[str, Any]) -> None:
        with self.lock, self._connect() as db:
            db.execute("INSERT INTO consultations VALUES (?, ?, ?, ?, ?)", (consultation_id, str(response["created_at"]), response["status"], question, json.dumps(response, ensure_ascii=False, default=str)))

    def get(self, consultation_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute("SELECT response_json FROM consultations WHERE consultation_id=?", (consultation_id,)).fetchone()
        return json.loads(row["response_json"]) if row else None

    def ready(self) -> bool:
        try:
            with self._connect() as db:
                db.execute("SELECT 1")
            return True
        except sqlite3.Error:
            return False
