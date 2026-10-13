import pytest

from dekanat.config import ConfigError, load_doc_types, load_settings, parse_doc_type_yaml

from conftest import ROOT

MINIMAL = """
id: certificate
title: Справка
fields:
  - id: name
    title: ФИО
    kind: person
    labels: [ФИО]
"""


def test_project_configs_are_valid():
    types = load_doc_types(ROOT / "config" / "doc_types")
    assert set(types) == {"study_certificate", "academic_leave", "practice_certificate"}
    study = types["study_certificate"]
    assert [f.id for f in study.fields][:2] == ["student_name", "university"]
    assert study.field_by_id("issue").parts[1].id == "date"


def test_minimal_config_ok():
    spec = parse_doc_type_yaml(MINIMAL)
    assert spec.id == "certificate" and spec.short_title == "Справка" and spec.aliases == ["Справка"]


@pytest.mark.parametrize("old, new", [
    ("kind: person", "kind: wizard"),
    ("id: certificate", "id: Bad-Id"),
    ("  - id: name", "  - id: Имя"),
])
def test_invalid_values(old, new):
    with pytest.raises(ConfigError):
        parse_doc_type_yaml(MINIMAL.replace(old, new))


def test_bad_regex_is_reported_with_field():
    bad = MINIMAL.replace("labels: [ФИО]", "labels: [ФИО]\n    patterns: ['(?P<value>[']")
    with pytest.raises(ConfigError, match="регуляр"):
        parse_doc_type_yaml(bad)


def test_duplicate_field_ids_and_missing_parts():
    dup = MINIMAL + "  - id: name\n    title: Ещё\n    kind: text\n    labels: [Ещё]\n"
    with pytest.raises(ConfigError, match="повторяющиеся"):
        parse_doc_type_yaml(dup)
    no_parts = MINIMAL.replace("kind: person", "kind: composite")
    with pytest.raises(ConfigError, match="parts"):
        parse_doc_type_yaml(no_parts)


def test_field_without_any_way_to_find_it():
    with pytest.raises(ConfigError, match="нечем искать"):
        parse_doc_type_yaml("id: x\ntitle: X\nfields:\n  - id: a\n    title: A\n    kind: text\n")


def test_date_order_check_must_point_at_known_fields():
    bad = MINIMAL + "checks:\n  - {type: date_order, before: name, after: nothing}\n"
    with pytest.raises(ConfigError, match="неизвестное поле"):
        parse_doc_type_yaml(bad)


def test_env_overrides_settings(monkeypatch):
    monkeypatch.setenv("DEKANAT_OCR_LANGUAGES", "rus")
    monkeypatch.setenv("DEKANAT_LLM_BACKEND", "ollama")
    monkeypatch.setenv("DEKANAT_OCR_FAST", "true")
    s = load_settings()
    assert s.get("ocr.languages") == "rus" and s.get("llm.backend") == "ollama" and s.get("ocr.fast") is True
