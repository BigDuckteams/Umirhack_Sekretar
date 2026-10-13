"""Командная строка: serve | ask | batch | ocr | doctor | validate-config | synth | eval."""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Optional


def _app():
    from .pipeline import Dekanat

    return Dekanat()


def cmd_serve(args) -> int:
    import uvicorn

    from .config import load_settings

    st = load_settings()
    host = args.host or st.get("server.host", "127.0.0.1")
    port = int(args.port or st.get("server.port", 8000))
    print(f"Онлайн-деканат: http://{host}:{port}")
    uvicorn.run("dekanat.web.app:create_app", host=host, port=port, factory=True, log_level="info")
    return 0


def cmd_ask(args) -> int:
    from .export import result_record
    from .highlight import draw_overlay, overlay_items

    app = _app()
    path = Path(args.image)
    res = app.analyze(path.read_bytes(), path.name, args.question or "", args.type)
    if args.json:
        print(json.dumps(result_record(res, image=path.name, question=args.question or ""), ensure_ascii=False, indent=2))
    else:
        dt = res.doc_type
        print(f"Тип документа: {dt.title if dt else 'не определён'} ({res.how})")
        print("Карточка полей:")
        for f in res.fields:
            mark = {"found": "✓", "partial": "◐", "missing": "✗"}[f.status]
            print(f"  {mark} {f.title}: {f.value or 'не найдено'}" + (f"  [{', '.join(p.title + ('✓' if p.found else '✗') for p in f.parts)}]" if f.parts else ""))
        a = res.answer
        print(f"\nОтвет ({a.verdict}): {a.text}")
        for s in a.sources:
            print(f"  источник: {s.label}")
        for n in a.notes:
            print(f"  примечание: {n}")
        for w in res.warnings:
            print(f"  ! {w}")
        print(f"\nВремя: {res.timings}")
    if args.highlight and res.original_pages:
        import cv2

        for i, img in enumerate(res.original_pages):
            out = draw_overlay(img, overlay_items(res.fields, res.answer), i)
            target = Path(args.highlight) if len(res.original_pages) == 1 else Path(args.highlight).with_name(f"{Path(args.highlight).stem}_{i + 1}{Path(args.highlight).suffix}")
            ok, buf = cv2.imencode(target.suffix or ".png", out)
            target.write_bytes(buf.tobytes())
            print(f"Подсветка сохранена: {target}")
    return 0


def cmd_batch(args) -> int:
    from .export import read_batch_input, result_record

    app = _app()
    inp = Path(args.input)
    items = read_batch_input(inp)
    base = Path(args.images_dir) if args.images_dir else inp.parent
    if args.limit:
        items = items[: args.limit]
    results = []
    t0 = time.time()
    for n, it in enumerate(items, 1):
        data = None
        if it["image"]:
            p = Path(it["image"])
            cand = [p, base / p, base / "images" / p, base / p.name, base / "images" / p.name]
            found = next((c for c in cand if c.exists()), None)
            if found is None:
                print(f"[{n}/{len(items)}] {it['id']}: файл «{it['image']}» не найден, пропускаю", file=sys.stderr)
                results.append({"id": it["id"], "image": it["image"], "question": it["question"], "error": "файл не найден"})
                continue
            data = found.read_bytes()
        try:
            res = app.analyze(data, it["image"] or "", it["question"], it["doc_type"])
            rec = result_record(res, it["id"], it["image"], it["question"])
        except Exception as exc:  # один плохой файл не должен ронять весь прогон
            logging.exception("Ошибка обработки %s", it["id"])
            rec = {"id": it["id"], "image": it["image"], "question": it["question"], "error": str(exc)}
        results.append(rec)
        print(f"[{n}/{len(items)}] {it['id']}: {rec.get('verdict', 'ошибка')}", flush=True)
    out = Path(args.out)
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Готово: {len(results)} записей -> {out} ({time.time() - t0:.0f} с)")
    return 0


def cmd_ocr(args) -> int:
    from .ocr import OcrOptions, OcrRunner, TesseractEngine
    from .ocr.preprocess import load_pages
    from .config import load_settings

    st = load_settings()
    runner = OcrRunner(TesseractEngine(st.get("ocr.tesseract_cmd"), str(st.get("ocr.languages", "rus+eng")), st.get("ocr.tessdata_dir")), OcrOptions())
    path = Path(args.image)
    for page in runner.run(load_pages(path.read_bytes(), path.name)):
        q = {k: v for k, v in page.quality.items() if k != "tried"}
        print(f"--- страница {page.index + 1}: вариант {page.variant}, наклон {page.deskew_angle}°, качество {q}")
        print(page.text)
    return 0


