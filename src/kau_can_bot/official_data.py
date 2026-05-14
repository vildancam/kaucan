from __future__ import annotations

import json
import re
import time
from difflib import SequenceMatcher
from urllib.parse import quote_plus, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from .config import DATA_DIR, Settings
from .extractor import extract_pdf
from .query_normalizer import normalize_for_matching
from .utils import clean_text, normalize_url


FACULTY_PERSONNEL_URL = "https://www.kafkas.edu.tr/iibf/tr/akademikpersonel"
FACULTY_ANNOUNCEMENTS_URL = "https://www.kafkas.edu.tr/iibf/tr/tumduyurular2"
FACULTY_NEWS_URL = "https://www.kafkas.edu.tr/iibf/tr/tumHaberler"
FACULTY_EVENTS_URL = "https://www.kafkas.edu.tr/iibf/tr/tumEtkinlikler2"
FACULTY_ROOT_URL = "https://www.kafkas.edu.tr/iibf"
SENATE_URL = "https://www.kafkas.edu.tr/rektorluk/TR/sayfaYeni651"
UNIS_BASE_URL = "https://unis.kafkas.edu.tr/"
UNIS_IIBF_MANAGEMENT_URL = "https://unis.kafkas.edu.tr/birim/yonetim/iktisadi-ve-idari-bilimler-fakultesi/id=2_CZa_54"
YBS_MANAGEMENT_URL = "https://www.kafkas.edu.tr/iibfybs/tr/sayfaYeni17874"
YBS_JOURNAL_URL = "https://www.kafkas.edu.tr/iibfybs/tr/sayfaYeni17891"
YBS_ADVISING_PDF_URL = "https://www.kafkas.edu.tr/dosyalar/iibfybs/a794b8fe-ccb5-45f3-8f61-b3823c2cef48.pdf"
YBS_CLUBS_URL = "https://www.kafkas.edu.tr/iibfybs/tr/sayfaYeni17976"
IIBF_MANAGEMENT_PAGE_URL = "https://www.kafkas.edu.tr/iibf/tr/sayfaYeni17980"
IIBF_CONTACT_PAGE_URL = "https://www.kafkas.edu.tr/iibf/tr/sayfaYeni18034"
FACULTY_PLACEHOLDER_IMAGE = "https://www.kafkas.edu.tr/imgs/haber.png"
FACULTY_DEPARTMENT_ROOT_OVERRIDES = {
    "iktisat": "https://www.kafkas.edu.tr/iibfikt#",
    "isletme": "https://www.kafkas.edu.tr/iibfisletme",
    "sbky": "https://www.kafkas.edu.tr/iibfsbky",
    "sbui": "https://www.kafkas.edu.tr/iibfsbui/tr/sayfaYeni16932",
    "utl": "https://www.kafkas.edu.tr/iibfutl",
    "sosyal-hizmet": "https://www.kafkas.edu.tr/iibfsh",
    "ybs": "https://www.kafkas.edu.tr/iibfybs",
    "ety": "https://www.kafkas.edu.tr/iibfety",
}
FACULTY_MANUAL_NAVIGATION = (
    {"title": "Dekanımızın Mesajı", "url": "https://www.kafkas.edu.tr/iibf/tr/sayfaYeni18044"},
    {"title": "Tanıtım", "url": "https://www.kafkas.edu.tr/iibf/tr/sayfaYeni17978"},
    {"title": "Misyon & Vizyon", "url": "https://www.kafkas.edu.tr/iibf/tr/sayfaYeni17979"},
    {"title": "Dekanlarımız", "url": "https://www.kafkas.edu.tr/iibf/tr/sayfaYeni18031"},
    {"title": "Yönetim", "url": "https://www.kafkas.edu.tr/iibf/tr/sayfaYeni17980"},
    {"title": "Organizasyon Şeması", "url": "https://www.kafkas.edu.tr/iibf/tr/sayfaYeni17981"},
    {"title": "Ders Programları", "url": "https://www.kafkas.edu.tr/iibf/tr/sayfaYeni17986"},
    {"title": "Sıkça Sorulan Sorular (SSS)", "url": "https://www.kafkas.edu.tr/iibf/tr/sayfaYeni17990"},
    {"title": "Akademik Personel", "url": "https://www.kafkas.edu.tr/iibf/tr/akademikpersonel"},
    {"title": "İdari Personel", "url": "https://www.kafkas.edu.tr/iibf/tr/sayfaYeni17993"},
    {"title": "Görev Tanımları", "url": "https://www.kafkas.edu.tr/iibf/tr/sayfaYeni17994"},
    {"title": "Fakülte Kurulu", "url": "https://www.kafkas.edu.tr/iibf/tr/sayfaYeni17996"},
    {"title": "Fakülte Yönetim Kurulu", "url": "https://www.kafkas.edu.tr/iibf/tr/sayfaYeni17997"},
    {"title": "Fakülte Danışma Kurulu", "url": "https://www.kafkas.edu.tr/iibf/tr/sayfaYeni18045"},
    {"title": "Akademik Gelişim Komisyonu", "url": "https://www.kafkas.edu.tr/iibf/tr/sayfaYeni18047"},
    {"title": "Sınav ve Ders Programı Komisyonu", "url": "https://www.kafkas.edu.tr/iibf/tr/sayfaYeni18048"},
    {"title": "Kurumsal İletişim Komisyonu", "url": "https://www.kafkas.edu.tr/iibf/tr/sayfaYeni18049"},
    {"title": "Dijital Dönüşüm Komisyonu", "url": "https://www.kafkas.edu.tr/iibf/tr/sayfaYeni18050"},
    {"title": "Hukuk İşleri Komisyonu", "url": "https://www.kafkas.edu.tr/iibf/tr/sayfaYeni18051"},
    {"title": "Kültür-Sanat Komisyonu", "url": "https://www.kafkas.edu.tr/iibf/tr/sayfaYeni18052"},
    {"title": "Spor ve Sağlık Komisyonu", "url": "https://www.kafkas.edu.tr/iibf/tr/sayfaYeni18053"},
    {"title": "Mezun Takip Komisyonu", "url": "https://www.kafkas.edu.tr/iibf/tr/sayfaYeni18054"},
    {"title": "Fakülte Yönetim Kurulu Kararları", "url": "https://www.kafkas.edu.tr/iibf/tr/sayfaYeni18035"},
    {"title": "Fakülte Kurulu Kararları", "url": "https://www.kafkas.edu.tr/iibf/tr/sayfaYeni18036"},
    {"title": "KAÜİİBF Dergisi", "url": "https://www.kafkas.edu.tr/iibf/tr/sayfaYeni18063"},
    {"title": "Fakülte Bülteni", "url": "https://www.kafkas.edu.tr/iibf/tr/sayfaYeni18180"},
    {"title": "Birim Faaliyet Raporu", "url": "https://www.kafkas.edu.tr/iibf/tr/sayfaYeni18001"},
    {"title": "İş Akış Süreçleri", "url": "https://www.kafkas.edu.tr/iibf/tr/sayfaYeni18002"},
    {"title": "Öğrenci Disiplin Soruşturma Formları", "url": "https://www.kafkas.edu.tr/iibf/tr/sayfaYeni18064"},
    {"title": "Formlar", "url": "https://www.kafkas.edu.tr/iibf/tr/sayfaYeni17988"},
    {"title": "Dekana Sor", "url": "https://www.kafkas.edu.tr/iibf/tr/sayfaYeni18817"},
    {"title": "İletişim", "url": "https://www.kafkas.edu.tr/iibf/tr/sayfaYeni18034"},
    {"title": "İktisat", "url": "https://www.kafkas.edu.tr/iibfikt#"},
    {"title": "İşletme", "url": "https://www.kafkas.edu.tr/iibfisletme"},
    {"title": "Siyaset Bilimi ve Kamu Yönetimi", "url": "https://www.kafkas.edu.tr/iibfsbky"},
    {"title": "Siyaset Bilimi ve Uluslararası İlişkiler", "url": "https://www.kafkas.edu.tr/iibfsbui/tr/sayfaYeni16932"},
    {"title": "Uluslararası Ticaret ve Lojistik", "url": "https://www.kafkas.edu.tr/iibfutl"},
    {"title": "Sosyal Hizmet", "url": "https://www.kafkas.edu.tr/iibfsh"},
    {"title": "Yönetim Bilişim Sistemleri", "url": "https://www.kafkas.edu.tr/iibfybs"},
    {"title": "YBS Bölüm Yönetimi", "url": YBS_MANAGEMENT_URL},
    {"title": "YBS Bölüm Dergisi", "url": YBS_JOURNAL_URL},
    {"title": "YBS Akademik Danışmanlıklar", "url": YBS_ADVISING_PDF_URL},
    {"title": "YBS Öğrenci Kulüpleri", "url": YBS_CLUBS_URL},
    {"title": "Elektronik Ticaret ve Yönetimi", "url": "https://www.kafkas.edu.tr/iibfety"},
)

YBS_SPECIAL_LINKS = {
    "management": YBS_MANAGEMENT_URL,
    "journal": YBS_JOURNAL_URL,
    "advising": YBS_ADVISING_PDF_URL,
    "clubs": YBS_CLUBS_URL,
}

CACHE_PATH = DATA_DIR / "official_snapshot.json"
MANUAL_PERSONNEL_PATH = DATA_DIR / "manual_personnel.json"
FILE_TTL_SECONDS = 60 * 60 * 6
MEMORY_TTL_SECONDS = 60 * 10
UNIS_CACHE_TTL_SECONDS = 60 * 30

RATE_LIMIT_MARKERS = (
    "TOO MANY REQUEST",
    "Please wait for 1 minute",
    "www.kafkas.edu.tr/hata.htm",
)

