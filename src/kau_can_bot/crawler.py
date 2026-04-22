from __future__ import annotations

import re
import time
from collections import deque
from collections.abc import Iterator
from urllib.parse import urlparse

import requests
from rich.progress import Progress, SpinnerColumn, TextColumn

from .config import Settings
from .extractor import (
    extract_docx,
    extract_html,
    extract_pdf,
    extract_plain_text,
    extract_spreadsheet,
    unsupported_document,
)
from .models import PageDocument
from .utils import extension_from_url, is_allowed_domain, looks_like_document, normalize_url


class WebsiteCrawler:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.settings.user_agent})

    def crawl(self, start_url: str | None = None, max_pages: int | None = None) -> list[PageDocument]:
        start = normalize_url(start_url or self.settings.target_url)
        if not start:
            raise ValueError("Geçerli bir başlangıç URL'si belirtilmelidir.")

        limit = max_pages or self.settings.max_pages
        attempt_limit = max(limit * 5, limit + 50)
        queue: deque[str] = deque([start])
        seen: set[str] = set()
        documents: list[PageDocument] = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            task = progress.add_task("Site taranıyor...", total=None)
            while queue and len(documents) < limit and len(seen) < attempt_limit:
                url = queue.popleft()
                if url in seen or not self._is_crawlable(url):
                    continue

                seen.add(url)
                progress.update(
                    task,
                    description=(
                        f"Taranıyor ({len(documents)}/{limit}, deneme {len(seen)}): {url}"
                    ),
                )
                document = self._fetch_document(url)
                if not document:
                    continue

                documents.append(document)
                links = [
                    link
                    for link in document.links
                    if link not in seen and self._is_crawlable(link)
                ]
                for link in sorted(links, key=self._link_priority):
                    if link not in seen and self._is_crawlable(link):
                        queue.append(link)

                if self.settings.request_delay > 0:
                    time.sleep(self.settings.request_delay)

        return documents

    def iter_crawl(
        self,
        start_url: str | None = None,
        max_pages: int | None = None,
    ) -> Iterator[PageDocument]:
        for document in self.crawl(start_url=start_url, max_pages=max_pages):
            yield document

    def _fetch_document(self, url: str) -> PageDocument | None:
        response: requests.Response | None = None
        for attempt in range(self.settings.max_retries + 1):
            try:
                response = self.session.get(
                    url,
                    timeout=self.settings.request_timeout,
                    allow_redirects=True,
                )
                response.raise_for_status()
            except requests.RequestException:
                if attempt >= self.settings.max_retries:
                    return None
                time.sleep(min(self.settings.rate_limit_wait, 5))
                continue

            if response.url:
                final_url = normalize_url(response.url) or url
                if not self._is_crawlable(final_url):
                    return None

            if not _is_rate_limited_response(response):
                break

            if attempt >= self.settings.max_retries:
                return None
            time.sleep(self.settings.rate_limit_wait)


        if response is None:
            return None

        final_url = normalize_url(response.url) or url
        content_type = response.headers.get("content-type", "").split(";")[0].lower()
        extension = extension_from_url(final_url)

        if "html" in content_type:
            return extract_html(response.text, final_url)

        if content_type == "application/pdf" or extension == ".pdf":
            return extract_pdf(response.content, final_url)

        if extension in {".xls", ".xlsx"}:
            return extract_spreadsheet(response.content, final_url)

        if extension == ".docx":
            return extract_docx(response.content, final_url)

        if content_type.startswith("text/") or extension == ".txt":
            return extract_plain_text(response.content, final_url, content_type or "text/plain")

        if extension:
            return unsupported_document(final_url, content_type or extension)

        return None

    def _is_crawlable(self, url: str) -> bool:
        if not is_allowed_domain(url, self.settings.allowed_domain):
            return False
        if self.settings.crawl_scope == "domain":
            return True
        return _is_faculty_scoped_url(url)

    def _link_priority(self, url: str) -> tuple[int, str]:
        target_path = urlparse(self.settings.target_url).path.strip("/").lower()
        path = urlparse(url).path.strip("/").lower()

        if target_path and (path == target_path or path.startswith(target_path + "/")):
            return (0, url)
        if "iibf" in path:
            return (1, url)
        if looks_like_document(url):
            return (3, url)
        return (2, url)


def _is_rate_limited_response(response: requests.Response) -> bool:
    sample = response.text[:500].upper() if response.text else ""
    return "TOO MANY REQUEST" in sample


FACULTY_PATH_PATTERNS = (
    r"^/iibf(?:/|$)",
    r"^/iibfikt(?:/|$)",
    r"^/iibfisletme(?:/|$)",
    r"^/iibfsbky(?:/|$)",
    r"^/iibfsbui(?:/|$)",
    r"^/iibfutl(?:/|$)",
    r"^/iibfsh(?:/|$)",
    r"^/iibfybs(?:/|$)",
    r"^/iibfety(?:/|$)",
    r"^/dersler\.aspx$",
    r"^/kau/rehber(?:/|$)",
)


def _is_faculty_scoped_url(url: str) -> bool:
    parsed_path = urlparse(url).path.lower()
    if any(re.search(pattern, parsed_path) for pattern in FACULTY_PATH_PATTERNS):
        return True
    if looks_like_document(url) and (
        "/iibf" in parsed_path
        or "/iktisadi" in parsed_path
        or "/idari" in parsed_path
        or "/fakulte" in parsed_path
        or "/fakülte" in parsed_path
    ):
        return True
    return False
