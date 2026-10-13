import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dekanat.config import Settings, load_settings  # noqa: E402
from dekanat.ocr import find_tesseract  # noqa: E402

needs_ocr = pytest.mark.skipif(find_tesseract() is None, reason="Tesseract OCR не установлен")


def make_settings(tmp: Path) -> Settings:
    """Копия конфигурации во временную папку: тесты могут менять типы документов, не трогая проект."""
    shutil.copytree(ROOT / "config", tmp / "config")
    (tmp / "data").mkdir(exist_ok=True)
    shutil.copytree(ROOT / "data" / "regulations", tmp / "data" / "regulations")
    shutil.copytree(ROOT / "data" / "samples", tmp / "data" / "samples")
    base = load_settings()
    return Settings(raw=base.raw, root=tmp)


@pytest.fixture(scope="session")
def app():
    from dekanat.pipeline import Dekanat

    return Dekanat()


@pytest.fixture()
def tmp_settings(tmp_path):
    return make_settings(tmp_path)


@pytest.fixture(scope="session")
def samples():
    return ROOT / "data" / "samples"


@pytest.fixture(scope="session")
def synth_set(tmp_path_factory):
    """Небольшой синтетический набор: чистые сканы и лёгкие фото, по одному документу каждого типа."""
    from dekanat import synth

    out = tmp_path_factory.mktemp("synth")
    synth.generate(out, n_per_type=3, levels=(0, 1), seed=21)
    return out
