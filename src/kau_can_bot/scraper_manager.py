from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .config import DOCUMENT_CATALOG_PATH
from .logging_utils import get_logger
from .models import PageDocument
from .utils import clean_text, stable_id


LOGGER = get_logger("scraper_manager")
OIDB_FORMS_URL = "https://www.kafkas.edu.tr/oidb/tr/sayfaYeni11090"
IIBF_FORMS_URL = "https://www.kafkas.edu.tr/iibf/tr/sayfaYeni17988"
DOCUMENT_EXTENSIONS = (".pdf", ".doc", ".docx", ".xls", ".xlsx")


@dataclass
class DocumentCatalogEntry:
    id: str
    title: str
    url: str
    category: str
    source_page: str
    source_type: str
    fetched_at: str


def fetch_document_catalog(force_refresh: bool = False) -> List[DocumentCatalogEntry]:
    if not force_refresh:
        cached = _load_cached_catalog()
        if cached:
            return cached

    entries = _parse_form_page(OIDB_FORMS_URL, "oidb_form", "document")
    entries.extend(_parse_form_page(IIBF_FORMS_URL, "iibf_form", "document"))
    entries = _dedupe_catalog(entries)
    _save_cached_catalog(entries)
    return entries


def build_document_catalog_documents() -> List[PageDocument]:
    documents: List[PageDocument] = []
    catalog = fetch_document_catalog(force_refresh=False)
    grouped: Dict[str, List[DocumentCatalogEntry]] = {}

    for entry in catalog:
        grouped.setdefault(entry.source_page, []).append(entry)

    for source_page, entries in grouped.items():
        lines = []
        for entry in entries:
            lines.append(
                f"{entry.title}\n"
                f"Kategori: {entry.category}\n"
                f"Kaynak sayfa: {entry.source_page}\n"
                f"Dosya URL: {entry.url}"
            )
        documents.append(
            PageDocument(
                url=source_page,
                title="Belge ve Form Kataloğu",
                content="\n\n".join(lines),
                content_type="text/html",
                links=[entry.url for entry in entries],
                metadata={
                    "source_type": "document",
                    "fetched_at": entries[0].fetched_at if entries else "",
                    "category": "forms",
                    "document_count": len(entries),
                },
            )
        )

    return documents


def _parse_form_page(source_url: str, category: str, source_type: str) -> List[DocumentCatalogEntry]:
    html = _fetch_html(source_url)
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    fetched_at = datetime.now(timezone.utc).isoformat()
    entries: List[DocumentCatalogEntry] = []

    for anchor in soup.select("a[href]"):
        href = clean_text(anchor.get("href", ""))
        url = urljoin(source_url, href)
        title = clean_text(anchor.get_text(" ", strip=True))

        if not title or not href:
            continue
        if not _is_document_link(url) and not _looks_like_document_title(title):
            continue

        entries.append(
            DocumentCatalogEntry(
                id=stable_id(source_url, title, url),
                title=title,
                url=url,
                category=category,
                source_page=source_url,
                source_type=source_type,
                fetched_at=fetched_at,
            )
        )

    return entries


def _fetch_html(url: str) -> str:
    try:
        response = requests.get(
            url,
            timeout=15,
            headers={"User-Agent": "KAUCAN/1.0 (+https://www.kafkas.edu.tr)"},
        )
        response.raise_for_status()
        return response.text
    except requests.RequestException as exc:
        LOGGER.warning("Document catalog fetch failed for %s: %s", url, exc)
        return ""


def _load_cached_catalog() -> List[DocumentCatalogEntry]:
    if not DOCUMENT_CATALOG_PATH.exists():
        return []
    try:
        payload = json.loads(DOCUMENT_CATALOG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []

    entries = payload.get("entries", [])
    return [
        DocumentCatalogEntry(**entry)
        for entry in entries
        if entry.get("title") and entry.get("url")
    ]


def _save_cached_catalog(entries: List[DocumentCatalogEntry]) -> None:
    DOCUMENT_CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    DOCUMENT_CATALOG_PATH.write_text(
        json.dumps({"entries": [asdict(entry) for entry in entries]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _dedupe_catalog(entries: List[DocumentCatalogEntry]) -> List[DocumentCatalogEntry]:
    deduped: List[DocumentCatalogEntry] = []
    seen = set()
    for entry in entries:
        key = (entry.title.lower(), entry.url.lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(entry)
    return deduped


def _is_document_link(url: str) -> bool:
    lowered = url.lower()
    return any(lowered.endswith(extension) for extension in DOCUMENT_EXTENSIONS)


def _looks_like_document_title(title: str) -> bool:
    lowered = title.lower()
    return any(
        term in lowered
        for term in (
            "form",
            "dilekçe",
            "dilekce",
            "başvuru",
            "basvuru",
            "itiraz",
            "kayıt",
            "kayit",
            "belge",
            "taahhütname",
            "taahhutname",
        )
    )
