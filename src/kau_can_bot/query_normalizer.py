from __future__ import annotations

import difflib
import re
import unicodedata

from .utils import clean_text


TURKISH_ASCII_MAP = str.maketrans(
    {
        "ç": "c",
        "ğ": "g",
        "ı": "i",
        "ö": "o",
        "ş": "s",
        "ü": "u",
    }
)

PHRASE_CORRECTIONS: dict[str, tuple[str, ...]] = {
    "merhaba": (
        "mrbb",
        "merhb",
        "merhba",
        "meraba",
        "mrb",
        "slm",
        "selm",
    ),
    "iktisadi ve idari bilimler fakültesi": (
        "iibf",
        "i ibf",
        "ii bf",
        "i i b f",
        "ııbf",
        "ibf",
    ),
    "duyurular": (
        "duyrular",
        "duyrulari",
        "duyrlari",
        "duyrlar",
        "duyurulari",
        "duyurulr",
        "duyurulair",
    ),
    "duyuru": (
        "duyru",
        "duyruu",
        "duyru",
    ),
    "sınav": (
        "snav",
        "sinav",
        "sınv",
        "sinv",
        "snavv",
    ),
    "akademik takvim": (
        "akademk takvim",
        "akdemik takvim",
        "akadmk takvim",
        "akademik takvmi",
        "akademik takvimi",
    ),
    "akademik": (
        "akademk",
        "akdemik",
        "akadamik",
    ),
    "iletişim": (
        "iletisim",
        "iletisimm",
        "iletişm",
        "iletşim",
        "iltisim",
        "iletism",
    ),
    "personel": (
        "personl",
        "persnel",
        "prsonel",
        "personle",
    ),
    "yemek menüsü": (
        "yemek menusu",
        "yemek menu",
        "yemek menusü",
        "yemk menusu",
        "yemk menu",
        "yemekhane menusu",
        "yemekhane menu",
    ),
    "bölüm": (
        "bolum",
        "bölm",
        "blum",
    ),
    "bölümler": (
        "bolumler",
        "bolmler",
        "bolumlr",
    ),
    "fakülte": (
        "fakulte",
        "faklute",
        "fakultee",
    ),
    "takvim": (
        "takvm",
        "takvım",
    ),
    "iletişim bilgileri": (
        "iletisim bilgileri",
        "iletişm bilgileri",
        "iletşim bilgileri",
    ),
    "akademik personel": (
        "akademk personel",
        "akdemik personel",
        "akadamik personel",
    ),
    "nasılsın": (
        "nasilsin",
        "nslsin",
        "nasılsn",
    ),
    "ne haber": (
        "naber",
        "naaber",
        "ne haberler",
    ),
}

TOKEN_CORRECTIONS: dict[str, str] = {
    "iibf": "iktisadi ve idari bilimler fakültesi",
    "ibf": "iktisadi ve idari bilimler fakültesi",
    "merhaba": "merhaba",
    "selam": "merhaba",
    "duyurular": "duyurular",
    "duyuru": "duyuru",
    "sinav": "sınav",
    "snav": "sınav",
    "iletisim": "iletişim",
    "akademik": "akademik",
    "takvim": "takvim",
    "personel": "personel",
    "fakulte": "fakülte",
    "bolum": "bölüm",
    "bolumler": "bölümler",
    "menu": "menü",
    "yemekhane": "yemekhane",
}

GREETING_PATTERNS = {
    "merhaba",
    "selam",
    "iyi gunler",
    "iyi aksamlar",
    "gunaydin",
    "iyi sabahlar",
}

SMALLTALK_PATTERNS = {
    "nasilsin",
    "ne haber",
    "naber",
    "iyi misin",
    "napiyorsun",
    "ne yapiyorsun",
    "tesekkurler",
    "tesekkur ederim",
}

ACTIONABLE_KEYWORDS = {
    "akademik",
    "akademik takvim",
    "bolum",
    "bolumler",
    "duyuru",
    "duyurular",
    "fakulte",
    "iibf",
    "iletisim",
    "menu",
    "personel",
    "rehber",
    "sinav",
    "takvim",
    "telefon",
    "yemek",
    "yemekhane",
}


def normalize_for_matching(text: str) -> str:
    value = clean_text(text).lower()
    value = value.translate(TURKISH_ASCII_MAP)
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


FUZZY_VARIANTS = tuple(
    sorted(
        {
            normalize_for_matching(variant)
            for variants in PHRASE_CORRECTIONS.values()
            for variant in variants
        }
        | set(TOKEN_CORRECTIONS)
    )
)


def normalize_query(text: str) -> str:
    working = f" {normalize_for_matching(text)} "
    if not working.strip():
        return ""

    working = re.sub(r"\bi\s*i\s*b\s*f\b", " iibf ", working)

    for variant, canonical in _sorted_phrase_pairs():
        pattern = rf"(?<!\w){re.escape(variant)}(?!\w)"
        working = re.sub(pattern, f" {canonical} ", working)

    corrected_tokens: list[str] = []
    for token in working.split():
        corrected_tokens.append(_correct_token(token))

    corrected = " ".join(corrected_tokens)
    corrected = re.sub(r"\s+", " ", corrected).strip()
    return corrected


def is_greeting_query(text: str) -> bool:
    normalized = normalize_for_matching(normalize_query(text) or text)
    if not normalized:
        return False
    return normalized in GREETING_PATTERNS


def looks_actionable(text: str) -> bool:
    normalized = normalize_for_matching(normalize_query(text) or text)
    if not normalized:
        return False
    return any(keyword in normalized for keyword in ACTIONABLE_KEYWORDS)


def is_smalltalk_query(text: str) -> bool:
    normalized = normalize_for_matching(normalize_query(text) or text)
    if not normalized:
        return False
    return normalized in SMALLTALK_PATTERNS


def _correct_token(token: str) -> str:
    normalized = normalize_for_matching(token)
    if normalized in TOKEN_CORRECTIONS:
        return TOKEN_CORRECTIONS[normalized]

    match = difflib.get_close_matches(normalized, FUZZY_VARIANTS, n=1, cutoff=0.88)
    if not match:
        return token

    matched = match[0]
    if matched in TOKEN_CORRECTIONS:
        return TOKEN_CORRECTIONS[matched]

    for canonical, variants in PHRASE_CORRECTIONS.items():
        if matched == normalize_for_matching(canonical):
            return canonical
        if any(matched == normalize_for_matching(variant) for variant in variants):
            return canonical
    return token


def _sorted_phrase_pairs() -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for canonical, variants in PHRASE_CORRECTIONS.items():
        canonical_variant = normalize_for_matching(canonical)
        pairs.append((canonical_variant, canonical))
        for variant in variants:
            pairs.append((normalize_for_matching(variant), canonical))
    pairs.sort(key=lambda item: len(item[0]), reverse=True)
    return pairs
