from __future__ import annotations

import json
import re
import time
from difflib import SequenceMatcher
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from .config import DATA_DIR, Settings
from .query_normalizer import normalize_for_matching
from .utils import clean_text


FACULTY_PERSONNEL_URL = "https://www.kafkas.edu.tr/iibf/tr/akademikpersonel"
FACULTY_ANNOUNCEMENTS_URL = "https://www.kafkas.edu.tr/iibf/tr/tumduyurular2"
FACULTY_NEWS_URL = "https://www.kafkas.edu.tr/iibf/tr/tumHaberler"
FACULTY_EVENTS_URL = "https://www.kafkas.edu.tr/iibf/tr/tumEtkinlikler2"
FACULTY_ROOT_URL = "https://www.kafkas.edu.tr/iibf"
SENATE_URL = "https://www.kafkas.edu.tr/rektorluk/TR/sayfaYeni651"
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
    {"title": "Elektronik Ticaret ve Yönetimi", "url": "https://www.kafkas.edu.tr/iibfety"},
)

CACHE_PATH = DATA_DIR / "official_snapshot.json"
FILE_TTL_SECONDS = 60 * 60 * 6
MEMORY_TTL_SECONDS = 60 * 10

RATE_LIMIT_MARKERS = (
    "TOO MANY REQUEST",
    "Please wait for 1 minute",
    "www.kafkas.edu.tr/hata.htm",
)

_memory_snapshot: dict | None = None
_memory_loaded_at: float = 0.0

ACADEMIC_PREFIXES = (
    "PROFESÖR",
    "DOÇENT",
    "DOKTOR ÖĞRETİM ÜYESİ",
    "DOKTOR",
    "ÖĞRETİM GÖREVLİSİ",
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


def _build_official_snapshot() -> dict:
    faculty_root_html = _fetch_html(FACULTY_ROOT_URL)
    faculty_personnel_html = _fetch_html(FACULTY_PERSONNEL_URL)
    senate_html = _fetch_html(SENATE_URL)

    faculty_root_soup = BeautifulSoup(faculty_root_html, "html.parser")
    faculty_personnel_soup = BeautifulSoup(faculty_personnel_html, "html.parser")
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
    if len(parts) == 1:
        return f"{name_tr} bölümüne ait resmi bağlantılar yayımlanmaktadır."
    return f"{parts[0]} {', '.join(parts[1:])} bağlantıları yer almaktadır."


def _default_department_links(root_url: str, department_key: str) -> dict[str, str]:
    base_url = _department_base_url(root_url, department_key)
    return {
        "academic_staff": f"{base_url}/tr/akademikpersonel",
        "announcements": f"{base_url}/tr/tumduyurular2",
        "news": f"{base_url}/tr/tumHaberler",
        "events": f"{base_url}/tr/tumEtkinlikler2",
    }


def _split_academic_title(raw_text: str) -> tuple[str, str]:
    text = clean_text(raw_text)
    for prefix in ACADEMIC_PREFIXES:
        if text.startswith(prefix):
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
