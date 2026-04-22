from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from .chunker import chunk_documents
from .config import INDEX_PATH, Settings
from .models import Chunk, PageDocument, SearchResult
from .utils import clean_text


class SearchIndex:
    def __init__(
        self,
        vectorizer: TfidfVectorizer,
        matrix,
        chunks: list[Chunk],
    ) -> None:
        self.vectorizer = vectorizer
        self.matrix = matrix
        self.chunks = chunks

    @classmethod
    def build(
        cls,
        documents: list[PageDocument],
        settings: Settings | None = None,
    ) -> "SearchIndex":
        active_settings = settings or Settings()
        chunks = chunk_documents(documents, active_settings)
        texts = [_searchable_text(chunk) for chunk in chunks]

        if not texts:
            raise ValueError("İndekslenecek metin bulunamadı.")

        vectorizer = TfidfVectorizer(
            lowercase=True,
            strip_accents=None,
            analyzer="word",
            ngram_range=(1, 2),
            min_df=1,
            max_features=120_000,
            sublinear_tf=True,
            norm="l2",
        )
        matrix = vectorizer.fit_transform(texts)
        return cls(vectorizer=vectorizer, matrix=matrix, chunks=chunks)

    def save(self, path: Path = INDEX_PATH) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "vectorizer": self.vectorizer,
                "matrix": self.matrix,
                "chunks": [chunk.to_dict() for chunk in self.chunks],
            },
            path,
        )

    @classmethod
    def load(cls, path: Path = INDEX_PATH) -> "SearchIndex":
        payload = joblib.load(path)
        return cls(
            vectorizer=payload["vectorizer"],
            matrix=payload["matrix"],
            chunks=[Chunk.from_dict(item) for item in payload["chunks"]],
        )

    def search(self, query: str, top_k: int = 3) -> list[SearchResult]:
        query = clean_text(query)
        if not query or not self.chunks:
            return []

        query_vector = self.vectorizer.transform([query])
        semantic_scores = (self.matrix @ query_vector.T).toarray().ravel()
        direct_scores = np.array(
            [_direct_match_score(query, chunk) for chunk in self.chunks],
            dtype=float,
        )
        scope_scores = np.array(
            [_faculty_scope_score(chunk) for chunk in self.chunks],
            dtype=float,
        ) if _query_mentions_faculty(query) else np.zeros(len(self.chunks), dtype=float)
        scores = (0.72 * semantic_scores) + (0.20 * direct_scores) + (0.08 * scope_scores)
        top_indices = np.argsort(scores)[::-1][:top_k]

        return [
            SearchResult(chunk=self.chunks[index], score=float(scores[index]))
            for index in top_indices
            if scores[index] > 0
        ]


def _searchable_text(chunk: Chunk) -> str:
    return f"{chunk.title}\n{chunk.text}"


def _direct_match_score(query: str, chunk: Chunk) -> float:
    terms = [_stem_token(term) for term in query.lower().split() if len(term) > 2]
    if not terms:
        return 0.0

    haystack = " ".join(_stem_token(term) for term in f"{chunk.title} {chunk.text}".lower().split())
    hits = sum(1 for term in terms if term in haystack)
    return hits / len(terms)


def _query_mentions_faculty(query: str) -> bool:
    normalized = query.lower()
    return any(
        term in normalized
        for term in ("iibf", "i̇ibf", "iktisadi", "idari bilimler", "fakülte")
    )


def _faculty_scope_score(chunk: Chunk) -> float:
    haystack = f"{chunk.url} {chunk.title} {chunk.text}".lower()
    if "/iibf" in haystack:
        return 1.0
    if "iktisadi ve idari bilimler" in haystack or "faculty of economics" in haystack:
        return 0.7
    if "iibf" in haystack or "i̇ibf" in haystack:
        return 0.6
    return 0.0


def _stem_token(token: str) -> str:
    token = token.strip(".,:;!?()[]{}\"'’`").lower()
    suffixes = (
        "lerinin",
        "larının",
        "lerden",
        "lardan",
        "lerin",
        "ların",
        "leri",
        "ları",
        "nin",
        "nın",
        "nun",
        "nün",
        "den",
        "dan",
        "ten",
        "tan",
        "ler",
        "lar",
        "in",
        "ın",
        "un",
        "ün",
    )
    for suffix in suffixes:
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            return token[: -len(suffix)]
    return token
