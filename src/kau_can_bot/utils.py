from __future__ import annotations

import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse


TRACKING_QUERY_PREFIXES = ("utm_",)
TRACKING_QUERY_KEYS = {"fbclid", "gclid", "yclid"}
DOCUMENT_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".txt",
}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def normalize_url(url: str, base_url: str | None = None) -> str | None:
    if not url:
        return None

    absolute = urljoin(base_url, url) if base_url else url
    parsed = urlparse(absolute)

    if parsed.scheme not in {"http", "https"}:
        return None

    query_pairs = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        if key in TRACKING_QUERY_KEYS or key.startswith(TRACKING_QUERY_PREFIXES):
            continue
        query_pairs.append((key, value))

    netloc = parsed.netloc.lower()
    if netloc == "www.kafkas.edu.tr":
        netloc = "kafkas.edu.tr"

    path = parsed.path.rstrip("/") or "/"
    while "/iibf/iibf/" in path.lower():
        path = re.sub(r"/iibf/iibf/", "/iibf/", path, flags=re.IGNORECASE)

    normalized = parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=netloc,
        path=path,
        params="",
        query=urlencode(query_pairs, doseq=True),
        fragment="",
    )
    return urlunparse(normalized)


def is_allowed_domain(url: str, allowed_domain: str) -> bool:
    host = urlparse(url).netloc.lower()
    allowed = allowed_domain.lower()
    return host == allowed or host.endswith("." + allowed)


def stable_id(*parts: str) -> str:
    digest = hashlib.sha256()
    for part in parts:
        digest.update(part.encode("utf-8", errors="ignore"))
        digest.update(b"\x00")
    return digest.hexdigest()[:20]


def extension_from_url(url: str) -> str:
    path = urlparse(url).path.lower()
    for extension in DOCUMENT_EXTENSIONS:
        if path.endswith(extension):
            return extension
    return ""


def looks_like_document(url: str) -> bool:
    return extension_from_url(url) in DOCUMENT_EXTENSIONS
