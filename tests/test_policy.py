from pathlib import Path
from app.services.policy import PolicyRetriever

def test_policy_loader_parses_stable_clause_ids():
    retriever = PolicyRetriever(Path("data/policies/admission_policy.md"))
    assert len(retriever.chunks) >= 5
    assert any(c.policy_id == "P-3.4" for c in retriever.chunks)

def test_policy_search_returns_relevant_clause():
    retriever = PolicyRetriever(Path("data/policies/admission_policy.md"))
    results = retriever.search("дата выдачи справки отсутствует", top_k=3)
    assert results
    assert results[0][0].policy_id == "P-3.4"
