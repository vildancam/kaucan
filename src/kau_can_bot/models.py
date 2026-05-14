from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class PageDocument:
    url: str
    title: str
    content: str
    content_type: str
    fetched_at: str = field(default_factory=utc_now_iso)
    links: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PageDocument":
        return cls(**data)


@dataclass
class Chunk:
    id: str
    url: str
    title: str
    text: str
    ordinal: int
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Chunk":
        return cls(**data)


@dataclass
class SearchResult:
    chunk: Chunk
    score: float


@dataclass
class UiAction:
    label: str
    url: str
    kind: str = "link"


@dataclass
class UiCard:
    title: str
    body: str = ""
    meta: str = ""
    image_url: str = ""
    alt_text: str = ""
    url: str = ""
    actions: List[UiAction] = field(default_factory=list)


@dataclass
class UiTable:
    columns: List[str] = field(default_factory=list)
    rows: List[List[str]] = field(default_factory=list)
    caption: str = ""


@dataclass
class AssistantResponse:
    answer: str
    sources: List[SearchResult] = field(default_factory=list)
    interaction_id: Optional[str] = None
    status: str = "ok"
    show_google_button: bool = False
    actions: List[UiAction] = field(default_factory=list)
    cards: List[UiCard] = field(default_factory=list)
    table: Optional[UiTable] = None
    normalized_query: str = ""
