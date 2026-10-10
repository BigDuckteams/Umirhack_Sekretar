from app.schemas import Citation
from app.services.policy import PolicyChunk

def build_grounded_answer(question: str, ocr_text: str, fields: dict,
                          retrieved: list[tuple[PolicyChunk, float]]) -> tuple[str, list[Citation], bool, list[str]]:
    warnings: list[str] = []
    citations: list[Citation] = []
    if not ocr_text.strip():
        warnings.append("OCR не извлёк текст; нужен новый снимок или ручная проверка.")
    if not retrieved:
        warnings.append("Релевантный пункт Положения не найден.")
        return ("Не могу обоснованно ответить: релевантный пункт Положения не найден. Передайте документ сотруднику деканата.", [], True, warnings)
    for chunk, score in retrieved:
        if score >= 0.01 and len(citations) < 3:
            citations.append(Citation(policy_id=chunk.policy_id, clause=chunk.clause,
                                     source=chunk.source, quote=" ".join(chunk.text.split())[:280]))
    missing = [label for key, label in [("full_name", "ФИО"), ("institution", "предыдущее учебное заведение"), ("issue_date", "дата выдачи")]
               if not fields.get(key) or not fields[key].value]
    lead = "Не удалось надёжно подтвердить: " + ", ".join(missing) + "." if missing else "Основные поля распознаны, но их нужно сверить с оригиналом."
    answer = lead + " Применимые пункты Положения: " + ", ".join(f"п. {c.clause}" for c in citations) + ". Это предварительная справка, не решение о переводе; итоговую проверку выполняет сотрудник."
    warnings.append("Поля извлекаются эвристиками и могут содержать ошибки.")
    return answer, citations, True, warnings
