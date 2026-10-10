from dataclasses import dataclass
from pathlib import Path
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

@dataclass(frozen=True)
class PolicyChunk:
    policy_id: str
    clause: str
    title: str
    source: str
    text: str

class PolicyRetriever:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.chunks = self._load(path)
        self.vectorizer = None
        self.matrix = None
        if self.chunks:
            self.vectorizer = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)
            self.matrix = self.vectorizer.fit_transform([f"{c.title} {c.text}" for c in self.chunks])

    @staticmethod
    def _load(path: Path) -> list[PolicyChunk]:
        if not path.exists():
            return []
        text = path.read_text(encoding="utf-8")
        matches = list(re.finditer(r"^##\s+(P-[\w.-]+)\s*[—-]\s*(.+)$", text, flags=re.MULTILINE))
        chunks = []
        for idx, match in enumerate(matches):
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
            chunks.append(PolicyChunk(match.group(1), match.group(1).removeprefix("P-"),
                                      match.group(2).strip(), path.name, text[match.end():end].strip()))
        return chunks

    def search(self, query: str, top_k: int = 4) -> list[tuple[PolicyChunk, float]]:
        if not self.chunks or self.vectorizer is None or self.matrix is None or not query.strip():
            return []
        scores = cosine_similarity(self.vectorizer.transform([query]), self.matrix).ravel()
        ranked = sorted(enumerate(scores), key=lambda pair: pair[1], reverse=True)
        return [(self.chunks[i], float(score)) for i, score in ranked[:top_k] if score > 0]
