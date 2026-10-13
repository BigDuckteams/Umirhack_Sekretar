"""Оценка OCR-части сервиса на MWS-Vision-Bench (https://huggingface.co/datasets/MTSAIR/MWS-Vision-Bench).

MWS-Vision-Bench — общий бенчмарк русскоязычных бизнес-документов для мультимодальных моделей
(сканы, таблицы, рукописные документы). Справок и Положения вуза в нём нет, поэтому он не заменяет
данные организаторов кейса, но хорошо проверяет главное звено — распознавание русского текста на
разных по качеству изображениях.

Датасет НЕ входит в репозиторий (≈820 МБ) и сам по себе не скачивается. Два способа:

  1) у вас уже есть локальная копия (папка с metadata.jsonl и images/):
         python scripts/eval_mws_vision.py --root D:/datasets/MWS-Vision-Bench --limit 30

  2) скачать только нужное (metadata.jsonl ≈ 2,3 МБ + первые N картинок) — только по явному флагу:
         python scripts/eval_mws_vision.py --root data/mws --download 15 --limit 15

Метрика: CER (доля символьных ошибок, меньше — лучше) между распознанным текстом и эталоном `answers[0]`
для заданий типа «full-page OCR». Сравниваются «голый» Tesseract (один проход без предобработки) и
полный пайплайн сервиса (выпрямление, нормализация освещения, перебор вариантов, перспектива).
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

BASE_URL = "https://huggingface.co/datasets/MTSAIR/MWS-Vision-Bench/resolve/main/"


def normalize_text(text: str) -> str:
    text = re.sub(r"[`*_#|>\\-]+", " ", text.lower().replace("ё", "е"))  # разметка markdown не считается ошибкой
    return re.sub(r"\s+", " ", text).strip()


def cer(pred: str, gold: str) -> float:
    from rapidfuzz.distance import Levenshtein

    p, g = normalize_text(pred), normalize_text(gold)
    if not g:
        return 0.0 if not p else 1.0
    return min(1.0, Levenshtein.distance(p, g) / len(g))


def word_recall(pred: str, gold: str) -> float:
    g = normalize_text(gold).split()
    if not g:
        return 1.0
    p = set(normalize_text(pred).split())
    return sum(1 for w in g if w in p) / len(g)


def load_items(root: Path, type_filter: str = "full-page ocr", limit: int | None = None) -> list[dict]:
    meta = root / "metadata.jsonl"
    if not meta.exists():
        raise SystemExit(f"Не найден {meta}. Укажите --root с локальной копией датасета или добавьте --download N.")
    items = []
    seen = set()
    for line in meta.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if type_filter and type_filter.lower() not in str(row.get("type", "")).lower():
            continue
        if row["file_name"] in seen or not row.get("answers"):
            continue  # одна картинка — один раз
        seen.add(row["file_name"])
        items.append(row)
        if limit and len(items) >= limit:
            break
    return items


def download(root: Path, n: int, type_filter: str) -> None:
    """Скачивает metadata.jsonl и первые n изображений нужного типа. Вызывается только с флагом --download."""
    root.mkdir(parents=True, exist_ok=True)
    meta = root / "metadata.jsonl"
    if not meta.exists():
        print(f"Скачиваю metadata.jsonl из {BASE_URL}")
        urllib.request.urlretrieve(BASE_URL + "metadata.jsonl", meta)
    for row in load_items(root, type_filter, n):
        dest = root / row["file_name"]
        if dest.exists():
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        print(f"Скачиваю {row['file_name']}")
        urllib.request.urlretrieve(BASE_URL + row["file_name"], dest)


def recognize_all(runner, path: Path) -> str:
    from dekanat.ocr.preprocess import load_pages

    return "\n".join(p.text for p in runner.run(load_pages(path.read_bytes(), path.name, 3)))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="CER на MWS-Vision-Bench: полный пайплайн против «голого» Tesseract")
    ap.add_argument("--root", default="data/mws", help="папка с metadata.jsonl и images/")
    ap.add_argument("--download", type=int, metavar="N", help="скачать metadata.jsonl и N изображений (только по этому флагу)")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--type", default="full-page ocr", help="подстрока в поле type (по умолчанию full-page OCR)")
    ap.add_argument("--out", help="сохранить подробный отчёт в JSON")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    root = Path(args.root)
    if args.download:
        download(root, args.download, args.type)

    from dekanat.config import load_settings
    from dekanat.ocr import OcrOptions, OcrRunner, TesseractEngine

    st = load_settings()
    engine = TesseractEngine(st.get("ocr.tesseract_cmd"), str(st.get("ocr.languages", "rus+eng")), st.get("ocr.tessdata_dir"))
    full = OcrRunner(engine, OcrOptions(good_score=float(st.get("ocr.good_score", 70))))
    base = OcrRunner(engine, OcrOptions(fast=True))

    items = load_items(root, args.type, args.limit)
    rows = []
    for i, it in enumerate(items, 1):
        path = root / it["file_name"]
        if not path.exists():
            print(f"[{i}/{len(items)}] нет файла {path}, пропускаю")
            continue
        gold = it["answers"][0]
        t0 = time.time()
        pred_full = recognize_all(full, path)
        t1 = time.time()
        pred_base = recognize_all(base, path)
        rows.append({"id": it.get("id"), "file": it["file_name"], "dataset": it.get("dataset_name"), "cer_full": cer(pred_full, gold), "cer_base": cer(pred_base, gold),
                     "recall_full": word_recall(pred_full, gold), "recall_base": word_recall(pred_base, gold), "seconds_full": round(t1 - t0, 1)})
        r = rows[-1]
        print(f"[{i}/{len(items)}] {Path(it['file_name']).name}: CER полный {r['cer_full']:.3f} · голый {r['cer_base']:.3f} · {r['seconds_full']} с")
    if not rows:
        print("Нет изображений для оценки.")
        return 1
    mean = lambda k: statistics.fmean(r[k] for r in rows)  # noqa: E731
    print(f"\nИзображений: {len(rows)}")
    print(f"CER (меньше — лучше):  полный пайплайн {mean('cer_full'):.3f} · один проход Tesseract {mean('cer_base'):.3f}")
    print(f"Доля найденных слов:    полный пайплайн {mean('recall_full'):.3f} · один проход Tesseract {mean('recall_base'):.3f}")
    if args.out:
        Path(args.out).write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
