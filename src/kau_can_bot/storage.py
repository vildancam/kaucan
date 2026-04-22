from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .models import PageDocument


def save_documents(path: Path, documents: Iterable[PageDocument]) -> int:
    count = 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for document in documents:
            handle.write(json.dumps(document.to_dict(), ensure_ascii=False) + "\n")
            count += 1
    return count


def load_documents(path: Path) -> list[PageDocument]:
    if not path.exists():
        return []

    documents: list[PageDocument] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                documents.append(PageDocument.from_dict(json.loads(line)))
    return documents
