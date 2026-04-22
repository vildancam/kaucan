from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class PageDocument:
    url: str
    title: str
    content: str
    content_type: str
    fetched_at: str = field(default_factory=utc_now_iso)
    links: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PageDocument":
        return cls(**data)


@dataclass
class Chunk:
    id: str
    url: str
    title: str
    text: str
    ordinal: int
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Chunk":
        return cls(**data)


@dataclass
class SearchResult:
    chunk: Chunk
    score: float


@dataclass
class AssistantResponse:
    answer: str
    sources: list[SearchResult] = field(default_factory=list)
    interaction_id: str | None = None
    status: str = "ok"
