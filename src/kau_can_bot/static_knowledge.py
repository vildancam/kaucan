from __future__ import annotations

import json
from functools import lru_cache
from typing import Dict, List, Optional

from .config import DATA_DIR
from .models import PageDocument
from .query_normalizer import normalize_for_matching
from .utils import clean_text, stable_id


DORMITORIES_PATH = DATA_DIR / "dormitories_kars.json"
TRANSPORT_PATH = DATA_DIR / "transport_kars.json"
CITY_PATH = DATA_DIR / "kars_city.json"


@lru_cache(maxsize=1)
def load_dormitories() -> Dict[str, object]:
    return _load_json_file(DORMITORIES_PATH)


@lru_cache(maxsize=1)
def load_transport_network() -> Dict[str, object]:
    return _load_json_file(TRANSPORT_PATH)


@lru_cache(maxsize=1)
def load_city_entries() -> Dict[str, object]:
    return _load_json_file(CITY_PATH)


def build_local_knowledge_documents() -> List[PageDocument]:
    documents: List[PageDocument] = []

    dormitory_data = load_dormitories()
    for entry in dormitory_data.get("entries", []):
        if not isinstance(entry, dict):
            continue
        primary_url = _primary_source_url(entry)
        lines = [
            f"Yurt adı: {entry.get('name', '')}",
            f"Tür: {entry.get('type', '')}",
            f"Cinsiyet: {entry.get('gender', '')}",
            f"İlçe: {entry.get('district', '')}",
            f"Adres: {entry.get('address', '')}",
            f"Telefon: {entry.get('phone', '')}",
            f"Kapasite: {entry.get('capacity', '')}",
            f"Oda bilgisi: {entry.get('room_capacity', '')}",
            f"Fiyat bilgisi: {entry.get('price_info', '')}",
            f"İnternet bilgisi: {entry.get('internet_info', '')}",
            f"Başvuru bilgisi: {entry.get('application_info', '')}",
            f"Üniversiteye uzaklık: {entry.get('distance_to_kau', '')}",
        ]
        documents.append(
            PageDocument(
                url=primary_url,
                title=str(entry.get("name", "Kars Yurdu")),
                content="\n".join(line for line in lines if clean_text(line.split(":", 1)[-1])),
                content_type="application/json",
                links=list(entry.get("source_urls", [])),
                metadata={
                    "source_type": "dormitory",
                    "category": "accommodation",
                    "fetched_at": entry.get("last_verified", ""),
                },
            )
        )

    transport_data = load_transport_network().get("network", {})
    route_names = transport_data.get("route_names", [])
    if route_names:
        documents.append(
            PageDocument(
                url=str((transport_data.get("source_urls") or ["https://www.kars.bel.tr"])[0]),
                title="Kars Kampüs Ulaşım Hatları",
                content="\n".join(
                    [
                        "Hatlar: " + ", ".join(route_names),
                        "Gidiş durakları: " + " | ".join(transport_data.get("outbound_stops", [])),
                        "Dönüş durakları: " + " | ".join(transport_data.get("inbound_stops", [])),
                    ]
                ),
                content_type="application/json",
                links=list(transport_data.get("source_urls", [])),
                metadata={
                    "source_type": "transport",
                    "category": "transport",
                    "fetched_at": load_transport_network().get("updated_at", ""),
                },
            )
        )

    city_data = load_city_entries()
    for entry in city_data.get("entries", []):
        if not isinstance(entry, dict):
            continue
        documents.append(
            PageDocument(
                url=str(entry.get("source_url", "")),
                title=str(entry.get("title", "Kars")),
                content="\n".join(
                    line
                    for line in (
                        entry.get("summary", ""),
                        entry.get("student_tip", ""),
                        f"Kategori: {entry.get('category', '')}",
                    )
                    if clean_text(line)
                ),
                content_type="application/json",
                links=[str(entry.get("source_url", ""))],
                metadata={
                    "source_type": "city",
                    "category": entry.get("category", ""),
                    "fetched_at": city_data.get("updated_at", ""),
                },
            )
        )

    return [
        document
        for document in documents
        if clean_text(document.url) and clean_text(document.content)
    ]


def search_dormitories(normalized_query: str) -> List[dict]:
    query_key = normalize_for_matching(normalized_query)
    matches: List[dict] = []

    wants_kyk = any(term in query_key for term in ("kyk", "kredi yurtlar", "devlet yurdu"))
    wants_private = "özel" in query_key or "tugva" in query_key
    wants_female = "kiz" in query_key
    wants_male = "erkek" in query_key

    for entry in load_dormitories().get("entries", []):
        if not isinstance(entry, dict):
            continue

        haystack = normalize_for_matching(
            " ".join(
                str(entry.get(field, ""))
                for field in ("name", "type", "gender", "district", "address")
            )
        )

        score = 0
        if wants_kyk and entry.get("type") == "kyk":
            score += 5
        if wants_private and entry.get("type") == "private":
            score += 5
        if wants_female and entry.get("gender") in {"female", "mixed"}:
            score += 3
        if wants_male and entry.get("gender") in {"male", "mixed"}:
            score += 3

        tokens = [token for token in query_key.split() if len(token) > 2]
        score += sum(1 for token in tokens if token in haystack)

        if score > 0:
            entry_copy = dict(entry)
            entry_copy["_score"] = score
            matches.append(entry_copy)

    matches.sort(key=lambda item: item.get("_score", 0), reverse=True)
    return matches


def search_city_places(normalized_query: str) -> List[dict]:
    query_key = normalize_for_matching(normalized_query)
    matches: List[dict] = []

    for entry in load_city_entries().get("entries", []):
        if not isinstance(entry, dict):
            continue
        haystack = normalize_for_matching(
            " ".join(str(entry.get(field, "")) for field in ("title", "summary", "student_tip", "category"))
        )
        score = sum(1 for token in query_key.split() if len(token) > 2 and token in haystack)
        if score > 0:
            copy = dict(entry)
            copy["_score"] = score
            matches.append(copy)

    matches.sort(key=lambda item: item.get("_score", 0), reverse=True)
    return matches


def get_transport_network() -> Dict[str, object]:
    return load_transport_network().get("network", {})


def _primary_source_url(entry: dict) -> str:
    source_urls = entry.get("source_urls", [])
    if isinstance(source_urls, list):
        for url in source_urls:
            if clean_text(str(url)):
                return str(url)
    return f"https://www.kafkas.edu.tr/knowledge/{stable_id(str(entry.get('name', '')), str(entry.get('id', '')))}"


def _load_json_file(path) -> Dict[str, object]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
