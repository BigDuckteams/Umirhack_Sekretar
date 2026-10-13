"""Прогон MWS-Vision-Bench через сайт и статистика.

Каждое задание датасета (изображение + вопрос) отправляется в работающий сервис тем же путём, что и из интерфейса:
POST /api/jobs (фоновая задача) -> опрос GET /api/jobs/{id} -> результат (ответ, текст OCR, рамки, тайминги).
Тип документа — «автоматически», как у пользователя по умолчанию.

    python -m dekanat serve --port 8001                       # сервис
    python scripts/eval_mws_site.py run   --root D:/mws-vision-bench --out D:/mws-run --base-url http://127.0.0.1:8001
    python scripts/eval_mws_site.py score --root D:/mws-vision-bench --out D:/mws-run

`run` дописывает results.jsonl и умеет продолжать с места остановки. `score` считает метрики и пишет stats.json и report.md.

Метрики по типам заданий (эталон — поле answers датасета):
  * full-page OCR, document parsing — качество распознавания: CER (строгий и «по окну» — если эталон только фрагмент страницы),
    полнота и F1 по словам (разметка в эталоне снимается);
    считается и по тексту OCR (то, что показывает сайт в «Технических подробностях»), и по самому ответу сайта;
  * reasoning VQA — эталонный ответ содержится в ответе сайта / в тексте OCR (верхняя граница), F1 по словам;
  * key information extraction — доля эталонных значений, найденных в ответе сайта / в тексте OCR;
  * text grounding — IoU рамки, которую сайт подсветил в ответе, с эталонной рамкой (hit при IoU ≥ 0,5).
"""

from __future__ import annotations

import argparse
import ast
import html
import json
import re
import statistics
import sys
import threading
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

TASKS = ("full-page OCR", "document parsing", "key information extraction", "reasoning VQA", "text grounding")


# ----------------------------------------------------------------------------- данные


def task_of(type_name: str) -> str:
    return type_name.rsplit(" ", 1)[0]


