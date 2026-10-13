"""Документы не из вуза: классификатор их отвергает, вопросы идут по тексту самого документа. Плюс фоновые задачи."""

import sys
import time

import pytest
from fastapi.testclient import TestClient

from conftest import ROOT, needs_ocr
from dekanat.classify import classify
from dekanat.config import load_doc_types, load_settings
from dekanat.qa.docqa import DocumentQA, _item_number
from dekanat.web.app import create_app

sys.path.insert(0, str(ROOT / "scripts"))
import check_classify as cc  # noqa: E402


@pytest.fixture(scope="module")
def doc_types():
    return load_doc_types(load_settings().doc_types_dir)


# ----------------------------------------------------------------------------- классификация без картинок


@pytest.mark.parametrize("want,text", [(w, t) for w, texts in cc.CASES.items() for t in texts])
def test_own_documents_are_recognized(doc_types, want, text):
    assert classify(doc_types, [cc.page_from_text(text)]).type_id == want


@pytest.mark.parametrize("text", cc.FOREIGN)
def test_foreign_documents_are_rejected(doc_types, text):
    c = classify(doc_types, [cc.page_from_text(text)])
    assert c.type_id is None and c.candidates and "не похож" in c.reason


# ----------------------------------------------------------------------------- вопросы по тексту документа

ORDER = """ПРИКАЗ
г. Тестовск
14.02.2025 № 2
О мерах по подготовке к весеннему паводку 2025 года
В целях предупреждения угрозы подтопления жилых домов приказываю:
1. Рекомендовать главам районов городского округа:
1.1. обеспечить очистку водоотводных канав до 01.03.2025;
1.2. организовать дежурство аварийных бригад и запас мешков с песком не менее 500 штук на район;
2. Начальнику отдела связи обеспечить работу системы оповещения населения.
3. Контроль за выполнением приказа оставляю за собой."""


def _docqa():
    return DocumentQA([])


def test_item_numbers_are_repaired_after_ocr_mistakes():
    assert _item_number("11.", "1") == "1.1"
    assert _item_number("12:", "1.1") == "1.2"
    assert _item_number("le", None) == "1"
    assert _item_number("2.", "1.3") == "2"
    assert _item_number("11.", "10") == "11"  # настоящий пункт 11 после 10 не трогаем
    assert _item_number("2025", None) is None


def test_question_about_an_item_returns_its_text_with_a_box():
    a = _docqa().answer("Что приказано в п. 1.2?", [cc.page_from_text(ORDER)])
    assert a.verdict == "ok" and "дежурство" in a.text and "500 штук" in a.text and "(п. 1.2 документа)" in a.text
    assert a.sources[0].kind == "document" and a.sources[0].boxes


def test_header_requisites_and_overview():
    pages = [cc.page_from_text(ORDER)]
    assert "14.02.2025" in _docqa().answer("Какая дата документа?", pages).text
    assert _docqa().answer("Какой номер документа?", pages).text.endswith(": 2")
    over = _docqa().answer("О чём документ?", pages)
    assert over.verdict == "ok" and "О мерах по подготовке к весеннему паводку" in over.text


def test_search_by_meaning_finds_the_item_and_unrelated_questions_get_no_answer():
    pages = [cc.page_from_text(ORDER)]
    a = _docqa().answer("Сколько мешков с песком нужно?", pages)
    assert a.verdict == "ok" and "500 штук" in a.text
    assert _docqa().answer("Какая стоимость аренды офиса?", pages).verdict == "no_answer"


# ----------------------------------------------------------------------------- через весь сервис


@needs_ocr
def test_order_sample_is_not_forced_into_a_student_type(app, samples):
    data = (samples / "sample_09.jpg").read_bytes()
    res = app.analyze(data, "sample_09.jpg", "Что приказано в п. 1.2?", None)
    assert res.doc_type is None and not res.fields
    assert res.answer.verdict == "ok" and "мешков" in res.answer.text and res.answer.sources[0].boxes
    assert any("не похож" in w for w in res.warnings)


@needs_ocr
def test_generic_mode_can_be_chosen_by_hand(app, samples):
    data = (samples / "sample_09.jpg").read_bytes()
    res = app.analyze(data, "sample_09.jpg", "О чём документ?", "generic")
    assert res.how == "generic" and res.to_dict(preview=False)["doc_type"]["title"] == "Другой документ"
    assert res.answer.verdict == "ok"


@needs_ocr
def test_a_check_question_on_a_foreign_document_explains_what_to_do(app, samples):
    data = (samples / "sample_09.jpg").read_bytes()
    res = app.analyze(data, "sample_09.jpg", "Хватит ли этой справки для перевода на 2 курс?", None)
    assert res.doc_type is None
    assert res.answer.verdict == "no_answer" and res.answer.text  # внятное объяснение, а не молчание


# ----------------------------------------------------------------------------- фоновые задачи


@pytest.fixture()
def client(tmp_settings):
    return TestClient(create_app(tmp_settings))


def _wait(client, job_id, timeout=120.0):
    end = time.time() + timeout
    while time.time() < end:
        snap = client.get(f"/api/jobs/{job_id}").json()
        if snap["status"] in ("done", "error", "cancelled"):
            return snap
        time.sleep(0.2)
    raise AssertionError("задача не завершилась")


