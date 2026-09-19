"""Text utilities shared by the built-in metrics (tokenisation, claims, lexical embeddings)."""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from collections.abc import Iterable

_STOPWORD_TEXT = """
a an the and or but if then else of to in on at by for with from as is are was were be been
being it its this that these those there here i you he she we they me him her us them my your
his our their what which who whom whose when where why how do does did done can could should
would will shall may might must not no yes so than too very just also about into over under
again further once all any both each few more most other some such only own same s t don now
please thanks thank sure great question happy help hi hello anything get got have has had
i'm it's you're can't won't don't isn't aren't
"""
STOPWORDS = frozenset(_STOPWORD_TEXT.split())
WORD_RE = re.compile(r"[a-z0-9]+(?:['.][a-z0-9]+)*")
NUMBER_RE = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)?(?![\w])")
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])")
PLEASANTRIES = re.compile(
    r"^(sure|of course|great question|happy to help|certainly|absolutely|okay|ok)[.!,]*$", re.I
)
REFUSAL_RE = re.compile(
    r"\b(i can(?:'|no)t|i cannot|i won't|i will not|i'm sorry, but|i am sorry, but|"
    r"i'm not able to|i am not able to|unable to (?:help|assist|provide)|"
    r"not able to (?:help|assist|provide)|i must decline|can't assist|can't help)\b",
    re.I,
)


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").lower().strip()
    text = re.sub(r"[^\w\s.%$-]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" .")


def tokens(text: str) -> list[str]:
    return WORD_RE.findall((text or "").lower())


def stem(word: str) -> str:
    for suffix in ("ing", "edly", "ed", "ies", "es", "s", "ly"):
        if len(word) > len(suffix) + 3 and word.endswith(suffix):
            return word[: -len(suffix)] + ("y" if suffix == "ies" else "")
    return word


def content_words(text: str) -> list[str]:
    return [stem(t) for t in tokens(text) if t not in STOPWORDS and not t.isdigit() and len(t) > 1]


def numbers(text: str) -> set[str]:
    return {n.replace(",", "") for n in NUMBER_RE.findall(text or "")}


def split_sentences(text: str) -> list[str]:
    parts = [p.strip() for p in SENTENCE_RE.split((text or "").strip())]
    return [p for p in parts if p]


def extract_claims(text: str) -> list[str]:
    """Split a response into atomic-ish factual claims (sentence level, minus pleasantries)."""
    claims: list[str] = []
    for sentence in split_sentences(text):
        stripped = re.sub(
            r"^(sure|of course|great question|happy to help|certainly)[.!,]*\s*",
            "",
            sentence,
            flags=re.I,
        ).strip()
        if not stripped or PLEASANTRIES.match(stripped):
            continue
        if len(content_words(stripped)) < 2:
            continue
        claims.append(stripped)
    return claims


def is_refusal(text: str) -> bool:
    return bool(REFUSAL_RE.search(text or ""))


def lexical_vector(text: str) -> Counter[str]:
    """Sparse bag of stemmed content words + character trigrams (a cheap offline embedding)."""
    vec: Counter[str] = Counter()
    for w in content_words(text):
        vec[f"w:{w}"] += 1.0
        padded = f" {w} "
        for i in range(len(padded) - 2):
            vec[f"c:{padded[i : i + 3]}"] += 0.25
    return vec


def cosine(a: Counter[str] | dict[str, float], b: Counter[str] | dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    small, large = (a, b) if len(a) < len(b) else (b, a)
    dot = sum(v * large.get(k, 0.0) for k, v in small.items())
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return 0.0 if na == 0 or nb == 0 else dot / (na * nb)


def dense_cosine(a: Iterable[float], b: Iterable[float]) -> float:
    la, lb = list(a), list(b)
    dot = sum(x * y for x, y in zip(la, lb, strict=False))
    na = math.sqrt(sum(x * x for x in la))
    nb = math.sqrt(sum(y * y for y in lb))
    return 0.0 if na == 0 or nb == 0 else dot / (na * nb)


def lexical_similarity(a: str, b: str) -> float:
    return cosine(lexical_vector(a), lexical_vector(b))


def coverage(claim: str, reference_words: set[str]) -> float:
    words = set(content_words(claim))
    if not words:
        return 1.0
    return len(words & reference_words) / len(words)