def load_gold(root: Path, langs: list[str]) -> list[dict]:
    """Задания всех языков. Русские — из metadata.jsonl, английские и китайские — из parquet (те же id и изображения)."""
    ru: dict[str, dict] = {}
    with open(root / "metadata.jsonl", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                ru[str(r["id"])] = r
    items: list[dict] = []

    def add(lang: str, r: dict) -> None:
        base = ru[str(r["id"])]
        items.append({
            "lang": lang, "id": str(r["id"]), "task": task_of(r["type"]), "file": base["file_name"], "subset": base.get("dataset_name", ""),
            "question": r["question"], "answers": list(r["answers"]),
        })

    if "ru" in langs:
        for r in ru.values():
            add("ru", r)
    for lang, folder in (("en", "en"), ("zh", "zh")):
        if lang in langs:
            import pyarrow.parquet as pq

            table = pq.read_table(root / folder / "train-00000-of-00001.parquet", columns=["id", "type", "question", "answers"])
            for r in table.to_pylist():
                if str(r["id"]) in ru:
                    add(lang, r)
    return items


# ----------------------------------------------------------------------------- прогон через сайт


def call_site(client: httpx.Client, base: str, image: bytes, name: str, question: str, doc_type: str = "auto", timeout: float = 600.0) -> dict:
    t0 = time.time()
    r = client.post(f"{base}/api/jobs", files={"file": (name, image)}, data={"question": question, "doc_type": doc_type}, timeout=120)
    r.raise_for_status()
    job = r.json()["id"]
    while True:
        s = client.get(f"{base}/api/jobs/{job}", timeout=120).json()
        if s["status"] in ("done", "error", "cancelled"):
            break
        if time.time() - t0 > timeout:
            client.delete(f"{base}/api/jobs/{job}")
            return {"status": "timeout", "client_s": round(time.time() - t0, 2)}
        time.sleep(0.25)
    out = {"status": s["status"], "client_s": round(time.time() - t0, 2)}
    if s["status"] == "error":
        out["error"] = s.get("error")
        return out
    if s["status"] != "done":
        return out
    res = s["result"]
    ans = res["answer"]
    boxes = [[b["x0"], b["y0"], b["x1"], b["y1"]] for src in ans.get("sources", []) for b in src.get("boxes", []) if b.get("page", 0) == 0]
    page = (res["ocr"]["pages"] or [{}])[0]
    out.update({
        "verdict": ans["verdict"], "answer": ans["text"], "intent": ans.get("intent"), "boxes": boxes,
        "labels": [src["label"] for src in ans.get("sources", [])], "doc_type": res["doc_type"]["id"], "how": res["doc_type"]["how"],
        "server_s": res["timings"].get("total"), "cached": bool(res["timings"].get("ocr_cached")), "ocr_s": page.get("seconds"),
        "ocr_words": page.get("words"), "ocr_score": page.get("score"), "ocr_text": res["ocr"]["text"],
    })
    return out


def run(args) -> None:
    root, out_dir = Path(args.root), Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    langs = args.langs.split(",")
    items = load_gold(root, langs)
    results_path = out_dir / "results.jsonl"
    done = set()
    if results_path.exists():
        with open(results_path, encoding="utf-8") as f:
            done = {(r["lang"], r["id"]) for r in map(json.loads, filter(str.strip, f)) if r.get("status") in ("done", "error")}
    by_file: dict[str, list[dict]] = defaultdict(list)
    for it in items:
        if (it["lang"], it["id"]) not in done:
            by_file[it["file"]].append(it)
    files = sorted(by_file, key=lambda x: int(re.search(r"\d+", x).group()))[: args.limit_images or None]
    total = sum(len(by_file[f]) for f in files)
    print(f"заданий к прогону: {total} (изображений: {len(files)}; уже готово: {len(done)}); сервис {args.base_url}", flush=True)

    lock = threading.Lock()
    counter = {"n": 0, "errors": 0}
    t_start = time.time()
    fh = open(results_path, "a", encoding="utf-8")

    def work(file: str) -> None:
        data = (root / file).read_bytes()
        with httpx.Client() as client:
            first = True
            for it in by_file[file]:
                try:
                    rec = call_site(client, args.base_url, data, Path(file).name, it["question"])
                except Exception as exc:  # noqa: BLE001 — сетевые сбои не должны останавливать прогон
                    rec = {"status": "error", "error": f"{type(exc).__name__}: {exc}", "client_s": 0}
                rec.update({"lang": it["lang"], "id": it["id"], "task": it["task"], "file": file, "subset": it["subset"]})
                if not first:
                    rec.pop("ocr_text", None)  # текст OCR храним один раз на изображение
                first = False
                with lock:
                    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    fh.flush()
                    counter["n"] += 1
                    counter["errors"] += rec["status"] != "done"
                    if counter["n"] % 25 == 0 or counter["n"] == total:
                        el = time.time() - t_start
                        eta = el / counter["n"] * (total - counter["n"])
                        print(f"  {counter['n']}/{total}  ошибок: {counter['errors']}  прошло {el / 60:.1f} мин, осталось ≈ {eta / 60:.1f} мин", flush=True)

    with ThreadPoolExecutor(args.workers) as pool:
        list(pool.map(work, files))
    fh.close()
    print(f"готово за {(time.time() - t_start) / 60:.1f} мин; ошибок: {counter['errors']}", flush=True)


# ----------------------------------------------------------------------------- метрики


def norm(text: str) -> str:
    t = html.unescape(str(text))
    t = re.sub(r"<[^>]+>", " ", t).lower().replace("ё", "е")
    t = re.sub(r"[^\w\s]|_", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def cer(pred: str, gold: str) -> float:
    from rapidfuzz.distance import Levenshtein

    p, g = norm(pred), norm(gold)
    if not g:
        return 0.0 if not p else 1.0
    return min(1.0, Levenshtein.distance(p, g) / len(g))


def cer_aligned(pred: str, gold: str) -> float:
    """CER с учётом того, что эталон может быть фрагментом страницы («приведи текст про обязанности заказчика»):
    если эталон заметно короче распознанного текста, сравнивается с лучшим по совпадению окном распознанного текста."""
    from rapidfuzz import fuzz
    from rapidfuzz.distance import Levenshtein

    p, g = norm(pred), norm(gold)
    if not g:
        return 0.0 if not p else 1.0
    if len(g) < 0.85 * len(p):
        a = fuzz.partial_ratio_alignment(g, p)
        window = p[a.dest_start:a.dest_end]
        return min(1.0, Levenshtein.distance(window, g) / len(g))
    return min(1.0, Levenshtein.distance(p, g) / len(g))


def word_scores(pred: str, gold: str) -> tuple[float, float, float]:
    """(полнота, точность, F1) по мультимножеству слов."""
    p, g = Counter(norm(pred).split()), Counter(norm(gold).split())
    if not g:
        return (1.0, 1.0, 1.0) if not p else (1.0, 0.0, 0.0)
    common = sum((p & g).values())
    rec = common / sum(g.values())
    prec = common / sum(p.values()) if p else 0.0
    f1 = 2 * rec * prec / (rec + prec) if rec + prec else 0.0
    return rec, prec, f1


def contains(text: str, needle: str) -> bool:
    n = norm(needle)
    return bool(n) and f" {n} " in f" {norm(text)} "


def kie_values(answer: str) -> list[str]:
    try:
        d = ast.literal_eval(answer)
        vals = []
        for v in (d.values() if isinstance(d, dict) else []):
            vals += [str(x) for x in (v if isinstance(v, (list, tuple)) else [v])]
        return [v for v in vals if norm(v)]
    except Exception:  # noqa: BLE001
        return []


def iou(a: list[float], b: list[float]) -> float:
    ix0, iy0, ix1, iy1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, ix1 - ix0) * max(0.0, iy1 - iy0)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def pctl(xs: list[float], q: float) -> float:
    if not xs:
        return float("nan")
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(q * (len(xs) - 1))))]