def test_job_for_a_rules_question(client):
    job = client.post("/api/jobs", data={"question": "Сколько дней рассматривается заявление?", "doc_type": "auto"}).json()
    snap = _wait(client, job["id"])
    assert snap["status"] == "done" and snap["fraction"] == 1.0
    assert snap["result"]["answer"]["sources"][0]["ref"] == "6.1"


def test_job_reports_errors_as_text(client):
    job = client.post("/api/jobs", files={"file": ("x.jpg", b"not an image", "image/jpeg")}, data={"question": "Что не так?"}).json()
    snap = _wait(client, job["id"])
    assert snap["status"] == "error" and "Не удалось прочитать" in snap["error"]


def test_unknown_job_is_404_and_input_is_validated(client):
    assert client.get("/api/jobs/nope").status_code == 404
    assert client.delete("/api/jobs/nope").status_code == 404
    assert client.post("/api/jobs", data={"question": ""}).status_code == 400


@needs_ocr
def test_job_can_be_cancelled(client, samples):
    data = (samples / "sample_09.jpg").read_bytes()
    job = client.post("/api/jobs", files={"file": ("a.jpg", data + b"\0", "image/jpeg")}, data={"question": "О чём документ?"}).json()
    assert client.delete(f"/api/jobs/{job['id']}").json() == {"ok": True}
    assert _wait(client, job["id"])["status"] in ("cancelled", "done")  # успеть отменить можно не всегда


def test_suggestions_have_three_kinds(client):
    study = next(t for t in client.get("/api/doctypes").json() if t["id"] == "study_certificate")
    assert {s["kind"] for s in study["suggestions"]} == {"check", "field", "rules"}


# ----------------------------------------------------------------------------- реальный документ: шапка, рукописные реквизиты

DECREE_LIKE = """ЕЕ
ФЕДЕРАЛЬНАЯ СЛУЖБА ПО НАДЗОРУ В СФЕРЕ ЗАЩИТЫ ПРАВ ПОТРЕБИТЕЛЕЙ И
БЛАГОПОЛУЧИЯ ЧЕЛОВЕКА
ГЛАВНЫЙ ГОСУДАРСТВЕННЫЙ САНИТАРНЫЙ ВРАЧ ПО ЧЕЛЯБИНСКОЙ
ОБЛАСТИ
ПОСТАНОВЛЕНИЕ
Челябинск
Об усилении мер по обеспечению качества питьевой воды в период весеннего паводка 2025г.
В соответствии со ст. 50, 51 Федерального закона РФ от 30.03.1999 г. № 52-ФЗ, во исполнение закона от 07.12.2011 г. постановляю:
I, Рекомендовать Главам муниципальных образований Челябинской области:
1/1. принять меры по обеспечению бесперебойной работы систем водоснабжения и водоотведения;
1.2. обеспечить запас дезинфицирующих средств на территориях, подверженных подтоплению;"""


def test_ocr_damaged_item_numbers_are_repaired_further():
    assert _item_number("1/1.", "1") == "1.1"
    assert _item_number("I,", None) == "1"


def test_overview_names_the_kind_of_document_not_a_junk_line():
    a = _docqa().answer("О чём документ?", [cc.page_from_text(DECREE_LIKE)])
    assert a.verdict == "ok" and a.text.startswith("Начало документа: ПОСТАНОВЛЕНИЕ — Об усилении мер")
    assert "ЕЕ" not in a.text.split("—")[0]


def test_handwritten_date_and_number_get_an_honest_answer():
    pages = [cc.page_from_text(DECREE_LIKE)]
    d = _docqa().answer("Какая дата документа?", pages)
    assert d.verdict == "no_answer" and "написана от руки" in d.text and "30.03.1999" in d.text
    n = _docqa().answer("Какой номер документа?", pages)
    assert n.verdict == "no_answer" and "Номер документа в шапке прочитать не удалось" in n.text


def test_item_with_a_slash_number_is_found():
    a = _docqa().answer("Что сказано в п. 1.1?", [cc.page_from_text(DECREE_LIKE)])
    assert a.verdict == "ok" and "водоснабжения" in a.text


def test_running_job_is_not_evicted_by_newer_jobs():
    """Регресс (нашёлся при прогоне датасета): долгая задача пропадала (404), если за время её работы создавалось больше max_jobs новых."""
    import threading

    from dekanat.web.jobs import JobManager

    mgr = JobManager(slots=4, max_jobs=3)
    release = threading.Event()
    slow = mgr.submit(lambda progress: (release.wait(10), {"ok": True})[1], str)
    quick = [mgr.submit(lambda progress: {"n": i}, str) for i in range(8)]
    deadline = time.time() + 10
    while time.time() < deadline and not all(mgr.get(q.id) is None or mgr.get(q.id).finished for q in quick):
        time.sleep(0.05)
    assert mgr.get(slow.id) is not None and mgr.get(slow.id).status in ("queued", "running")
    release.set()
    deadline = time.time() + 10
    while time.time() < deadline and mgr.get(slow.id).status != "done":
        time.sleep(0.05)
    assert mgr.get(slow.id).status == "done" and mgr.get(slow.id).result == {"ok": True}
