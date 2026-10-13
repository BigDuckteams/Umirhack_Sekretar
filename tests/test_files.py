"""Проверка входных файлов: повреждённые, огромные, «бомбы», неподдерживаемые — понятная ошибка вместо падения."""

import struct
import zlib

import pytest

from dekanat.ocr.preprocess import MAX_PDF_PIXELS, UnsupportedFile, load_pages


def png_header(width, height) -> bytes:
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)) + chunk(b"IEND", b"")


def pdf_with_page(width, height) -> bytes:
    return (b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
            + f"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 {width} {height}]>>endobj\ntrailer<</Root 1 0 R>>\n".encode())


@pytest.mark.parametrize("name, data", [
    ("empty.png", b""), ("text.jpg", b"just text"), ("bad.pdf", b"%PDF-1.7 not really"), ("exe.png", b"MZ\x90\x00\x03\x00\x00\x00"),
    ("truncated.png", png_header(10, 10)[:-12] + b"\x00\x00\x00\x05IDAT"),
])
def test_unreadable_files_raise_a_clear_error(name, data):
    with pytest.raises(UnsupportedFile):
        load_pages(data, name)


def test_pixel_bomb_image_is_rejected_before_decoding():
    with pytest.raises(UnsupportedFile):
        load_pages(png_header(60000, 60000), "bomb.png")


def test_page_with_a_gigantic_mediabox_is_rendered_at_a_safe_scale():
    pages = load_pages(pdf_with_page(14400, 14400), "huge.pdf")  # без ограничения это ~1,8 млрд пикселей
    h, w = pages[0].shape[:2]
    assert w * h <= MAX_PDF_PIXELS * 1.05


def test_ordinary_pdf_keeps_full_resolution():
    pages = load_pages(pdf_with_page(595, 842), "a4.pdf")
    h, w = pages[0].shape[:2]
    assert abs(w - 595 * 3) <= 3 and abs(h - 842 * 3) <= 3


def test_page_count_is_limited():
    kids = " ".join(f"{i + 3} 0 R" for i in range(8))
    objs = "".join(f"{i + 3} 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 100 100]>>endobj\n" for i in range(8))
    pdf = (f"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[{kids}]/Count 8>>endobj\n{objs}trailer<</Root 1 0 R>>\n").encode()
    assert len(load_pages(pdf, "many.pdf", max_pages=5)) == 5