_memory_snapshot: dict | None = None
_memory_loaded_at: float = 0.0
_unis_search_cache: dict[str, tuple[float, list[dict]]] = {}
_unis_profile_cache: dict[str, tuple[float, dict]] = {}
_unis_management_cache: tuple[float, list[dict]] | None = None
_manual_personnel_cache: list[dict] | None = None

ACADEMIC_PREFIXES = (
    "PROF. DR.",
    "PROFESÖR",
    "DOÇ. DR.",
    "DOÇENT",
    "DR. ÖĞR. ÜYESİ",
    "DOKTOR ÖĞRETİM ÜYESİ",
    "DR.",
    "DOKTOR",
    "ÖĞR. GÖR.",
    "ÖĞRETİM GÖREVLİSİ",
    "ARŞ. GÖR.",
    "ARAŞTIRMA GÖREVLİSİ",
)

KNOWN_DEPARTMENTS = {
    "iktisat": {
        "name_tr": "İktisat",
        "name_en": "Economics",
        "aliases": ("iktisat", "economics"),
        "root_slug": "iibfikt",
    },
    "isletme": {
        "name_tr": "İşletme",
        "name_en": "Business Administration",
        "aliases": ("işletme", "isletme", "business"),
        "root_slug": "iibfisletme",
    },
    "sbky": {
        "name_tr": "Siyaset Bilimi ve Kamu Yönetimi",
        "name_en": "Political Science and Public Administration",
        "aliases": ("sbky", "siyaset bilimi ve kamu yönetimi", "political science and public administration"),
        "root_slug": "iibfsbky",
    },
    "sbui": {
        "name_tr": "Siyaset Bilimi ve Uluslararası İlişkiler",
        "name_en": "Political Science and International Relations",
        "aliases": ("sbui", "siyaset bilimi ve uluslararası ilişkiler", "political science and international relations"),
        "root_slug": "iibfsbui",
    },
    "utl": {
        "name_tr": "Uluslararası Ticaret ve Lojistik",
        "name_en": "International Trade and Logistics",
        "aliases": ("utl", "uluslararası ticaret ve lojistik", "international trade and logistics"),
        "root_slug": "iibfutl",
    },
    "sosyal-hizmet": {
        "name_tr": "Sosyal Hizmet",
        "name_en": "Social Work",
        "aliases": ("sosyal hizmet", "social work"),
        "root_slug": "iibfsh",
    },
    "ybs": {
        "name_tr": "Yönetim Bilişim Sistemleri",
        "name_en": "Management Information Systems",
        "aliases": ("ybs", "yönetim bilişim sistemleri", "yonetim bilisim sistemleri", "management information systems"),
        "root_slug": "iibfybs",
    },
    "ety": {
        "name_tr": "Elektronik Ticaret ve Yönetimi",
        "name_en": "Electronic Commerce and Management",
        "aliases": ("elektronik ticaret ve yönetimi", "electronic commerce and management"),
        "root_slug": "iibfety",
    },
}

FACULTY_QUERY_STOPWORDS = {
    "iibf",
    "iktisadi",
    "idari",
    "bilimler",
    "fakultesi",
    "fakulte",
    "faculty",
    "feas",
    "about",
    "hakkinda",
    "hakkında",
    "sayfasi",
    "sayfasi",
    "sayfa",
    "page",
    "nedir",
    "kim",
    "kimdir",
    "what",
    "who",
    "show",
    "goster",
    "göster",
    "bilgi",
    "ver",
}

PERSON_QUERY_STOPWORDS = {
    "akademik",
    "akademisyen",
    "akademisyenler",
    "bana",
    "bilgi",
    "bilgileri",
    "bolum",
    "bolumde",
    "bolumu",
    "bölüm",
    "bölümde",
    "bölümü",
    "calisma",
    "calismalari",
    "calismasi",
    "contact",
    "details",
    "dr",
    "doc",
    "doç",
    "email",
    "eposta",
    "e-posta",
    "fakulte",
    "fakultede",
    "fakultesi",
    "fakülte",
    "fakültede",
    "fakültesi",
    "gorev",
    "gorevli",
    "gorevlisi",
    "görev",
    "görevli",
    "görevlisi",
    "hangi",
    "hoca",
    "hocanin",
    "hocanın",
    "hocalar",
    "idari",
    "iletisim",
    "iletişim",
    "kim",
    "kimdir",
    "mail",
    "maili",
    "nedir",
    "ne",
    "numarasi",
    "numarası",
    "ogretim",
    "ogr",
    "personel",
    "prof",
    "telefon",
    "telefonu",
    "unis",
    "unvani",
    "unvanı",
    "works",
    "yayin",
    "yayinlari",
    "yayini",
    "yayın",
    "yayınları",
    "yayını",
}


def get_official_snapshot(force_refresh: bool = False) -> dict:
    global _memory_loaded_at, _memory_snapshot

    now = time.time()
    if not force_refresh and _memory_snapshot and now - _memory_loaded_at < MEMORY_TTL_SECONDS:
        return _memory_snapshot

    if not force_refresh and CACHE_PATH.exists():
        age = now - CACHE_PATH.stat().st_mtime
        if age < FILE_TTL_SECONDS:
            try:
                cached_snapshot = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
                _memory_snapshot = _hydrate_snapshot(cached_snapshot)
                _memory_loaded_at = now
                return _memory_snapshot
            except json.JSONDecodeError:
                pass

    snapshot = _hydrate_snapshot(_build_official_snapshot())
    _persist_snapshot(snapshot)
    return snapshot


def find_unis_person_profile(query: str, snapshot: dict | None = None) -> dict | None:
    candidate = _extract_person_candidate(query, snapshot or {})
    if not candidate:
        return None

    manual_person = _find_manual_person(candidate, query)
    if manual_person:
        return manual_person

    snapshot_person = _find_snapshot_person(candidate, snapshot or {})
    unis_query = candidate
    if snapshot_person and snapshot_person.get("name"):
        unis_query = snapshot_person["name"]

    search_results = _search_unis_people(unis_query)
    best_result = _select_best_unis_person_result(unis_query, search_results)

    if best_result and best_result.get("detail_url"):
        profile = _fetch_unis_person_profile(best_result["detail_url"])
        if profile:
            merged = _merge_person_records(best_result, profile)
            if snapshot_person:
                merged = _merge_person_records(snapshot_person, merged)
            return merged

    if snapshot_person and _is_unis_person_url(snapshot_person.get("detail_url", "")):
        profile = _fetch_unis_person_profile(snapshot_person["detail_url"])
        if profile:
            return _merge_person_records(snapshot_person, profile)

    management_person = _find_unis_management_person(candidate, snapshot or {})
    if management_person:
        return management_person

    if snapshot_person:
        return snapshot_person
    return None


def has_manual_person_match(query: str) -> bool:
    query_key = normalize_for_matching(query)
    if not query_key:
        return False

    for person in _load_manual_personnel():
        name = clean_text(person.get("name", ""))
        name_key = normalize_for_matching(name)
        if name_key and name_key in query_key:
            return True
        for keyword in person.get("keywords", []) or []:
            keyword_key = normalize_for_matching(keyword)
            if keyword_key and keyword_key in query_key:
                return True
    return False


def department_keys_for_query(query: str) -> list[str]:
    normalized = normalize_for_matching(query)
    matches: list[str] = []
    for key, item in KNOWN_DEPARTMENTS.items():
        if any(normalize_for_matching(alias) in normalized for alias in item["aliases"]):
            matches.append(key)
    return matches


def ensure_faculty_content(snapshot: dict, content_types: tuple[str, ...] = ("announcements", "news", "events")) -> dict:
    faculty_content = snapshot.setdefault("faculty_content", {})
    changed = False
    factories = {
        "announcements": lambda: _parse_announcements_page(FACULTY_ANNOUNCEMENTS_URL, limit=8, enrich_details=True),
        "news": lambda: _parse_news_page(FACULTY_NEWS_URL, limit=8),
        "events": lambda: _parse_events_page(FACULTY_EVENTS_URL, limit=8),
    }

    for content_type in content_types:
        if faculty_content.get(content_type):
            continue
        factory = factories.get(content_type)
        if factory is None:
            continue
        try:
            items = factory()
        except requests.RequestException:
            items = []
        if items:
            faculty_content[content_type] = items
            changed = True

    if changed:
        snapshot["faculty_content"] = faculty_content
        _persist_snapshot(snapshot)
    return snapshot


def ensure_department_content(
    snapshot: dict,
    department_key: str,
    content_types: tuple[str, ...] = ("announcements", "news", "events"),
) -> dict:
    department = snapshot.get("departments", {}).get(department_key)
    if not department:
        return snapshot

    changed = _hydrate_department(snapshot, department_key, department)
    links = department.get("important_links", {})
    factories = {
        "announcements": _parse_announcements_page,
        "news": _parse_news_page,
        "events": _parse_events_page,
    }

    for content_type in content_types:
        if department.get(content_type):
            continue
        content_url = links.get(content_type)
        factory = factories.get(content_type)
        if not content_url or factory is None:
            continue
        try:
            items = factory(content_url, limit=6)
        except requests.RequestException:
            items = []
        if items:
            department[content_type] = items
            changed = True

    if changed:
        snapshot["departments"][department_key] = department
        _persist_snapshot(snapshot)
    return snapshot


