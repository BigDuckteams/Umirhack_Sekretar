"""Единый конвейер: файл + вопрос -> OCR -> тип документа -> карточка полей -> ответ со ссылкой на источник."""

from __future__ import annotations

import base64
import hashlib
import logging
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

import cv2
import numpy as np

from .classify import Classification, classify
from .config import DocTypeSpec, Settings, load_doc_types, load_settings
from .extract import FieldExtractor
from .kb import ClauseIndex, RequirementModel, load_regulation, load_synonym_groups, parse_regulation_text
from .models import Answer, Clause, FieldResult, OcrPage
from .ocr import OcrOptions, OcrRunner, TesseractEngine
from .ocr.preprocess import load_pages
from .qa import LlmClient, QAEngine
from .qa.docqa import GENERIC_WORDS, DocumentQA

log = logging.getLogger(__name__)

Progress = Callable[[str, str, float], None]  # (этап, подпись, доля 0..1)


class Cancelled(Exception):
    """Пользователь отменил проверку."""


NEED_DOCUMENT_TEXT = ("Чтобы проверить документ, загрузите его фото или скан — без файла проверять нечего. "
                      "Вопросы о правилах (например, «Сколько дней рассматривается заявление?») можно задавать и без документа.")
NO_TYPE_TEXT = "Не удалось определить тип документа, поэтому проверить его не получится. Выберите тип документа — и проверка запустится сразу."
UNSUPPORTED_NOTE = ("Документ не похож на справку об обучении, заявление на академический отпуск или справку о практике, поэтому ответ дан по тексту "
                    "самого документа, без сверки с Положением.")
GENERIC_ID = "generic"  # doc_type для режима «другой документ»: вопросы по тексту, без карточки полей


