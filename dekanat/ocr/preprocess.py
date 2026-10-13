"""Предобработка фотографий документов: загрузка, тень, наклон, перспектива, блики.

Все геометрические операции возвращают матрицу 3x3 «до -> после», чтобы рамки слов
можно было вернуть на исходное фото (подсветка найденных полей).
"""

from __future__ import annotations

import io
from typing import Optional

import cv2
import numpy as np
from PIL import Image, ImageOps

PDF_SCALE = 3.0  # ~216 dpi для листа A4
MAX_PDF_PIXELS = 45_000_000  # потолок размера отрисованной страницы PDF (лист A4 при PDF_SCALE — около 4,5 млн)
MAX_SIDE = 6000


class UnsupportedFile(ValueError):
    pass


def _odd(n: int) -> int:
    n = int(n)
    return n if n % 2 == 1 else n + 1


def load_pages(data: bytes, filename: str = "", max_pages: int = 5) -> list[np.ndarray]:
    """Байты файла (JPG/PNG/WEBP/BMP/TIFF/PDF) -> список страниц BGR (с учётом EXIF-поворота)."""
    head = data[:5]
    is_pdf = head.startswith(b"%PDF") or filename.lower().endswith(".pdf")
    pages: list[np.ndarray] = []
    if is_pdf:
        try:
            import pypdfium2 as pdfium
        except ImportError as exc:  # pragma: no cover
            raise UnsupportedFile("Для PDF нужен пакет pypdfium2 (pip install pypdfium2)") from exc
        try:
            pdf = pdfium.PdfDocument(data)
        except Exception as exc:
            raise UnsupportedFile(f"Не удалось открыть PDF: {exc}") from exc
        for i in range(min(len(pdf), max_pages)):
            width, height = pdf[i].get_size()
            # страница с гигантским MediaBox не должна съесть всю память: масштаб снижается до разумного числа пикселей
            scale = min(PDF_SCALE, (MAX_PDF_PIXELS / max(1.0, width * height)) ** 0.5)
            pil = pdf[i].render(scale=scale).to_pil().convert("RGB")
            pages.append(cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR))
        if not pages:
            raise UnsupportedFile("В PDF нет страниц")
        return pages
    try:
        pil = Image.open(io.BytesIO(data))
        n_frames = getattr(pil, "n_frames", 1)
        for i in range(min(n_frames, max_pages)):
            pil.seek(i)
            frame = ImageOps.exif_transpose(pil.copy()).convert("RGB")
            pages.append(cv2.cvtColor(np.array(frame), cv2.COLOR_RGB2BGR))
    except Exception as exc:
        raise UnsupportedFile(f"Не удалось прочитать изображение (поддерживаются JPG, PNG, WEBP, BMP, TIFF, PDF): {exc}") from exc
    return pages


def limit_size(img: np.ndarray, max_side: int = MAX_SIDE) -> np.ndarray:
    h, w = img.shape[:2]
    if max(h, w) <= max_side:
        return img
    s = max_side / max(h, w)
    return cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)


def scale_matrix(sx: float, sy: Optional[float] = None) -> np.ndarray:
    return np.array([[sx, 0, 0], [0, sy if sy is not None else sx, 0], [0, 0, 1]], dtype=np.float64)


def affine3(m23: np.ndarray) -> np.ndarray:
    return np.vstack([m23, [0, 0, 1]]).astype(np.float64)


def resize_for_ocr(img: np.ndarray, target_long: int = 2200) -> tuple[np.ndarray, np.ndarray]:
    """Приводит длинную сторону к удобному для OCR размеру. Возвращает (img, M)."""
    h, w = img.shape[:2]
    long_side = max(h, w)
    if long_side < 1700:
        s = 2000 / long_side
    elif long_side > 3600:
        s = 3000 / long_side
    else:
        return img, np.eye(3)
    interp = cv2.INTER_CUBIC if s > 1 else cv2.INTER_AREA
    return cv2.resize(img, None, fx=s, fy=s, interpolation=interp), scale_matrix(s)