def summarize(xs: list[float]) -> dict:
    if not xs:
        return {"n": 0}
    return {"n": len(xs), "mean": round(statistics.fmean(xs), 3), "median": round(statistics.median(xs), 3), "p90": round(pctl(xs, 0.9), 3), "max": round(max(xs), 3)}


def score(args) -> None:
    root, out_dir = Path(args.root), Path(args.out)
    gold = {(g["lang"], g["id"]): g for g in load_gold(root, args.langs.split(","))}
    recs = []
    with open(out_dir / "results.jsonl", encoding="utf-8") as f:
        recs = [json.loads(line) for line in f if line.strip()]
    ocr_text = {r["file"]: r["ocr_text"] for r in recs if r.get("ocr_text") is not None}
    stats: dict = {"samples": len(recs)}
    total_tasks = len(gold)
    covered = {r["file"] for r in recs}
    stats["coverage"] = {
        "samples_done": len(recs), "samples_total": total_tasks, "images_touched": len(covered),
        "by_subset_ru": dict(Counter(r["subset"] for r in recs if r["lang"] == "ru")),
        "subset_totals_ru": dict(Counter(g["subset"] for (lg, _), g in gold.items() if lg == "ru")),
    }

    # --- надёжность и скорость
    status = Counter(r["status"] for r in recs)
    stats["status"] = dict(status)
    ok = [r for r in recs if r["status"] == "done"]
    first = [r for r in ok if not r.get("cached")]
    cached = [r for r in ok if r.get("cached")]
    stats["latency_s"] = {"all_client": summarize([r["client_s"] for r in ok]), "with_ocr_client": summarize([r["client_s"] for r in first]),
                          "cached_ocr_client": summarize([r["client_s"] for r in cached]), "ocr_server": summarize([r["ocr_s"] for r in first if r.get("ocr_s")])}
    stats["errors"] = Counter(r.get("error", "")[:90] for r in recs if r["status"] != "done").most_common(5)
    stats["ocr"] = {"words": summarize([r["ocr_words"] for r in first if r.get("ocr_words") is not None]), "score": summarize([r["ocr_score"] for r in first if r.get("ocr_score") is not None])}

    # --- как сайт определил тип документа (все изображения — не справки вуза)
    per_image = {r["file"]: r for r in ok if r["lang"] == "ru" or True}
    stats["doc_type_auto"] = dict(Counter(str(r["doc_type"]) for r in per_image.values()))
    stats["verdicts"] = {lang: dict(Counter(r["verdict"] for r in ok if r["lang"] == lang)) for lang in sorted({r["lang"] for r in ok})}
    stats["answers_with_boxes_pct"] = round(100 * sum(1 for r in ok if r.get("boxes")) / max(1, len(ok)), 1)

    # --- качество по типам заданий
    by: dict[str, dict] = {}
    for lang in sorted({r["lang"] for r in ok}):
        for task in TASKS:
            rows = [r for r in ok if r["lang"] == lang and r["task"] == task]
            if not rows:
                continue
            m: dict = {"n": len(rows)}
            if task in ("full-page OCR", "document parsing"):
                def pack(texts):
                    vals = [(cer(t, gold[(lang, r["id"])]["answers"][0]), cer_aligned(t, gold[(lang, r["id"])]["answers"][0]), *word_scores(t, gold[(lang, r["id"])]["answers"][0])) for r, t in zip(rows, texts)]
                    return {"cer_strict_mean": round(statistics.fmean(v[0] for v in vals), 3), "cer_aligned_mean": round(statistics.fmean(v[1] for v in vals), 3),
                            "cer_aligned_median": round(statistics.median(v[1] for v in vals), 3), "word_recall": round(statistics.fmean(v[2] for v in vals), 3),
                            "word_f1": round(statistics.fmean(v[4] for v in vals), 3), "cer_aligned_le_0.1_pct": round(100 * sum(v[1] <= 0.1 for v in vals) / len(vals), 1),
                            "cer_aligned_le_0.2_pct": round(100 * sum(v[1] <= 0.2 for v in vals) / len(vals), 1)}

                m["ocr_text"] = pack([ocr_text.get(r["file"], "") for r in rows])
                m["site_answer"] = pack([r["answer"] for r in rows])
            elif task == "reasoning VQA":
                hit_site = [any(contains(r["answer"], a) for a in gold[(lang, r["id"])]["answers"]) for r in rows]
                hit_ocr = [any(contains(ocr_text.get(r["file"], ""), a) for a in gold[(lang, r["id"])]["answers"]) for r in rows]
                f1 = [max(word_scores(r["answer"], a)[2] for a in gold[(lang, r["id"])]["answers"]) for r in rows]
                m.update({"answer_hit_pct": round(100 * sum(hit_site) / len(rows), 1), "gold_in_ocr_pct": round(100 * sum(hit_ocr) / len(rows), 1), "word_f1": round(statistics.fmean(f1), 3),
                          "no_answer_pct": round(100 * sum(r["verdict"] == "no_answer" for r in rows) / len(rows), 1)})
            elif task == "key information extraction":
                site_rec, ocr_rec, n_vals = [], [], 0
                for r in rows:
                    vals = kie_values(gold[(lang, r["id"])]["answers"][0])
                    n_vals += len(vals)
                    if vals:
                        site_rec.append(sum(contains(r["answer"], v) for v in vals) / len(vals))
                        ocr_rec.append(sum(contains(ocr_text.get(r["file"], ""), v) for v in vals) / len(vals))
                m.update({"gold_values": n_vals, "value_recall_site_pct": round(100 * statistics.fmean(site_rec), 1) if site_rec else None,
                          "value_recall_ocr_pct": round(100 * statistics.fmean(ocr_rec), 1) if ocr_rec else None})
            elif task == "text grounding":
                ious = []
                for r in rows:
                    g = gold[(lang, r["id"])]["answers"]
                    try:
                        gb = [float(x) for x in g[:4]]
                    except ValueError:
                        continue
                    ious.append(max((iou(b, gb) for b in r.get("boxes", [])), default=0.0))
                m.update({"scored": len(ious), "mean_iou": round(statistics.fmean(ious), 3) if ious else None,
                          "hit_iou_0.5_pct": round(100 * sum(i >= 0.5 for i in ious) / len(ious), 1) if ious else None,
                          "with_any_box_pct": round(100 * sum(1 for r in rows if r.get("boxes")) / len(rows), 1)})
            by.setdefault(lang, {})[task] = m
    stats["by_lang_task"] = by

    # --- OCR по поднаборам (бизнес-сканы и рукописные)
    sub: dict = {}
    for r in ok:
        if r["lang"] == "ru" and r["task"] == "full-page OCR":
            g = gold[("ru", r["id"])]
            sub.setdefault(r["subset"], []).append(cer_aligned(ocr_text.get(r["file"], ""), g["answers"][0]))
    stats["ocr_cer_by_subset_ru"] = {k: {"n": len(v), "cer_aligned_mean": round(statistics.fmean(v), 3), "cer_aligned_median": round(statistics.median(v), 3)} for k, v in sub.items()}

    (out_dir / "stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(out_dir, stats)


def write_report(out_dir: Path, s: dict) -> None:
    c = s["coverage"]
    L = ["# MWS-Vision-Bench через сайт: статистика", "",
         f"Отправлено заданий: **{c['samples_done']} из {c['samples_total']}** ({100 * c['samples_done'] / max(1, c['samples_total']):.0f}%), затронуто изображений: {c['images_touched']} из 400. "
         f"Подмножества (русские задания): прогнано {c['by_subset_ru']}, всего в датасете {c['subset_totals_ru']}. Статусы запросов: {s['status']}.", ""]
    lat = s["latency_s"]
    L += ["## Скорость", "", "| Запросы | n | среднее, с | медиана, с | p90, с | максимум, с |", "|---|---|---|---|---|---|"]
    for k, title in (("with_ocr_client", "Первый запрос по снимку (с распознаванием и очередью)"), ("cached_ocr_client", "Повторный вопрос по тому же снимку (OCR в кэше)"), ("ocr_server", "Только OCR на сервере")):
        v = lat[k]
        L.append(f"| {title} | {v.get('n', 0)} | {v.get('mean', '—')} | {v.get('median', '—')} | {v.get('p90', '—')} | {v.get('max', '—')} |")
    L += ["", f"Слов распознано на снимок: среднее {s['ocr']['words'].get('mean', '—')}, медиана {s['ocr']['words'].get('median', '—')}, максимум {s['ocr']['words'].get('max', '—')}. "
          f"Внутренняя оценка качества OCR: среднее {s['ocr']['score'].get('mean', '—')} из 100, медиана {s['ocr']['score'].get('median', '—')}.", ""]
    if s.get("errors"):
        L += [f"Ошибки запросов: {s['errors']}", ""]
    L += ["## Автоопределение типа документа", "", f"Все изображения датасета — не справки вуза. Результат по изображениям: {s['doc_type_auto']} "
          "(None = «не похож ни на один известный тип»; любой другой ответ — ложное причисление к справке/заявлению).", ""]

    ocr = [(lang, m) for lang, tasks in s["by_lang_task"].items() for t, m in tasks.items() if t in ("full-page OCR", "document parsing") and lang == "ru"]
    L += ["## Качество распознавания (текст OCR, который сайт показывает в «Технических подробностях»)", "",
          "CER «по окну» сравнивает с лучшим фрагментом страницы, если эталон — только её часть; строгий CER — со всем текстом. Эталон очищен от разметки markdown/HTML.", "",
          "| Задание | n | CER по окну: среднее | медиана | ≤ 10% | ≤ 20% | строгий CER | полнота слов | F1 слов |", "|---|---|---|---|---|---|---|---|---|"]
    for task in ("full-page OCR", "document parsing"):
        m = s["by_lang_task"].get("ru", {}).get(task)
        if m:
            o = m["ocr_text"]
            L.append(f"| {task} | {m['n']} | {o['cer_aligned_mean']} | {o['cer_aligned_median']} | {o['cer_aligned_le_0.1_pct']}% | {o['cer_aligned_le_0.2_pct']}% | {o['cer_strict_mean']} | {o['word_recall']} | {o['word_f1']} |")
    L += ["", "## Ответы сайта на задания датасета", "", "| Язык | Задание | n | Показатель |", "|---|---|---|---|"]
    for lang, tasks in s["by_lang_task"].items():
        for task, m in tasks.items():
            if task in ("full-page OCR", "document parsing"):
                o = m["site_answer"]
                L.append(f"| {lang} | {task} | {m['n']} | ответ сайта: полнота слов {o['word_recall']}, CER {o['cer_aligned_mean']} |")
            elif task == "reasoning VQA":
                L.append(f"| {lang} | {task} | {m['n']} | эталон в ответе сайта: {m['answer_hit_pct']}%; «ответа нет»: {m['no_answer_pct']}%; эталон есть в тексте OCR: {m['gold_in_ocr_pct']}% |")
            elif task == "key information extraction":
                L.append(f"| {lang} | {task} | {m['n']} | значений в эталоне: {m['gold_values']}; найдено в ответе сайта: {m['value_recall_site_pct']}%; присутствует в тексте OCR: {m['value_recall_ocr_pct']}% |")
            elif task == "text grounding":
                L.append(f"| {lang} | {task} | {m['n']} | рамка в ответе: {m['with_any_box_pct']}%; IoU ≥ 0,5: {m['hit_iou_0.5_pct']}%; средний IoU {m['mean_iou']} |")
    L += ["", "## Вердикты сайта по языкам", "", str(s["verdicts"]), "", f"Доля ответов с рамкой на снимке: {s['answers_with_boxes_pct']}%.", ""]
    (out_dir / "report.md").write_text("\n".join(L), encoding="utf-8")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("run", "score"):
        p = sub.add_parser(name)
        p.add_argument("--root", required=True, help="папка датасета (metadata.jsonl, images/, en/, zh/)")
        p.add_argument("--out", required=True, help="папка для results.jsonl, stats.json, report.md")
        p.add_argument("--langs", default="ru,en,zh")
        if name == "run":
            p.add_argument("--base-url", default="http://127.0.0.1:8000")
            p.add_argument("--workers", type=int, default=3)
            p.add_argument("--limit-images", type=int, default=0, help="для проверки: обработать только первые N изображений")
    args = ap.parse_args()
    (run if args.cmd == "run" else score)(args)


if __name__ == "__main__":
    main()
