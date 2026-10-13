"""База знаний: поиск по Положению и документам с регламентами (раздел `knowledge_base/` рекомендуемой структуры ТЗ).

Реализация живёт в `dekanat/kb/` и здесь не дублируется: модуль собирает её в одном месте под названием из ТЗ.
Поиск — BM25 по основам слов с синонимами, локально, без языковой модели и внешних API.
"""

from ..kb import ClauseIndex, RequirementModel, load_regulation, load_synonym_groups, parse_regulation_text
from ..kb.documents import ALLOWED_SUFFIXES, BASE_ID, KnowledgeBaseError, doc_clauses, read_upload
from ..kb.manager import KnowledgeBaseManager
from ..kb.parser import read_regulation_file

__all__ = [
    "ClauseIndex", "RequirementModel", "load_regulation", "load_synonym_groups", "parse_regulation_text", "read_regulation_file",
    "KnowledgeBaseManager", "KnowledgeBaseError", "ALLOWED_SUFFIXES", "BASE_ID", "doc_clauses", "read_upload",
]
