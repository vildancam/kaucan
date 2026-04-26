from __future__ import annotations

import time
import re
from dataclasses import dataclass, field
from functools import lru_cache
from urllib.parse import quote, quote_plus

import requests

from .query_normalizer import is_coding_query, normalize_for_matching
from .utils import clean_text


WEATHER_TERMS = (
    "hava durumu",
    "weather",
    "forecast",
    "temperature",
    "sicaklik",
    "sıcaklık",
    "طقس",
    "الطقس",
    "الحرارة",
)

RESEARCH_TERMS = (
    "arastir",
    "araştır",
    "research",
    "makale",
    "article",
    "paper",
    "tez",
    "thesis",
    "literature",
    "kaynak",
    "source",
    "referans",
    "reference",
    "مقال",
    "بحث",
    "رسالة",
    "اطروحة",
)

QUESTION_FILLERS = (
    "nedir",
    "ne",
    "kimdir",
    "kim",
    "hakkinda",
    "hakkında",
    "bilgi ver",
    "bilgi",
    "acikla",
    "açıkla",
    "explain",
    "tell me about",
    "what is",
    "who is",
    "about",
    "من هو",
    "ما هو",
    "اشرح",
    "حول",
)

RESEARCH_FILLERS = RESEARCH_TERMS + (
    "kisa",
    "kısa",
    "detayli",
    "detaylı",
    "oner",
    "öner",
    "bul",
    "list",
    "listele",
    "özetle",
    "ozetle",
    "yap",
    "yapar misin",
    "hakkinda",
    "hakkında",
    "about",
    "uzerine",
    "üzerine",
)

FACT_TRIGGER_TERMS = (
    "nedir",
    "kimdir",
    "kim",
    "what is",
    "who is",
    "tell me about",
    "hakkında bilgi",
    "hakkinda bilgi",
    "explain",
    "about",
    "ما هو",
    "من هو",
    "اشرح",
)


@dataclass(frozen=True)
class LiveSupportResult:
    answer: str = ""
    context: str = ""
    sources: list[tuple[str, str]] = field(default_factory=list)
    prefer_direct: bool = False


def build_live_support(query: str, language: str) -> LiveSupportResult | None:
    query = clean_text(query)
    if not query:
        return None

    weather_support = _weather_support(query, language)
    if weather_support is not None:
        return weather_support

    research_support = _research_support(query, language)
    if research_support is not None:
        return research_support

    fact_support = _fact_support(query, language)
    if fact_support is not None:
        return fact_support

    return None


