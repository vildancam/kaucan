from __future__ import annotations

from typing import Iterable, List, Sequence

from .models import Chunk, SearchResult
from .utils import clean_text, stable_id


def build_source_results(
    entries: Sequence[dict] | Sequence[tuple[str, str]],
    source_type: str = "general",
) -> List[SearchResult]:
    results: List[SearchResult] = []

    for ordinal, entry in enumerate(entries, start=1):
        if isinstance(entry, tuple):
            title, url = entry
            snippet = ""
        else:
            title = clean_text(str(entry.get("title", "")))
            url = clean_text(str(entry.get("url", "")))
            snippet = clean_text(str(entry.get("snippet", "")))

        if not title or not url:
            continue

        results.append(
            SearchResult(
                chunk=Chunk(
                    id=stable_id(source_type, title, url, str(ordinal)),
                    url=url,
                    title=title,
                    text=snippet or title,
                    ordinal=ordinal,
                    metadata={"source_type": source_type},
                ),
                score=1.0,
            )
        )

    return dedupe_search_results(results)


def dedupe_search_results(results: Iterable[SearchResult]) -> List[SearchResult]:
    deduped: List[SearchResult] = []
    seen_urls: set[str] = set()

    for result in results:
        url = clean_text(result.chunk.url)
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        deduped.append(result)

    return deduped
