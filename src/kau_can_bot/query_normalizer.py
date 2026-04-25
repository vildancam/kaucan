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
        "hello",
        "hi",
        "hey",
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
        "announcements",
        "announcement",
    ),
    "duyuru": (
        "duyru",
        "duyruu",
        "duyru",
    ),
    "haberler": (
        "habrler",
        "habrlar",
        "news",
    ),
    "etkinlikler": (
        "etknlikler",
        "etkinlkler",
        "events",
    ),
    "sınav": (
        "snav",
        "sinav",
        "sınv",
        "sinv",
        "snavv",
        "exam",
        "midterm",
        "final exam",
    ),
    "akademik takvim": (
        "akademk takvim",
        "akdemik takvim",
        "akadmk takvim",
        "akademik takvmi",
        "akademik takvimi",
        "academic calendar",
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
        "contact",
    ),
    "personel": (
        "personl",
        "persnel",
        "prsonel",
        "personle",
        "staff",
        "faculty members",
    ),
    "yemek menüsü": (
        "yemek menusu",
        "yemek menu",
        "yemek menusü",
        "yemk menusu",
        "yemk menu",
        "yemekhane menusu",
        "yemekhane menu",
        "cafeteria menu",
        "food menu",
        "dining menu",
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
        "calendar",
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
        "nasilsin",
        "how are you",
    ),
    "ne haber": (
        "naber",
        "naaber",
        "ne haberler",
        "whats up",
        "what s up",
    ),
    "ne yapıyorsun": (
        "napıyorsun",
        "napiyorsun",
        "ne yapiyorsun",
        "napion",
    ),
    "iyi misin": (
        "iyimisn",
        "iyi misn",
    ),
    "teşekkürler": (
        "tesekkurler",
        "tskler",
        "eyw",
        "thank you",
        "thanks",
    ),
    "rektör": (
        "rektor",
        "rktor",
    ),
    "rektör yardımcıları": (
        "rektor yardimcilari",
        "rektor yardimcilari kim",
        "rektör yardimcilari",
        "vice rectors",
        "vice rector",
    ),
    "senato": (
        "senatp",
    ),
    "dekanlıklar": (
        "dekanliklar",
        "dekanlklar",
        "dekanlar",
    ),
    "konum": (
        "konm",
        "lokasyon",
        "location",
        "map",
    ),
    "nerede": (
        "nrd",
        "where",
    ),
    "obs": (
        "student information system",
    ),
    "dekan": (
        "dekn",
        "dean",
    ),
    "bölüm başkanı": (
        "bolum baskani",
        "department chair",
        "head of department",
    ),
    "akademik kadro": (
        "academic staff",
        "academic roster",
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
    "rektor": "rektör",
    "konum": "konum",
    "nerede": "nerede",
    "contact": "iletişim",
    "location": "konum",
    "where": "nerede",
    "calendar": "takvim",
    "announcements": "duyurular",
    "announcement": "duyuru",
    "haberler": "haberler",
    "news": "haberler",
    "etkinlikler": "etkinlikler",
    "events": "etkinlikler",
    "exam": "sınav",
    "dekan": "dekan",
    "dean": "dekan",
    "chair": "bölüm başkanı",
    "staff": "personel",
    "ybs": "yönetim bilişim sistemleri",
    "thanks": "teşekkürler",
    "hello": "merhaba",
    "hi": "merhaba",
    "hey": "merhaba",
}

GREETING_PATTERNS = {
    "merhaba",
    "selam",
    "iyi gunler",
    "iyi aksamlar",
    "gunaydin",
    "iyi sabahlar",
    "hello",
    "hi",
    "hey",
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
    "selam nasilsin",
    "merhaba nasilsin",
    "nasil gidiyor",
    "iyi aksamlar nasilsin",
    "gunun nasil geciyor",
    "how are you",
    "what s up",
    "whats up",
    "thank you",
    "thanks",
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
    "rektor",
    "senato",
    "dekanlik",
    "dekanliklar",
    "konum",
    "nerede",
    "contact",
    "location",
    "where",
    "announcements",
    "haberler",
    "etkinlikler",
    "dekan",
    "ybs",
    "exam",
    "staff",
    "calendar",
}

ENGLISH_HINT_WORDS = {
    "about",
    "academic",
    "announcement",
    "announcements",
    "dean",
    "bug",
    "calendar",
    "department",
    "departments",
    "events",
    "code",
    "contact",
    "debug",
    "error",
    "exam",
    "fix",
    "hello",
    "help",
    "hey",
    "history",
    "how",
    "improve",
    "location",
    "menu",
    "please",
    "python",
    "react",
    "staff",
    "news",
    "thanks",
    "what",
    "where",
    "who",
    "why",
}

TURKISH_HINT_WORDS = {
    "akademik",
    "duyuru",
    "duyurular",
    "iletisim",
    "kim",
    "menu",
    "merhaba",
    "nasilsin",
    "nedir",
    "nerede",
    "nasil",
    "personel",
    "sinav",
    "takvim",
    "tesekkurler",
    "yemek",
}

CODING_KEYWORDS = {
    "api",
    "bug",
    "code",
    "coding",
    "css",
    "debug",
    "error",
    "exception",
    "fastapi",
    "fix",
    "flask",
    "function",
    "html",
    "javascript",
    "js",
    "json",
    "kod",
    "python",
    "react",
    "sql",
    "stack trace",
    "typescript",
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
    return any(pattern in normalized for pattern in SMALLTALK_PATTERNS)


def is_english_query(text: str) -> bool:
    normalized = normalize_for_matching(text)
    if not normalized:
        return False

    tokens = normalized.split()
    english_hits = sum(1 for token in tokens if token in ENGLISH_HINT_WORDS)
    turkish_hits = sum(1 for token in tokens if token in TURKISH_HINT_WORDS)
    has_turkish_chars = any(char in text for char in "çğıöşüÇĞİÖŞÜ")

    if has_turkish_chars and english_hits == 0:
        return False
    if english_hits >= 1 and turkish_hits == 0:
        return True
    if english_hits >= 2:
        return True
    return False


def is_coding_query(text: str) -> bool:
    normalized = normalize_for_matching(text)
    if not normalized:
        return False
    return any(keyword in normalized for keyword in CODING_KEYWORDS)


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