def _weather_support(query: str, language: str) -> LiveSupportResult | None:
    normalized = normalize_for_matching(query)
    if not any(term in normalized for term in map(normalize_for_matching, WEATHER_TERMS)):
        return None

    location = _extract_weather_location(query)
    if not location:
        return LiveSupportResult(
            answer=_text_for_language(
                language,
                "🌤️ Güncel hava durumunu paylaşabilmem için şehir adı da yazılması gerekir. Örnek: Kars hava durumu.",
                "🌤️ Please include a city name so I can share the current weather. Example: weather in Kars.",
                "🌤️ يرجى كتابة اسم المدينة أيضًا حتى أتمكن من مشاركة حالة الطقس الحالية. مثال: طقس قارص.",
            ),
            context="",
            sources=[],
            prefer_direct=True,
        )

    try:
        payload = _fetch_weather_payload(location, int(time.time() // 600))
    except requests.RequestException:
        return LiveSupportResult(
            answer=_text_for_language(
                language,
                "⚠️ Güncel hava durumu verisine şu anda ulaşılamadı.",
                "⚠️ The current weather data could not be reached at the moment.",
                "⚠️ تعذر الوصول إلى بيانات الطقس الحالية في الوقت الحالي.",
            ),
            context="",
            sources=[],
            prefer_direct=True,
        )

    current = (payload.get("current_condition") or [{}])[0]
    nearest_area = (payload.get("nearest_area") or [{}])[0]
    resolved_location = clean_text(_nested_value(nearest_area, "areaName")) or location
    if normalize_for_matching(location) not in normalize_for_matching(resolved_location):
        resolved_location = location
    description = clean_text(_nested_value(current, "weatherDesc")) or "-"
    temp_c = clean_text(current.get("temp_C", ""))
    feels_like_c = clean_text(current.get("FeelsLikeC", ""))
    humidity = clean_text(current.get("humidity", ""))
    wind_kmph = clean_text(current.get("windspeedKmph", ""))
    source_url = f"https://wttr.in/{quote(location)}?format=j1"

    answer = _text_for_language(
        language,
        f"🌤️ {resolved_location} için güncel hava {description.lower()}, sıcaklık {temp_c}°C, hissedilen {feels_like_c}°C, nem %{humidity}, rüzgar {wind_kmph} km/sa.",
        f"🌤️ The current weather in {resolved_location} is {description.lower()}, temperature {temp_c}°C, feels like {feels_like_c}°C, humidity {humidity}%, wind {wind_kmph} km/h.",
        f"🌤️ الطقس الحالي في {resolved_location} هو {description.lower()}، ودرجة الحرارة {temp_c}°م، والمحسوسة {feels_like_c}°م، والرطوبة {humidity}%، والرياح {wind_kmph} كم/س.",
    )
    context = (
        f"Current weather data for {resolved_location}: "
        f"description={description}; temp_C={temp_c}; feels_like_C={feels_like_c}; "
        f"humidity={humidity}; wind_kmph={wind_kmph}."
    )
    return LiveSupportResult(
        answer=answer,
        context=context,
        sources=[("wttr.in Weather", source_url)],
        prefer_direct=True,
    )


def _research_support(query: str, language: str) -> LiveSupportResult | None:
    normalized = normalize_for_matching(query)
    if not any(term in normalized for term in map(normalize_for_matching, RESEARCH_TERMS)):
        return None

    topic = _extract_topic(query, RESEARCH_FILLERS)
    if not topic:
        return LiveSupportResult(
            answer=_text_for_language(
                language,
                "📚 Araştırma yapılacak konu biraz daha net yazılırsa makale ve kaynak önerileri sunulabilir.",
                "📚 If the research topic is stated more clearly, I can provide article and source suggestions.",
                "📚 إذا تم توضيح موضوع البحث بشكل أدق، يمكنني تقديم مقالات ومصادر مناسبة.",
            ),
            context="",
            sources=[],
            prefer_direct=True,
        )

    works = _fetch_crossref_works(topic)
    if not works:
        google_url = f"https://www.google.com/search?q={quote_plus(topic + ' makale research article')}"
        yok_url = "https://tez.yok.gov.tr/UlusalTezMerkezi/"
        return LiveSupportResult(
            answer=_text_for_language(
                language,
                f"📚 {topic} için hızlı akademik taramada doğrudan kayıt bulunamadı. Kaynak araması için aşağıdaki bağlantılar kullanılabilir.",
                f"📚 A direct academic match could not be found quickly for {topic}. The links below can be used for source research.",
                f"📚 لم يتم العثور سريعًا على تطابق أكاديمي مباشر لموضوع {topic}. يمكن استخدام الروابط التالية للبحث عن المصادر.",
            ),
            context=f"Research request topic: {topic}. No direct Crossref results were found.",
            sources=[("Google Research Search", google_url), ("YÖK Ulusal Tez Merkezi", yok_url)],
            prefer_direct=True,
        )

    rows = []
    sources = []
    context_rows = []
    for item in works[:3]:
        title = clean_text(item.get("title", ""))
        venue = clean_text(item.get("venue", ""))
        year = clean_text(str(item.get("year", "")))
        url = clean_text(item.get("url", ""))
        if not title or not url:
            continue
        row = f"• {title}"
        if venue and year:
            row += f" ({venue}, {year})"
        elif year:
            row += f" ({year})"
        rows.append(row)
        sources.append((title, url))
        context_rows.append(f"title={title}; venue={venue}; year={year}; url={url}")

    thesis_url = "https://tez.yok.gov.tr/UlusalTezMerkezi/"
    google_url = f"https://www.google.com/search?q={quote_plus(topic + ' academic sources')}"
    if "tez" in normalized or "thesis" in normalized or "اطروحة" in normalized:
        sources.append(("YÖK Ulusal Tez Merkezi", thesis_url))
    sources.append(("Google Academic Search", google_url))

    answer = _text_for_language(
        language,
        f"📚 {topic} için hızlı akademik taramada öne çıkan çalışmalar:\n" + "\n".join(rows),
        f"📚 Highlighted academic works found in a quick scan for {topic}:\n" + "\n".join(rows),
        f"📚 أبرز الأعمال الأكاديمية التي ظهرت في بحث سريع حول {topic}:\n" + "\n".join(rows),
    )
    context = "Academic research results:\n" + "\n".join(context_rows)
    return LiveSupportResult(answer=answer, context=context, sources=sources[:5], prefer_direct=True)


def _fact_support(query: str, language: str) -> LiveSupportResult | None:
    normalized = normalize_for_matching(query)
    if is_coding_query(query) and any(
        term in normalized
        for term in ("fix", "error", "bug", "code", "snippet", "traceback", "print(", "def ", "class ", "function")
    ):
        return None
    if any(term in normalized for term in map(normalize_for_matching, WEATHER_TERMS + RESEARCH_TERMS)):
        return None
    if not any(term in normalized for term in map(normalize_for_matching, FACT_TRIGGER_TERMS)):
        return None

    topic = _extract_topic(query, QUESTION_FILLERS)
    if not topic or len(topic) < 3:
        return None

    summary = _fetch_wikipedia_summary(topic, language)
    if not summary:
        return None

    answer = _text_for_language(
        language,
        f"📌 {summary['extract']}",
        f"📌 {summary['extract']}",
        f"📌 {summary['extract']}",
    )
    context = f"Wikipedia summary for {summary['title']}: {summary['extract']}"
    return LiveSupportResult(
        answer=answer,
        context=context,
        sources=[(summary["title"], summary["url"])],
        prefer_direct=True,
    )


def _extract_weather_location(query: str) -> str:
    patterns = (
        r"(?i)^(.+?)\s+hava durumu$",
        r"(?i)^hava durumu\s+(.+)$",
        r"(?i)^(.+?)\s+weather$",
        r"(?i)^weather in\s+(.+)$",
        r"(?i)^weather\s+(.+)$",
        r"(?i)^(.+?)\s+forecast$",
        r"(?i)^طقس\s+(.+)$",
        r"(?i)^(.+?)\s+الطقس$",
    )
    for pattern in patterns:
        match = re.match(pattern, clean_text(query))
        if match:
            return clean_text(match.group(1))
    return ""


def _extract_topic(query: str, fillers: tuple[str, ...]) -> str:
    working = clean_text(query)
    for filler in sorted(fillers, key=len, reverse=True):
        pattern = rf"(?<!\w){re.escape(filler)}(?!\w)"
        working = re.sub(pattern, " ", working, flags=re.IGNORECASE)

    working = re.sub(r"\s+", " ", working).strip(" -:,.?")
    if not working:
        return ""
    return clean_text(working)


@lru_cache(maxsize=32)
def _fetch_weather_payload(location: str, cache_bucket: int) -> dict:
    del cache_bucket
    response = requests.get(
        f"https://wttr.in/{quote(location)}",
        params={"format": "j1"},
        timeout=4.5,
        headers={"User-Agent": "KAUCAN/1.0 (+https://www.kafkas.edu.tr)"},
    )
    response.raise_for_status()
    return response.json()


@lru_cache(maxsize=64)
def _fetch_crossref_works(topic: str) -> list[dict]:
    response = requests.get(
        "https://api.crossref.org/works",
        params={
            "rows": 4,
            "query.bibliographic": topic,
            "select": "DOI,title,URL,container-title,published-print,published-online,issued",
        },
        timeout=5.5,
        headers={"User-Agent": "KAUCAN/1.0 (+https://www.kafkas.edu.tr)"},
    )
    response.raise_for_status()
    items = response.json().get("message", {}).get("items", [])
    works: list[dict] = []
    for item in items:
        title = clean_text((item.get("title") or [""])[0])
        url = clean_text(item.get("URL", ""))
        venue = clean_text((item.get("container-title") or [""])[0])
        year = _crossref_year(item)
        if not title or not url:
            continue
        works.append({"title": title, "url": url, "venue": venue, "year": year})
    return works


@lru_cache(maxsize=64)
def _fetch_wikipedia_summary(topic: str, language: str) -> dict[str, str] | None:
    wiki_domain = {
        "tr": "tr.wikipedia.org",
        "ar": "ar.wikipedia.org",
        "en": "en.wikipedia.org",
    }.get(language, "en.wikipedia.org")
    search_response = requests.get(
        f"https://{wiki_domain}/w/api.php",
        params={
            "action": "opensearch",
            "search": topic,
            "limit": 1,
            "namespace": 0,
            "format": "json",
        },
        timeout=4.5,
        headers={"User-Agent": "KAUCAN/1.0 (+https://www.kafkas.edu.tr)"},
    )
    search_response.raise_for_status()
    payload = search_response.json()
    titles = payload[1] if len(payload) > 1 else []
    urls = payload[3] if len(payload) > 3 else []
    if not titles or not urls:
        return None

    title = clean_text(titles[0])
    url = clean_text(urls[0])
    summary_response = requests.get(
        f"https://{wiki_domain}/api/rest_v1/page/summary/{quote(title)}",
        timeout=4.5,
        headers={"User-Agent": "KAUCAN/1.0 (+https://www.kafkas.edu.tr)"},
    )
    summary_response.raise_for_status()
    summary_payload = summary_response.json()
    extract = clean_text(summary_payload.get("extract", ""))
    if not extract:
        return None
    return {"title": title, "url": url, "extract": extract}


def _crossref_year(item: dict) -> str:
    for key in ("published-print", "published-online", "issued"):
        parts = item.get(key, {}).get("date-parts", [])
        if parts and parts[0]:
            return str(parts[0][0])
    return ""


def _nested_value(payload: dict, key: str) -> str:
    rows = payload.get(key) or []
    if not rows or not isinstance(rows, list):
        return ""
    first = rows[0]
    if not isinstance(first, dict):
        return ""
    return clean_text(first.get("value", ""))


def _text_for_language(language: str, tr_text: str, en_text: str, ar_text: str | None = None) -> str:
    if language == "ar":
        return ar_text or en_text
    return en_text if language == "en" else tr_text
