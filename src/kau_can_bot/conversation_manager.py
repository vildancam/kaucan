from __future__ import annotations

import re
from typing import Optional

from .document_generator import generate_document_response
from .models import AssistantResponse
from .query_normalizer import normalize_for_matching
from .source_manager import build_source_results
from .user_session import (
    disable_addressing,
    get_session_state,
    remember_disallowed_name,
    set_preferred_address,
    set_user_name_allowed,
)
from .utils import clean_text


_ADDRESS_VALUE_PATTERN = r"[A-Za-zÇĞİÖŞÜçğıöşü0-9' -]{2,30}"
_EXCLUDED_REJECTION_WORDS = {
    "bu",
    "su",
    "şu",
    "o",
    "oyle",
    "öyle",
    "boyle",
    "böyle",
    "dogru",
    "doğru",
    "yanlis",
    "yanlış",
    "cevap",
    "metin",
    "dilekce",
    "dilekçe",
    "bilgi",
    "konu",
}


def normalize_tr(text: str) -> str:
    return normalize_for_matching(clean_text(text))


def is_name_rejection(text: str, session: Optional[dict] = None) -> bool:
    normalized = normalize_tr(text)
    state = session or {}
    return bool(_extract_disallowed_name(clean_text(text), normalized, state))


def is_no_name_usage(text: str) -> bool:
    normalized = normalize_tr(text)
    return any(
        phrase in normalized
        for phrase in (
            "adimi kullanma",
            "adımı kullanma",
            "ismimi kullanma",
            "isim kullanma",
            "bana isimle hitap etme",
            "isimle hitap etme",
            "bana bu isimle hitap etme",
            "bu isimle hitap etme",
        )
    )


def detect_preferred_name(text: str) -> str:
    cleaned = clean_text(text)
    patterns = (
        rf"(?i)^\s*adim\s+({_ADDRESS_VALUE_PATTERN})\s*$",
        rf"(?i)^\s*adım\s+({_ADDRESS_VALUE_PATTERN})\s*$",
        rf"(?i)^\s*ismim\s+({_ADDRESS_VALUE_PATTERN})\s*$",
        rf"(?i)^\s*bana\s+({_ADDRESS_VALUE_PATTERN})\s+diye\s+hitap\s+et\s*$",
        rf"(?i)^\s*bana\s+({_ADDRESS_VALUE_PATTERN})\s+de\s*$",
        rf"(?i)^\s*bana\s+artik\s+({_ADDRESS_VALUE_PATTERN})\s+de\s*$",
        rf"(?i)^\s*bana\s+artık\s+({_ADDRESS_VALUE_PATTERN})\s+de\s*$",
        rf"(?i)^\s*bundan\s+sonra\s+({_ADDRESS_VALUE_PATTERN})\s+de\s*$",
        rf"(?i)^\s*beni\s+({_ADDRESS_VALUE_PATTERN})\s+diye\s+cagir\s*$",
        rf"(?i)^\s*beni\s+({_ADDRESS_VALUE_PATTERN})\s+diye\s+çağır\s*$",
    )
    for pattern in patterns:
        match = re.search(pattern, cleaned)
        if not match:
            continue
        preferred = _clean_address_value(match.group(1))
        if preferred and preferred.lower() not in _EXCLUDED_REJECTION_WORDS:
            return preferred
    return ""


def is_document_request(text: str) -> bool:
    normalized = normalize_tr(text)
    has_document_term = any(
        term in normalized
        for term in (
            "dilekce",
            "dilekçe",
            "sablon",
            "şablon",
            "mail",
            "e posta",
            "e-posta",
            "email",
            "resmi metin",
            "kurumsal cevap",
            "duyuru metni",
            "afis metni",
            "afiş metni",
            "metin",
            "cevap",
        )
    )
    has_request_term = any(
        term in normalized
        for term in ("yaz", "olustur", "oluştur", "hazirla", "hazırla", "ver", "goster", "göster")
    )
    return has_document_term and has_request_term


