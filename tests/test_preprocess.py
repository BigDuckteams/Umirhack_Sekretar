import cv2
import numpy as np
import pytest

from dekanat.models import OcrPage
from dekanat.ocr import preprocess as pp
from dekanat.ocr.runner import build_rows, quality, split_glued
from dekanat.models import Word

from conftest import ROOT


@pytest.fixture(scope="module")
def doc():
    return cv2.imdecode(np.fromfile(str(ROOT / "data" / "samples" / "sample_01.png"), np.uint8), cv2.IMREAD_COLOR)


@pytest.mark.parametrize("angle", [-30, -17, -5, 4, 12, 29])
def test_skew_estimation(doc, angle):
    tilted = pp.rotate_expand(doc, angle)[0]
    est, _ = pp.estimate_skew(pp.to_gray(pp.normalize_illumination(tilted)))
    # оценка — угол поворота, который нужно применить, чтобы выпрямить: противоположный наклону
    assert abs(est + angle) <= 1.5, (angle, est)


def test_straight_page_is_left_alone(doc):
    assert pp.estimate_skew(pp.to_gray(doc))[0] == 0.0


def test_box_mapping_roundtrip(doc):
    h, w = doc.shape[:2]
    rotated, m = pp.rotate_expand(doc, 20)
    page = OcrPage(0, rotated.shape[1], rotated.shape[0], [], [], m, (w, h))
    # прямоугольник в координатах повёрнутого изображения -> в исходных; его центр совпадает с прямым отображением
    cx, cy = 300.0, 220.0
    p = m @ np.array([cx, cy, 1.0])
    p = p[:2] / p[2]
    box = page.map_box(p[0] - 10, p[1] - 10, p[0] + 10, p[1] + 10)
    assert abs((box.x0 + box.x1) / 2 - cx) < 3 and abs((box.y0 + box.y1) / 2 - cy) < 3


def test_page_quad_found_on_a_photo(doc):
    h, w = doc.shape[:2]
    pad = 160
    canvas = np.full((h + 2 * pad, w + 2 * pad, 3), (70, 90, 110), np.uint8)
    canvas[pad:pad + h, pad:pad + w] = doc
    photo = pp.rotate_expand(canvas, 18, (70, 90, 110))[0]
    quad = pp.find_page_quad(photo)
    assert quad is not None
    warped, _ = pp.warp_quad(photo, quad)
    assert 0.6 < warped.shape[1] / warped.shape[0] < 0.85  # лист A4 книжной ориентации
    assert pp.find_page_quad(doc) is None  # скан во весь кадр — искать нечего


def test_exif_orientation_is_respected(tmp_path, doc):
    from PIL import Image

    img = Image.fromarray(cv2.cvtColor(doc, cv2.COLOR_BGR2RGB))
    exif = img.getexif()
    exif[274] = 6  # «повернуть на 90° по часовой»
    path = tmp_path / "exif.jpg"
    img.save(path, exif=exif)
    page = pp.load_pages(path.read_bytes(), "exif.jpg")[0]
    assert page.shape[:2] == (doc.shape[1], doc.shape[0])


def test_table_lines_are_removed():
    img = np.full((600, 900), 255, np.uint8)
    cv2.rectangle(img, (50, 50), (850, 550), 0, 3)
    cv2.line(img, (450, 50), (450, 550), 0, 3)
    cv2.putText(img, "Hello", (80, 120), cv2.FONT_HERSHEY_SIMPLEX, 1.4, 0, 3)
    cleaned = pp.remove_lines(img)
    assert (cleaned[48:54, 100:800] < 128).sum() == 0  # линия стёрта
    assert (cleaned[80:130, 80:240] < 128).sum() > 100  # текст остался


def test_glued_label_is_split():
    words = [Word("курс:ЮР-32,", 90, 100, 10, 210, 30), Word("2", 90, 230, 10, 240, 30)]
    out = split_glued(words)
    assert [w.text for w in out] == ["курс:", "ЮР-32,", "2"] and out[0].x1 <= out[1].x0


def test_rows_group_cells_of_a_table_row():
    words = [Word("Форма", 95, 100, 100, 180, 124), Word("обучения", 95, 190, 101, 300, 125), Word("очная", 95, 600, 98, 680, 124),
             Word("Период", 95, 100, 160, 190, 184)]
    rows = build_rows(words)
    assert [r.text for r in rows] == ["Форма обучения очная", "Период"]


def test_quality_prefers_real_text():
    good = [Word("Справка", 95, 0, 0, 80, 20), Word("об", 95, 90, 0, 110, 20), Word("обучении", 94, 120, 0, 210, 20)] * 4
    junk = [Word("a(|", 40, 0, 0, 30, 20), Word("~~", 30, 40, 0, 60, 20), Word("Ё5", 20, 70, 0, 90, 20)] * 4
    assert quality(good)["score"] > 60 > quality(junk)["score"]
