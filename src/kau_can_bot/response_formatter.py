from __future__ import annotations

from typing import Iterable, List

from .utils import clean_text


def make_bullets(lines: Iterable[str]) -> str:
    cleaned = [clean_text(line) for line in lines if clean_text(line)]
    return "\n".join(f"- {line}" for line in cleaned)


def maybe_prefix_with_address(answer: str, preferred_address: str = "") -> str:
    text = clean_text(answer)
    name = clean_text(preferred_address)
    if not text or not name:
        return answer
    if text.startswith(name):
        return answer
    return f"{name}, {text}"


def join_sections(sections: Iterable[str]) -> str:
    cleaned: List[str] = [section.strip() for section in sections if clean_text(section)]
    return "\n\n".join(cleaned)