def is_revision_request(text: str) -> bool:
    normalized = normalize_tr(text)
    return any(
        phrase in normalized
        for phrase in (
            "daha resmi",
            "resmi olsun",
            "kurumsal yap",
            "akademik yap",
            "daha samimi",
            "samimi olsun",
            "daha kisa",
            "kisa yaz",
            "bunu kisa yaz",
            "daha uzun",
            "uzun yaz",
            "detaylandir",
            "detaylandır",
            "aciklayici",
            "açıklayıcı",
            "tekrar yaz",
            "yeniden yaz",
            "bunu duzelt",
            "bunu düzelt",
            "yanlis oldu",
            "yanlış oldu",
            "begenmedim",
            "beğenmedim",
            "olmadi",
            "olmadı",
            "bunu cikar",
            "bunu çıkar",
            "sunu cikar",
            "şunu çıkar",
            "bunu ekle",
            "link ekle",
            "emoji ekle",
            "daha guzel yaz",
            "daha güzel yaz",
            "tekrar etmeden yaz",
        )
    )


def generate_ders_ekle_birak_dilekcesi() -> str:
    generated = generate_document_response(
        "ders ekle bırak için bana bir dilekçe şablonu oluştur",
        "tr",
        tone="formal",
        concise=False,
        remove_name=True,
    )
    return generated.answer if generated is not None else ""


def handle_pre_router(message: str, session: Optional[dict], language: str = "tr", client_id: str = "") -> Optional[AssistantResponse]:
    manager = ConversationManager()
    state = session or get_session_state(client_id)
    return manager.route(message, language=language, client_id=client_id, state_override=state)


