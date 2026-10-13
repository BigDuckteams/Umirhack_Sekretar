"""Автоопределение типа документа.

Признаки (все берутся из конфигов типов — новый тип подхватывается без кода):
  * ключевые фразы и «минус-фразы» из `classify` (с бонусом за шапку документа);
  * «покрытие полей»: какая доля названий полей типа найдена в тексте;
  * словарное сходство: общая лексика типа, редкие слова весят больше общих;
  * нечёткое совпадение названия типа с заголовком документа;
  * сходство по символьным 4-граммам (TF-IDF, косинус): почти не боится опечаток и потерянных слов OCR.
Результат — не «да/нет», а ранжирование с долями: интерфейс показывает кандидатов и просит подтвердить, когда не уверены.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache

from rapidfuzz import fuzz

from .config import DocTypeSpec
from .extract.labels import compile_labels, find_hits, label_stems, word_tokens
from .models import OcrPage
from .textutil import normalize, stem_eq

NGRAM_WEIGHT = 24.0  # вклад косинуса 4-грамм в итоговый счёт
MIN_COSINE = 0.2  # сходство по n-граммам, ниже которого (и без ключевых фраз) тип не называем
MIN_KEYWORD_SCORE = 6.0


@dataclass
class Classification:
    type_id: str | None
    confidence: float
    ranking: list[tuple[str, float]]
    reason: str = ""
    uncertain: bool = False
    candidates: list[dict] = field(default_factory=list)  # [{id, share}] по убыванию
    features: dict = field(default_factory=dict)  # отладка: косинус, ключевые баллы, длина текста


def _phrase_count(tokens: list[str], phrase: list[str], max_gap: int = 1) -> int:
    n = 0
    if not phrase:
        return 0
    for i, t in enumerate(tokens):
        if not stem_eq(t, phrase[0]):
            continue
        last, ok = i, True
        for want in phrase[1:]:
            for k in range(last + 1, min(len(tokens), last + 2 + max_gap)):
                if stem_eq(tokens[k], want):
                    last = k
                    break
            else:
                ok = False
                break
        n += ok
    return n


def _phrases(dt: DocTypeSpec) -> list[str]:
    phrases = [dt.title, *dt.aliases, *[p for p, _ in dt.keywords]]
    for f in dt.fields:
        phrases += [f.title, *f.labels, *f.mention]
        for p in f.parts:
            phrases += [p.title, *p.labels, *p.mention]
    return phrases


def _vocabulary(dt: DocTypeSpec) -> set[str]:
    vocab: set[str] = set()
    for ph in _phrases(dt):
        vocab.update(s for s in label_stems(ph) if len(s) >= 3)
    return vocab


def _vocab_overlap(vocabs: dict[str, set[str]], doc_stems: set[str]) -> dict[str, float]:
    """Доля «веса» лексики типа, найденная в документе (чем меньше типов используют слово, тем оно весомее)."""
    n = len(vocabs)
    df: dict[str, int] = {}
    for v in vocabs.values():
        for w in v:
            df[w] = df.get(w, 0) + 1
    out = {}
    for tid, v in vocabs.items():
        total = got = 0.0
        for w in v:
            wt = math.log(1.0 + n / df[w])
            total += wt
            if w in doc_stems or (len(w) >= 5 and any(stem_eq(w, d) for d in doc_stems)):
                got += wt
        out[tid] = got / total if total else 0.0
    return out


# ----------------------------------------------------------------------------- символьные n-граммы


def _ngrams(text: str, n: int = 4) -> Counter:
    t = re.sub(r"\s+", " ", re.sub(r"[^а-яa-z0-9 ]", " ", normalize(text)))
    out: Counter = Counter()
    for word in t.split():
        w = f" {word} "
        for i in range(len(w) - n + 1):
            out[w[i:i + n]] += 1
    return out


@lru_cache(maxsize=64)
def _profile(joined_phrases: str) -> Counter:
    return _ngrams(joined_phrases)


def _ngram_cosines(doc_types: dict[str, DocTypeSpec], doc_text: str) -> dict[str, float]:
    profiles = {tid: _profile(" ".join(_phrases(dt))) for tid, dt in doc_types.items()}
    n = len(profiles)
    df: Counter = Counter()
    for p in profiles.values():
        df.update(p.keys())

    def vec(c: Counter) -> dict[str, float]:
        return {g: (1 + math.log(v)) * math.log(1 + n / df[g]) for g, v in c.items() if g in df}

    doc = vec(_ngrams(doc_text))
    dn = math.sqrt(sum(x * x for x in doc.values())) or 1.0
    out = {}
    for tid, p in profiles.items():
        pv = vec(p)
        pn = math.sqrt(sum(x * x for x in pv.values())) or 1.0
        out[tid] = sum(w * pv[g] for g, w in doc.items() if g in pv) / (dn * pn)
    return out


def classify(doc_types: dict[str, DocTypeSpec], pages: list[OcrPage]) -> Classification:
    rows = [r for p in pages for r in p.rows]
    if not rows:
        return Classification(None, 0.0, [], "текст не распознан")
    head_rows = rows[:8]
    toks_all = [t for r in rows for w in r.words for t in word_tokens(w)]
    toks_head = [t for r in head_rows for w in r.words for t in word_tokens(w)]
    head_text = [normalize(r.text) for r in head_rows]
    vocabs = {tid: _vocabulary(dt) for tid, dt in doc_types.items()}
    overlap = _vocab_overlap(vocabs, set(toks_all))
    cosines = _ngram_cosines(doc_types, " ".join(r.text for r in rows))
    keyword_scores: dict[str, float] = {}
    scores: dict[str, float] = {}
    for tid, dt in doc_types.items():
        s = 0.0
        for phrase, weight in dt.keywords:
            ps = label_stems(phrase)
            hits = min(_phrase_count(toks_all, ps), 2)
            if hits:
                s += weight * (1 + 0.5 * (hits - 1))
                if _phrase_count(toks_head, ps):
                    s += 0.5 * weight
        for phrase, weight in dt.negative:
            if _phrase_count(toks_all, label_stems(phrase)):
                s -= weight
        # покрытие полей: какая доля полей этого типа имеет «свои» метки в документе
        labels = compile_labels(dt)
        found_fields = set()
        for p in pages:
            for h in find_hits(p.rows, labels, p.index):
                found_fields.add(h.field_id)
        if dt.fields:
            s += 8.0 * len(found_fields) / len(dt.fields)
        s += 8.0 * overlap.get(tid, 0.0)
        for alias in dt.aliases:
            a = normalize(alias)
            if len(a) >= 8 and any(fuzz.partial_ratio(a, row) >= 86 for row in head_text):
                s += 4.0
                break
        keyword_scores[tid] = s
        scores[tid] = s + NGRAM_WEIGHT * cosines.get(tid, 0.0)
    ranking = sorted(scores.items(), key=lambda kv: -kv[1])
    exps = [math.exp((sc - ranking[0][1]) / 5.0) for _, sc in ranking]
    total = sum(exps)
    candidates = [{"id": tid, "share": e / total} for (tid, _), e in zip(ranking, exps)]
    top_id, top = ranking[0]
    second = ranking[1][1] if len(ranking) > 1 else -99.0
    feats = {"cos": round(cosines[top_id], 3), "keywords": round(keyword_scores[top_id], 2), "margin": round(top - second, 2), "words": len(toks_all), "top": round(top, 2)}
    cos, kw, margin, words = cosines[top_id], keyword_scores[top_id], top - second, len(toks_all)
    # открытое множество: «это вообще наш тип?» — справки и заявления короткие (десятки слов), длинный документ должен
    # доказывать своё родство сильнее. Пороги подобраны по настоящим и посторонним документам (см. scripts/check_classify.py).
    strong = kw >= 14.0 or (cos >= 0.45 and margin >= 8.0)
    medium = words <= 200 and ((kw >= 8.0 and margin >= 3.0) or (cos >= 0.38 and margin >= 5.0))
    short = words <= 40 and kw >= 5.0 and margin >= 3.0  # записка в пару строк: мало слов, но они «наши»
    if not (strong or medium or short):
        return Classification(None, 0.0, ranking, "документ не похож ни на один из известных типов", False, candidates, feats)
    conf = candidates[0]["share"]
    uncertain = not strong or conf < 0.6 or margin < 3.0
    reason = "тип определён неуверенно: признаки нескольких типов близки" if uncertain else ""
    return Classification(top_id, min(conf, 0.5) if uncertain else conf, ranking, reason, uncertain, candidates, feats)
