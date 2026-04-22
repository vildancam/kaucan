from __future__ import annotations

from urllib.parse import urlparse

from .config import Settings
from .models import Chunk, PageDocument
from .utils import clean_text, stable_id


def chunk_documents(
    documents: list[PageDocument],
    settings: Settings | None = None,
) -> list[Chunk]:
    active_settings = settings or Settings()
    chunks: list[Chunk] = []

    for document in documents:
        content = _content_for_index(document)
        if not clean_text(content):
            continue

        title = _effective_title(document)
        for ordinal, text in enumerate(
            split_text(
                content,
                max_chars=active_settings.chunk_size,
                overlap=active_settings.chunk_overlap,
            )
        ):
            chunks.append(
                Chunk(
                    id=stable_id(document.url, str(ordinal), text[:80]),
                    url=document.url,
                    title=title,
                    text=text,
                    ordinal=ordinal,
                    metadata={
                        "content_type": document.content_type,
                        **document.metadata,
                    },
                )
            )

    return chunks


def _effective_title(document: PageDocument) -> str:
    title = clean_text(document.title)
    if title and title.lower() not in {"kafkas üniversitesi-yeni", "kafkas üniversitesi"}:
        return title
    first_line = next(
        (clean_text(line) for line in document.content.splitlines() if clean_text(line)),
        "",
    )
    return first_line or title or document.url


def _content_for_index(document: PageDocument) -> str:
    lines = [line for line in document.content.splitlines() if clean_text(line)]
    if _keep_link_blocks(document.url):
        lines.extend(_department_link_blocks(document.links))
    if _keep_link_blocks(document.url):
        return "\n".join(lines)
    return "\n".join(line for line in lines if not line.startswith("Bağlantı:"))


def _keep_link_blocks(url: str) -> bool:
    normalized = url.rstrip("/").lower()
    return normalized in {
        "https://kafkas.edu.tr/iibf",
        "https://kafkas.edu.tr/iibf/tr",
        "https://kafkas.edu.tr/iibf/en",
    } or normalized.endswith("/tumduyurular2") or normalized.endswith("/tumhaberler") or normalized.endswith(
        "/tumetkinlikler2"
    )


DEPARTMENT_LINK_LABELS = {
    "/iibfikt": "İktisat",
    "/iibfisletme": "İşletme",
    "/iibfsbky": "Siyaset Bilimi ve Kamu Yönetimi",
    "/iibfsbui": "Siyaset Bilimi ve Uluslararası İlişkiler",
    "/iibfutl": "Uluslararası Ticaret ve Lojistik",
    "/iibfsh": "Sosyal Hizmet",
    "/iibfybs": "Yönetim Bilişim Sistemleri",
    "/iibfety": "Elektronik Ticaret ve Yönetimi",
}


def _department_link_blocks(links: list[str]) -> list[str]:
    blocks: list[str] = []
    for link in links:
        path = urlparse(link).path.rstrip("/").lower()
        for prefix, label in DEPARTMENT_LINK_LABELS.items():
            if path == prefix or path.startswith(prefix + "/"):
                block = f"Bağlantı: {label} Bölümü | URL: {link}"
                if block not in blocks:
                    blocks.append(block)
    return blocks


def split_text(text: str, max_chars: int = 1200, overlap: int = 180) -> list[str]:
    paragraphs = [clean_text(part) for part in text.splitlines() if clean_text(part)]
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        if len(paragraph) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(_split_long_paragraph(paragraph, max_chars, overlap))
            continue

        candidate = f"{current}\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= max_chars:
            current = candidate
            continue

        if current:
            chunks.append(current)
        current = _with_overlap(current, paragraph, max_chars, overlap)

    if current:
        chunks.append(current)

    return chunks


def _split_long_paragraph(text: str, max_chars: int, overlap: int) -> list[str]:
    parts: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        parts.append(text[start:end].strip())
        if end == len(text):
            break
        start = max(0, end - overlap)
    return [part for part in parts if part]


def _with_overlap(previous: str, paragraph: str, max_chars: int, overlap: int) -> str:
    tail = previous[-overlap:].strip() if overlap > 0 else ""
    candidate = f"{tail}\n{paragraph}".strip() if tail else paragraph
    return candidate[-max_chars:].strip()