def ensure_department_special_pages(
    snapshot: dict,
    department_key: str,
    page_keys: tuple[str, ...],
) -> dict:
    department = snapshot.get("departments", {}).get(department_key)
    if not department:
        return snapshot

    changed = _hydrate_department(snapshot, department_key, department)
    links = department.get("important_links", {})
    special_pages = department.setdefault("special_pages", {})
    requested_keys = tuple(dict.fromkeys(page_keys))

    for page_key in requested_keys:
        if page_key in special_pages:
            continue
        source_url = clean_text(links.get(page_key, ""))
        if not source_url:
            continue
        try:
            if page_key == "management":
                parsed = _parse_ybs_management_page(_fetch_html(source_url), source_url)
            elif page_key == "journal":
                parsed = _parse_ybs_journal_page(_fetch_html(source_url), source_url)
            elif page_key == "clubs":
                parsed = _parse_ybs_clubs_page(_fetch_html(source_url), source_url)
            elif page_key == "advising":
                parsed = _parse_ybs_advising_pdf(
                    _fetch_binary(source_url),
                    source_url,
                    department.get("personnel", []),
                )
            else:
                parsed = {}
        except requests.RequestException:
            parsed = {}

        if parsed:
            special_pages[page_key] = parsed
            changed = True

    if changed:
        department["special_pages"] = special_pages
        snapshot["departments"][department_key] = department
        _persist_snapshot(snapshot)
    return snapshot


def find_faculty_navigation_matches(snapshot: dict, query: str, limit: int = 3) -> list[dict]:
    navigation = snapshot.get("faculty_navigation", [])
    if not navigation:
        return []

    query_key = normalize_for_matching(query)
    query_tokens = [
        token
        for token in re.split(r"\s+", query_key)
        if token and token not in FACULTY_QUERY_STOPWORDS and len(token) > 1
    ]
    matches: list[tuple[float, dict]] = []

    for entry in navigation:
        score = _navigation_match_score(query_key, query_tokens, entry)
        if score <= 0:
            continue
        matches.append((score, entry))

    matches.sort(key=lambda item: item[0], reverse=True)
    return [entry for _, entry in matches[:limit]]


def ensure_faculty_page(snapshot: dict, url: str) -> dict:
    if not url:
        return snapshot

    pages = snapshot.setdefault("faculty_pages", {})
    existing = pages.get(url) or {}
    if existing.get("summary") and existing.get("body_excerpt"):
        return snapshot

    try:
        soup = BeautifulSoup(_fetch_html(url), "html.parser")
    except requests.RequestException:
        return snapshot

    title = _navigation_title_for_url(snapshot, url) or _best_page_title(soup) or clean_text(urlsplit(url).path.rsplit("/", 1)[-1])
    body = _extract_faculty_page_body(soup)
    page_data = {
        "title": title,
        "url": url,
        "summary": _extract_summary_from_body(body, title),
        "body_excerpt": _truncate_text(body, 1400),
    }
    pages[url] = page_data
    snapshot["faculty_pages"] = pages
    _persist_snapshot(snapshot)
    return snapshot


def _search_unis_people(query: str, limit: int = 8) -> list[dict]:
    normalized_query = normalize_for_matching(query)
    if not normalized_query:
        return []

    now = time.time()
    cached = _unis_search_cache.get(normalized_query)
    if cached and now - cached[0] < UNIS_CACHE_TTL_SECONDS:
        return cached[1]

    page_url = _unis_search_page_url(query)
    page_html = _fetch_html(page_url)
    original_url = _extract_original_url(page_html)
    if not original_url:
        return []
    original_url = _append_query_param(original_url, "grid", "1")
    original_url = _append_query_param(original_url, "table_id", "SolrRecord")

    payload = _unis_grid_payload(page_html, search_text=query, page_size=limit)
    response = _unis_post(
        original_url,
        payload,
        referer=page_url,
    )
    data = response.json()
    results = [_parse_unis_search_result_row(row, page_url) for row in data.get("aaData", [])]
    results = [item for item in results if item]
    _unis_search_cache[normalized_query] = (now, results)
    return results


def _fetch_unis_person_profile(url: str) -> dict | None:
    profile_url = normalize_url(url, UNIS_BASE_URL) or _absolute_url(UNIS_BASE_URL, url)
    if not profile_url:
        return None

    now = time.time()
    cached = _unis_profile_cache.get(profile_url)
    if cached and now - cached[0] < UNIS_CACHE_TTL_SECONDS:
        return cached[1]

    profile_html = _fetch_html(profile_url)
    profile = _parse_unis_person_profile_html(profile_html, profile_url)
    if profile:
        _unis_profile_cache[profile_url] = (now, profile)
    return profile


def _find_unis_management_person(candidate: str, snapshot: dict) -> dict | None:
    people = snapshot.get("faculty_management") or _get_unis_management_people()
    if not people:
        return None
    return _best_matching_person(candidate, people, minimum_score=0.82)


def _get_unis_management_people() -> list[dict]:
    global _unis_management_cache

    now = time.time()
    if _unis_management_cache and now - _unis_management_cache[0] < UNIS_CACHE_TTL_SECONDS:
        return _unis_management_cache[1]

    html = _fetch_html(UNIS_IIBF_MANAGEMENT_URL)
    people = _parse_unis_management_cards(BeautifulSoup(html, "html.parser"), UNIS_IIBF_MANAGEMENT_URL)
    _unis_management_cache = (now, people)
    return people


def _extract_person_candidate(query: str, snapshot: dict) -> str:
    query_text = clean_text(query)
    query_key = normalize_for_matching(query_text)
    if not query_key:
        return ""

    known_people = _all_known_people(snapshot)
    direct = _direct_name_match(query_key, known_people)
    if direct:
        return direct

    tokens = [
        token
        for token in re.split(r"\s+", query_key)
        if token and token not in PERSON_QUERY_STOPWORDS and len(token) > 1 and not token.isdigit()
    ]
    if len(tokens) < 2:
        return ""
    return clean_text(" ".join(tokens[:4]))


def _all_known_people(snapshot: dict) -> list[dict]:
    people: list[dict] = []
    people.extend(_load_manual_personnel())
    for key in ("senate_people", "faculty_personnel", "faculty_management"):
        for person in snapshot.get(key, []) or []:
            if clean_text(person.get("name", "")):
                people.append(person)
    for department in (snapshot.get("departments") or {}).values():
        for person in department.get("personnel", []) or []:
            if clean_text(person.get("name", "")):
                people.append(person)
    return people


def _direct_name_match(query_key: str, people: list[dict]) -> str:
    for person in people:
        name = clean_text(person.get("name", ""))
        if not name:
            continue
        name_key = normalize_for_matching(name)
        if name_key and name_key in query_key:
            return name
    return ""


def _find_snapshot_person(candidate: str, snapshot: dict) -> dict | None:
    return _best_matching_person(candidate, _all_known_people(snapshot), minimum_score=0.76)


def _find_manual_person(candidate: str, query: str) -> dict | None:
    people = _load_manual_personnel()
    if not people:
        return None

    candidate_key = normalize_for_matching(candidate)
    query_key = normalize_for_matching(query)
    scored: list[tuple[float, dict]] = []
    for person in people:
        name = clean_text(person.get("name", ""))
        name_key = normalize_for_matching(name)
        if not name_key:
            continue

        score = _person_name_score(candidate_key, name_key)
        if candidate_key and candidate_key in name_key:
            score += 0.2
        if name_key and name_key in query_key:
            score += 0.15

        for keyword in person.get("keywords", []) or []:
            keyword_key = normalize_for_matching(keyword)
            if keyword_key and keyword_key in query_key:
                score += 0.08
                break

        if score >= 0.84:
            scored.append((score, person))

    if not scored:
        return None
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1]


def _load_manual_personnel() -> list[dict]:
    global _manual_personnel_cache

    if _manual_personnel_cache is not None:
        return _manual_personnel_cache

    try:
        raw_items = json.loads(MANUAL_PERSONNEL_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        _manual_personnel_cache = []
        return _manual_personnel_cache

    normalized_people: list[dict] = []
    for item in raw_items if isinstance(raw_items, list) else []:
        person = _normalize_manual_person_record(item)
        if person:
            normalized_people.append(person)

    _manual_personnel_cache = normalized_people
    return _manual_personnel_cache


def _normalize_manual_person_record(item: dict) -> dict | None:
    if not isinstance(item, dict):
        return None

    full_name = clean_text(item.get("ad_soyad", ""))
    academic_title = clean_text(item.get("unvan", ""))
    unit = clean_text(item.get("birim", ""))
    department = clean_text(item.get("bolum", ""))
    division = clean_text(item.get("anabilim_dali", ""))
    source_url = clean_text(item.get("source_url", ""))
    detail_url = clean_text(item.get("detail_url", "")) or source_url

    if not full_name:
        return None

    name = full_name
    if academic_title:
        title_key = normalize_for_matching(academic_title)
        full_name_key = normalize_for_matching(full_name)
        if full_name_key.startswith(title_key):
            name = clean_text(full_name[len(academic_title) :])

    normalized_keywords = [
        clean_text(keyword)
        for keyword in item.get("anahtar_kelimeler", []) or []
        if clean_text(keyword)
    ]
    if full_name not in normalized_keywords:
        normalized_keywords.append(full_name)
    if name and name not in normalized_keywords:
        normalized_keywords.append(name)

    return {
        "name": name or full_name,
        "academic_title": academic_title,
        "unit": unit,
        "department": department,
        "division": division,
        "source_url": source_url,
        "detail_url": detail_url,
        "keywords": normalized_keywords,
        "manual_verified": True,
    }


def _best_matching_person(candidate: str, people: list[dict], minimum_score: float) -> dict | None:
    candidate_key = normalize_for_matching(candidate)
    if not candidate_key:
        return None

    scored: list[tuple[float, dict]] = []
    for person in people:
        name = clean_text(person.get("name", ""))
        if not name:
            continue
        score = _person_name_score(candidate_key, normalize_for_matching(name))
        if score >= minimum_score:
            scored.append((score, person))

    if not scored:
        return None
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1]


