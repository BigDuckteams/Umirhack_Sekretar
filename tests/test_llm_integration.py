"""НЕОБЯЗАТЕЛЬНЫЙ интеграционный тест с настоящей локальной моделью (CPU). По умолчанию пропускается.

Запуск (нужны запущенная Ollama и установленная модель, по умолчанию qwen2.5:3b-instruct):

    DEKANAT_TEST_REAL_LLM=1 python -m pytest tests/test_llm_integration.py -s
    DEKANAT_TEST_REAL_LLM=1 DEKANAT_LLM_MODEL=llama3.1:8b python -m pytest tests/test_llm_integration.py -s   # другая модель

Проверяется не «качество ответов» (оно зависит от модели), а то, что связка работает: запросы доходят, JSON валиден, значения проходят проверки.
"""

import os

import pytest

from dekanat.config import Settings, load_settings
from dekanat.llm import LLMService
from dekanat.models import Clause

pytestmark = pytest.mark.skipif(not os.environ.get("DEKANAT_TEST_REAL_LLM"), reason="реальная модель: включается DEKANAT_TEST_REAL_LLM=1")


@pytest.fixture(scope="module")
def llm():
    base = load_settings()
    base.raw["USE_LOCAL_LLM"] = True
    svc = LLMService.from_settings(Settings(raw=base.raw, root=base.root))
    if not svc.available():
        pytest.skip(f"модель {svc.cfg.model} недоступна: запустите Ollama и выполните `ollama pull {svc.cfg.model}`")
    return svc


def test_real_model_runs_on_cpu_and_status_is_reported(llm):
    st = llm.status()
    assert st["enabled"] and st["available"] and st["cpu_only"] is True


def test_real_intent(llm):
    res = llm.detect_intent("Здравствуйте, хочу перевестись к вам из другого университета")
    assert res is not None and res.intent in ("transfer", "statement", "enrollment") and res.confidence in ("high", "medium", "low")


def test_real_hedged_debts_answer_is_never_taken_as_debts(llm):
    res = llm.normalize_answer("Есть ли у вас академические задолженности?", "Да не, долгов вроде нет, всё закрыл", "bool",
                               value_hint="true — у студента ЕСТЬ академические задолженности, false — задолженностей НЕТ")
    assert res is not None and res.status in ("clear", "ambiguous", "invalid")
    assert not (res.status == "clear" and res.value is True)


def test_real_extraction_is_grounded(llm):
    text = "СПРАВКА\nУниверситет Тестовск\nФИО студента: Иванов Иван Иванович\nПрофиль подготовки: Прикладная информатика\nФорма обучения: очная"
    got = llm.extract_fields(text, "Справка об обучении", [("direction", "Направление подготовки"), ("study_period", "Период обучения")])
    for item in got.values():  # всё, что принято, обязано подтверждаться текстом
        assert item.source_text and item.source_text.lower().split()[0] in text.lower()
    assert "study_period" not in got  # периода в тексте нет — выдумывать его модель не вправе


def test_real_judge_returns_known_clause_only(llm):
    clauses = [Clause("3.5", "Справка об обучении выдаётся бесплатно в течение 3 рабочих дней со дня обращения студента."), Clause("6.1", "Деканат рассматривает заявления в течение 5 рабочих дней.")]
    res = llm.judge_clauses(clauses, "Сколько дней делают справку об обучении?")
    assert res is not None and res.clause_number in (None, "3.5", "6.1")
