"""Загруженный документ в рамках сессии: хранится только карточка полей (без снимка и OCR-текста), правится пользователем,
подсказывает ответы анкеты. Данные текущего вуза из документа не смешиваются с целевыми."""

from __future__ import annotations

import time
from typing import Any, Optional

from ..config import DocTypeSpec
from ..extract.values import parse_value
from ..models import FieldResult, PartResult
from .questions import QUESTIONS, OK

# какие поля карточки подсказывают ответы анкеты (документ выдан ТЕКУЩИМ вузом)
SUGGESTION_MAP = {
    "student_name": "student_name",
    "university": "current_university",
    "direction": "current_specialty",
    "study_form": "education_form",
    "group_course.course": "current_course",
}

_YES = {"есть", "да", "true", "1", "yes", "+"}
_NO = {"нет", "false", "0", "no", "-"}


def make_record(result: Any, filename: str) -> dict:
    """AnalysisResult -> компактная запись для сессии. Ни снимка, ни OCR-текста, ни рамок."""
    dt = result.doc_type
    fields = []
    for f in result.fields:
        d = f.to_dict()
        fields.append({
            "id": d["id"], "title": d["title"], "kind": d["kind"], "found": d["found"], "value": d["value"] if d["found"] or d["parts"] else "",
            "normalized": d["normalized"], "confidence": d["confidence"], "method": d["method"],
            "parts": [{"id": p["id"], "title": p["title"], "found": p["found"], "value": p["value"] if p["found"] else "",
                       "normalized": p["normalized"], "confidence": p["confidence"]} for p in d["parts"]],
        })
    return {
        "filename": filename[:120], "uploaded_at": time.time(),
        "doc_type": {"id": dt.id if dt else None, "title": dt.title if dt else None, "how": result.how},
        "fields": fields, "corrected": [], "warnings": list(result.warnings),
    }


def restore_fields(record: Optional[dict]) -> list[FieldResult]:
    out = []
    for f in (record or {}).get("fields", []):
        parts = [PartResult(p["id"], p["title"], bool(p["found"]), p.get("value") or "", p.get("normalized"), float(p.get("confidence") or 0.0))
                 for p in f.get("parts", [])]
        out.append(FieldResult(f["id"], f["title"], f["kind"], bool(f["found"]), f.get("value") or "", f.get("normalized"),
                               float(f.get("confidence") or 0.0), [], f.get("method", ""), "", parts))
    return out


def public_fields(record: Optional[dict]) -> list[dict]:
    """Карточка для показа и правки: у каждого поля/части — идентификатор единицы, значение, статус, исправлено ли пользователем."""
    corrected = set((record or {}).get("corrected", []))
    items = []
    for f in restore_fields(record):
        d = f.to_dict()
        if f.parts:
            for p in d["parts"]:
                uid = f"{f.id}.{p['id']}"
                items.append({"unit": uid, "field": f.id, "title": f"{f.title}: {p['title']}", "kind": "mark" if f.kind == "marks" else "part", "found": p["found"],
                              "value": p["value"], "confidence": p["confidence"], "corrected": uid in corrected})
        else:
            items.append({"unit": f.id, "field": f.id, "title": f.title, "kind": f.kind, "found": d["found"], "value": d["value"],
                          "confidence": d["confidence"], "corrected": f.id in corrected})
    return items


def suggestions_from_record(record: Optional[dict]) -> dict:
    """Подсказки для анкеты из карточки документа. Подсказка принимается, только если проходит те же проверки, что и ввод руками."""
    out: dict[str, str] = {}
    if not record:
        return out
    for f in record.get("fields", []):
        units = [(f"{f['id']}.{p['id']}", p) for p in f.get("parts", [])] or [(f["id"], f)]
        for uid, item in units:
            key = SUGGESTION_MAP.get(uid)
            if not key or not item.get("found") or not item.get("value"):
                continue
            res = QUESTIONS[key].parse(str(item["value"]))
            if res.status == OK:
                out[key] = str(res.value)
    return out


def apply_correction(record: dict, spec: Optional[DocTypeSpec], unit: str, value: str) -> tuple[bool, str]:
    """Пользователь исправил значение поля. Возвращает (успех, сообщение об ошибке). Значение проходит ту же проверку формата, что и при OCR."""
    field_id, _, part_id = unit.partition(".")
    rec = next((f for f in record.get("fields", []) if f["id"] == field_id), None)
    if rec is None:
        return False, "Такого поля нет в карточке документа"
    target = next((p for p in rec["parts"] if p["id"] == part_id), None) if part_id else rec
    if target is None:
        return False, "Такой части поля нет в карточке документа"
    fspec = spec.field_by_id(field_id) if spec else None
    pspec = fspec.part(part_id) if (fspec and part_id) else None
    kind = (pspec.kind if pspec else (fspec.kind if fspec else rec["kind"]))
    value = (value or "").strip()
    if len(value) > 300:
        return False, "Значение слишком длинное"
    if kind in ("mark", "marks") or (pspec and pspec.mark):
        low = value.lower()
        if low in _YES:
            target.update(found=True, value="есть", normalized=True, confidence=1.0)
        elif low in _NO:
            target.update(found=False, value="нет", normalized=False, confidence=1.0)
        else:
            return False, "Для подписи и печати ответьте «есть» или «нет»"
    elif not value:
        target.update(found=False, value="", normalized=None, confidence=0.0)  # пользователь очистил поле: «не найдено»
    else:
        parsed = parse_value(kind, value, fspec.choices if fspec else None)
        if parsed is None:
            return False, "Не удалось разобрать значение: проверьте формат (для даты — ДД.ММ.ГГГГ)"
        target.update(found=True, value=parsed.value, normalized=parsed.normalized, confidence=1.0)
    if rec["parts"]:
        found = [p for p in rec["parts"] if p["found"]]
        rec["found"] = bool(found)
        if fspec and fspec.format and len(found) == len(rec["parts"]):
            rec["value"] = fspec.format.format(**{p["id"]: p["value"] for p in rec["parts"]})
        else:
            rec["value"] = "; ".join(f"{p['title']}: {p['value']}" for p in found)
        rec["normalized"] = {p["id"]: p["normalized"] for p in found} or None
        rec["confidence"] = min((p["confidence"] for p in rec["parts"] if p["found"]), default=0.0)
    rec["method"] = "user" if not rec["parts"] else rec.get("method", "")
    if unit not in record.setdefault("corrected", []):
        record["corrected"].append(unit)
    return True, ""