def _select_best_unis_person_result(candidate: str, results: list[dict]) -> dict | None:
    candidate_key = normalize_for_matching(candidate)
    if not candidate_key:
        return None

    scored: list[tuple[float, dict]] = []
    for item in results:
        if normalize_for_matching(item.get("result_type", "")) != "akademisyen":
            continue
        name_key = normalize_for_matching(item.get("name", ""))
        score = _person_name_score(candidate_key, name_key)
        if candidate_key and candidate_key in name_key:
            score += 0.15
        if score >= 0.72:
            scored.append((score, item))

    if not scored:
        return None

    scored.sort(key=lambda item: item[0], reverse=True)
    top_score = scored[0][0]
    close_matches = [item for item in scored if top_score - item[0] <= 0.03]
    if len(close_matches) > 1 and top_score < 0.9:
        return None
    return scored[0][1]


def _person_name_score(candidate_key: str, name_key: str) -> float:
    if not candidate_key or not name_key:
        return 0.0
    if candidate_key == name_key:
        return 1.0

    candidate_tokens = [token for token in candidate_key.split() if token]
    name_tokens = [token for token in name_key.split() if token]
    overlap = sum(1 for token in candidate_tokens if token in name_tokens)
    overlap_ratio = overlap / max(1, len(candidate_tokens))
    seq = SequenceMatcher(None, candidate_key, name_key).ratio()
    return (seq * 0.65) + (overlap_ratio * 0.35)


def _parse_unis_search_result_row(row: list, source_url: str) -> dict | None:
    if len(row) < 5:
        return None

    title = clean_text(str(row[1]))
    result_type = clean_text(str(row[2]))
    detail_url = _absolute_url(UNIS_BASE_URL, str(row[3]))
    card_html = str(row[4])
    card_soup = BeautifulSoup(card_html, "html.parser")

    academic_title, name = _split_academic_title(title)
    if not name:
        name = title

    faculty = clean_text(_text_or_empty(card_soup.select_one(".fw-semibold")))
    unit_line = clean_text(_text_or_empty(card_soup.select_one("small.text-gray")))
    department, unit = _split_department_unit(unit_line)
    roles = [clean_text(node.get_text(" ", strip=True)) for node in card_soup.select(".badge")]
    image = card_soup.select_one("img")

    works_links: dict[str, str] = {}
    for anchor in card_soup.select("div.calismalar a[href]"):
        label_text = clean_text(anchor.get_text(" ", strip=True))
        if not label_text:
            continue
        _, label = _split_stat_label(label_text)
        works_links[label] = _absolute_url(UNIS_BASE_URL, anchor.get("href"))

    return {
        "name": name,
        "academic_title": academic_title,
        "faculty": faculty,
        "department": department,
        "unit": unit,
        "roles": [role for role in roles if role],
        "detail_url": detail_url,
        "works_url": works_links.get("Yayın") or works_links.get("Yayin") or detail_url,
        "image_url": _absolute_url(UNIS_BASE_URL, image.get("data-src") or image.get("src")) if image else "",
        "result_type": result_type,
        "source_url": source_url,
        "work_links": works_links,
    }


def _parse_unis_person_profile_html(html: str, source_url: str) -> dict | None:
    soup = BeautifulSoup(html, "html.parser")
    name = clean_text(_text_or_empty(soup.select_one(".user-avatar-section h3")))
    academic_title = clean_text(_text_or_empty(soup.select_one(".user-avatar-section h5")))
    if not name:
        title = clean_text(soup.title.get_text(" ", strip=True)) if soup.title else ""
        academic_title, name = _split_academic_title(title.split(" - UNIS", 1)[0])

    if not name:
        return None

    unit_links = [
        clean_text(anchor.get_text(" ", strip=True))
        for anchor in soup.select(".user-avatar-section .birimler a")
        if clean_text(anchor.get_text(" ", strip=True))
    ]
    faculty = unit_links[0] if unit_links else ""
    department = unit_links[1] if len(unit_links) > 1 else ""
    unit = unit_links[2] if len(unit_links) > 2 else ""

    email = ""
    phone = ""
    for anchor in soup.select("a.Contact[data-bs-title]"):
        value = clean_text(anchor.get("data-bs-title", ""))
        icon_classes = " ".join(anchor.select_one("i").get("class", [])) if anchor.select_one("i") else ""
        if not value:
            continue
        if "envelope" in icon_classes or "@" in value:
            email = value
        elif "phone" in icon_classes or re.search(r"\(?\d{3,4}\)?[\s-]?\d{3,4}", value):
            phone = value

    roles = [clean_text(node.get_text(" ", strip=True)) for node in soup.select("span.yetkiAd")]

    work_counts: dict[str, int] = {}
    work_links: dict[str, str] = {}
    for anchor in soup.select("div.calismalar a[href]"):
        label_text = clean_text(anchor.get_text(" ", strip=True))
        count, label = _split_stat_label(label_text)
        if not label:
            continue
        work_counts[label] = count
        work_links[label] = _absolute_url(UNIS_BASE_URL, anchor.get("href"))

    external_links: list[dict] = []
    for anchor in soup.select(".academic-link a[href]"):
        label = clean_text(anchor.get("tool-title", ""))
        href = _absolute_url(UNIS_BASE_URL, anchor.get("href"))
        if label and href:
            external_links.append({"label": label, "url": href})

    research_areas = [
        clean_text(node.get_text(" ", strip=True))
        for node in soup.select(".accordion-body .child")
        if clean_text(node.get_text(" ", strip=True))
    ]
    if not research_areas:
        research_areas = [
            clean_text(node.get_text(" ", strip=True))
            for node in soup.select(".accordion-body .node")
            if clean_text(node.get_text(" ", strip=True))
        ]

    tabs: dict[str, str] = {}
    for anchor in soup.select("#mobileDropdownMenu a[href]"):
        label = clean_text(anchor.get_text(" ", strip=True))
        href = _absolute_url(UNIS_BASE_URL, anchor.get("href"))
        if label and href:
            tabs[label] = href

    image = soup.select_one(".user-avatar-section img")
    return {
        "name": name,
        "academic_title": academic_title,
        "faculty": faculty,
        "department": department,
        "unit": unit,
        "roles": roles,
        "email": email,
        "phone": phone,
        "research_areas": research_areas[:8],
        "work_counts": work_counts,
        "work_links": work_links,
        "external_links": external_links,
        "profile_tabs": tabs,
        "detail_url": source_url,
        "works_url": tabs.get("Akademik Çalışmalar") or work_links.get("Yayın") or source_url,
        "source_url": source_url,
        "image_url": _absolute_url(source_url, image.get("data-src") or image.get("src")) if image else "",
    }


def _parse_unis_management_cards(soup: BeautifulSoup, source_url: str) -> list[dict]:
    people: list[dict] = []
    for card in soup.select("#tab-yonetim .card.w-px-300"):
        role = clean_text(_text_or_empty(card.select_one(".fw-bold")))
        title_parts = [
            clean_text(part)
            for part in card.select_one(".card-title").stripped_strings
            if clean_text(part)
        ] if card.select_one(".card-title") else []
        academic_title = title_parts[0] if len(title_parts) > 1 else ""
        name = title_parts[-1] if title_parts else ""
        anchor = card.select_one("a[href]")
        image = card.select_one("img")
        if not name or not role:
            continue
        people.append(
            {
                "name": name,
                "academic_title": academic_title,
                "faculty": "İktisadi ve İdari Bilimler Fakültesi",
                "department": "",
                "unit": "",
                "roles": [role],
                "detail_url": _absolute_url(source_url, anchor.get("href")) if anchor else "",
                "source_url": source_url,
                "image_url": _absolute_url(source_url, image.get("src")) if image else "",
                "work_counts": {},
                "research_areas": [],
                "external_links": [],
            }
        )
    return people


def _merge_person_records(base: dict, enriched: dict) -> dict:
    merged = dict(base or {})
    for key, value in (enriched or {}).items():
        if value in (None, "", [], {}):
            continue
        if key == "roles":
            base_roles = [clean_text(item) for item in merged.get("roles", []) if clean_text(item)]
            extra_roles = [clean_text(item) for item in value if clean_text(item)]
            merged[key] = list(dict.fromkeys([*base_roles, *extra_roles]))
            continue
        if key in {"work_counts", "work_links", "profile_tabs"}:
            combined = dict(merged.get(key, {}))
            combined.update(value)
            merged[key] = combined
            continue
        if key == "external_links":
            seen = {(item.get("label"), item.get("url")) for item in merged.get(key, [])}
            combined = list(merged.get(key, []))
            for item in value:
                token = (item.get("label"), item.get("url"))
                if token in seen:
                    continue
                seen.add(token)
                combined.append(item)
            merged[key] = combined
            continue
        if key == "research_areas":
            combined = [clean_text(item) for item in merged.get(key, []) if clean_text(item)]
            for item in value:
                cleaned = clean_text(item)
                if cleaned and cleaned not in combined:
                    combined.append(cleaned)
            merged[key] = combined
            continue
        merged[key] = value
    return merged


def _unis_search_page_url(query: str) -> str:
    return f"{UNIS_BASE_URL}search/sorgu={quote_plus(query)}"


def _extract_original_url(html: str) -> str:
    match = re.search(r"ORIGINAL_URL=`([^`]+)`", html)
    return clean_text(match.group(1)) if match else ""