class ConversationManager:
    def route(
        self,
        query: str,
        language: str,
        client_id: str = "",
        state_override: Optional[dict] = None,
    ) -> Optional[AssistantResponse]:
        cleaned = clean_text(query)
        normalized = normalize_tr(cleaned)
        state = state_override if state_override is not None else (get_session_state(client_id) if clean_text(client_id) else {})

        response = self._handle_address_correction(cleaned, normalized, state, client_id)
        if response is not None:
            return response

        response = self._handle_address_preference(cleaned, normalized, client_id)
        if response is not None:
            return response

        response = self._handle_revision_request(cleaned, normalized, state, language, client_id)
        if response is not None:
            return response

        response = self._handle_document_request(cleaned, language, state)
        if response is not None:
            return response

        response = self._handle_smalltalk(cleaned, normalized)
        if response is not None:
            return response

        return None

    def _handle_address_correction(
        self,
        query: str,
        normalized: str,
        state: dict,
        client_id: str,
    ) -> Optional[AssistantResponse]:
        if not clean_text(client_id):
            return None

        generic_disable = is_no_name_usage(query) or any(
            phrase in normalized for phrase in ("bana oyle deme", "bana boyle deme")
        )
        name = _extract_disallowed_name(query, normalized, state)

        if not generic_disable and not name:
            return None

        if name:
            remember_disallowed_name(client_id, name)
            if normalize_tr(clean_text(state.get("preferred_address", ""))) == normalize_tr(name):
                disable_addressing(client_id)
        else:
            set_user_name_allowed(client_id, False)

        correction_lines = ["Anladım, o isimle hitap etmeyeceğim."]
        if clean_text(state.get("last_document_type", "")) or clean_text(state.get("last_bot_response", "")):
            correction_lines.append("Gerekli alanlarda [Ad Soyad] yer tutucusunu kullanacağım.")
        return AssistantResponse(
            answer=" ".join(correction_lines),
            status="address_correction",
        )

    def _handle_address_preference(
        self,
        query: str,
        normalized: str,
        client_id: str,
    ) -> Optional[AssistantResponse]:
        if not clean_text(client_id):
            return None

        if any(phrase in normalized for phrase in ("hitap kullanma", "isimsiz hitap", "isimle hitap etme")):
            disable_addressing(client_id)
            return AssistantResponse(
                answer="Tabii, size isimsiz şekilde yardımcı olabilirim.",
                status="memory_saved",
            )

        preferred = detect_preferred_name(query)
        if preferred:
            set_preferred_address(client_id, preferred)
            return AssistantResponse(
                answer=f"Tabii, bundan sonra size {preferred} diye hitap edeceğim.",
                status="memory_saved",
            )
        return None

    def _handle_revision_request(
        self,
        query: str,
        normalized: str,
        state: dict,
        language: str,
        client_id: str,
    ) -> Optional[AssistantResponse]:
        if not is_revision_request(query):
            return None

        previous_text = str(state.get("last_bot_response", "") or "").strip()
        if not previous_text:
            return AssistantResponse(
                answer="Hangi metni düzenlememi istediğinizi belirtir misiniz?",
                status="clarification",
            )

        revision_kind = self._revision_kind(normalized)
        if revision_kind == "add_source":
            source_urls = [clean_text(item) for item in state.get("last_sources", []) if clean_text(item)]
            if not source_urls:
                return AssistantResponse(
                    answer="Önceki cevap için ekleyebileceğim doğrulanmış bir kaynak bağlantısı görünmüyor.",
                    status="clarification",
                )
            return AssistantResponse(
                answer="Önceki cevabın kaynak bağlantılarını ekledim.",
                status="revision",
                sources=build_source_results(
                    [{"title": f"Kaynak {index}", "url": url} for index, url in enumerate(source_urls, start=1)],
                    source_type="reference",
                ),
            )

        if revision_kind == "remove_phrase":
            phrase = self._extract_phrase_to_remove(query, normalized, state)
            if not phrase:
                return AssistantResponse(
                    answer="Hangi kelimeyi ya da hangi bölümü çıkarmamı istediğinizi belirtir misiniz?",
                    status="clarification",
                )
            updated_text = self._remove_phrase(previous_text, phrase)
            if updated_text == previous_text:
                return AssistantResponse(
                    answer="Belirttiğiniz ifadeyi önceki metinde net olarak bulamadım. Çıkarmamı istediğiniz kısmı aynen yazabilirsiniz.",
                    status="clarification",
                )
            return AssistantResponse(answer=updated_text, status="revision")

        document_prompt = clean_text(state.get("last_topic") or state.get("last_user_message"))
        last_document_type = clean_text(state.get("last_document_type"))
        if last_document_type:
            regenerated = generate_document_response(
                document_prompt,
                language,
                tone="institutional" if revision_kind == "formal" else "friendly" if revision_kind == "friendly" else "formal",
                concise=revision_kind == "shorten",
                remove_name=revision_kind == "remove_name" or not bool(state.get("user_name_allowed", True)),
            )
            if regenerated is not None:
                lead = {
                    "formal": "Önceki metni daha resmi biçimde yeniden düzenledim.",
                    "friendly": "Önceki metni daha samimi bir üslupla yeniden düzenledim.",
                    "shorten": "Önceki metni daha kısa hale getirdim.",
                    "lengthen": "Önceki metni biraz daha açıklayıcı hale getirdim.",
                    "rewrite": "Önceki metni yeniden düzenledim.",
                    "remove_name": "Metindeki isim kullanımını kaldırarak yeniden düzenledim.",
                }.get(revision_kind, "Önceki metni yeniden düzenledim.")
                answer = lead + "\n\n" + regenerated.answer
                if revision_kind == "lengthen":
                    answer = lead + "\n\n" + self._expand_text(regenerated.answer)
                return AssistantResponse(answer=answer, status="revision")

        if revision_kind == "formal":
            return AssistantResponse(answer=self._make_formal(previous_text), status="style_revision")
        if revision_kind == "friendly":
            return AssistantResponse(answer=self._make_friendly(previous_text), status="style_revision")
        if revision_kind == "shorten":
            return AssistantResponse(answer=self._shorten_text(previous_text), status="revision")
        if revision_kind == "lengthen":
            return AssistantResponse(answer=self._expand_text(previous_text), status="revision")
        if revision_kind == "remove_name":
            return AssistantResponse(answer=self._remove_name_like_prefix(previous_text), status="revision")

        return AssistantResponse(
            answer="Önceki mesajınızı düzenlemek istediğinizi anladım. Hangi kısmı değiştirmemi istersiniz?",
            status="clarification",
        )

    def _handle_document_request(self, query: str, language: str, state: dict) -> Optional[AssistantResponse]:
        if not is_document_request(query):
            return None
        document_response = generate_document_response(
            query,
            language,
            tone="formal",
            concise=False,
            remove_name=True,
        )
        if document_response is None:
            return None
        return AssistantResponse(
            answer=document_response.answer,
            status="document",
        )

    def _handle_smalltalk(self, query: str, normalized: str) -> Optional[AssistantResponse]:
        if normalized in {
            "tesekkur",
            "tesekkur ederim",
            "tesekkurler",
            "sag ol",
            "sagol",
            "eyvallah",
            "eyw",
        }:
            return AssistantResponse(
                answer="Rica ederim. İsterseniz devam edebiliriz.",
                status="smalltalk",
            )
        if normalized in {
            "gorusuruz",
            "gorusmek uzere",
            "görüşürüz",
            "hoşça kal",
            "hosca kal",
            "bye",
            "bb",
        }:
            return AssistantResponse(
                answer="Görüşmek üzere. İhtiyacınız olduğunda yine yardımcı olabilirim.",
                status="smalltalk",
            )
        return None

    def _revision_kind(self, normalized: str) -> str:
        if "link ekle" in normalized:
            return "add_source"
        if any(phrase in normalized for phrase in ("bunu cikar", "bunu çıkar", "sunu cikar", "şunu çıkar", "bu kelimeyi cikar", "bu kelimeyi çıkar")):
            return "remove_phrase"
        if any(phrase in normalized for phrase in ("ismi kaldir", "ismi kaldır", "ismi kullanma", "adimi kullanma")):
            return "remove_name"
        if any(phrase in normalized for phrase in ("daha resmi", "resmi olsun", "kurumsal yap", "akademik yap")):
            return "formal"
        if any(phrase in normalized for phrase in ("daha samimi", "samimi olsun")):
            return "friendly"
        if any(phrase in normalized for phrase in ("daha kisa", "kisa yaz", "bunu kisa yaz", "sadelestir", "sadeleştir")):
            return "shorten"
        if any(phrase in normalized for phrase in ("daha uzun", "uzun yaz", "detaylandir", "detaylandır", "aciklayici", "açıklayıcı")):
            return "lengthen"
        return "rewrite"

    def _extract_phrase_to_remove(self, query: str, normalized: str, state: dict) -> str:
        quoted = re.search(r"[\"“”']([^\"“”']{2,80})[\"“”']", query)
        if quoted:
            return clean_text(quoted.group(1))
        name = _extract_disallowed_name(query, normalized, state)
        if name:
            return name
        if any(phrase in normalized for phrase in ("ismi kaldir", "ismi kaldır")):
            return clean_text(state.get("preferred_address", "")) or clean_text(state.get("user_name", ""))
        return ""

    def _remove_phrase(self, text: str, phrase: str) -> str:
        if not clean_text(phrase):
            return text
        updated = re.sub(re.escape(phrase), "", text, flags=re.IGNORECASE)
        updated = re.sub(r"[ ]{2,}", " ", updated)
        updated = re.sub(r"\n{3,}", "\n\n", updated)
        return updated.strip()

    def _make_formal(self, text: str) -> str:
        updated = text
        replacements = (
            ("Merhaba,", "Sayın Yetkili,"),
            ("merhaba,", "Sayın Yetkili,"),
            ("rica ederim", "bilgilerinize sunarım"),
            ("İyi çalışmalar", "Gereğini bilgilerinize arz ederim."),
        )
        for old, new in replacements:
            updated = updated.replace(old, new)
        updated = re.sub(r"[😊🙂😉😄👍]+", "", updated)
        if "Sayın Yetkili" not in updated:
            updated = "Sayın Yetkili,\n\n" + updated
        return updated.strip()

    def _make_friendly(self, text: str) -> str:
        updated = text
        if not updated.startswith("Merhaba"):
            updated = "Merhaba,\n\n" + updated
        updated = updated.replace("Sayın Yetkili,", "Merhaba,")
        updated = updated.replace("Gereğini bilgilerinize arz ederim.", "Şimdiden teşekkür ederim.")
        return updated.strip()

    def _shorten_text(self, text: str) -> str:
        blocks = [clean_text(block) for block in str(text).split("\n\n") if clean_text(block)]
        if not blocks:
            return text
        if len(blocks) == 1:
            sentences = re.split(r"(?<=[.!?])\s+", blocks[0])
            compact = " ".join(sentence for sentence in sentences[:3] if clean_text(sentence))
            return clean_text(compact) or blocks[0]
        return "\n\n".join(blocks[: min(3, len(blocks))])

    def _expand_text(self, text: str) -> str:
        stripped = text.strip()
        if not stripped or "Not:" in stripped:
            return stripped
        return stripped + "\n\nNot: Gerekirse ilgili birim, tarih veya belge bilgisi eklenerek metin daha da özelleştirilebilir."

    def _remove_name_like_prefix(self, text: str) -> str:
        return re.sub(r"^[A-ZÇĞİÖŞÜa-zçğıöşü0-9' -]{2,25},\s*", "", text).strip()


