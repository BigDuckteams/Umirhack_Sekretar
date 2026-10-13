"""Поиск фрагмента текста среди слов OCR: нужен, чтобы показать рамку на снимке для значения, найденного не правилами, а моделью."""

from __future__ import annotations

from typing import Optional

from rapidfuzz import fuzz

from ..models import Box, OcrPage, Word


def _n(text: str) -> str:
    return text.lower().replace("ё", "е").strip(" .,:;«»\"'()")


def locate_fragment(pages: list[OcrPage], fragment: str, min_ratio: float = 85.0) -> tuple[list[Word], Optional[OcrPage]]:
    """Окно подряд идущих слов страницы, которое лучше всего совпадает с фрагментом. Пусто, если уверенного совпадения нет."""
    tokens = [t for t in (_n(x) for x in fragment.split()) if t]
    if not tokens:
        return [], None
    target = " ".join(tokens)
    best: tuple[float, list[Word], Optional[OcrPage]] = (0.0, [], None)
    for page in pages:
        words = [w for row in page.rows for w in row.words]
        norm = [_n(w.text) for w in words]
        size = len(tokens)
        for start in range(0, max(1, len(words) - size + 1)):
            window = norm[start:start + size]
            if not window:
                continue
            score = fuzz.ratio(" ".join(window), target)
            if score > best[0]:
                best = (score, words[start:start + size], page)
    if best[0] >= min_ratio:
        return best[1], best[2]
    return [], None


def boxes_for_words(page: OcrPage, words: list[Word]) -> list[Box]:
    """По одному прямоугольнику на строку (в координатах исходного снимка)."""
    rows: dict[int, list[Word]] = {}
    for w in words:
        rows.setdefault(round(w.yc / max(1.0, w.h)), []).append(w)
    return [page.map_box(min(w.x0 for w in ws), min(w.y0 for w in ws), max(w.x1 for w in ws), max(w.y1 for w in ws)) for _, ws in sorted(rows.items())]