def _append_query_param(url: str, key: str, value: str) -> str:
    separator = "&" if "?" in url else "?"
    if re.search(rf"([?&]){re.escape(key)}=", url):
        return url
    return f"{url}{separator}{key}={value}"


def _unis_grid_payload(page_html: str, search_text: str = "", page_size: int = 8) -> dict[str, str]:
    match = re.search(r'DataCols\.Visible = JSON\.parse\(\'([^\']+)\'\);', page_html)
    if match:
        try:
            visible_columns = json.loads(match.group(1))
        except json.JSONDecodeError:
            visible_columns = ["Id", "Title", "TurStr", "Url", "Html"]
    else:
        visible_columns = ["Id", "Title", "TurStr", "Url", "Html"]

    payload: dict[str, str] = {
        "sEcho": "1",
        "iColumns": str(len(visible_columns)),
        "sColumns": ",".join(visible_columns),
        "iDisplayStart": "0",
        "iDisplayLength": str(max(1, min(page_size, 50))),
        "sSearch": "",
        "bRegex": "false",
        "iSortCol_0": "1",
        "sSortDir_0": "asc",
        "iSortingCols": "1",
        "table_id": "SolrRecord",
        "sorgu": clean_text(search_text),
    }
    for index, column in enumerate(visible_columns):
        payload[f"mDataProp_{index}"] = column
        payload[f"sSearch_{index}"] = ""
        payload[f"bRegex_{index}"] = "false"
        payload[f"bSearchable_{index}"] = "true"
        payload[f"bSortable_{index}"] = "true"
    return payload


def _unis_post(original_url: str, payload: dict[str, str], referer: str) -> requests.Response:
    settings = Settings()
    target_url = urljoin(
        UNIS_BASE_URL,
        original_url if original_url.startswith("?") else f"?{original_url.lstrip('?')}",
    )
    waits = (0.0, 1.0, 2.0)
    last_error: requests.RequestException | None = None

    for wait_seconds in waits:
        if wait_seconds:
            time.sleep(wait_seconds)
        try:
            response = requests.post(
                target_url,
                data=payload,
                timeout=min(settings.request_timeout, 25),
                headers={
                    "User-Agent": settings.user_agent,
                    "Referer": referer,
                    "X-Requested-With": "XMLHttpRequest",
                },
                allow_redirects=True,
            )
            response.raise_for_status()
            return response
        except requests.RequestException as error:
            last_error = error

    raise last_error or requests.RequestException(f"Could not post to {target_url}")


def _split_department_unit(value: str) -> tuple[str, str]:
    if not value:
        return "", ""
    parts = [clean_text(part) for part in value.split("/") if clean_text(part)]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]


def _split_stat_label(label_text: str) -> tuple[int, str]:
    match = re.match(r"(\d+)\s+(.*)", label_text)
    if not match:
        return 0, clean_text(label_text)
    return int(match.group(1)), clean_text(match.group(2))


def _is_unis_person_url(url: str) -> bool:
    normalized = normalize_url(url) or clean_text(url)
    return normalized.startswith(f"{UNIS_BASE_URL}akademisyen") if normalized else False


def _build_official_snapshot() -> dict:
    faculty_root_html = _fetch_html(FACULTY_ROOT_URL)
    faculty_personnel_html = _fetch_html(FACULTY_PERSONNEL_URL)
    senate_html = _fetch_html(SENATE_URL)
    management_html = _fetch_html(UNIS_IIBF_MANAGEMENT_URL)

    faculty_root_soup = BeautifulSoup(faculty_root_html, "html.parser")
    faculty_personnel_soup = BeautifulSoup(faculty_personnel_html, "html.parser")
    management_soup = BeautifulSoup(management_html, "html.parser")
    faculty_personnel = _parse_personnel_cards(
        faculty_personnel_soup.select(".inner-box"),
        FACULTY_PERSONNEL_URL,
    )
    department_roots = _merge_department_roots(
        _parse_department_roots(faculty_root_soup),
        _parse_department_roots(faculty_personnel_soup),
    )
    faculty_navigation = _parse_faculty_navigation(faculty_root_soup, FACULTY_ROOT_URL)
    senate_people = _parse_role_cards(
        BeautifulSoup(senate_html, "html.parser").select(".inner-box"),
        SENATE_URL,
    )

    departments: dict[str, dict] = {}
    for department in department_roots:
        default_links = _default_department_links(department["url"], department["key"])
        departments[department["key"]] = {
            "key": department["key"],
            "name_tr": department["name_tr"],
            "name_en": department["name_en"],
            "aliases": list(department["aliases"]),
            "root_url": department["url"],
            "important_links": default_links,
            "overview": _build_department_overview(department["name_tr"], default_links),
            "personnel": _filter_department_people(faculty_personnel, department),
            "announcements": [],
            "news": [],
            "events": [],
            "special_pages": {},
        }

    return {
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sources": {
            "senate": SENATE_URL,
            "faculty_personnel": FACULTY_PERSONNEL_URL,
            "faculty_announcements": FACULTY_ANNOUNCEMENTS_URL,
            "faculty_news": FACULTY_NEWS_URL,
            "faculty_events": FACULTY_EVENTS_URL,
            "faculty_root": FACULTY_ROOT_URL,
        },
        "faculty_dean": _extract_faculty_dean(senate_people),
        "senate_people": senate_people,
        "faculty_personnel": faculty_personnel,
        "faculty_management": _parse_unis_management_cards(management_soup, UNIS_IIBF_MANAGEMENT_URL),
        "faculty_navigation": faculty_navigation,
        "faculty_pages": {},
        "faculty_content": {
            "announcements": [],
            "news": [],
            "events": [],
        },
        "departments": departments,
        "department_order": list(departments),
    }


def _fetch_html(url: str) -> str:
    settings = Settings()
    waits = (0.0, 1.25, 2.5)
    last_error: requests.RequestException | None = None

    for wait_seconds in waits:
        if wait_seconds:
            time.sleep(wait_seconds)
        try:
            response = requests.get(
                url,
                timeout=min(settings.request_timeout, 20),
                headers={"User-Agent": settings.user_agent},
                allow_redirects=True,
            )
            response.raise_for_status()
            if _looks_rate_limited(response.text, response.url):
                raise requests.RequestException("rate_limited")
            return response.text
        except requests.RequestException as error:
            last_error = error

    raise last_error or requests.RequestException(f"Could not fetch {url}")


def _fetch_binary(url: str) -> bytes:
    settings = Settings()
    waits = (0.0, 1.25, 2.5)
    last_error: requests.RequestException | None = None

    for wait_seconds in waits:
        if wait_seconds:
            time.sleep(wait_seconds)
        try:
            response = requests.get(
                url,
                timeout=min(settings.request_timeout, 20),
                headers={"User-Agent": settings.user_agent},
                allow_redirects=True,
            )
            response.raise_for_status()
            return response.content
        except requests.RequestException as error:
            last_error = error

    raise last_error or requests.RequestException(f"Could not fetch {url}")


def _parse_department_roots(soup: BeautifulSoup) -> list[dict]:
    seen: set[str] = set()
    roots: list[dict] = []

    for link in soup.find_all("a", href=True):
        title = clean_text(link.get_text(" ", strip=True))
        href = _absolute_url(FACULTY_PERSONNEL_URL, link.get("href"))
        key = _department_key_from_name(title)
        if not key or not href or key in seen:
            continue
        seen.add(key)
        department = KNOWN_DEPARTMENTS[key]
        roots.append(
            {
                "key": key,
                "name_tr": department["name_tr"],
                "name_en": department["name_en"],
                "aliases": department["aliases"],
                "url": href,
            }
        )

    if roots:
        return roots

    fallback_roots: list[dict] = []
    for key, department in KNOWN_DEPARTMENTS.items():
        fallback_roots.append(
            {
                "key": key,
                "name_tr": department["name_tr"],
                "name_en": department["name_en"],
                "aliases": department["aliases"],
                "url": f"https://www.kafkas.edu.tr/{department['root_slug']}",
            }
        )
    return fallback_roots


def _merge_department_roots(*groups: list[dict]) -> list[dict]:
    merged: list[dict] = []
    seen: set[str] = set()
    for group in groups:
        for item in group:
            key = item.get("key", "")
            if not key or key in seen:
                continue
            merged.append(item)
            seen.add(key)
    return merged


def _parse_faculty_navigation(soup: BeautifulSoup, source_url: str) -> list[dict]:
    entries: list[dict] = []
    seen_urls: set[str] = set()

    for link in soup.find_all("a", href=True):
        title = clean_text(link.get_text(" ", strip=True))
        url = _absolute_url(source_url, link.get("href"))
        if not _looks_navigation_candidate(title, url):
            continue
        if url in seen_urls:
            continue
        entries.append(
            {
                "title": title,
                "url": url,
                "normalized_title": normalize_for_matching(title),
            }
        )
        seen_urls.add(url)
    return _merge_manual_navigation(entries)


def _looks_navigation_candidate(title: str, url: str) -> bool:
    if not title or not url:
        return False
    if "kafkas.edu.tr" not in url or "/iibf" not in url:
        return False
    if any(part in url.lower() for part in ("/duyuru2/", "/haber", "/etkinlik", "/video", "/galeri")):
        return False
    if title.upper() == "DEVAMINI OKU":
        return False
    normalized_title = normalize_for_matching(title)
    if len(normalized_title) < 2 or normalized_title in {"turkce", "english", "anasayfa"}:
        return False
    return any(
        marker in url.lower()
        for marker in (
            "/sayfayeni",
            "/akademikpersonel",
            "/tumduyurular2",
            "/tumhaberler",
            "/tumetkinlikler2",
            "iibfikt",
            "iibfisletme",
            "iibfsbky",
            "iibfsbui",
            "iibfutl",
            "iibfsh",
            "iibfybs",
            "iibfety",
            "/iibf",
        )
    )


