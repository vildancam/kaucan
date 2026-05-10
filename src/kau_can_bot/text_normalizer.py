from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Tuple

from .query_normalizer import normalize_for_matching, normalize_query
from .utils import clean_text


FILLER_TERMS = {
    "abi",
    "abla",
    "la",
    "lan",
    "ya",
    "yaa",
    "kanka",
    "reis",
    "hocam",
}

PHRASE_EXPANSIONS: Dict[str, str] = {
    "sss": "sıkça sorulan sorular",
    "kyk": "kredi yurtlar kurumu",
    "üni": "üniversite",
    "uni": "üniversite",
    "fak": "fakülte",
    "fakulte": "fakülte",
    "otobus": "otobüs",
    "gidiyo": "gider",
    "gidio": "gider",
    "gidiyr": "gider",
    "prog": "programı",
    "mail": "e-posta",
}

DISPLAY_REPLACEMENTS: Dict[str, str] = {
    "kiz": "kız",
    "ogrenci": "öğrenci",
    "otobus": "otobüs",
    "universite": "üniversite",
    "fakulte": "fakülte",
    "ulasim": "ulaşım",
    "iletisim": "iletişim",
    "sikca": "sıkça",
    "yuzde": "yüzde",
}

REGEX_REPLACEMENTS: Tuple[Tuple[str, str], ...] = (
    (r"\bhangi\s+otobus\b", "hangi belediye otobüsü"),
    (r"\botobus\s+saatleri\b", "otobüs saatleri"),
    (r"\bkyk\s+kiz\s+yurdu\b", "kredi yurtlar kurumu kız öğrenci yurdu"),
    (r"\bkyk\s+erkek\s+yurdu\b", "kredi yurtlar kurumu erkek öğrenci yurdu"),
    (r"\bkredi yurtlar kurumu\s+kiz\s+yurdu\b", "kredi yurtlar kurumu kız öğrenci yurdu"),
    (r"\bkredi yurtlar kurumu\s+erkek\s+yurdu\b", "kredi yurtlar kurumu erkek öğrenci yurdu"),
    (r"\bdevlet\s+yurdu\b", "kredi yurtlar kurumu öğrenci yurdu"),
    (r"\biibf\s+sss\b", "iktisadi ve idari bilimler fakültesi sıkça sorulan sorular"),
    (r"\bfakulteye\s+hangi\s+otobus\s+gid\w+\b", "fakülteye hangi belediye otobüsü gider"),
)


@dataclass(frozen=True)
class NormalizedText:
    original: str
    cleaned: str
    normalized: str
    normalized_for_matching: str


def normalize_user_message(text: str) -> NormalizedText:
    cleaned = clean_text(text)
    compact = _strip_noisy_punctuation(cleaned)
    normalized = normalize_query(compact) or compact
    normalized = _expand_phrases(normalized)
    normalized = _remove_fillers(normalized)
    normalized = _apply_regex_replacements(normalized)
    normalized = _restore_display_turkish(normalized)
    normalized = clean_text(normalized)
    return NormalizedText(
        original=text,
        cleaned=cleaned,
        normalized=normalized,
        normalized_for_matching=normalize_for_matching(normalized),
    )


def _strip_noisy_punctuation(text: str) -> str:
    value = text.lower()
    value = re.sub(r"([!?.,])\1+", r"\1", value)
    value = re.sub(r"[_~`]+", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _expand_phrases(text: str) -> str:
    working = f" {text} "
    for raw, expanded in PHRASE_EXPANSIONS.items():
        working = re.sub(
            rf"(?<!\w){re.escape(raw)}(?!\w)",
            expanded,
            working,
            flags=re.IGNORECASE,
        )
    return clean_text(working)


def _remove_fillers(text: str) -> str:
    tokens = []
    for token in text.split():
        if normalize_for_matching(token) in FILLER_TERMS:
            continue
        tokens.append(token)
    return " ".join(tokens)


def _apply_regex_replacements(text: str) -> str:
    working = text
    for pattern, replacement in REGEX_REPLACEMENTS:
        working = re.sub(pattern, replacement, working, flags=re.IGNORECASE)
    return working


def _restore_display_turkish(text: str) -> str:
    working = f" {text} "
    for raw, display in DISPLAY_REPLACEMENTS.items():
        working = re.sub(
            rf"(?<!\w){re.escape(raw)}(?!\w)",
            display,
            working,
            flags=re.IGNORECASE,
        )
    return clean_text(working)
