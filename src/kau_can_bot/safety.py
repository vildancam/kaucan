from __future__ import annotations

import re


INAPPROPRIATE_PATTERNS = [
    r"\b(amk|aq|mk)\b",
    r"\b(siktir|orospu|piç|yarrak|göt|salak|aptal)\b",
]

HARMFUL_INTENT_PATTERNS = [
    r"\b(bomba|patlayıcı)\s+(yap|hazırla|üret)",
    r"\b(silah)\s+(yap|hazırla|üret)",
    r"\b(hack|hackle|çökert|çal)\b",
]


def has_inappropriate_language(text: str) -> bool:
    normalized = text.lower()
    return any(re.search(pattern, normalized) for pattern in INAPPROPRIATE_PATTERNS)


def has_harmful_intent(text: str) -> bool:
    normalized = text.lower()
    return any(re.search(pattern, normalized) for pattern in HARMFUL_INTENT_PATTERNS)


def is_ambiguous(text: str) -> bool:
    tokens = re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü0-9]{2,}", text)
    if len(tokens) <= 1:
        return True
    return len(text.strip()) < 5