def _navigation_match_score(query_key: str, query_tokens: list[str], entry: dict) -> float:
    title_key = normalize_for_matching(entry.get("normalized_title") or entry.get("title", ""))
    url_key = normalize_for_matching(entry.get("url", ""))
    haystack = f"{title_key} {url_key}".strip()
    if not haystack:
        return 0.0

    title_tokens = [token for token in re.split(r"\s+", title_key) if token]
    overlap = 0.0
    for token in query_tokens:
        if token in title_tokens:
            overlap += 1.6
        elif any(part.startswith(token) or token.startswith(part) for part in title_tokens if len(part) > 3):
            overlap += 0.8
        elif re.search(rf"(?<!\w){re.escape(token)}(?!\w)", haystack):
            overlap += 0.7

    if title_key and title_key in query_key:
        overlap += 3.2
    if query_key and query_key in title_key:
        overlap += 3.6

    ratio = SequenceMatcher(None, query_key, title_key).ratio() if title_key else 0.0
    if overlap <= 0 and ratio < 0.45:
        return 0.0
    return overlap + ratio


def _best_page_title(soup: BeautifulSoup) -> str:
    selectors = (
        "h1",
        ".page-title",
        ".title h1",
        ".breadcrumb-title",
        ".inner-page-title",
    )
    for selector in selectors:
        node = soup.select_one(selector)
        text = _text_or_empty(node)
        if text and len(text) > 2:
            return text
    if soup.title:
        return clean_text(soup.title.get_text(" ", strip=True))
    return ""


def _navigation_title_for_url(snapshot: dict, url: str) -> str:
    for entry in snapshot.get("faculty_navigation", []):
        if clean_text(entry.get("url", "")) == url:
            return clean_text(entry.get("title", ""))
    return ""


def _extract_faculty_page_body(soup: BeautifulSoup) -> str:
    selectors = (
        ".default-content",
        ".page-content",
        ".post-content",
        ".editor-content",
        ".content-body",
        ".content",
        ".blog-content",
        "article",
        ".container",
    )
    longest = ""
    for selector in selectors:
        for node in soup.select(selector):
            text = clean_text(node.get_text("\n", strip=True))
            if len(text) > len(longest):
                longest = text

    if len(longest) >= 240:
        return longest
    body = soup.body or soup
    return clean_text(body.get_text("\n", strip=True))


def _truncate_text(value: str, limit: int = 600) -> str:
    text = clean_text(value)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _parse_personnel_cards(boxes: list, source_url: str, default_department: str | None = None) -> list[dict]:
    people: list[dict] = []

    for box in boxes:
        info = box.select_one(".academic-info-box")
        if info is None:
            continue

        name_tag = info.select_one(".name")
        if name_tag is None:
            continue

        raw_name_text = clean_text(name_tag.get_text(" ", strip=True))
        academic_title, person_name = _split_academic_title(raw_name_text)
        if not person_name:
            person_name = raw_name_text

        roles = [clean_text(item.get_text(" ", strip=True)) for item in info.select(".designation")]
        role_paths = [clean_text(item.get("title", "")) for item in info.select(".designation")]

        detail_link = info.select_one("a.academic-profile-details")
        image = box.select_one("img")
        people.append(
            {
                "name": person_name,
                "academic_title": academic_title,
                "roles": [role for role in roles if role],
                "role_paths": [path for path in role_paths if path],
                "department": default_department or _extract_department(name_tag.get("title", ""), role_paths),
                "detail_url": _absolute_url(source_url, detail_link.get("href")) if detail_link else source_url,
                "image_url": _absolute_url(source_url, image.get("src")) if image else "",
                "source_url": source_url,
            }
        )

    return people


def _parse_role_cards(boxes: list, source_url: str) -> list[dict]:
    items: list[dict] = []
    for box in boxes:
        name_tag = box.select_one(".name")
        designation_tag = box.select_one(".designation")
        detail_tag = box.select_one("a[href]")
        image = box.select_one("img")

        if not name_tag or not designation_tag:
            continue

        items.append(
            {
                "name": clean_text(name_tag.get_text(" ", strip=True)),
                "designation": clean_text(designation_tag.get_text(" ", strip=True)),
                "detail_url": _absolute_url(source_url, detail_tag.get("href")) if detail_tag else source_url,
                "image_url": _absolute_url(source_url, image.get("src")) if image else "",
                "source_url": source_url,
            }
        )
    return items


def _extract_faculty_dean(items: list[dict]) -> dict:
    for item in items:
        designation_key = normalize_for_matching(item.get("designation", ""))
        if "iktisadi ve idari bilimler fakultesi dekani" in designation_key:
            return item
    return {}


def _parse_announcements_page(url: str | None, limit: int = 8, enrich_details: bool = False) -> list[dict]:
    if not url:
        return []

    soup = BeautifulSoup(_fetch_html(url), "html.parser")
    items: list[dict] = []
    for block in soup.select("a.announcement-block")[:limit]:
        item = {
            "title": clean_text(_text_or_empty(block.select_one(".announcement-title"))),
            "date": _join_non_empty(
                [
                    _text_or_empty(block.select_one(".vma_item_date_day")),
                    _text_or_empty(block.select_one(".vma_item_date_month")),
                    _text_or_empty(block.select_one(".vma_item_date_time")),
                ]
            ),
            "relative_date": clean_text(_text_or_empty(block.select_one(".announcement-alert"))),
            "summary": "",
            "url": _absolute_url(url, block.get("href")),
            "image_url": FACULTY_PLACEHOLDER_IMAGE,
            "source_url": url,
            "type": "announcement",
        }
        if enrich_details:
            try:
                item.update(_fetch_detail_enrichment(item["url"], fallback_image=item["image_url"]))
            except requests.RequestException:
                pass
        items.append(item)
    return items


def _parse_news_page(url: str | None, limit: int = 8) -> list[dict]:
    if not url:
        return []

    soup = BeautifulSoup(_fetch_html(url), "html.parser")
    items: list[dict] = []
    for block in soup.select(".company-wrap")[:limit]:
        anchor = block.select_one("h4 a[href]") or block.select_one("a[href]")
        image = block.select_one("img")
        items.append(
            {
                "title": clean_text(_text_or_empty(block.select_one("h4"))),
                "date": clean_text(_text_or_empty(block.select_one(".date"))),
                "summary": clean_text(_text_or_empty(block.select_one(".body span"))),
                "url": _absolute_url(url, anchor.get("href")) if anchor else url,
                "image_url": _absolute_url(url, image.get("src")) if image else FACULTY_PLACEHOLDER_IMAGE,
                "source_url": url,
                "type": "news",
            }
        )
    return items


def _parse_events_page(url: str | None, limit: int = 8) -> list[dict]:
    if not url:
        return []

    soup = BeautifulSoup(_fetch_html(url), "html.parser")
    items: list[dict] = []
    for block in soup.select(".event-box")[:limit]:
        anchor = block.select_one("a.event-details-button[href]") or block.select_one("a[href]")
        image = block.select_one("img")
        items.append(
            {
                "title": clean_text(_text_or_empty(block.select_one(".event-title"))),
                "date": clean_text(_text_or_empty(block.select_one(".event-date span"))),
                "time": clean_text(_text_or_empty(block.select_one(".event-clock span"))),
                "location": clean_text(_text_or_empty(block.select_one(".event-loc span"))),
                "summary": clean_text(_text_or_empty(block.select_one(".event-loc span"))),
                "url": _absolute_url(url, anchor.get("href")) if anchor else url,
                "image_url": _absolute_url(url, image.get("src")) if image else FACULTY_PLACEHOLDER_IMAGE,
                "source_url": url,
                "type": "event",
            }
        )
    return items


def _fetch_detail_enrichment(url: str, fallback_image: str = FACULTY_PLACEHOLDER_IMAGE) -> dict:
    soup = BeautifulSoup(_fetch_html(url), "html.parser")
    body = clean_text(soup.get_text("\n", strip=True))
    title = clean_text(soup.title.get_text(" ", strip=True)) if soup.title else ""
    summary = _extract_summary_from_body(body, title)

    image_url = ""
    for candidate in soup.find_all("img"):
        src = clean_text(candidate.get("src", ""))
        if not src or src.startswith("data:image"):
            continue
        if any(segment in src.lower() for segment in ("/tema/", "/menu/", "logo", "favicon")):
            continue
        image_url = _absolute_url(url, src)
        break

    return {
        "summary": summary,
        "image_url": image_url or fallback_image,
    }


def _build_department_overview(name_tr: str, important_links: dict[str, str]) -> str:
    parts = [f"{name_tr} bölüm sayfasında"]
    if important_links.get("academic_staff"):
        parts.append("akademik kadro")
    if important_links.get("administrative_staff"):
        parts.append("idari kadro")
    if important_links.get("announcements"):
        parts.append("duyurular")
    if important_links.get("news"):
        parts.append("haberler")
    if important_links.get("events"):
        parts.append("etkinlikler")
    if important_links.get("management"):
        parts.append("yönetim")
    if important_links.get("journal"):
        parts.append("bölüm dergisi")
    if important_links.get("advising"):
        parts.append("akademik danışmanlıklar")
    if important_links.get("clubs"):
        parts.append("öğrenci kulüpleri")
    if len(parts) == 1:
        return f"{name_tr} bölümüne ait resmi bağlantılar yayımlanmaktadır."
    return f"{parts[0]} {', '.join(parts[1:])} bağlantıları yer almaktadır."


