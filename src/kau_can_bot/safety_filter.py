from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .query_normalizer import is_smalltalk_query
from .safety import has_harmful_intent, has_inappropriate_language, has_targeted_abuse
from .user_session import increment_violation, reset_violation
from .utils import clean_text


@dataclass(frozen=True)
class SafetyDecision:
    blocked: bool
    status: str = ""
    answer: str = ""


def apply_safety_filter(query: str, language: str, client_id: str = "") -> Optional[SafetyDecision]:
    cleaned = clean_text(query)
    if not cleaned or is_smalltalk_query(cleaned):
        return None

    if has_harmful_intent(cleaned):
        return SafetyDecision(
            blocked=True,
            status="blocked_safety",
            answer=_text_for_language(
                language,
                "Bu talebe yardımcı olamam.",
                "I cannot help with that request.",
            ),
        )

    if has_targeted_abuse(cleaned):
        if not clean_text(client_id):
            return None
        count = increment_violation(client_id, "abuse")
        return SafetyDecision(
            blocked=True,
            status="blocked_abuse",
            answer=(
                "Bu şekilde devam ederse sağlıklı bir destek sunamam. Lütfen sorunuzu uygun bir dille yeniden yazın."
                if count > 1
                else "Lütfen daha saygılı bir dil kullanalım. Size yardımcı olmak isterim, ancak hakaret veya küfür içeren mesajlara yanıt veremem."
            ),
        )

    if has_inappropriate_language(cleaned):
        if not clean_text(client_id):
            return None
        count = increment_violation(client_id, "language")
        return SafetyDecision(
            blocked=True,
            status="blocked_language",
            answer=(
                "Bu şekilde devam ederse sağlıklı bir destek sunamam. Lütfen sorunuzu uygun bir dille yeniden yazın."
                if count > 1
                else "Mesajınızdaki bazı ifadeler uygun değil. Sorunuzu daha açık ve saygılı bir şekilde yazarsanız yardımcı olabilirim."
            ),
        )

    if clean_text(client_id):
        reset_violation(client_id, "abuse")
        reset_violation(client_id, "language")
    return None


def _text_for_language(language: str, tr_text: str, en_text: str) -> str:
    return en_text if language == "en" else tr_text
