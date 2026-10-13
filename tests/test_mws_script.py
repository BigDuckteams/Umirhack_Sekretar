"""Скрипт оценки на MWS-Vision-Bench: проверяем «обвязку» на поддельной копии датасета (сам датасет не нужен)."""

import importlib.util
import json
import shutil

import pytest

from conftest import ROOT, needs_ocr

spec = importlib.util.spec_from_file_location("eval_mws_vision", ROOT / "scripts" / "eval_mws_vision.py")
mws = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mws)


def test_cer():
    assert mws.cer("Привет, мир", "привет мир") == pytest.approx(0.1, abs=0.11)  # регистр и пунктуация почти не считаются
    assert mws.cer("привет мир", "привет мир") == 0
    assert mws.cer("", "привет") == 1.0
    assert mws.cer("**Привет** мир", "привет мир") == 0  # разметка markdown не ошибка
    assert 0 < mws.cer("привет мер", "привет мир") < 0.2
    assert mws.word_recall("один два", "один два три четыре") == 0.5


def test_load_items_filters_and_deduplicates(tmp_path):
    rows = [
        {"file_name": "images/a.jpg", "id": "1", "type": "full-page OCR ru", "dataset_name": "business", "answers": ["текст"]},
        {"file_name": "images/a.jpg", "id": "2", "type": "full-page OCR ru", "dataset_name": "business", "answers": ["текст"]},
        {"file_name": "images/b.jpg", "id": "3", "type": "reasoning VQA ru", "dataset_name": "business", "answers": ["да"]},
        {"file_name": "images/c.jpg", "id": "4", "type": "full-page OCR ru", "dataset_name": "personal", "answers": []},
    ]
    (tmp_path / "metadata.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    items = mws.load_items(tmp_path)
    assert [i["id"] for i in items] == ["1"]
    with pytest.raises(SystemExit):
        mws.load_items(tmp_path / "нет")


@needs_ocr
def test_script_runs_on_a_local_copy(tmp_path, capsys):
    from dekanat.ocr import OcrOptions, OcrRunner, TesseractEngine

    (tmp_path / "images").mkdir()
    image = tmp_path / "images" / "img0.png"
    shutil.copy(ROOT / "data" / "samples" / "sample_01.png", image)
    reference = mws.recognize_all(OcrRunner(TesseractEngine(), OcrOptions()), image)
    gold = reference.replace("Форма", "Фирма", 1)  # эталон с одной ошибкой: CER маленький, но не нулевой
    row_in = {"file_name": "images/img0.png", "id": "x", "type": "full-page OCR ru", "dataset_name": "business", "answers": [gold]}
    (tmp_path / "metadata.jsonl").write_text(json.dumps(row_in, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "report.json"
    assert mws.main(["--root", str(tmp_path), "--limit", "3", "--out", str(out)]) == 0
    assert "CER" in capsys.readouterr().out
    row = json.loads(out.read_text(encoding="utf-8"))[0]
    assert 0 < row["cer_full"] < 0.05 and row["recall_full"] > 0.9