def _default_department_links(root_url: str, department_key: str) -> dict[str, str]:
    base_url = _department_base_url(root_url, department_key)
    links = {
        "academic_staff": f"{base_url}/tr/akademikpersonel",
        "announcements": f"{base_url}/tr/tumduyurular2",
        "news": f"{base_url}/tr/tumHaberler",
        "events": f"{base_url}/tr/tumEtkinlikler2",
    }
    if department_key == "ybs":
        links.update(YBS_SPECIAL_LINKS)
    return links


def _split_academic_title(raw_text: str) -> tuple[str, str]:
    text = clean_text(raw_text)
    upper_text = text.upper()
    for prefix in ACADEMIC_PREFIXES:
        if upper_text.startswith(prefix):
            return prefix.title(), clean_text(text[len(prefix) :])
    return "", text


def _extract_department(title_value: str, role_paths: list[str]) -> str:
    combined = " / ".join([title_value, *role_paths])
    for department in KNOWN_DEPARTMENTS.values():
        if normalize_for_matching(department["name_tr"]) in normalize_for_matching(combined):
            return department["name_tr"]
    match = re.search(r"([A-ZÇĞİÖŞÜ\s]+) BÖLÜMÜ", combined)
    if match:
        return clean_text(match.group(1).title())
    return "İİBF"


def _filter_department_people(faculty_people: list[dict], department: dict) -> list[dict]:
    people: list[dict] = []
    for person in faculty_people:
        if _person_matches_department(person, department):
            people.append(person)
    return people


def _person_matches_department(person: dict, department: dict) -> bool:
    department_name = normalize_for_matching(person.get("department", ""))
    if not department_name:
        return False
    candidates = [department.get("name_tr", ""), department.get("name_en", ""), *department.get("aliases", ())]
    return any(normalize_for_matching(candidate) in department_name for candidate in candidates if candidate)


def _department_key_from_name(name: str) -> str:
    normalized = normalize_for_matching(name)
    for key, department in KNOWN_DEPARTMENTS.items():
        if any(normalize_for_matching(alias) == normalized for alias in department["aliases"]):
            return key
    return ""


def _department_base_url(root_url: str, department_key: str) -> str:
    parsed = urlsplit(root_url)
    path_segments = [segment for segment in parsed.path.split("/") if segment]
    root_segment = path_segments[0] if path_segments else KNOWN_DEPARTMENTS.get(department_key, {}).get("root_slug", "")
    scheme = parsed.scheme or "https"
    netloc = parsed.netloc or "www.kafkas.edu.tr"
    return f"{scheme}://{netloc}/{root_segment}".rstrip("/")


def _extract_summary_from_body(body: str, title: str) -> str:
    body = body.replace("Duyuruyu Paylaş:", " ").replace("kez görüntülendi.", " ")
    body = re.sub(r"\s+", " ", body).strip()
    title_key = normalize_for_matching(title) if title else ""

    sentences = [clean_text(item) for item in re.split(r"(?<=[.!?])\s+", body) if clean_text(item)]
    for sentence in sentences:
        sentence_key = normalize_for_matching(sentence)
        if title_key and sentence_key == title_key:
            continue
        if len(sentence) < 25:
            continue
        if any(term in sentence_key for term in ("menus", "anasayfa", "fakulte hakkinda", "duyuruyu paylas")):
            continue
        return sentence[:220]
    return ""