def cmd_doctor(args) -> int:
    app = _app()
    info = app.info()
    ocr = info["ocr"]
    ok = True
    print("Диагностика окружения")
    print(f"  Python: {sys.version.split()[0]}")
    if ocr.get("available"):
        print(f"  Tesseract: {ocr['version']} ({ocr['cmd']}), языки rus/eng — есть")
    else:
        ok = False
        print(f"  Tesseract: ПРОБЛЕМА — {ocr.get('reason')}")
    print(f"  Типы документов: {', '.join(d['title'] for d in info['doc_types'])}")
    print(f"  Положение: {info['regulation']['name'] or 'не загружено'} ({info['regulation']['clauses']} пунктов)")
    llm = info["llm"]
    print(f"  Локальная LLM: {llm['backend']}" + (f" ({llm['model']}, {'доступна' if llm['available'] else 'недоступна'})" if llm["backend"] != "none" else " (не используется)"))
    return 0 if ok else 1


def cmd_validate(args) -> int:
    from .config import ConfigError, load_doc_types, load_settings

    st = load_settings()
    try:
        types = load_doc_types(Path(args.dir) if args.dir else st.doc_types_dir)
    except ConfigError as exc:
        print(f"ОШИБКА КОНФИГА: {exc}", file=sys.stderr)
        return 1
    for t in types.values():
        units = sum(len(f.parts) or 1 for f in t.fields)
        print(f"  ✓ {t.id}: «{t.title}», полей {len(t.fields)} (проверяемых единиц {units})")
    print("Конфиг корректен.")
    return 0


def cmd_synth(args) -> int:
    from . import synth

    return synth.main(args.rest)


def cmd_eval(args) -> int:
    from .evaluate import print_report, run_eval, run_qa_oracle

    app = _app()
    if args.oracle:
        rep = run_qa_oracle(app, Path(args.data), args.verbose, Path(args.out) if args.out else None)
    else:
        rep = run_eval(app, Path(args.data), args.limit, args.verbose, Path(args.out) if args.out else None)
    print_report(rep)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="dekanat", description="Онлайн-деканат: цифровой секретарь")
    p.add_argument("-v", "--verbose", action="store_true", help="подробный лог")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("serve", help="запустить веб-интерфейс")
    s.add_argument("--host")
    s.add_argument("--port", type=int)
    s.set_defaults(func=cmd_serve)

    a = sub.add_parser("ask", help="проверить документ и ответить на вопрос")
    a.add_argument("image", help="JPG/PNG/PDF")
    a.add_argument("question", nargs="?", default="")
    a.add_argument("--type", help="тип документа (по умолчанию определяется автоматически)")
    a.add_argument("--json", action="store_true")
    a.add_argument("--highlight", help="сохранить снимок с подсветкой найденных полей")
    a.set_defaults(func=cmd_ask)

    b = sub.add_parser("batch", help="прогнать набор документов и вопросов -> results.json")
    b.add_argument("--input", required=True, help="JSON/JSONL/CSV с полями id, image, question[, doc_type]")
    b.add_argument("--out", default="results.json")
    b.add_argument("--images-dir")
    b.add_argument("--limit", type=int)
    b.set_defaults(func=cmd_batch)

    o = sub.add_parser("ocr", help="показать результат OCR")
    o.add_argument("image")
    o.set_defaults(func=cmd_ocr)

    d = sub.add_parser("doctor", help="проверить окружение")
    d.set_defaults(func=cmd_doctor)

    v = sub.add_parser("validate-config", help="проверить YAML типов документов")
    v.add_argument("--dir")
    v.set_defaults(func=cmd_validate)

    y = sub.add_parser("synth", help="сгенерировать синтетические документы (см. dekanat/synth.py)")
    y.add_argument("rest", nargs=argparse.REMAINDER)
    y.set_defaults(func=cmd_synth)

    e = sub.add_parser("eval", help="оценка качества на синтетическом наборе")
    e.add_argument("--data", default="data/synthetic")
    e.add_argument("--limit", type=int)
    e.add_argument("--out", help="сохранить подробный отчёт в JSON")
    e.add_argument("--verbose", action="store_true", help="показывать ошибочные ответы")
    e.add_argument("--oracle", action="store_true", help="только логика ответов: поля берутся из эталона, OCR не запускается")
    e.set_defaults(func=cmd_eval)
    return p


def main(argv: Optional[list[str]] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    raw = list(sys.argv[1:] if argv is None else argv)
    if raw and raw[0] == "synth":  # аргументы генератора передаём как есть
        from . import synth

        return synth.main(raw[1:])
    args = build_parser().parse_args(raw)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
