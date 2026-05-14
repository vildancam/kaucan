from __future__ import annotations

import re

from .query_normalizer import is_short_ambiguous_query, looks_actionable, normalize_for_matching


INAPPROPRIATE_PATTERNS = [
    r"\b(amk|aq|mk|sg|sgk)\b",
    r"\b(oc|o c|o\.c|oç|o ç|o\.ç|pic|pıc|p\*c|ococuk|ocuk)\b",
    r"\b(siktir|sikik|orospu|piç|pic|yarrak|got|göt|bok|boktan|gerizekali|geri zekali|salak\w*|aptal\w*|mal)\b",
    r"\b(ibne|kahpe|pezevenk|şerefsiz|serefsiz|ahmak|dangalak|gerzek|sapsal|hiyar|hıyar|lavuk|gavat)\b",
    r"\b(kopek|köpek|haysiyetsiz|namussuz)\b",
    r"\b(fuck|shit|bitch|asshole|idiot|stupid|dumb|moron|bastard)\b",
    r"(يا ?غبي|غبي|تافه|قذر|حقير|كلب)",
]

PROTECTED_TARGET_PATTERNS = [
    r"\b(rektor\w*|rector\w*|rectorate\w*|rektorluk\w*|rektor makami\w*|rektorluk makami\w*|vice rector\w*|rektor yardimci\w*|dekan\w*|dean\w*|dekanlik\w*)\b",
    r"\b(akademik personel|academic staff|akademisyen\w*|ogretim uyesi\w*|hoca\w*|hocalar\w*|personel\w*|idari personel|administrative staff|memur\w*|gorevli\w*|bolum baskani\w*|department chair\w*)\b",
    r"\b(ogrenci\w*|student\w*|ogrenci isleri\w*|student affairs\w*|universite\w*|university\w*|kampus\w*|campus\w*|fakulte\w*|faculty\w*|iibf\w*|yurt\w*|dorm\w*)\b",
    r"\b(kutuphane\w*|library\w*|yemekhane\w*|cafeteria\w*|kafeterya\w*|merkezi kafeterya\w*|hali saha\w*|spor tesisi\w*|saglik kultur\w*|skdb\w*|daire baskanligi\w*)\b",
    r"\b(kars\w*|turkiye\w*|turk\w*|millet\w*|nation\w*|uyruk\w*|nationality\w*|bayrak\w*|flag\w*|ataturk\w*)\b",
    r"(رئيس الجامعة|العميد|الطلاب|الجامعة|السكن|تركيا|العلم|اتاتورك|الامة)",
]

TARGETED_ABUSE_CONTENT_PATTERNS = [
    r"\b(allah belasini versin|allah kahretsin|allah cezasini versin|belasini versin|cezasini versin|lanet olsun|kahrolsun|kahretsin|geber\w*|cehenneme git\w*|defol\w*|kovulsun|kovulmali|istifa etsin)\b",
    r"\b(cok\s+)?kotu\s+(birisi|biri|insan|adam|kadin|kisi|kisilik)\b",
    r"\b(tam bir\s+)?(kotu|berbat|rezil|igrenc|igren\w*|sevimsiz|yalanci|sahtekar|terbiyesiz|saygisiz|pislik|adi|ukala|suratsiz|suursuz|karaktersiz|onursuz|asagilik|kepaze|zavalli|ezik|bos|\w*bozuk|ise yaramaz|bes para etmez|beceriksiz)\b",
    r"\b(sevmiyorum|sevmi?yo\w*|nefret ediyorum|nefret\w*|hoslanmiyorum|hoşlanmıyorum|tiksiniyorum|sinir oluyorum|katlanamiyorum|katlanamıyorum|gicik oluyorum)\b",
    r"\b(adam degil|insan degil|suratina bakilmaz|yuzunu gormek istemiyorum|yüzünü görmek istemiyorum)\b",
    r"(ياخذه الله|لعنة الله|سيئ جدا|شخص سيئ|اكرهه|لا احبه|مقرف|حقير جدا)",
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
    return _matches_any(normalized, INAPPROPRIATE_PATTERNS)


def has_targeted_abuse(text: str) -> bool:
    normalized = normalize_for_matching(text)
    has_abusive_content = _matches_any(normalized, INAPPROPRIATE_PATTERNS) or _matches_any(
        normalized,
        TARGETED_ABUSE_CONTENT_PATTERNS,
    )
    if not has_abusive_content:
        return False
    return _matches_any(normalized, PROTECTED_TARGET_PATTERNS)


def has_harmful_intent(text: str) -> bool:
    normalized = normalize_for_matching(text)
    return _matches_any(normalized, HARMFUL_INTENT_PATTERNS)


def is_ambiguous(text: str) -> bool:
    normalized = normalize_for_matching(text)
    if is_short_ambiguous_query(text):
        return True
    tokens = [token for token in normalized.split() if len(token) >= 2]
    if looks_actionable(normalized):
        return False
    if len(tokens) <= 1:
        return True
    return len(normalized.strip()) < 5


def _matches_any(text: str, patterns) -> bool:
    return any(re.search(pattern, text) for pattern in patterns)
