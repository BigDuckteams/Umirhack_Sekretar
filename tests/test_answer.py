from pathlib import Path
from app.services.answer import build_grounded_answer
from app.services.extraction import extract_fields
from app.services.policy import PolicyRetriever

def test_answer_has_policy_citation_and_human_review():
    retriever = PolicyRetriever(Path("data/policies/admission_policy.md"))
    chunks = retriever.search("дата выдачи справки", top_k=3)
    answer, citations, needs_review, warnings = build_grounded_answer("Есть ли дата выдачи?", "ФИО: Иванов Иван Иванович", extract_fields("ФИО: Иванов Иван Иванович"), chunks)
    assert citations
    assert "п." in answer
    assert needs_review is True
    assert warnings

def test_no_evidence_abstains():
    answer, citations, needs_review, warnings = build_grounded_answer("Вопрос", "", {}, [])
    assert not citations
    assert needs_review is True
    assert "не найден" in answer
