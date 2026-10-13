import csv
import json

import pytest

from conftest import ROOT, needs_ocr
from dekanat.cli import main
from dekanat.export import read_batch_input


def test_read_batch_input_accepts_several_formats(tmp_path):
    rows = [{"id": "q1", "image": "a.png", "question": "Что не так?", "doc_type": "study_certificate"}]
    (tmp_path / "list.json").write_text(json.dumps(rows), encoding="utf-8")
    (tmp_path / "wrapped.json").write_text(json.dumps({"questions": [{"question_id": 7, "file_name": "b.jpg", "query": "Хватит?"}]}), encoding="utf-8")
    (tmp_path / "lines.jsonl").write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    with open(tmp_path / "t.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "path", "question", "type"], delimiter=";")
        w.writeheader()
        w.writerow({"id": "c1", "path": "c.pdf", "question": "Ок?", "type": "academic_leave"})
    assert read_batch_input(tmp_path / "list.json")[0]["image"] == "a.png"
    w = read_batch_input(tmp_path / "wrapped.json")[0]
    assert (w["id"], w["image"], w["question"]) == ("7", "b.jpg", "Хватит?")
    assert read_batch_input(tmp_path / "lines.jsonl")[0]["doc_type"] == "study_certificate"
    c = read_batch_input(tmp_path / "t.csv")[0]
    assert (c["id"], c["image"], c["doc_type"]) == ("c1", "c.pdf", "academic_leave")


@needs_ocr
def test_batch_writes_results_json(tmp_path):
    samples = ROOT / "data" / "samples"
    manifest = json.loads((samples / "manifest.json").read_text(encoding="utf-8"))
    tasks = [{"id": f"t{i}", "image": m["file"], "question": m["question"]} for i, m in enumerate(manifest[:3], 1)]
    tasks.append({"id": "missing-file", "image": "нет_такого.png", "question": "?"})
    tasks.append({"id": "rules-only", "question": "Сколько дней рассматривается заявление?"})
    inp = tmp_path / "tasks.json"
    inp.write_text(json.dumps(tasks, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "results.json"
    assert main(["batch", "--input", str(inp), "--out", str(out), "--images-dir", str(samples)]) == 0
    res = json.loads(out.read_text(encoding="utf-8"))
    assert [r["id"] for r in res] == ["t1", "t2", "t3", "missing-file", "rules-only"]
    first = res[1]
    assert first["doc_type"] == "study_certificate" and first["verdict"] == "missing"
    assert first["fields"]["ФИО студента"] and first["fields"]["Номер и дата выдачи"].endswith("(не найдено: дата выдачи)")
    assert first["sources"] == ["п. 3.4"] and "даты выдачи" in first["answer"]
    assert res[3]["error"] == "файл не найден"  # один плохой файл не роняет весь прогон
    assert res[4]["sources"] == ["п. 6.1"]


@needs_ocr
def test_ask_json_and_highlight(tmp_path, capsys):
    img = ROOT / "data" / "samples" / "sample_02.png"
    out = tmp_path / "hl.png"
    assert main(["ask", str(img), "Хватит ли справки для перевода?", "--json", "--highlight", str(out)]) == 0
    printed = json.loads(capsys.readouterr().out.split("Подсветка сохранена")[0])
    assert printed["verdict"] == "missing" and out.exists() and out.stat().st_size > 10_000


def test_doctor_and_validate(capsys):
    assert main(["validate-config"]) == 0
    assert "Конфиг корректен" in capsys.readouterr().out
    assert main(["doctor"]) in (0, 1)
    assert "Диагностика окружения" in capsys.readouterr().out
