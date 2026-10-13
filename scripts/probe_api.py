"""Прогоняет через живой сервер набор «неудобных» входов и печатает, что вернул API. Нужен для отладки.

    python scripts/probe_api.py http://127.0.0.1:8000 [photo.jpg ...]
"""

import io
import sys
import time
from pathlib import Path

import cv2
import httpx
import numpy as np

ROOT = Path(__file__).resolve().parent.parent


def png(img) -> bytes:
    return cv2.imencode(".png", img)[1].tobytes()


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
    extra = [Path(p) for p in sys.argv[2:]]
    rng = np.random.default_rng(1)
    noise = cv2.GaussianBlur((rng.random((900, 1200, 3)) * 255).astype("uint8"), (0, 0), 9)
    white = np.full((1000, 800, 3), 255, np.uint8)
    tiny = cv2.imread(str(ROOT / "data" / "samples" / "sample_01.png"))
    tiny = cv2.resize(tiny, (200, 280))
    cases = [
        ("файл + вопрос про документ", (ROOT / "data/samples/sample_02.png").read_bytes(), "sample.png", "Хватит ли этой справки для перевода на 2 курс?", "auto"),
        ("файл, пустой вопрос", (ROOT / "data/samples/sample_02.png").read_bytes(), "sample.png", "", "auto"),
        ("файл + вопрос о правилах", (ROOT / "data/samples/sample_01.png").read_bytes(), "sample.png", "Сколько дней рассматривается заявление?", "auto"),
        ("файл + вопрос о поле", (ROOT / "data/samples/sample_01.png").read_bytes(), "sample.png", "Какая форма обучения указана?", "auto"),
        ("только вопрос о документе (без файла)", None, "", "Хватит ли справки для перевода?", "auto"),
        ("только вопрос о правилах (без файла)", None, "", "Сколько дней рассматривается заявление?", "auto"),
        ("картинка-шум", png(noise), "noise.png", "Хватит ли справки?", "auto"),
        ("белый лист", png(white), "white.png", "Хватит ли справки?", "auto"),
        ("крошечное изображение", png(tiny), "tiny.png", "Хватит ли справки?", "auto"),
        ("не изображение", b"hello", "x.jpg", "Хватит ли справки?", "auto"),
    ]
    for p in extra:
        cases.append((f"ваш файл {p.name}", p.read_bytes(), p.name, "Хватит ли этой справки для перевода?", "auto"))
    with httpx.Client(timeout=300) as client:
        for title, data, name, question, dtype in cases:
            files = {"file": (name, data, "application/octet-stream")} if data is not None else None
            t = time.time()
            try:
                r = client.post(f"{base}/api/analyze", data={"question": question, "doc_type": dtype}, files=files)
            except Exception as exc:  # noqa: BLE001
                print(f"✗ {title}: исключение {exc!r}")
                continue
            dt = time.time() - t
            if r.status_code != 200:
                print(f"✗ {title}: HTTP {r.status_code} {r.text[:160]}  ({dt:.1f} с)")
                continue
            j = r.json()
            print(f"✓ {title}: тип={j['doc_type']['id']} ({j['doc_type']['how']}), вердикт={j['answer']['verdict']}, интент={j['answer']['intent']}  ({dt:.1f} с)")
            print(f"    ответ: {j['answer']['text'][:130]}")
            if j["warnings"]:
                print(f"    предупреждения: {j['warnings']}")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
