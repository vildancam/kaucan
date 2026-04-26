from __future__ import annotations

import re

from .query_normalizer import looks_actionable, normalize_for_matching


INAPPROPRIATE_PATTERNS = [
    r"\b(amk|aq|mk|sg|sgk)\b",
    r"\b(siktir|sikik|orospu|piç|pic|yarrak|got|gerizekali|geri zekali|salak\w*|aptal\w*|mal)\b",
    r"\b(ibne|kahpe|pezevenk|şerefsiz|serefsiz|ahmak|dangalak)\b",
    r"\b(fuck|shit|bitch|asshole|idiot|stupid|dumb|moron|bastard)\b",
    r"(يا ?غبي|غبي|تافه|قذر|حقير|كلب)",
]

HARMFUL_INTENT_PATTERNS = [
    r"\b(bomba|patlayici|patlayıcı|molotof|explosive|bomb)\b.*\b(yap|hazirla|uret|build|make|prepare)\b",
    r"\b(silah|tabanca|tufek|tüfek|weapon|gun)\b.*\b(yap|hazirla|uret|build|make|obtain)\b",
    r"\b(hack|hackle|cokert|çökert|cal|çal|phish|ddos|ransomware|malware)\b",
    r"\b(zehir|poison|uyusturucu|uyuşturucu|drug)\b.*\b(yap|uret|hazirla|build|make|prepare)\b",
    r"\b(kendimi oldur|kendimi öldür|intihar|suicide|kill myself|self harm)\b",
    r"(اصنع.*قنبلة|اختراق|هاكر|انتحار|قتل نفسي)",
]


def has_inappropriate_language(text: str) -> bool:
    normalized = normalize_for_matching(text)
    return any(re.search(pattern, normalized) for pattern in INAPPROPRIATE_PATTERNS)


def has_harmful_intent(text: str) -> bool:
    normalized = normalize_for_matching(text)
    return any(re.search(pattern, normalized) for pattern in HARMFUL_INTENT_PATTERNS)


def is_ambiguous(text: str) -> bool:
    normalized = normalize_for_matching(text)
    tokens = [token for token in normalized.split() if len(token) >= 2]
    if looks_actionable(normalized):
        return False
    if len(tokens) <= 1:
        return True
    return len(normalized.strip()) < 5
