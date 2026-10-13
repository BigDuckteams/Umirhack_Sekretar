import pytest

from dekanat.extract.values import (find_dates, parse_choice, parse_course, parse_date, parse_grade, parse_group, parse_number,
                                    parse_period, parse_person, repair_text)
from dekanat.textutil import is_blank_value, stem_eq


class TestDates:
    def test_numeric(self):
        d = find_dates("Дата выдачи: 15.05.2024")[0]
        assert (d.day, d.month, d.year) == (15, 5, 2024) and d.dmy == "15.05.2024" and d.iso == "2024-05-15"

    def test_spaces_and_short_year(self):
        assert find_dates("выдана 5 . 3 . 24")[0].iso == "2024-03-05"

    def test_text_month(self):
        assert find_dates("«15» мая 2024 г.")[0].iso == "2024-05-15"
        assert find_dates("1 сентября 2023 года")[0].iso == "2023-09-01"

    def test_ocr_digit_confusion(self):
        assert repair_text("О1.О9.2О23") == "01.09.2023"
        assert find_dates("Дата: l5.O5.2O24")[0].iso == "2024-05-15"

    def test_rejects_garbage(self):
        assert find_dates("версия 99.99.2024") == []
        assert parse_date("нет даты") is None

    def test_repair_keeps_length(self):
        s = "срок: О1.О9.2О23 по 3O.O6.2O27"
        assert len(repair_text(s)) == len(s)


class TestPerson:
    def test_full_name(self):
        assert parse_person("Иванов Иван Иванович").value == "Иванов Иван Иванович"

    def test_all_caps_is_title_cased(self):
        assert parse_person("ИВАНОВ ИВАН ИВАНОВИЧ").value == "Иванов Иван Иванович"

    def test_stops_at_comma_and_digits(self):
        assert parse_person("Петрова Анна Сергеевна, ИВТ-21").value == "Петрова Анна Сергеевна"

    def test_does_not_swallow_following_words(self):
        assert parse_person("Иванов Иван обучается в вузе").value == "Иванов Иван"

    def test_rejects_titles(self):
        assert parse_person("Справка О. Практике") is None
        assert parse_person("СПРАВКА ОБ ОБУЧЕНИИ") is None

    def test_initials(self):
        assert parse_person("Иванов И.И.").value == "Иванов И.И."


class TestOther:
    def test_number(self):
        assert parse_number("№ 458 от 15.05.2024").value == "458"
        assert parse_number("Б-12/24").value == "Б-12/24"
        assert parse_number("15.05.2024") is None  # это дата, а не номер

    def test_period(self):
        p = parse_period("с 01.09.2022 по 30.06.2026")
        assert p.value == "01.09.2022 – 30.06.2026" and p.normalized == {"start": "2022-09-01", "end": "2026-06-30"}
        assert parse_period("2022–2026 гг.").normalized == {"start": "2022", "end": "2026"}

    def test_grade_exact_beats_fuzzy(self):
        assert parse_grade("зачтено").value == "зачтено"
        assert parse_grade("незачтено").value == "незачтено"
        assert parse_grade("5 (отлично)").value == "5 (отлично)"
        assert parse_grade("отпично").value == "отлично"  # ошибка OCR

    def test_choice(self):
        choices = {"очная": ["очная", "очной"], "заочная": ["заочная", "заочной"], "очно-заочная": ["очно-заочная", "очно-заочной"]}
        assert parse_choice("на очной форме", choices).value == "очная"
        assert parse_choice("очно-заочной", choices).value == "очно-заочная"
        assert parse_choice("заочнап", choices).value == "заочная"

    def test_group_and_course(self):
        assert parse_group("группы ИВТ-21").value == "ИВТ-21"
        assert parse_group("ИВТ 21").value == "ИВТ-21"
        assert parse_group("33-14").value == "33-14"  # OCR принял «Э» за «3» — код всё равно найден
        assert parse_course("2 курс").value == "2"
        assert parse_course("курс 3").value == "3"

    def test_blank_placeholders(self):
        assert is_blank_value("__________")
        assert is_blank_value(" … ")
        assert not is_blank_value("очная")


def test_stem_eq_handles_snowball_quirks():
    assert stem_eq("подп", "подпис")  # «подпись» и «подписи» стеммер даёт по-разному
    assert stem_eq("печа", "печат")
    assert not stem_eq("практик", "практикант")
    assert not stem_eq("срок", "сроки"[:3])
