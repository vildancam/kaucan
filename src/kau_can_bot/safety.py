from __future__ import annotations

import re

from .query_normalizer import looks_actionable, normalize_for_matching


INAPPROPRIATE_PATTERNS = [
    r"\b(amk|aq|mk)\b",
    r"\b(siktir|orospu|pic|yarrak|got|salak|aptal)\b",
]

HARMFUL_INTENT_PATTERNS = [
    r"\b(bomba|patlayici)\s+(yap|hazirla|uret)",
    r"\b(silah)\s+(yap|hazirla|uret)",
    r"\b(hack|hackle|cokert|cal)\b",
]


def has_inappropriate_language(text: str) -> bool:
    normalized = normalize_for_matching(text)
    return any(re.search(pattern, normalized) for pattern in INAPPROPRIATE_PATTERNS)


def has_harmful_intent(text: str) -> bool:
    normalized = normalize_for_matching(text)
    return any(re.search(pattern, normalized) for pattern in HARMFUL_INTENT_PATTERNS)


def is_ambiguous(text: str) -> bool:
    normalized = normalize_for_matching(text)
    tokens = re.findall(r"[a-z0-9]{2,}", normalized)
    if looks_actionable(normalized):
        return False
    if len(tokens) <= 1:
        return True
    return len(normalized.strip()) < 5