def background_gain(gray: np.ndarray) -> np.ndarray:
    """Оценка фона (бумаги + тени): убирает текст морфологией и сглаживает."""
    h, w = gray.shape
    k = _odd(max(5, w // 220))
    bgk = _odd(max(21, w // 40))
    dil = cv2.dilate(gray, np.ones((k, k), np.uint8))
    bg = cv2.medianBlur(dil, bgk)
    return cv2.GaussianBlur(bg, (0, 0), max(3, w / 300))


def normalize_illumination(bgr: np.ndarray) -> np.ndarray:
    """Убирает тень и неравномерную освещённость: бумага -> белая, цвета чернил сохраняются."""
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    bg = background_gain(gray).astype(np.float32)
    gain = 255.0 / np.maximum(bg, 40.0)
    out = np.clip(bgr.astype(np.float32) * gain[..., None], 0, 255)
    return out.astype(np.uint8)


def glare_mask(bgr: np.ndarray) -> np.ndarray:
    """Маска пересвеченных областей (блики): очень яркие и малонасыщенные пиксели крупными пятнами."""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    mask = ((hsv[..., 2] > 248) & (hsv[..., 1] < 25)).astype(np.uint8) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    return cv2.dilate(mask, np.ones((9, 9), np.uint8))


def estimate_skew(gray: np.ndarray, max_angle: float = 45.0) -> tuple[float, float]:
    """Угол поворота (для cv2.getRotationMatrix2D), выпрямляющий строки текста, и «уверенность» 0..1."""
    h, w = gray.shape
    s = 900.0 / max(h, w)
    small = cv2.resize(gray, None, fx=s, fy=s, interpolation=cv2.INTER_AREA) if s < 1 else gray
    thr = cv2.adaptiveThreshold(small, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 25, 14)
    thr = cv2.morphologyEx(thr, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    # склеиваем буквы в строки по горизонтали (по направлению строки)
    thr = cv2.dilate(thr, cv2.getStructuringElement(cv2.MORPH_RECT, (9, 1)))
    sh, sw = thr.shape
    center = (sw / 2, sh / 2)

    def score(angle: float) -> float:
        m = cv2.getRotationMatrix2D(center, angle, 1.0)
        rot = cv2.warpAffine(thr, m, (sw, sh), flags=cv2.INTER_NEAREST)
        rows = rot.sum(axis=1, dtype=np.float64) / 255.0
        d = np.diff(rows)
        return float(np.sum(d * d))

    coarse = np.arange(-max_angle, max_angle + 0.01, 1.5)
    scores = np.array([score(a) for a in coarse])
    best = float(coarse[int(scores.argmax())])
    fine = np.arange(best - 1.5, best + 1.51, 0.25)
    fscores = np.array([score(a) for a in fine])
    angle = float(fine[int(fscores.argmax())])
    base = score(0.0)
    top = float(fscores.max())
    conf = 0.0 if top <= 0 else float(np.clip((top - base) / (top + 1e-9) * 4, 0, 1))
    if abs(angle) < 0.4 or top < base * 1.02:
        return 0.0, 1.0
    return angle, max(conf, 0.05)


def rotate_expand(img: np.ndarray, angle: float, border=(255, 255, 255)) -> tuple[np.ndarray, np.ndarray]:
    """Поворот с расширением холста. Возвращает (img, M 3x3)."""
    h, w = img.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    cos, sin = abs(m[0, 0]), abs(m[0, 1])
    nw, nh = int(h * sin + w * cos), int(h * cos + w * sin)
    m[0, 2] += nw / 2 - w / 2
    m[1, 2] += nh / 2 - h / 2
    out = cv2.warpAffine(img, m, (nw, nh), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT, borderValue=border)
    return out, affine3(m)


def rotate90(img: np.ndarray, degrees: int) -> tuple[np.ndarray, np.ndarray]:
    """Поворот на кратный 90° (по часовой стрелке). Возвращает (img, M 3x3)."""
    degrees %= 360
    h, w = img.shape[:2]
    if degrees == 0:
        return img, np.eye(3)
    if degrees == 90:
        return cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE), np.array([[0, -1, h], [1, 0, 0], [0, 0, 1]], dtype=np.float64)
    if degrees == 180:
        return cv2.rotate(img, cv2.ROTATE_180), np.array([[-1, 0, w], [0, -1, h], [0, 0, 1]], dtype=np.float64)
    return cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE), np.array([[0, 1, 0], [-1, 0, w], [0, 0, 1]], dtype=np.float64)


def _paper_masks(small: np.ndarray):
    """Кандидаты маски листа: заливка фона от краёв кадра (устойчива к тени) и порог Otsu."""
    sh, sw = small.shape[:2]
    gray = cv2.GaussianBlur(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY), (7, 7), 0)
    # 1) фон = область, достижимая от краёв плавными переходами яркости
    ff = np.zeros((sh + 2, sw + 2), np.uint8)
    xs = [2, sw // 4, sw // 2, 3 * sw // 4, sw - 3]
    ys = [2, sh // 4, sh // 2, 3 * sh // 4, sh - 3]
    seeds = [(x, y) for x in xs for y in (2, sh - 3)] + [(x, y) for x in (2, sw - 3) for y in ys]
    flags = 4 | cv2.FLOODFILL_MASK_ONLY | cv2.FLOODFILL_FIXED_RANGE | (255 << 8)
    for x, y in seeds:
        if ff[y + 1, x + 1] == 0:
            cv2.floodFill(gray, ff, (x, y), 0, 26, 26, flags)
    yield "flood", ((1 - (ff[1:-1, 1:-1] > 0).astype(np.uint8)) * 255)
    # 2) глобальный порог
    _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    yield "otsu", th


def _is_real_boundary(gray: np.ndarray, quad: np.ndarray) -> bool:
    """Лист на фото отличается от окружающего фона по яркости. Если внутри и снаружи «рамки» одно и то же (белый лист во весь кадр,
    а найденный четырёхугольник — просто блок текста внутри него), это не граница листа: обрезка по ней отрежет шапку и поля."""
    sh, sw = gray.shape[:2]
    inner = np.zeros((sh, sw), np.uint8)
    cv2.fillConvexPoly(inner, quad.astype(np.int32), 255)
    k = max(9, int(0.05 * min(sh, sw)))
    outer = cv2.dilate(inner, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * k + 1, 2 * k + 1)))
    ring = (outer > 0) & (inner == 0)
    if ring.sum() < 0.01 * sh * sw:
        return True  # лист у самого края кадра: сравнивать не с чем
    # яркость самой бумаги (а не медиана: в плотном тексте она занижена) против типичной яркости вокруг
    return abs(float(np.percentile(gray[inner > 0], 85)) - float(np.median(gray[ring]))) >= 14.0


def find_page_quad(bgr: np.ndarray) -> Optional[np.ndarray]:
    """Четыре угла листа бумаги на фото (если лист хорошо отделим от фона и не обрезан рамкой)."""
    h, w = bgr.shape[:2]
    s = 700.0 / max(h, w)
    small = cv2.resize(bgr, None, fx=s, fy=s, interpolation=cv2.INTER_AREA) if s < 1 else bgr.copy()
    sh, sw = small.shape[:2]
    small_gray = cv2.GaussianBlur(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY), (7, 7), 0)
    for _, mask in _paper_masks(small):
        th = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15)))
        th = cv2.morphologyEx(th, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15)))
        contours, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue
        cnt = max(contours, key=cv2.contourArea)
        if not (0.22 < cv2.contourArea(cnt) / float(sh * sw) < 0.97):
            continue
        hull = cv2.convexHull(cnt)
        peri = cv2.arcLength(hull, True)
        quad = None
        for eps in (0.015, 0.02, 0.03, 0.045, 0.06):
            approx = cv2.approxPolyDP(hull, eps * peri, True)
            if len(approx) == 4:
                quad = approx.reshape(4, 2).astype(np.float32)
                break
        if quad is None:
            continue
        # лист не должен упираться в края кадра (иначе он обрезан)
        margin = 3
        if sum(1 for x, y in quad if x < margin or y < margin or x > sw - 1 - margin or y > sh - 1 - margin) >= 2:
            continue
        ssum, sdiff = quad.sum(axis=1), np.diff(quad, axis=1).ravel()
        ordered = np.array([quad[np.argmin(ssum)], quad[np.argmin(sdiff)], quad[np.argmax(ssum)], quad[np.argmax(sdiff)]], dtype=np.float32)
        wt, wb = np.linalg.norm(ordered[1] - ordered[0]), np.linalg.norm(ordered[2] - ordered[3])
        hl, hr = np.linalg.norm(ordered[3] - ordered[0]), np.linalg.norm(ordered[2] - ordered[1])
        if min(wt, wb) < 0.5 * max(wt, wb) or min(hl, hr) < 0.5 * max(hl, hr):
            continue
        # соотношение сторон листа должно быть «документным» (A4 ~ 1.41), иначе это не лист
        ratio = max(wt + wb, hl + hr) / max(1.0, min(wt + wb, hl + hr))
        if not (1.1 < ratio < 1.9):
            continue
        if not _is_real_boundary(small_gray, ordered):
            continue
        return ordered / s
    return None