@dataclass
class AnalysisResult:
    doc_type: Optional[DocTypeSpec]
    how: str  # manual | auto | none
    classification: Optional[Classification]
    pages: list[OcrPage]
    fields: list[FieldResult]
    answer: Answer
    timings: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    original_pages: list[np.ndarray] = field(default_factory=list)
    type_titles: dict = field(default_factory=dict)

    @property
    def text(self) -> str:
        return "\n".join(p.text for p in self.pages)

    def to_dict(self, preview: bool = True) -> dict:
        dt = self.doc_type
        cls = self.classification
        out: dict[str, Any] = {
            "doc_type": {
                "id": dt.id if dt else None,
                "title": dt.title if dt else ("Другой документ" if self.how == "generic" else None),
                "how": self.how,
                "confidence": round(cls.confidence, 3) if (cls and self.how == "auto") else (1.0 if dt else 0.0),
                "uncertain": bool(cls and self.how == "auto" and cls.uncertain),
                "ranking": [{"id": i, "score": round(s, 2)} for i, s in (cls.ranking if cls else [])],
                "candidates": [{"id": c["id"], "title": self.type_titles.get(c["id"], c["id"]), "share": round(c["share"], 3)} for c in (cls.candidates if cls else [])],
                "reason": cls.reason if cls else "",
            },
            "ocr": {
                "engine": self.pages[0].engine if self.pages else None,
                "pages": [
                    {"index": p.index, "width": p.orig_size[0], "height": p.orig_size[1], "variant": p.variant, "deskew_angle": p.deskew_angle,
                     "rotation": p.rotation, "score": p.quality.get("score"), "mean_conf": p.quality.get("mean_conf"), "words": p.quality.get("words"),
                     "seconds": p.quality.get("seconds")}
                    for p in self.pages
                ],
                "text": self.text,
            },
            "fields": [f.to_dict() for f in self.fields],
            "answer": self.answer.to_dict(),
            "warnings": self.warnings,
            "timings": self.timings,
        }
        if preview:
            out["images"] = [self._preview(i) for i in range(len(self.original_pages))]
        return out

    def _preview(self, i: int, max_side: int = 1600) -> dict:
        img = self.original_pages[i]
        h, w = img.shape[:2]
        s = min(1.0, max_side / max(h, w))
        small = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA) if s < 1 else img
        ok, buf = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 82])
        return {"page": i, "width": w, "height": h, "data_url": "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode()}


class Dekanat:
    """Фасад сервиса: настройки, типы документов, Положение, OCR и ответы."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or load_settings()
        self._lock = threading.Lock()
        self._ocr_cache: "OrderedDict[str, list[OcrPage]]" = OrderedDict()
        self._field_cache: "OrderedDict[tuple[str, str], list[FieldResult]]" = OrderedDict()
        self.engine = TesseractEngine(
            cmd=self.settings.get("ocr.tesseract_cmd"), languages=str(self.settings.get("ocr.languages", "rus+eng")),
            tessdata_dir=self.settings.get("ocr.tessdata_dir"),
        )
        self.runner = OcrRunner(self.engine, OcrOptions(good_score=float(self.settings.get("ocr.good_score", 70)), fast=bool(self.settings.get("ocr.fast", False))))
        self.doc_types: dict[str, DocTypeSpec] = {}
        self.clauses: list[Clause] = []
        self.regulation_name = ""
        self.reload()

    # ------------------------------------------------------------------ загрузка конфигурации и Положения
    def reload(self) -> None:
        s = self.settings
        self.doc_types = load_doc_types(s.doc_types_dir)
        reg_path = s.path("regulation.path", "data/regulations/polozhenie.md")
        self.clauses = load_regulation(reg_path) if reg_path.exists() else []
        self.regulation_name = reg_path.name if reg_path.exists() else ""
        self._rebuild_kb()

    def set_regulation_text(self, text: str, name: str = "загруженное Положение") -> int:
        self.clauses = parse_regulation_text(text)
        self.regulation_name = name
        self._rebuild_kb()
        return len(self.clauses)

    def _rebuild_kb(self) -> None:
        s = self.settings
        syn_path = s.path("synonyms_file", "config/synonyms.yaml")
        groups = load_synonym_groups(syn_path)
        field_groups = load_synonym_groups(syn_path, "field_groups")
        self.index = ClauseIndex(self.clauses, groups)
        self.requirements = RequirementModel(self.doc_types, self.clauses)
        llm = None
        if str(s.get("llm.backend", "none")).lower() == "ollama":
            llm = LlmClient(str(s.get("llm.ollama_url")), str(s.get("llm.model")), float(s.get("llm.timeout", 180)))
        self.docqa = DocumentQA(load_synonym_groups(syn_path, "doc_groups") + groups)
        self.qa = QAEngine(self.doc_types, self.clauses, self.index, self.requirements,
                           min_coverage=float(s.get("qa.min_coverage", 0.55)), max_related=int(s.get("qa.max_related", 2)), llm=llm,
                           field_groups=field_groups)
        self._extractors = {tid: FieldExtractor(dt, bool(s.get("marks.enabled", True))) for tid, dt in self.doc_types.items()}
        self._field_cache.clear()

    # ------------------------------------------------------------------ OCR
    def _ocr(self, data: bytes, filename: str, progress: Optional[Progress] = None) -> tuple[list[np.ndarray], list[OcrPage], bool]:
        report = progress or (lambda *_: None)
        key = hashlib.sha1(data).hexdigest()
        report("load", "Открываю файл", 0.04)
        originals = load_pages(data, filename, int(self.settings.get("ocr.max_pages", 5)))
        with self._lock:
            cached = self._ocr_cache.get(key)
            if cached is not None:
                self._ocr_cache.move_to_end(key)
                return originals, cached, True
        n = len(originals)
        counter = {"k": 0}

        def step(page: int, msg: str) -> None:
            counter["k"] += 1
            frac = 0.08 + 0.62 * ((page + min(0.95, counter["k"] / 5.0)) / n)
            suffix = f" (страница {page + 1} из {n})" if n > 1 else ""
            report("ocr", f"Читаю текст{suffix}: {msg}", min(frac, 0.7))

        pages = self.runner.run(originals, step)
        with self._lock:
            self._ocr_cache[key] = pages
            while len(self._ocr_cache) > 4:
                self._ocr_cache.popitem(last=False)
        return originals, pages, False

    # ------------------------------------------------------------------ анализ
    def analyze(self, data: Optional[bytes], filename: str = "", question: str = "", doc_type: Optional[str] = None,
                progress: Optional[Progress] = None) -> AnalysisResult:
        """progress(этап, подпись, доля) можно использовать для индикатора; исключение из него (Cancelled) прерывает проверку."""
        report = progress or (lambda *_: None)
        t0 = time.time()
        timings: dict[str, float] = {}
        warnings: list[str] = []
        pages: list[OcrPage] = []
        originals: list[np.ndarray] = []
        spec: Optional[DocTypeSpec] = None
        how = "none"
        cls: Optional[Classification] = None
        fields: list[FieldResult] = []
        ocr_notes: list[str] = []
        titles = {tid: d.title for tid, d in self.doc_types.items()}
        if data:
            originals, pages, cached = self._ocr(data, filename, progress)
            timings["ocr"] = round(time.time() - t0, 2)
            if cached:
                timings["ocr_cached"] = True
            has_text = any(p.words for p in pages)
            if not has_text:
                warnings.append("Текст на изображении не распознан. Сфотографируйте документ ровнее, при хорошем освещении и без бликов.")
            elif any(p.quality.get("score", 100) < 45 for p in pages):
                ocr_notes.append("Качество снимка невысокое — часть данных могла быть прочитана неверно. Если ответ кажется странным, пришлите более чёткое фото.")
            report("classify", "Определяю тип документа", 0.74)
            if doc_type == GENERIC_ID:
                how = "generic"
            elif doc_type and doc_type not in ("auto", "") and doc_type in self.doc_types:
                spec, how = self.doc_types[doc_type], "manual"
            elif doc_type and doc_type not in ("auto", ""):
                warnings.append(f"Неизвестный тип документа «{doc_type}», определяю автоматически.")
            if has_text and how != "generic":
                cls = classify(self.doc_types, pages)
                if spec is None:
                    if cls.type_id:
                        spec, how = self.doc_types[cls.type_id], "auto"
                        if cls.uncertain:
                            warnings.append(f"Тип определён неуверенно — похоже на «{spec.title}», но проверьте и при необходимости выберите другой.")
                    else:
                        warnings.append("Документ не похож ни на один из известных типов. Ответ будет по тексту документа; тип можно выбрать вручную.")
            t1 = time.time()
            if spec is not None and has_text:
                report("extract", "Заполняю карточку полей", 0.84)
                fkey = (hashlib.sha1(data).hexdigest(), spec.id)
                with self._lock:
                    fields = self._field_cache.get(fkey)
                if fields is None:
                    fields = self._extractors[spec.id].extract(pages)
                    with self._lock:
                        self._field_cache[fkey] = fields
                        while len(self._field_cache) > 16:
                            self._field_cache.popitem(last=False)
            timings["extract"] = round(time.time() - t1, 2)
        t2 = time.time()
        report("answer", "Ищу ответ в Положении", 0.93)
        if data is None and self.qa.needs_document(question):
            answer = Answer("no_answer", NEED_DOCUMENT_TEXT, "no_document", confidence=1.0)
        elif data and spec is None:
            answer = self._answer_unsupported(question, pages, how == "generic", ocr_notes)
        else:
            answer = self.qa.answer(question, spec, fields or None, ocr_notes)
        timings["answer"] = round(time.time() - t2, 2)
        timings["total"] = round(time.time() - t0, 2)
        report("done", "Готово", 1.0)
        return AnalysisResult(spec, how, cls, pages, fields, answer, timings, warnings, originals, titles)

    def _answer_unsupported(self, question: str, pages: list[OcrPage], chosen_generic: bool, ocr_notes: list[str]) -> Answer:
        """Тип документа не определён (или выбран «другой документ»): отвечаем по тексту документа и по Положению."""
        q = question.strip()
        needs_check = self.qa.needs_document(q)
        rule = self.qa.answer(q, None, None) if q and not needs_check else None
        doc = self.docqa.answer(q, pages) if (q and not needs_check) and any(p.words for p in pages) else None
        note = [] if chosen_generic else [UNSUPPORTED_NOTE]
        if q and not needs_check and doc is not None and not self.index.query_terms(q, extra_drop=GENERIC_WORDS):
            doc.notes += note + ocr_notes  # «что в документе?» — показываем начало документа, а не случайный пункт Положения
            return doc
        if doc is not None and doc.debug.get("requisite"):
            doc.notes += note + ocr_notes  # «Какая дата/какой номер документа?» — спрашивают про сам документ, а не про Положение
            return doc
        if rule is not None and rule.verdict == "ok" and rule.debug.get("coverage", 0) >= 0.75:
            return rule  # вопрос явно про правила — тип документа не важен
        if doc is not None and doc.verdict == "ok":
            doc.notes += note + ocr_notes
            return doc
        if rule is not None and rule.verdict == "ok":
            return rule
        if doc is not None and chosen_generic:
            doc.notes += ocr_notes
            return doc
        if needs_check or not q:
            return Answer("no_answer", NO_TYPE_TEXT, "no_document_type", confidence=0.5)
        if doc is not None:
            doc.notes += note + ocr_notes
            return doc
        return Answer("no_answer", NO_TYPE_TEXT, "no_document_type", confidence=0.5)

    def info(self) -> dict:
        ocr = self.engine.info()
        llm = None
        if str(self.settings.get("llm.backend", "none")).lower() == "ollama":
            client = LlmClient(str(self.settings.get("llm.ollama_url")), str(self.settings.get("llm.model")))
            llm = {"backend": "ollama", "model": client.model, "available": client.available()}
        return {
            "ocr": ocr,
            "doc_types": [{"id": d.id, "title": d.title, "fields": len(d.fields)} for d in self.doc_types.values()],
            "regulation": {"name": self.regulation_name, "clauses": len(self.clauses)},
            "llm": llm or {"backend": "none"},
        }