def _clean_address_value(value: str) -> str:
    cleaned = clean_text(value)
    cleaned = re.sub(r"(?i)\bdiye hitap et\b", "", cleaned)
    cleaned = re.sub(r"(?i)\bdiye cagir\b", "", cleaned)
    cleaned = re.sub(r"(?i)\bdiye çağır\b", "", cleaned)
    cleaned = re.sub(r"(?i)\bde\b$", "", cleaned).strip()
    return clean_text(cleaned)


def _extract_disallowed_name(query: str, normalized: str, state: dict) -> str:
    patterns = (
        rf"(?i)\bbana\s+({_ADDRESS_VALUE_PATTERN})\s+deme\b",
        rf"(?i)\b({_ADDRESS_VALUE_PATTERN})\s+deme\b",
        rf"(?i)\bbeni\s+({_ADDRESS_VALUE_PATTERN})\s+diye\s+cagirma\b",
        rf"(?i)\bbeni\s+({_ADDRESS_VALUE_PATTERN})\s+diye\s+çağırma\b",
        rf"(?i)\badim\s+({_ADDRESS_VALUE_PATTERN})\s+degil\b",
        rf"(?i)\badım\s+({_ADDRESS_VALUE_PATTERN})\s+değil\b",
        rf"(?i)\bismim\s+({_ADDRESS_VALUE_PATTERN})\s+degil\b",
        rf"(?i)\bismim\s+({_ADDRESS_VALUE_PATTERN})\s+değil\b",
        rf"(?i)\bbenim\s+adim\s+({_ADDRESS_VALUE_PATTERN})\s+degil\b",
        rf"(?i)\bbenim\s+adım\s+({_ADDRESS_VALUE_PATTERN})\s+değil\b",
        rf"(?i)\b({_ADDRESS_VALUE_PATTERN})\s+degil\b",
        rf"(?i)\b({_ADDRESS_VALUE_PATTERN})\s+değil\b",
    )
    for pattern in patterns:
        match = re.search(pattern, query)
        if not match:
            continue
        value = _clean_address_value(match.group(1))
        if _is_plausible_name(value):
            return value

    preferred = clean_text(state.get("preferred_address", ""))
    if any(phrase in normalized for phrase in ("bana oyle deme", "bana boyle deme")) and preferred:
        return preferred
    return ""


def _is_plausible_name(value: str) -> bool:
    cleaned = clean_text(value).strip(" .,:;!?")
    if not cleaned:
        return False
    normalized = normalize_tr(cleaned)
    if normalized in _EXCLUDED_REJECTION_WORDS:
        return False
    tokens = cleaned.split()
    if len(tokens) > 3:
        return False
    return all(token and token[0].isalpha() for token in tokens)
