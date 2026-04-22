from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from collections import Counter
from pathlib import Path
from typing import Any

from .config import FEEDBACK_LOG_PATH, INTERACTION_LOG_PATH, QUERY_LOG_PATH
from .models import SearchResult, utc_now_iso
from .utils import clean_text, stable_id


STOPWORDS = {
    "acaba",
    "ama",
    "bir",
    "bu",
    "da",
    "de",
    "detay",
    "detaylı",
    "fakülte",
    "fakültenin",
    "için",
    "hakkında",
    "ile",
    "bilgi",
    "bilgileri",
    "güncel",
    "lütfen",
    "mı",
    "mi",
    "misiniz",
    "mu",
    "mü",
    "nedir",
    "nasıl",
    "nelerdir",
    "programı",
    "ve",
    "veya",
    "var",
    "verir",
    "veriniz",
    "yok",
}

DOMAIN_SYNONYMS = {
    "akademik": ["akademik personel", "öğretim elemanı", "öğretim üyesi"],
    "ara": ["vize", "ara sınav", "sınav programı"],
    "bölüm": [
        "bölümler",
        "iktisat",
        "işletme",
        "siyaset bilimi",
        "kamu yönetimi",
        "uluslararası ilişkiler",
        "sağlık yönetimi",
        "yönetim bilişim sistemleri",
        "elektronik ticaret",
    ],
    "bölümleri": [
        "bölüm",
        "iktisat",
        "işletme",
        "siyaset bilimi",
        "kamu yönetimi",
        "uluslararası ilişkiler",
        "sağlık yönetimi",
        "yönetim bilişim sistemleri",
        "elektronik ticaret",
    ],
    "bölümler": ["bölüm", "program", "anabilim dalı"],
    "ders": ["ders programı", "müfredat", "bologna"],
    "duyuru": ["duyurular", "ilan"],
    "duyurular": ["duyuru", "ilan"],
    "e-posta": ["email", "mail", "iletişim"],
    "email": ["e-posta", "mail", "iletişim"],
    "etkinlik": ["etkinlikler", "faaliyet"],
    "final": ["yarıyıl sonu", "sınav programı"],
    "haber": ["haberler"],
    "iletişim": ["adres", "telefon", "e-posta", "email", "mail"],
    "mail": ["e-posta", "email", "iletişim"],
    "personel": ["akademik personel", "idari personel", "öğretim elemanı"],
    "sınav": ["vize", "final", "bütünleme", "mazeret", "sınav programı"],
    "telefon": ["iletişim", "adres", "e-posta"],
    "vize": ["ara sınav", "sınav programı"],
}


@dataclass
class InteractionSummary:
    id: str
    created_at: str
    query: str
    answer: str
    status: str
    source_urls: list[str]
    scores: list[float]
    keywords: list[str]


def extract_keywords(query: str, limit: int = 8) -> list[str]:
    tokens = [
        token.lower()
        for token in re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü0-9]{3,}", query)
        if token.lower() not in STOPWORDS
    ]
    return [token for token, _ in Counter(tokens).most_common(limit)]


def log_query(
    query: str,
    results: list[SearchResult],
    path: Path = QUERY_LOG_PATH,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "created_at": utc_now_iso(),
        "query": query,
        "keywords": extract_keywords(query),
        "result_urls": [result.chunk.url for result in results],
        "scores": [round(result.score, 6) for result in results],
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def expand_query(query: str, path: Path = QUERY_LOG_PATH) -> str:
    query = clean_text(query)
    keywords = extract_keywords(query)
    additions: list[str] = []

    for keyword in keywords:
        additions.extend(DOMAIN_SYNONYMS.get(keyword.lower(), []))

    additions.extend(_learned_related_keywords(keywords, path))
    unique_additions: list[str] = []
    for addition in additions:
        addition = clean_text(addition)
        if addition and addition.lower() not in query.lower() and addition not in unique_additions:
            unique_additions.append(addition)

    if not unique_additions:
        return query
    return f"{query} {' '.join(unique_additions[:12])}"


def log_interaction(
    query: str,
    answer: str,
    results: list[SearchResult],
    status: str,
    path: Path = INTERACTION_LOG_PATH,
) -> InteractionSummary:
    path.parent.mkdir(parents=True, exist_ok=True)
    source_urls = _unique_urls(results)
    created_at = utc_now_iso()
    interaction_id = stable_id(created_at, query, answer[:160])
    summary = InteractionSummary(
        id=interaction_id,
        created_at=created_at,
        query=query,
        answer=answer,
        status=status,
        source_urls=source_urls,
        scores=[round(result.score, 6) for result in results],
        keywords=extract_keywords(query),
    )
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(asdict(summary), ensure_ascii=False) + "\n")
    return summary


def log_feedback(
    interaction_id: str,
    rating: str,
    comment: str = "",
    path: Path = FEEDBACK_LOG_PATH,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "created_at": utc_now_iso(),
        "interaction_id": clean_text(interaction_id),
        "rating": clean_text(rating).lower(),
        "comment": clean_text(comment)[:600],
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def learning_summary(path: Path = QUERY_LOG_PATH) -> dict[str, Any]:
    records = _read_jsonl(path, limit=500)
    keyword_counter: Counter[str] = Counter()
    fallback_count = 0
    for record in records:
        keyword_counter.update(
            keyword for keyword in record.get("keywords", []) if keyword not in STOPWORDS
        )
        if not record.get("result_urls"):
            fallback_count += 1
    return {
        "query_count": len(records),
        "fallback_count": fallback_count,
        "top_keywords": keyword_counter.most_common(12),
    }


def _learned_related_keywords(keywords: list[str], path: Path) -> list[str]:
    if not keywords:
        return []

    keyword_set = set(keywords)
    counter: Counter[str] = Counter()
    for record in _read_jsonl(path, limit=300):
        record_keywords = set(record.get("keywords", []))
        if len(keyword_set & record_keywords) >= 2:
            counter.update(record_keywords - keyword_set)

    return [keyword for keyword, _ in counter.most_common(6)]


def _read_jsonl(path: Path, limit: int) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records[-limit:]


def _unique_urls(results: list[SearchResult]) -> list[str]:
    urls: list[str] = []
    for result in results:
        if result.chunk.url not in urls:
            urls.append(result.chunk.url)
    return urls