def warp_quad(bgr: np.ndarray, quad: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Перспективное выравнивание листа. Возвращает (img, M 3x3)."""
    wt, wb = np.linalg.norm(quad[1] - quad[0]), np.linalg.norm(quad[2] - quad[3])
    hl, hr = np.linalg.norm(quad[3] - quad[0]), np.linalg.norm(quad[2] - quad[1])
    width, height = int(round(max(wt, wb))), int(round(max(hl, hr)))
    dst = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], dtype=np.float32)
    m = cv2.getPerspectiveTransform(quad.astype(np.float32), dst)
    out = cv2.warpPerspective(bgr, m, (width, height), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    return out, m.astype(np.float64)


def to_gray(bgr: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY) if bgr.ndim == 3 else bgr


def _thin_segments(mask: np.ndarray, horizontal: bool, min_len: int, max_thick: int) -> np.ndarray:
    """Из маски оставляет только тонкие длинные отрезки (линии), отбрасывая стебли и перекладины крупных жирных букв."""
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    keep = np.zeros_like(mask)
    for i in range(1, n):
        x, y, w, h, _ = stats[i]
        length, thick = (w, h) if horizontal else (h, w)
        if length >= min_len and thick <= max_thick and length / max(thick, 1) >= 12:
            keep[labels == i] = 255
    return keep


def remove_lines(gray: np.ndarray) -> np.ndarray:
    """Стирает длинные тонкие линии (рамки таблиц, подчёркивания): они сбивают разметку строк в Tesseract.

    Жирные заголовки не страдают: их штрихи толще и короче по отношению к длине, чем у линии."""
    h, w = gray.shape
    bw = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 15)
    kh = cv2.getStructuringElement(cv2.MORPH_RECT, (max(60, w // 30), 1))
    kv = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(45, h // 55)))
    max_thick = max(8, int(w * 0.004))
    lines = _thin_segments(cv2.morphologyEx(bw, cv2.MORPH_OPEN, kh), True, max(60, w // 30), max_thick)
    lines |= _thin_segments(cv2.morphologyEx(bw, cv2.MORPH_OPEN, kv), False, max(45, h // 55), max_thick)
    if not lines.any():
        return gray
    lines = cv2.dilate(lines, np.ones((3, 3), np.uint8))
    out = gray.copy()
    out[lines > 0] = 255
    return out


def glare_fraction(bgr: np.ndarray) -> float:
    """Доля площади, занятая бликами (для решения, нужен ли вариант с их заделкой)."""
    return float(np.count_nonzero(glare_mask(bgr))) / bgr.shape[0] / bgr.shape[1]


def make_variant(color_norm: np.ndarray, name: str) -> np.ndarray:
    """Из выровненного цветного изображения -> одноканальное для Tesseract."""
    gray = remove_lines(to_gray(color_norm))
    if name == "clean":
        blur = cv2.GaussianBlur(gray, (0, 0), 1.2)
        return cv2.addWeighted(gray, 1.5, blur, -0.5, 0)
    if name == "binary":
        den = cv2.medianBlur(gray, 3)  # быстрое шумоподавление (fastNlMeans на странице А4 съедал секунды)
        block = _odd(max(31, gray.shape[1] // 40))
        return cv2.adaptiveThreshold(den, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, block, 14)
    if name == "clahe":
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        return clahe.apply(gray)
    if name == "deglare":
        mask = glare_mask(color_norm)
        inp = cv2.inpaint(gray, mask, 5, cv2.INPAINT_TELEA) if mask.any() else gray
        return cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8)).apply(inp)
    return gray