def _parse_ybs_management_page(html: str, source_url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    content_root = soup.select_one(".post-content .c-padding") or soup.select_one(".post-content") or soup
    body = clean_text(content_root.get_text("\n", strip=True))
    people: list[dict] = []
    current_name = ""

    for node in content_root.select("h2, h3"):
        text = clean_text(node.get_text(" ", strip=True))
        normalized = normalize_for_matching(text)
        if not text:
            continue
        if node.name == "h2" and "yonetim" not in normalized:
            current_name = text
            continue
        if node.name == "h3" and current_name and any(
            marker in normalized for marker in ("bolum baskani", "bölüm başkanı", "yardimc", "yardımc", "yonet")
        ):
            people.append({"name": current_name, "role": text})
            current_name = ""

    summary = _extract_summary_from_body(body, "YBS Bölüm Yönetimi")
    if not summary and people:
        summary = "Bölüm yönetimi sayfasında bölüm başkanı ve bölüm başkan yardımcısı bilgileri yayımlanmaktadır."

    return {
        "title": "YBS Bölüm Yönetimi",
        "url": source_url,
        "summary": summary,
        "body_excerpt": _truncate_text(body, 1400),
        "people": people,
    }


def _parse_ybs_journal_page(html: str, source_url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    content_root = soup.select_one(".post-content .c-padding") or soup.select_one(".post-content") or soup
    body = clean_text(content_root.get_text("\n", strip=True))
    links: list[dict] = []
    seen_urls: set[str] = set()
    for anchor in content_root.select("a[href]"):
        url = _absolute_url(source_url, anchor.get("href"))
        label = clean_text(anchor.get_text(" ", strip=True))
        if not url or url in seen_urls:
            continue
        links.append({"label": label or "Bağlantı", "url": url})
        seen_urls.add(url)

    journal_name_match = re.search(
        r"(Kafkas Üniversitesi Yönetim ve Bilişim Dergisi\s*\(KAÜYÖNBİD\))",
        body,
        flags=re.IGNORECASE,
    )
    journal_name = clean_text(journal_name_match.group(1)) if journal_name_match else ""
    purpose = _first_matching_sentence(body, ("amacıyla", "yayimlanmaktadir", "yayımlanmaktadır"))
    scope = _first_matching_sentence(
        body,
        ("dergimiz", "acik erisimli", "açık erişimli", "hakemli", "yapay zeka", "yapay zekâ"),
        exclude=purpose,
    )
    purpose = re.sub(r"^Bölüm Dergisi\s*", "", purpose, flags=re.IGNORECASE).strip()
    scope = re.sub(r"^Bölüm Dergisi\s*", "", scope, flags=re.IGNORECASE).strip()
    if not purpose:
        purpose = "Bölüm dergisi sayfasında derginin amacı ve yayın ortamına dair resmi açıklama yer almaktadır."

    return {
        "title": "YBS Bölüm Dergisi",
        "url": source_url,
        "summary": purpose,
        "body_excerpt": _truncate_text(body, 1400),
        "journal_name": journal_name,
        "purpose": purpose,
        "scope": scope,
        "links": links,
    }


def _parse_ybs_clubs_page(html: str, source_url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    content_root = soup.select_one(".post-content .c-padding") or soup.select_one(".post-content") or soup
    body = clean_text(content_root.get_text("\n", strip=True))
    clubs: list[dict] = []
    for card in content_root.select(".club-card"):
        club_name = clean_text(_text_or_empty(card.select_one("h3")))
        advisor_name = clean_text(_text_or_empty(card.select_one(".advisor-name")))
        advisor_role = clean_text(_text_or_empty(card.select_one(".advisor-label"))) or "Akademik Danışman"
        if not club_name:
            continue
        clubs.append(
            {
                "name": club_name,
                "advisor_name": advisor_name,
                "advisor_role": advisor_role,
            }
        )

    summary = f"Resmi kulüp sayfasında {len(clubs)} öğrenci kulübü listelenmektedir." if clubs else ""
    return {
        "title": "YBS Öğrenci Kulüpleri",
        "url": source_url,
        "summary": summary,
        "body_excerpt": _truncate_text(body, 1400),
        "clubs": clubs,
    }


def _parse_ybs_advising_pdf(content: bytes, source_url: str, department_people: list[dict]) -> dict:
    document = extract_pdf(content, source_url)
    body = clean_text(document.content)
    class_advisors = _extract_ybs_class_advisors(body, department_people)
    summary = ""
    if class_advisors:
        class_labels = ", ".join(entry["class_label"] for entry in class_advisors)
        summary = f"PDF dosyasında {class_labels} için akademik danışman listeleri ve danışmanlık saatleri yer almaktadır."
    elif document.metadata.get("extract_error"):
        summary = "Akademik danışmanlık PDF dosyası okunamadı; resmi kaynak bağlantısı kullanılmalıdır."
    else:
        summary = "Akademik danışmanlık bilgileri resmi PDF dosyasında yayımlanmaktadır."

    return {
        "title": "YBS Akademik Danışmanlıklar",
        "url": source_url,
        "summary": summary,
        "body_excerpt": _truncate_text(body, 1800),
        "document_title": document.title,
        "page_count": document.metadata.get("page_count", 0),
        "extract_error": clean_text(str(document.metadata.get("extract_error", ""))),
        "class_advisors": class_advisors,
    }


def _extract_ybs_class_advisors(text: str, department_people: list[dict]) -> list[dict]:
    if not text:
        return []

    sections: list[dict] = []
    pattern = re.compile(r"\b(I{1,3}|IV)\.?\s*SINIF\b", re.IGNORECASE)
    matches = list(pattern.finditer(text))
    roman_to_label = {
        "I": "1. Sınıf",
        "II": "2. Sınıf",
        "III": "3. Sınıf",
        "IV": "4. Sınıf",
    }

    for index, match in enumerate(matches):
        roman = match.group(1).upper()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        section_text = text[start:end]
        advisors = _extract_ybs_advisors_from_section(section_text, department_people)
        if advisors:
            sections.append({"class_label": roman_to_label.get(roman, roman), "advisors": advisors})

    return sections


def _extract_ybs_advisors_from_section(section_text: str, department_people: list[dict]) -> list[dict]:
    title_pattern = r"(Prof\. Dr\.|Doç\. Dr\.|Dr\. Öğr\. Üyesi|Öğr\. Gör\.|Arş\. Gör\.)"
    pattern = re.compile(
        rf"{title_pattern}\s+([A-ZÇĞİÖŞÜİIÖÜŞĞÇA-Za-zçğıöşüİIÖÜŞĞÇ\.\* ]{{4,60}}?)\s+YBS",
        re.IGNORECASE,
    )
    schedule_pattern = re.compile(
        r"((?:Pazartesi|Salı|Çarşamba|Perşembe|Cuma)\s+\d{1,2}[:.]\d{2}-\d{1,2}[:.]\d{2}"
        r"(?:\s+(?:Pazartesi|Salı|Çarşamba|Perşembe|Cuma)\s+\d{1,2}[:.]\d{2}-\d{1,2}[:.]\d{2})*)"
    )
    advisors: list[dict] = []
    seen_names: set[tuple[str, str]] = set()

    for match in pattern.finditer(section_text):
        academic_title = clean_text(match.group(1))
        masked_name = clean_text(match.group(2))
        resolved_name = _resolve_masked_person_name(masked_name, department_people) or masked_name
        key = (academic_title, resolved_name)
        if key in seen_names:
            continue
        schedule_window = section_text[match.end() : match.end() + 180]
        schedule_match = schedule_pattern.search(schedule_window)
        schedule = clean_text(schedule_match.group(1)) if schedule_match else ""
        advisors.append(
            {
                "academic_title": academic_title,
                "name": resolved_name,
                "masked_name": masked_name,
                "schedule": schedule,
            }
        )
        seen_names.add(key)

    return advisors


def _resolve_masked_person_name(masked_name: str, people: list[dict]) -> str:
    prefixes = [
        normalize_for_matching(token).replace("*", "")
        for token in clean_text(masked_name).split()
        if normalize_for_matching(token).replace("*", "")
    ]
    if not prefixes:
        return ""

    best_name = ""
    best_score = 0
    for person in people:
        name = clean_text(person.get("name", ""))
        if not name:
            continue
        name_tokens = [normalize_for_matching(token) for token in name.split() if normalize_for_matching(token)]
        if len(name_tokens) < len(prefixes):
            continue
        score = 0
        matched_tokens = 0
        for prefix in prefixes:
            if any(token.startswith(prefix) for token in name_tokens):
                score += len(prefix)
                matched_tokens += 1
            else:
                score = 0
                break
        if matched_tokens >= min(2, len(prefixes)) and score > best_score:
            best_name = name
            best_score = score
    return best_name


def _first_matching_sentence(body: str, terms: tuple[str, ...], exclude: str = "") -> str:
    sentences = [clean_text(item) for item in re.split(r"(?<=[.!?])\s+", body) if clean_text(item)]
    exclude_key = normalize_for_matching(exclude)
    for sentence in sentences:
        key = normalize_for_matching(sentence)
        if exclude_key and key == exclude_key:
            continue
        if any(term in key for term in terms):
            return sentence[:260]
    return ""


def _text_or_empty(node) -> str:
    return clean_text(node.get_text(" ", strip=True)) if node else ""


def _absolute_url(base_url: str, value: str | None) -> str:
    if not value or value.startswith("javascript"):
        return ""
    return urljoin(base_url, value)


def _join_non_empty(parts: list[str]) -> str:
    return " ".join(item for item in parts if item).strip()


def _hydrate_snapshot(snapshot: dict) -> dict:
    changed = False
    departments = snapshot.setdefault("departments", {})
    sources = snapshot.setdefault("sources", {})

    if not snapshot.get("department_order"):
        snapshot["department_order"] = list(departments)
        changed = True

    if not snapshot.get("faculty_dean"):
        dean = _extract_faculty_dean(snapshot.get("senate_people", []))
        if dean:
            snapshot["faculty_dean"] = dean
            changed = True

    snapshot.setdefault("faculty_content", {"announcements": [], "news": [], "events": []})
    snapshot.setdefault("faculty_personnel", [])
    snapshot.setdefault("faculty_management", [])
    snapshot.setdefault("faculty_pages", {})
    if not sources.get("faculty_root"):
        sources["faculty_root"] = FACULTY_ROOT_URL
        changed = True
    if not snapshot.get("faculty_navigation"):
        try:
            navigation_html = _fetch_html(FACULTY_ROOT_URL)
            snapshot["faculty_navigation"] = _parse_faculty_navigation(
                BeautifulSoup(navigation_html, "html.parser"),
                FACULTY_ROOT_URL,
            )
            changed = True
        except requests.RequestException:
            snapshot.setdefault("faculty_navigation", [])
    if not snapshot.get("faculty_management"):
        try:
            management_html = _fetch_html(UNIS_IIBF_MANAGEMENT_URL)
            snapshot["faculty_management"] = _parse_unis_management_cards(
                BeautifulSoup(management_html, "html.parser"),
                UNIS_IIBF_MANAGEMENT_URL,
            )
            changed = True
        except requests.RequestException:
            snapshot.setdefault("faculty_management", [])
    merged_navigation = _merge_manual_navigation(snapshot.get("faculty_navigation", []))
    if len(merged_navigation) != len(snapshot.get("faculty_navigation", [])):
        snapshot["faculty_navigation"] = merged_navigation
        changed = True

    for key, department in KNOWN_DEPARTMENTS.items():
        if key not in departments:
            departments[key] = {
                "key": key,
                "name_tr": department["name_tr"],
                "name_en": department["name_en"],
                "aliases": list(department["aliases"]),
                "root_url": FACULTY_DEPARTMENT_ROOT_OVERRIDES.get(key, f"https://www.kafkas.edu.tr/{department['root_slug']}"),
                "important_links": _default_department_links(
                    FACULTY_DEPARTMENT_ROOT_OVERRIDES.get(key, f"https://www.kafkas.edu.tr/{department['root_slug']}"),
                    key,
                ),
                "overview": "",
                "personnel": [],
                "announcements": [],
                "news": [],
                "events": [],
                "special_pages": {},
            }
            changed = True

        if _hydrate_department(snapshot, key, departments[key]):
            changed = True

    if changed:
        snapshot["departments"] = departments
        _persist_snapshot(snapshot)
    return snapshot


def _hydrate_department(snapshot: dict, key: str, department_snapshot: dict) -> bool:
    changed = False
    reference = KNOWN_DEPARTMENTS.get(key, {})
    manual_root_url = FACULTY_DEPARTMENT_ROOT_OVERRIDES.get(key, "")

    department_snapshot.setdefault("key", key)
    if not department_snapshot.get("name_tr") and reference.get("name_tr"):
        department_snapshot["name_tr"] = reference["name_tr"]
        changed = True
    if not department_snapshot.get("name_en") and reference.get("name_en"):
        department_snapshot["name_en"] = reference["name_en"]
        changed = True
    if not department_snapshot.get("aliases"):
        department_snapshot["aliases"] = list(reference.get("aliases", ()))
        changed = True
    if manual_root_url and department_snapshot.get("root_url") != manual_root_url:
        department_snapshot["root_url"] = manual_root_url
        changed = True
    elif not department_snapshot.get("root_url") and reference.get("root_slug"):
        department_snapshot["root_url"] = f"https://www.kafkas.edu.tr/{reference['root_slug']}"
        changed = True
    expected_links = _default_department_links(department_snapshot["root_url"], key) if department_snapshot.get("root_url") else {}
    if not department_snapshot.get("important_links"):
        department_snapshot["important_links"] = expected_links
        changed = True
    elif expected_links and department_snapshot.get("important_links") != expected_links:
        department_snapshot["important_links"] = expected_links
        changed = True
    if changed or not department_snapshot.get("overview"):
        department_snapshot["overview"] = _build_department_overview(
            department_snapshot.get("name_tr", reference.get("name_tr", "Bölüm")),
            department_snapshot.get("important_links", {}),
        )
        changed = True
    if not department_snapshot.get("personnel"):
        department_snapshot["personnel"] = _filter_department_people(
            snapshot.get("faculty_personnel", []),
            {
                "name_tr": department_snapshot.get("name_tr", ""),
                "name_en": department_snapshot.get("name_en", ""),
                "aliases": department_snapshot.get("aliases", []),
            },
        )
        changed = True

    department_snapshot.setdefault("announcements", [])
    department_snapshot.setdefault("news", [])
    department_snapshot.setdefault("events", [])
    department_snapshot.setdefault("special_pages", {})
    return changed


def _persist_snapshot(snapshot: dict) -> None:
    global _memory_loaded_at, _memory_snapshot

    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    _memory_snapshot = snapshot
    _memory_loaded_at = time.time()


def _merge_manual_navigation(entries: list[dict]) -> list[dict]:
    merged: list[dict] = []
    seen_urls: set[str] = set()

    for entry in entries:
        url = clean_text(entry.get("url", ""))
        title = clean_text(entry.get("title", ""))
        if not url or not title or url in seen_urls:
            continue
        merged.append(
            {
                "title": title,
                "url": url,
                "normalized_title": normalize_for_matching(entry.get("normalized_title") or title),
            }
        )
        seen_urls.add(url)

    for entry in FACULTY_MANUAL_NAVIGATION:
        url = clean_text(entry.get("url", ""))
        title = clean_text(entry.get("title", ""))
        if not url or not title or url in seen_urls:
            continue
        merged.append(
            {
                "title": title,
                "url": url,
                "normalized_title": normalize_for_matching(title),
            }
        )
        seen_urls.add(url)

    return merged


def _looks_rate_limited(text: str, final_url: str = "") -> bool:
    haystack = f"{final_url}\n{text[:600]}".lower()
    return any(marker.lower() in haystack for marker in RATE_LIMIT_MARKERS)
