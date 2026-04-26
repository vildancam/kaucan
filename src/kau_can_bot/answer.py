from __future__ import annotations

import ast
import operator
import re
from dataclasses import dataclass
from functools import lru_cache
from html import unescape
from urllib.parse import quote_plus

import requests

from .config import (
    FALLBACK_RESPONSE,
    INDEX_PATH,
    POLITE_LANGUAGE_RESPONSE,
    Settings,
    WELCOME_MESSAGE,
)
from .indexer import SearchIndex
from .learning import expand_query, log_interaction, log_query
from .llm import OllamaAnswerGenerator, OpenAIAnswerGenerator
from .memory import (
    build_user_summary,
    find_relevant_user_fact,
    get_user_memory,
    learn_from_user_message,
    touch_user,
    user_department_name,
    user_display_name,
    user_role_name,
)
from .models import AssistantResponse, Chunk, SearchResult
from .official_data import (
    department_keys_for_query,
    ensure_department_content,
    ensure_faculty_content,
    get_official_snapshot,
)
from .query_normalizer import (
    is_arabic_query,
    is_coding_query,
    is_english_query,
    is_greeting_query,
    is_smalltalk_query,
    looks_actionable,
    normalize_for_matching,
    normalize_query,
)
from .safety import has_harmful_intent, has_inappropriate_language, is_ambiguous
from .utils import clean_text, stable_id


MIN_RELIABLE_SCORE = 0.035
MAX_SUMMARY_ITEMS = 3
LINK_PATTERN = re.compile(r"Bağlantı:\s*([^|\n]+?)\s*\|\s*URL:\s*(\S+)", re.IGNORECASE)
DATE_PATTERN = re.compile(r"\b\d{1,2}\s+[A-Za-zÇĞİÖŞÜçğıöşü]+\s+\d{4}\b")
NOISE_PATTERNS = (
    r"Yeni Pencerede Aç",
    r"\d+\s*kez görüntülendi\.?",
    r"Duyuruyu Paylaş:?",
    r"DEVAMINI OKU",
)
DIRECT_SERVICE_LINKS = (
    {
        "key": "yemek-menusu",
        "title": "Yemekhane Menüsü",
        "url": "https://www.kafkas.edu.tr/skdb",
        "message_tr": "🍽️ Yemekhane menüsüne SKDB sayfası üzerinden erişilebilir.",
        "message_en": "🍽️ The cafeteria menu can be accessed through the SKDB page.",
        "message_ar": "🍽️ يمكن الوصول إلى قائمة الطعام عبر صفحة إدارة الخدمات الصحية والثقافية.",
        "terms": ("yemek", "yemekhane", "menü", "menu", "yemek menusu", "cafeteria", "food", "dining"),
    },
    {
        "key": "akademik-takvim",
        "title": "Akademik Takvim",
        "url": "https://www.kafkas.edu.tr/oidb/tr/sayfaYeni6016",
        "message_tr": "📅 Akademik takvime Öğrenci İşleri sayfası üzerinden erişilebilir.",
        "message_en": "📅 The academic calendar can be accessed through the Student Affairs page.",
        "message_ar": "📅 يمكن الوصول إلى التقويم الأكاديمي عبر صفحة شؤون الطلاب.",
        "terms": ("akademik takvim", "egitim takvimi", "öğretim takvimi", "ders takvimi", "academic calendar"),
    },
    {
        "key": "obs",
        "title": "OBS",
        "url": "https://obsyeni.kafkas.edu.tr",
        "message_tr": "✅ OBS sistemine aşağıdaki bağlantı üzerinden erişilebilir.",
        "message_en": "✅ The OBS system can be accessed through the link below.",
        "message_ar": "✅ يمكن الوصول إلى نظام معلومات الطلاب عبر الرابط التالي.",
        "terms": ("obs", "ogrenci bilgi sistemi", "öğrenci bilgi sistemi", "student information system"),
    },
    {
        "key": "wifi",
        "title": "Okul İnternet Erişimi",
        "url": "https://captive.kafkas.edu.tr:6082/php/uid.php?vsys=1&rule=4&url=https://www.yok.gov.tr",
        "message_tr": "🌐 Kampüs internet erişimi için aşağıdaki bağlantı kullanılabilir.",
        "message_en": "🌐 The campus internet access page can be opened from the link below.",
        "message_ar": "🌐 يمكن فتح صفحة الوصول إلى إنترنت الحرم الجامعي من الرابط التالي.",
        "terms": (
            "wifi",
            "wi fi",
            "kablosuz",
            "okul interneti",
            "kampus interneti",
            "internete baglan",
            "internet baglantisi",
            "internet access",
            "campus internet",
            "wireless",
        ),
    },
    {
        "key": "kutuphane",
        "title": "Kütüphane",
        "url": "https://www.kafkas.edu.tr/kddb/TR/default.aspx",
        "message_tr": "📚 Kütüphane hizmetlerine aşağıdaki bağlantı üzerinden erişilebilir.",
        "message_en": "📚 Library services can be accessed through the link below.",
        "message_ar": "📚 يمكن الوصول إلى خدمات المكتبة عبر الرابط التالي.",
        "terms": ("kutuphane", "kütüphane", "library", "lib"),
    },
    {
        "key": "ebys",
        "title": "EBYS",
        "url": "https://ebys.kafkas.edu.tr/DYS/documentmanagement/",
        "message_tr": "🗂️ EBYS sistemine aşağıdaki bağlantı üzerinden erişilebilir.",
        "message_en": "🗂️ The EBYS system can be accessed through the link below.",
        "message_ar": "🗂️ يمكن الوصول إلى نظام إدارة المستندات EBYS عبر الرابط التالي.",
        "terms": ("ebys", "evrak", "belge yonetim", "document management"),
    },
    {
        "key": "telefon-rehberi",
        "title": "Telefon Rehberi",
        "url": "https://www.kafkas.edu.tr/kau/rehber2",
        "message_tr": "📞 Telefon rehberine aşağıdaki bağlantı üzerinden erişilebilir.",
        "message_en": "📞 The phone directory can be accessed through the link below.",
        "message_ar": "📞 يمكن الوصول إلى دليل الهاتف عبر الرابط التالي.",
        "terms": ("telefon rehberi", "rehber", "telefon listesi", "phone directory", "directory"),
    },
)
FACULTY_CONTACT_PAGE = "https://kafkas.edu.tr/iibf/tr/sayfaYeni18034"
MAPS_LINK = ("Maps'te Aç", "https://maps.app.goo.gl/HMYYaxbZBcZVisbN7")
RECTOR_PAGE = ("Rektör", "https://www.kafkas.edu.tr/rektorluk/tr/sayfaYeni655")
RECTOR_ASSISTANTS_PAGE = ("Rektör Yardımcıları", "https://www.kafkas.edu.tr/rektorluk/TR/sayfaYeni652")
SENATE_PAGE = ("Senato ve Dekanlıklar", "https://www.kafkas.edu.tr/rektorluk/TR/sayfaYeni651")
SMALLTALK_RESPONSES = {
    "naber": {
        "tr": "😊 İyiyim, teşekkür ederim. Akademik ya da genel bir konuda yardımcı olmam istenirse memnuniyetle destek sunabilirim.",
        "en": "😊 I'm doing well, thank you. I can gladly help with campus topics or general questions.",
        "ar": "😊 أنا بخير، شكرًا لك. يمكن المساعدة في موضوع جامعي أو عام بكل سرور.",
    },
    "ne haber": {
        "tr": "😊 Her şey yolunda görünüyor. İİBF, genel bilgi ya da günlük bir konuda yardımcı olabilirim.",
        "en": "😊 Everything looks good. I can help with IIBF, general information, or casual conversation.",
        "ar": "😊 كل شيء بخير. يمكن المساعدة في شؤون الكلية أو في الأسئلة العامة أو في دردشة يومية قصيرة.",
    },
    "nasilsin": {
        "tr": "😊 Teşekkür ederim, gayet iyiyim. İstenirse sohbet edebilir ya da herhangi bir konuda bilgi paylaşabilirim.",
        "en": "😊 I'm well, thank you. We can chat or continue with any question you'd like.",
        "ar": "😊 أنا بخير، شكرًا لك. يمكننا الدردشة أو متابعة أي سؤال ترغب به.",
    },
    "iyi misin": {
        "tr": "😊 Teşekkür ederim, iyiyim. İstenirse hemen bir soruya geçilebilir.",
        "en": "😊 Thank you, I'm doing well. We can move straight to your next question.",
        "ar": "😊 شكرًا لك، أنا بخير. يمكننا الانتقال مباشرة إلى سؤالك التالي.",
    },
    "ne yapiyorsun": {
        "tr": "😊 Sorulara yanıt vermek ve birlikte çözüm üretmek için hazır durumdayım. İstenirse kampüs, dersler ya da genel bilgi konularında devam edilebilir.",
        "en": "😊 I'm here to answer questions and help work through problems. We can continue with campus, coursework, or general topics.",
        "ar": "😊 أنا جاهز للإجابة عن الأسئلة والمساعدة في إيجاد الحلول. يمكننا المتابعة في موضوع جامعي أو عام أو تقني.",
    },
    "tesekkurler": {
        "tr": "😊 Rica ederim. Yeni bir soru olduğunda yardımcı olmaktan memnuniyet duyarım.",
        "en": "😊 You're welcome. I'd be happy to help again whenever you have another question.",
        "ar": "😊 على الرحب والسعة. يسعدني أن أساعد مرة أخرى متى احتجت.",
    },
    "merhaba": {
        "tr": "👋 Merhaba. Hazır durumdayım; istenirse bilgi verilebilir, metin yazılabilir veya bir konu birlikte araştırılabilir.",
        "en": "👋 Hello. I'm ready to help with information, writing, coding, or short research tasks.",
        "ar": "👋 مرحبًا. أنا جاهز للمساعدة في المعلومات والكتابة والبرمجة والمهام البحثية القصيرة.",
    },
    "adın ne": {
        "tr": "👋 Ben KAÜCAN Beta. Kafkas Üniversitesi İİBF için bilgi, yazım desteği ve genel yapay zeka yardımı sunabilirim.",
        "en": "👋 I am KAUCAN Beta. I can help with FEAS information, writing support, and general AI assistance.",
        "ar": "👋 أنا KAÜCAN Beta. يمكنني المساعدة في معلومات الكلية والكتابة والدعم الذكي العام.",
    },
    "ne yapabilirsin": {
        "tr": "✅ İİBF bilgileri, duyurular, personel, iletişim, konum, kod soruları, metin düzeltme, mail ve dilekçe yazımı gibi konularda destek sunabilirim.",
        "en": "✅ I can help with FEAS information, announcements, staff, contact, location, coding, text correction, emails, and petition drafting.",
        "ar": "✅ يمكنني المساعدة في معلومات الكلية والإعلانات والكوادر والاتصال والموقع والبرمجة وتصحيح النصوص وكتابة الرسائل والطلبات.",
    },
    "كيف حالك": {
        "tr": "😊 İyiyim, teşekkür ederim. İstenirse sohbete ya da bir soruya hemen geçilebilir.",
        "en": "😊 I'm doing well, thank you. We can move straight to chatting or to your next question.",
        "ar": "😊 أنا بخير، شكرًا لك. يمكننا الانتقال مباشرة إلى الدردشة أو إلى سؤالك التالي.",
    },
    "شكرا": {
        "tr": "😊 Rica ederim. Yeni bir soru olduğunda yardımcı olmaktan memnuniyet duyarım.",
        "en": "😊 You're welcome. I'd be happy to help again whenever you have another question.",
        "ar": "😊 على الرحب والسعة. يسعدني أن أساعدك في أي وقت.",
    },
}
MATH_BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}


@dataclass(frozen=True)
class ComposedAnswer:
    text: str
    sources: list[SearchResult]


def _response_language(query: str, preferred_language: str | None = None) -> str:
    preferred = clean_text(preferred_language or "").lower()
    if preferred in {"tr", "en", "ar"}:
        return preferred
    if is_arabic_query(query):
        return "ar"
    return "en" if is_english_query(query) else "tr"


def _text_for_language(language: str, tr_text: str, en_text: str, ar_text: str | None = None) -> str:
    if language == "ar":
        return ar_text or en_text
    return en_text if language == "en" else tr_text


def _welcome_message(language: str, user_memory: dict[str, object] | None = None) -> str:
    greeting = _text_for_language(
        language,
        WELCOME_MESSAGE,
        "👋 Hello, I am KAUCAN Beta - the Digital Assistant of Kafkas University. I can help with IIBF announcements, academic information, staff, contact, exams, cafeteria menu, writing, coding, and many other topics.",
        "👋 مرحبًا، أنا KAÜCAN Beta، المساعد الرقمي لجامعة قفقاس. يمكنني المساعدة في إعلانات الكلية والمعلومات الأكاديمية والكوادر والاتصال والامتحانات وقائمة الطعام والكتابة والبرمجة وغيرها.",
    )
    display_name = user_display_name(user_memory or {})
    if not display_name:
        return greeting
    return _text_for_language(
        language,
        f"👋 Merhaba {display_name}, ben KAÜCAN Beta. İİBF, genel bilgi, yazım ve günlük sorularda yardımcı olabilirim.",
        f"👋 Hello {display_name}, I am KAUCAN Beta. I can help with IIBF topics, general questions, writing, and everyday conversation.",
        f"👋 مرحبًا {display_name}، أنا KAÜCAN Beta. يمكنني المساعدة في موضوعات الكلية والأسئلة العامة والكتابة والمحادثة اليومية.",
    )


class WebsiteGroundedAssistant:
    def __init__(
        self,
        index: SearchIndex | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or Settings()
        self.index = index or SearchIndex.load(INDEX_PATH)

    def answer(self, query: str, client_id: str | None = None, preferred_language: str | None = None) -> str:
        return self.answer_with_context(query, client_id=client_id, preferred_language=preferred_language).answer

    def answer_with_context(
        self,
        query: str,
        client_id: str | None = None,
        preferred_language: str | None = None,
    ) -> AssistantResponse:
        original_query = clean_text(query)
        normalized_query = normalize_query(original_query) or original_query
        general_query = original_query or normalized_query
        language = _response_language(general_query, preferred_language)
        client_key = clean_text(client_id or "")
        if client_key:
            touch_user(client_key)
        memory_update = learn_from_user_message(client_key, original_query) if client_key else None
        user_memory = get_user_memory(client_key) if client_key else {}

        if has_inappropriate_language(normalized_query):
            return AssistantResponse(
                answer=_text_for_language(
                    language,
                    POLITE_LANGUAGE_RESPONSE,
                    "⚠️ Please use academic and appropriate language. I would be glad to assist.",
                    "⚠️ يُرجى استخدام لغة أكاديمية ومناسبة. يسعدني مساعدتك.",
                ),
                status="blocked_language",
            )

        if has_harmful_intent(normalized_query):
            return AssistantResponse(
                answer=_text_for_language(
                    language,
                    "Bu talebe yardımcı olamam.",
                    "I cannot help with that request.",
                    "لا يمكنني المساعدة في هذا الطلب.",
                ),
                status="blocked_safety",
            )

        memory_recall_response = _memory_recall_shortcut(original_query or normalized_query, language, user_memory, client_key)
        if memory_recall_response is not None:
            interaction = log_interaction(
                original_query or normalized_query,
                memory_recall_response.text,
                memory_recall_response.sources,
                "memory_recall",
            )
            return AssistantResponse(
                answer=memory_recall_response.text,
                sources=memory_recall_response.sources,
                interaction_id=interaction.id,
                status="memory_recall",
            )

        if memory_update and memory_update.saved and memory_update.memory_only:
            memory_saved_response = _memory_saved_shortcut(memory_update, language, user_memory)
            interaction = log_interaction(
                original_query or normalized_query,
                memory_saved_response.text,
                [],
                "memory_saved",
            )
            return AssistantResponse(
                answer=memory_saved_response.text,
                interaction_id=interaction.id,
                status="memory_saved",
            )

        if is_greeting_query(normalized_query):
            answer = _welcome_message(language, user_memory)
            interaction = log_interaction(original_query or normalized_query, answer, [], "greeting")
            return AssistantResponse(
                answer=answer,
                interaction_id=interaction.id,
                status="greeting",
            )

        management_response = _management_shortcut(normalized_query, language)
        if management_response is not None:
            interaction = log_interaction(
                original_query or normalized_query,
                management_response.text,
                management_response.sources,
                "direct_link",
            )
            return AssistantResponse(
                answer=management_response.text,
                sources=management_response.sources,
                interaction_id=interaction.id,
                status="direct_link",
            )

        faculty_contact_response = _faculty_contact_shortcut(normalized_query, language)
        if faculty_contact_response is not None:
            interaction = log_interaction(
                original_query or normalized_query,
                faculty_contact_response.text,
                faculty_contact_response.sources,
                "direct_link",
            )
            return AssistantResponse(
                answer=faculty_contact_response.text,
                sources=faculty_contact_response.sources,
                interaction_id=interaction.id,
                status="direct_link",
            )

        location_response = _location_shortcut(normalized_query, language)
        if location_response is not None:
            interaction = log_interaction(
                original_query or normalized_query,
                location_response.text,
                location_response.sources,
                "direct_link",
            )
            return AssistantResponse(
                answer=location_response.text,
                sources=location_response.sources,
                interaction_id=interaction.id,
                status="direct_link",
            )

        direct_link_response = _match_direct_service_link(normalized_query, language)
        if direct_link_response is not None:
            interaction = log_interaction(
                original_query or normalized_query,
                direct_link_response.text,
                direct_link_response.sources,
                "direct_link",
            )
            return AssistantResponse(
                answer=direct_link_response.text,
                sources=direct_link_response.sources,
                interaction_id=interaction.id,
                status="direct_link",
            )

        official_response = _official_data_shortcut(general_query, language)
        if official_response is not None:
            interaction = log_interaction(
                original_query or normalized_query,
                official_response.text,
                official_response.sources,
                "official",
            )
            return AssistantResponse(
                answer=official_response.text,
                sources=official_response.sources,
                interaction_id=interaction.id,
                status="official",
            )

        custom_memory_response = _custom_memory_fact_shortcut(original_query or normalized_query, language, user_memory, client_key)
        if custom_memory_response is not None:
            interaction = log_interaction(
                original_query or normalized_query,
                custom_memory_response.text,
                [],
                "memory_fact",
            )
            return AssistantResponse(
                answer=custom_memory_response.text,
                interaction_id=interaction.id,
                status="memory_fact",
            )

        composition_response = _composition_shortcut(general_query, language)
        if composition_response is not None:
            interaction = log_interaction(
                original_query or normalized_query,
                composition_response.text,
                composition_response.sources,
                "general",
            )
            return AssistantResponse(
                answer=composition_response.text,
                sources=composition_response.sources,
                interaction_id=interaction.id,
                status="general",
            )

        if is_smalltalk_query(normalized_query):
            answer = _smalltalk_response(normalized_query, language, user_memory)
            interaction = log_interaction(
                original_query or normalized_query,
                answer,
                _general_support_sources(original_query or normalized_query, language, include_google=False),
                "smalltalk",
            )
            return AssistantResponse(
                answer=answer,
                sources=_general_support_sources(original_query or normalized_query, language, include_google=False),
                interaction_id=interaction.id,
                status="smalltalk",
            )

        math_answer = _solve_basic_math(general_query, language)
        if math_answer:
            general_sources = _general_support_sources(original_query or normalized_query, language)
            interaction = log_interaction(original_query or normalized_query, math_answer, general_sources, "general")
            return AssistantResponse(
                answer=math_answer,
                sources=general_sources,
                interaction_id=interaction.id,
                status="general",
            )

        if _should_answer_with_general_knowledge(general_query):
            general_answer = self._generate_general_with_llm(general_query, user_memory, preferred_language=language)
            if general_answer:
                answer = _sanitize_answer_text(general_answer)
                if answer:
                    general_sources = _general_support_sources(original_query or normalized_query, language)
                    interaction = log_interaction(original_query or normalized_query, answer, general_sources, "general")
                    return AssistantResponse(
                        answer=answer,
                        sources=general_sources,
                        interaction_id=interaction.id,
                        status="general",
                    )

        if is_ambiguous(normalized_query) and not looks_actionable(normalized_query):
            answer = _text_for_language(
                language,
                "📌 Sorunun daha doğru yanıtlanabilmesi için konu başlığının biraz daha netleştirilmesi rica olunur. Bölüm, duyuru, akademik personel, iletişim, sınav, akademik takvim veya yemek menüsü gibi bir başlık belirtilebilir.",
                "📌 Please make the topic a little more specific so that I can answer more accurately. You may mention a department, announcement, academic staff, contact, exam, academic calendar, or cafeteria menu.",
                "📌 يُرجى توضيح الموضوع قليلًا حتى أتمكن من الإجابة بدقة أكبر. يمكن ذكر قسم أو إعلان أو كادر أكاديمي أو تواصل أو امتحان أو تقويم أكاديمي أو قائمة طعام.",
            )
            interaction = log_interaction(original_query or normalized_query, answer, [], "ambiguous")
            return AssistantResponse(answer=answer, interaction_id=interaction.id, status="ambiguous")

        candidate_count = max(self.settings.top_k * 4, 12)
        search_query = _build_search_query(normalized_query)
        if self.settings.use_learning_expansion:
            search_query = expand_query(search_query)

        results = self.index.search(search_query, top_k=candidate_count)
        log_query(original_query or normalized_query, results)

        reliable_results = [
            result
            for result in results
            if result.score >= MIN_RELIABLE_SCORE and _passes_context_requirements(normalized_query, result)
        ]
        reliable_results.sort(
            key=lambda result: (_context_priority(normalized_query, result), result.score),
            reverse=True,
        )

        if not reliable_results:
            fallback_text = _text_for_language(
                language,
                FALLBACK_RESPONSE,
                "⚠️ I could not reach reliable information on this topic. For the most accurate information, please contact the faculty directly.",
                "⚠️ لم أتمكن من الوصول إلى معلومات موثوقة حول هذا الموضوع. للحصول على أدق معلومة، يُنصح بالتواصل مع الكلية مباشرة.",
            )
            interaction = log_interaction(original_query or normalized_query, fallback_text, [], "fallback")
            return AssistantResponse(
                answer=fallback_text,
                interaction_id=interaction.id,
                status="fallback",
            )

        top_results = _dedupe_results_by_url(reliable_results)[: self.settings.top_k]

        if _prefer_local_answer(normalized_query):
            local_answer = _build_local_answer(normalized_query, top_results, language)
            interaction = log_interaction(
                original_query or normalized_query,
                local_answer.text,
                local_answer.sources,
                "local",
            )
            return AssistantResponse(
                answer=local_answer.text,
                sources=local_answer.sources,
                interaction_id=interaction.id,
                status="local",
            )

        llm_answer = self._generate_with_llm(normalized_query, top_results)
        if llm_answer:
            answer = _sanitize_answer_text(llm_answer)
            if answer:
                interaction = log_interaction(original_query or normalized_query, answer, top_results, "llm")
                return AssistantResponse(
                    answer=answer,
                    sources=top_results,
                    interaction_id=interaction.id,
                    status="llm",
                )

        local_answer = _build_local_answer(normalized_query, top_results, language)
        interaction = log_interaction(
            original_query or normalized_query,
            local_answer.text,
            local_answer.sources,
            "local",
        )
        return AssistantResponse(
            answer=local_answer.text,
            sources=local_answer.sources,
            interaction_id=interaction.id,
            status="local",
        )

    def _generate_with_llm(self, query: str, results: list[SearchResult]) -> str | None:
        generator = _generator_for_settings(self.settings)
        if not generator.is_configured:
            return None

        try:
            return generator.generate(query, results)
        except Exception:
            return None

    def _generate_general_with_llm(
        self,
        query: str,
        user_memory: dict[str, object] | None = None,
        preferred_language: str | None = None,
    ) -> str | None:
        generator = _general_generator_for_settings(self.settings)
        if not generator.is_configured:
            return None

        try:
            memory_context = _general_memory_context(user_memory or {}, _response_language(query, preferred_language))
            return generator.generate_general(query, memory_context=memory_context)
        except Exception:
            return None


def _build_local_answer(query: str, results: list[SearchResult], language: str) -> ComposedAnswer:
    if _is_department_query(query):
        answer = _format_department_answer(results, language)
        if answer:
            return answer
    if _is_contact_query(query):
        answer = _format_contact_answer(results, language)
        if answer:
            return answer
    if _is_personnel_query(query):
        return _format_personnel_answer(query, results, language)
    if _is_announcement_query(query):
        answer = _format_announcement_answer(results, language)
        if answer:
            return answer
    if _is_exam_query(query):
        answer = _format_exam_answer(results, language)
        if answer:
            return answer
    if _is_academic_calendar_query(query):
        answer = _format_academic_calendar_answer(results, language)
        if answer:
            return answer
    return _format_general_answer(query, results, language)


def _format_department_answer(results: list[SearchResult], language: str) -> ComposedAnswer | None:
    entries: list[tuple[str, str]] = []
    for result in results:
        for label, url in _extract_link_pairs(result.chunk.text):
            normalized_label = normalize_for_matching(label)
            if "bolum" in normalized_label or any(
                term in normalized_label for term in map(normalize_for_matching, DEPARTMENT_TERMS)
            ):
                if (label, url) not in entries:
                    entries.append((label, url))

    if not entries:
        return None

    bullets = "\n".join(f"• {label}" for label, _ in entries[:8])
    return ComposedAnswer(
        text=_text_for_language(
            language,
            "📌 İİBF bünyesinde erişilebilen bölüm bağlantıları aşağıdadır:\n" + bullets,
            "📌 The department links available under IIBF are listed below:\n" + bullets,
        ),
        sources=_build_link_sources(entries),
    )


def _format_contact_answer(results: list[SearchResult], language: str) -> ComposedAnswer | None:
    entries: list[tuple[str, str]] = []
    for result in results:
        for label, url in _extract_link_pairs(result.chunk.text):
            normalized_label = normalize_for_matching(label)
            if any(term in normalized_label for term in ("telefon", "rehber", "dekana sor", "iletisim")):
                if (label, url) not in entries:
                    entries.append((label, url))

    if entries:
        unique_labels: list[str] = []
        observed: set[str] = set()
        unique_entries: list[tuple[str, str]] = []
        for label, _ in entries:
            normalized_label = normalize_for_matching(label)
            if normalized_label in observed:
                continue
            unique_labels.append(label)
            observed.add(normalized_label)
        observed.clear()
        for label, url in entries:
            normalized_label = normalize_for_matching(label)
            if normalized_label in observed:
                continue
            unique_entries.append((label, url))
            observed.add(normalized_label)

        bullets = "\n".join(f"• {label}" for label in unique_labels[:4])
        return ComposedAnswer(
            text=_text_for_language(
                language,
                "📞 İletişim için fakülte sayfasında öne çıkan başlıklar aşağıdadır:\n" + bullets,
                "📞 The highlighted contact links on the faculty page are listed below:\n" + bullets,
            ),
            sources=_build_link_sources(unique_entries),
        )

    first_source = _dedupe_results_by_url(results)[:2]
    if not first_source:
        return None

    return ComposedAnswer(
        text=_text_for_language(
            language,
            "📞 İletişim bilgileri ilgili fakülte sayfalarında yayımlanmaktadır. Güncel telefon, e-posta ve rehber bağlantıları kaynak kısmından incelenebilir.",
            "📞 Contact information is published on the related faculty pages. Current phone, email, and directory links can be reviewed from the source section.",
        ),
        sources=first_source,
    )


def _format_personnel_answer(query: str, results: list[SearchResult], language: str) -> ComposedAnswer:
    source = _dedupe_results_by_url(results)[:1]
    profile_label = _text_for_language(
        language,
        "akademik personel" if "akademik" in _query_key(query) else "personel",
        "academic staff" if "akademik" in _query_key(query) else "staff",
    )
    display_title = _display_title(source[0], language) if source else _text_for_language(language, "ilgili personel sayfası", "the related staff page")
    return ComposedAnswer(
        text=_text_for_language(
            language,
            f"👤 {profile_label.capitalize()} bilgileri fakültenin \"{display_title}\" sayfasında yayımlanmaktadır. Güncel isim ve iletişim bilgileri kaynak bağlantısından incelenebilir.",
            f"👤 {profile_label.capitalize()} information is published on the faculty page titled \"{display_title}\". Current names and contact details can be reviewed from the source link.",
        ),
        sources=source,
    )


def _format_announcement_answer(results: list[SearchResult], language: str) -> ComposedAnswer | None:
    candidates = [
        result
        for result in _dedupe_results_by_url(results)
        if "/duyuru2/" in result.chunk.url.lower()
        or any(term in normalize_for_matching(result.chunk.title) for term in ("duyuru", "haber", "etkinlik"))
    ]
    rows = [_build_titled_row(result, language) for result in candidates]
    rows = [row for row in rows if row][:MAX_SUMMARY_ITEMS]
    if not rows:
        return None
    return ComposedAnswer(
        text=_text_for_language(
            language,
            "📢 Web sitesindeki ilgili kayıtlara göre öne çıkan duyurular:\n" + "\n".join(rows),
            "📢 According to the related records on the website, the highlighted announcements are:\n" + "\n".join(rows),
        ),
        sources=candidates[:MAX_SUMMARY_ITEMS],
    )


def _format_exam_answer(results: list[SearchResult], language: str) -> ComposedAnswer | None:
    candidates = [
        result
        for result in _dedupe_results_by_url(results)
        if "/duyuru2/" in result.chunk.url.lower() or _is_exam_related(result)
    ]
    rows = [_build_titled_row(result, language) for result in candidates]
    rows = [row for row in rows if row][:MAX_SUMMARY_ITEMS]
    if not rows:
        return None
    return ComposedAnswer(
        text=_text_for_language(
            language,
            "📅 İlgili sınav kayıtlarında öne çıkan başlıklar:\n" + "\n".join(rows),
            "📅 The highlighted titles in the related exam records are:\n" + "\n".join(rows),
        ),
        sources=candidates[:MAX_SUMMARY_ITEMS],
    )


def _format_academic_calendar_answer(results: list[SearchResult], language: str) -> ComposedAnswer | None:
    rows = [_build_titled_row(result, language) for result in _dedupe_results_by_url(results)]
    rows = [row for row in rows if row][:MAX_SUMMARY_ITEMS]
    if not rows:
        return None
    return ComposedAnswer(
        text=_text_for_language(
            language,
            "📅 Akademik takvimle ilişkili erişilebilen kayıtlar:\n" + "\n".join(rows),
            "📅 The accessible records related to the academic calendar are:\n" + "\n".join(rows),
        ),
        sources=_dedupe_results_by_url(results)[:MAX_SUMMARY_ITEMS],
    )


def _format_general_answer(query: str, results: list[SearchResult], language: str) -> ComposedAnswer:
    lines = [_build_summary_line(result, language) for result in _dedupe_results_by_url(results)]
    lines = [line for line in lines if line][:MAX_SUMMARY_ITEMS]
    if not lines:
        lines = [_text_for_language(language, "• İlgili bilgi kaynak bağlantılarında yer almaktadır.", "• The related information is available in the source links.")]
    return ComposedAnswer(
        text=_text_for_language(
            language,
            f"{_response_emoji(query)} İlgili web içeriklerine göre öne çıkan bilgiler:\n" + "\n".join(lines),
            f"{_response_emoji(query)} According to the related web content, the key points are:\n" + "\n".join(lines),
        ),
        sources=_dedupe_results_by_url(results)[:MAX_SUMMARY_ITEMS],
    )


def _build_summary_line(result: SearchResult, language: str) -> str:
    title = _display_title(result, language)
    summary = _extract_summary_sentence(result.chunk.text, title)
    if summary:
        return f"• {title}: {summary}"
    return f"• {title}"


def _build_titled_row(result: SearchResult, language: str = "tr") -> str:
    title = _display_title(result, language)
    date = _extract_date(result.chunk.text)
    summary = _extract_summary_sentence(result.chunk.text, title, max_chars=130)

    if date and summary:
        return f"• {title} - {date}: {summary}"
    if date:
        return f"• {title} - {date}"
    if summary:
        return f"• {title}: {summary}"
    return f"• {title}"


def _extract_summary_sentence(text: str, title: str, max_chars: int = 180) -> str:
    cleaned = _strip_noise(text)
    if cleaned.lower().startswith(title.lower()):
        cleaned = cleaned[len(title) :].strip(" .:-")
    sentences = [
        clean_text(part)
        for part in re.split(r"(?<=[.!?])\s+|\n+", cleaned)
        if clean_text(part)
    ]
    for sentence in sentences:
        normalized = normalize_for_matching(sentence)
        if len(sentence) < 20:
            continue
        if any(term in normalized for term in ("baglanti", "url", "kaynak", "metadata", "chunk")):
            continue
        if sentence.lower() == title.lower():
            continue
        return _truncate(sentence, max_chars)
    return ""


def _strip_noise(text: str) -> str:
    cleaned = text.replace("\u200b", " ")
    cleaned = LINK_PATTERN.sub(" ", cleaned)
    for pattern in NOISE_PATTERNS:
        cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"https?://\S+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _extract_date(text: str) -> str:
    match = DATE_PATTERN.search(text)
    if not match:
        return ""
    return clean_text(match.group(0))


def _build_link_sources(entries: list[tuple[str, str]]) -> list[SearchResult]:
    sources: list[SearchResult] = []
    for index, (label, url) in enumerate(entries[:8], start=1):
        sources.append(
            SearchResult(
                chunk=Chunk(
                    id=stable_id(label, url),
                    url=url,
                    title=label,
                    text=label,
                    ordinal=index,
                    metadata={"derived": True},
                ),
                score=max(0.1, 1 - (index * 0.05)),
            )
        )
    return sources


def _general_support_sources(query: str, language: str, include_google: bool = True) -> list[SearchResult]:
    normalized = _query_key(query)
    entries: list[tuple[str, str]] = []

    if is_coding_query(query):
        if "python" in normalized:
            entries.append(("Python Docs", "https://docs.python.org/3/"))
        if any(term in normalized for term in ("javascript", "js", "html", "css")):
            entries.append(("MDN Web Docs", "https://developer.mozilla.org/"))
        if "react" in normalized:
            entries.append(("React Docs", "https://react.dev/"))
        if "fastapi" in normalized:
            entries.append(("FastAPI Docs", "https://fastapi.tiangolo.com/"))
        if "flask" in normalized:
            entries.append(("Flask Docs", "https://flask.palletsprojects.com/"))
        if not entries:
            entries.append(("Stack Overflow", "https://stackoverflow.com/"))

    if include_google:
        entries.append(
            (
                _text_for_language(language, "Google'da Ara", "Search on Google", "ابحث في Google"),
                f"https://www.google.com/search?q={quote_plus(query)}",
            )
        )

    deduped: list[tuple[str, str]] = []
    seen_urls: set[str] = set()
    for title, url in entries:
        if url in seen_urls:
            continue
        deduped.append((title, url))
        seen_urls.add(url)
    return _build_link_sources(deduped[:3])


def _match_direct_service_link(query: str, language: str) -> ComposedAnswer | None:
    normalized = _query_key(query)
    for item in DIRECT_SERVICE_LINKS:
        if any(normalize_for_matching(term) in normalized for term in item["terms"]):
            return ComposedAnswer(
                text=_text_for_language(language, item["message_tr"], item["message_en"], item.get("message_ar")),
                sources=_build_link_sources([(item["title"], item["url"])]),
            )
    return None


def _management_shortcut(query: str, language: str) -> ComposedAnswer | None:
    normalized = _query_key(query)
    if not normalized:
        return None

    if "rektor yardimci" in normalized or "vice rector" in normalized or (
        any(term in normalized for term in ("rektor", "rector"))
        and any(term in normalized for term in ("yardimci", "yardimcilari", "vice"))
    ):
        names = _fetch_rector_assistant_names()
        if names:
            joined_names = ", ".join(names[:3])
            text = _text_for_language(
                language,
                f"👤 Güncel rektör yardımcıları resmi sayfada {joined_names} olarak yayımlanmaktadır.",
                f"👤 The current vice rectors are listed on the official page as {joined_names}.",
            )
        else:
            text = _text_for_language(
                language,
                "👤 Güncel rektör yardımcıları bilgisi resmi sayfada yayımlanmaktadır.",
                "👤 Current vice rector information is published on the official page.",
            )
        return ComposedAnswer(
            text=text,
            sources=_build_link_sources([RECTOR_ASSISTANTS_PAGE]),
        )

    if any(term in normalized for term in ("senato", "dekanlik", "dekanliklar", "dekanlar", "senate", "deans")):
        return ComposedAnswer(
            text=_text_for_language(
                language,
                "👤 Üniversite senatosu ve dekanlık bilgileri resmi yönetim sayfasında yayımlanmaktadır.",
                "👤 Senate and dean's office information is published on the official management page.",
            ),
            sources=_build_link_sources([SENATE_PAGE]),
        )

    if "rektor" in normalized or "rector" in normalized:
        rector_name = _fetch_rector_name()
        if rector_name:
            text = _text_for_language(
                language,
                f"👤 Kafkas Üniversitesi Rektörü resmi sayfada {rector_name} olarak yayımlanmaktadır.",
                f"👤 The official page lists the Rector of Kafkas University as {rector_name}.",
            )
        else:
            text = _text_for_language(
                language,
                "👤 Güncel rektör bilgisi resmi rektörlük sayfasında yayımlanmaktadır.",
                "👤 Current rector information is published on the official rectorate page.",
            )
        return ComposedAnswer(
            text=text,
            sources=_build_link_sources([RECTOR_PAGE]),
        )

    return None


def _faculty_contact_shortcut(query: str, language: str) -> ComposedAnswer | None:
    if not (_is_contact_query(query) and _is_faculty_query(query)):
        return None

    return ComposedAnswer(
        text=_text_for_language(
            language,
            "📞 İİBF iletişim bilgileri:\n"
            "• E-posta: iibf@kafkas.edu.tr\n"
            "• Telefon: 0474 225 12 50\n"
            "• Fax: 0474 225 12 57\n"
            "• Dekanımıza Ulaşmak İçin: dozyakisir@gmail.com",
            "📞 IIBF contact information:\n"
            "• Email: iibf@kafkas.edu.tr\n"
            "• Phone: 0474 225 12 50\n"
            "• Fax: 0474 225 12 57\n"
            "• To Reach the Dean: dozyakisir@gmail.com",
            "📞 معلومات التواصل لكلية الاقتصاد والعلوم الإدارية:\n"
            "• البريد الإلكتروني: iibf@kafkas.edu.tr\n"
            "• الهاتف: 0474 225 12 50\n"
            "• الفاكس: 0474 225 12 57\n"
            "• للتواصل مع العميد: dozyakisir@gmail.com",
        ),
        sources=_build_link_sources(
            [
                ("İİBF İletişim Sayfası", FACULTY_CONTACT_PAGE),
                ("Telefon: 0474 225 12 50", "tel:+904742251250"),
                ("E-posta: iibf@kafkas.edu.tr", "mailto:iibf@kafkas.edu.tr"),
                ("Dekana Ulaşın: dozyakisir@gmail.com", "mailto:dozyakisir@gmail.com"),
                ("Telefon Rehberi", "https://www.kafkas.edu.tr/kau/rehber2"),
            ]
        ),
    )


def _location_shortcut(query: str, language: str) -> ComposedAnswer | None:
    normalized = _query_key(query)
    if not normalized:
        return None
    if not _is_location_query(query):
        return None
    if not (
        _is_faculty_query(query)
        or "kafkas universitesi" in normalized
        or "kau" in normalized
        or "universite" in normalized
    ):
        return None

    return ComposedAnswer(
        text=_text_for_language(
            language,
            "📌 Konum bilgisi için aşağıdaki harita bağlantısı kullanılabilir. Bağlantı Maps uygulamasında açılabilir.",
            "📌 The map link below can be used for location information. It can be opened directly in the Maps application.",
            "📌 يمكن استخدام رابط الخريطة التالي لمعرفة الموقع، ويمكن فتحه مباشرة في تطبيق الخرائط.",
        ),
        sources=_build_link_sources([MAPS_LINK]),
    )


def _memory_saved_shortcut(memory_update, language: str, user_memory: dict[str, object]) -> ComposedAnswer:
    display_name = user_display_name(user_memory)
    saved_labels: list[str] = []
    profile_label_map = {
        "name": _text_for_language(language, "ad", "name"),
        "preferred_name": _text_for_language(language, "hitap adı", "preferred name"),
        "department": _text_for_language(language, "bölüm", "department"),
        "role": _text_for_language(language, "rol", "role"),
    }
    for key in ("name", "preferred_name", "department", "role"):
        value = clean_text(memory_update.profile_updates.get(key, ""))
        if value:
            saved_labels.append(f"{profile_label_map[key]}: {value}")

    saved_labels.extend(memory_update.facts[:2])
    summary = ", ".join(saved_labels[:3])

    if display_name:
        return ComposedAnswer(
            text=_text_for_language(
                language,
                f"✅ Tamam {display_name}, bu bilgi belleğe kaydedildi." + (f" {summary}" if summary else ""),
                f"✅ Alright {display_name}, I saved that to memory." + (f" {summary}" if summary else ""),
            ),
            sources=[],
        )

    return ComposedAnswer(
        text=_text_for_language(
            language,
            "✅ Paylaşılan bilgi belleğe kaydedildi." + (f" {summary}" if summary else ""),
            "✅ The shared information has been saved to memory." + (f" {summary}" if summary else ""),
        ),
        sources=[],
    )


def _memory_recall_shortcut(
    query: str,
    language: str,
    user_memory: dict[str, object],
    client_id: str,
) -> ComposedAnswer | None:
    if not client_id or not user_memory:
        return None

    normalized = _query_key(query)
    display_name = user_display_name(user_memory)
    department = user_department_name(user_memory, language)
    role = user_role_name(user_memory, language)
    summary = build_user_summary(user_memory, language)

    if any(term in normalized for term in ("adim ne", "ismim ne", "what is my name", "my name")):
        if not display_name:
            return _missing_memory_answer(language)
        return ComposedAnswer(
            text=_text_for_language(
                language,
                f"👤 Daha önce paylaşılan bilgiye göre adı {display_name} olarak kayıtlı.",
                f"👤 According to the saved information, the name is recorded as {display_name}.",
            ),
            sources=[],
        )

    if any(term in normalized for term in ("hangi bolumdeyim", "bolumum ne", "what do i study", "which department")):
        if not department:
            return _missing_memory_answer(language)
        return ComposedAnswer(
            text=_text_for_language(
                language,
                f"📌 Kayıtlı bilgiye göre {department} bölümünde {role or 'kişi'} olarak yer alıyor.",
                f"📌 According to the saved information, the user is recorded as a {role or 'member'} in {department}.",
            ),
            sources=[],
        )

    if any(term in normalized for term in ("bana nasil hitap", "beni nasil cagir", "what should you call me", "call me what")):
        if not display_name:
            return _missing_memory_answer(language)
        return ComposedAnswer(
            text=_text_for_language(
                language,
                f"😊 Kayıtlı bilgiye göre {display_name} diye hitap edilmesi uygun olur.",
                f"😊 According to the saved information, it would be appropriate to address the user as {display_name}.",
            ),
            sources=[],
        )

    if any(term in normalized for term in ("beni taniyor musun", "ben kimim", "do you know me", "who am i", "do you remember me")):
        if not summary:
            return _missing_memory_answer(language)
        return ComposedAnswer(
            text=_text_for_language(
                language,
                f"😊 Evet, bellekte şu bilgiler bulunuyor: {summary}.",
                f"😊 Yes, the following information is stored in memory: {summary}.",
            ),
            sources=[],
        )

    return None


def _custom_memory_fact_shortcut(
    query: str,
    language: str,
    user_memory: dict[str, object],
    client_id: str,
) -> ComposedAnswer | None:
    if not client_id:
        return None

    fact = find_relevant_user_fact(client_id, query)
    if not fact:
        return None

    fact_text = clean_text(fact.get("text", ""))
    if not fact_text:
        return None

    return ComposedAnswer(
        text=_text_for_language(
            language,
            f"📌 Daha önce paylaşılan bilgiye göre: {fact_text}",
            f"📌 Based on the previously shared information: {fact_text}",
        ),
        sources=[],
    )


def _general_memory_context(user_memory: dict[str, object], language: str) -> str:
    summary = build_user_summary(user_memory, language)
    if not summary:
        return ""
    return _text_for_language(
        language,
        f"Kullanıcı hakkında daha önce paylaşılan bilgiler: {summary}. Uygun olduğunda doğal biçimde dikkate alınabilir.",
        f"Previously shared information about the user: {summary}. Use it naturally when helpful.",
    )


def _missing_memory_answer(language: str) -> ComposedAnswer:
    return ComposedAnswer(
        text=_text_for_language(
            language,
            "⚠️ Bu konuda bellekte yeterli kişisel bilgi bulunmuyor. İstenirse ad, bölüm veya özel bilgi paylaşılabilir.",
            "⚠️ There is not enough personal information in memory yet. The user may share a name, department, or another detail.",
        ),
        sources=[],
    )


def _official_data_shortcut(query: str, language: str) -> ComposedAnswer | None:
    normalized = _query_key(query)
    if not normalized:
        return None

    if not _should_use_official_data(query):
        return None

    try:
        snapshot = get_official_snapshot()
    except Exception:
        return None

    if _is_dean_query(query):
        answer = _official_dean_answer(snapshot, language)
        if answer is not None:
            return answer

    department_keys = department_keys_for_query(query)
    topic = _official_content_topic(query)

    if topic and not department_keys:
        snapshot = ensure_faculty_content(snapshot, (topic,))
        answer = _official_faculty_content_answer(snapshot, topic, language)
        if answer is not None:
            return answer

    if department_keys:
        department_key = department_keys[0]
        answer = _official_department_answer(snapshot, department_key, query, language, topic)
        if answer is not None:
            return answer

    if _is_faculty_department_heads_query(query):
        answer = _official_faculty_heads_answer(snapshot, language)
        if answer is not None:
            return answer

    if _is_faculty_staff_query(query):
        answer = _official_faculty_staff_answer(snapshot, query, language)
        if answer is not None:
            return answer

    if _is_short_faculty_staff_query(query):
        answer = _official_faculty_staff_answer(snapshot, f"iibf {query}", language)
        if answer is not None:
            return answer

    if _is_department_listing_query(query):
        answer = _official_department_listing_answer(snapshot, language)
        if answer is not None:
            return answer

    return None


def _official_dean_answer(snapshot: dict, language: str) -> ComposedAnswer | None:
    dean = snapshot.get("faculty_dean") or {}
    if not dean:
        return None

    dean_name = clean_text(dean.get("name", ""))
    designation = clean_text(dean.get("designation", ""))
    source_url = clean_text(dean.get("source_url", "")) or SENATE_PAGE[1]
    detail_url = clean_text(dean.get("detail_url", "")) or source_url

    if not dean_name:
        return None

    return ComposedAnswer(
        text=_text_for_language(
            language,
            f"👤 İİBF dekanı resmi senato sayfasına göre {dean_name} olarak yer almaktadır. {designation}".strip(),
            f"👤 According to the official senate page, the dean of FEAS is {dean_name}. Dean of the Faculty of Economics and Administrative Sciences.",
            f"👤 وفقًا لصفحة مجلس الجامعة الرسمية، فإن عميد الكلية هو {dean_name}.",
        ),
        sources=_build_link_sources(
            [
                ("Senato ve Dekanlıklar", source_url),
                ("Dekan Profili", detail_url),
            ]
        ),
    )


def _official_faculty_content_answer(snapshot: dict, topic: str, language: str) -> ComposedAnswer | None:
    items = snapshot.get("faculty_content", {}).get(topic, [])
    if not items:
        label = _content_label(topic, language)
        return ComposedAnswer(
            text=_text_for_language(
                language,
                f"{_content_emoji(topic)} Güncel {label.lower()} için resmi fakülte sayfası kullanılabilir.",
                f"{_content_emoji(topic)} The official faculty page can be used for the latest {label.lower()}.",
            ),
            sources=_build_link_sources([(_content_label(topic, "tr"), _content_source_url(topic))]),
        )

    rows = [_official_item_row(item) for item in items[:3]]
    return ComposedAnswer(
        text=_text_for_language(
            language,
            f"{_content_emoji(topic)} İİBF için öne çıkan {_content_label(topic, 'tr').lower()}:\n" + "\n".join(rows),
            f"{_content_emoji(topic)} Highlighted {_content_label(topic, 'en').lower()} for FEAS:\n" + "\n".join(rows),
        ),
        sources=_official_item_sources(items[:3], fallback_title=_content_label(topic, "tr")),
    )


def _official_department_answer(
    snapshot: dict,
    department_key: str,
    query: str,
    language: str,
    topic: str | None,
) -> ComposedAnswer | None:
    department = snapshot.get("departments", {}).get(department_key)
    if not department:
        return None

    if topic:
        snapshot = ensure_department_content(snapshot, department_key, (topic,))
        department = snapshot.get("departments", {}).get(department_key, department)
        answer = _official_department_content_answer(department, topic, language)
        if answer is not None:
            return answer

    if _is_department_head_query(query):
        answer = _official_department_heads_answer(department, language)
        if answer is not None:
            return answer

    if _is_department_staff_query(query):
        answer = _official_department_staff_shortcut(department, query, language)
        if answer is not None:
            return answer

    if _is_department_info_query(query):
        answer = _official_department_info_answer(department, language)
        if answer is not None:
            return answer

    if normalize_for_matching(query) in {department_key, normalize_for_matching(department.get("name_tr", ""))}:
        return _official_department_info_answer(department, language)

    return None


def _official_faculty_heads_answer(snapshot: dict, language: str) -> ComposedAnswer | None:
    people = snapshot.get("faculty_personnel", [])
    department_heads = []
    for person in people:
        if any("bolum baskani" in normalize_for_matching(role) for role in person.get("roles", [])):
            department_heads.append(person)

    if not department_heads:
        return None

    rows = []
    for person in department_heads[:8]:
        department_name = clean_text(person.get("department", ""))
        person_name = _normalize_person_name(person.get("name", ""))
        rows.append(f"• {department_name}: {person_name}")

    return ComposedAnswer(
        text=_text_for_language(
            language,
            "👤 İİBF bölüm başkanları resmi akademik personel sayfasına göre şöyledir:\n" + "\n".join(rows),
            "👤 According to the official academic staff page, the department chairs of FEAS are:\n" + "\n".join(rows),
        ),
        sources=_build_link_sources([("İİBF Akademik Personel", "https://www.kafkas.edu.tr/iibf/tr/akademikpersonel")]),
    )


def _official_faculty_staff_answer(snapshot: dict, query: str, language: str) -> ComposedAnswer | None:
    people = snapshot.get("faculty_personnel", [])
    if not people:
        return None

    if _is_academic_staff_query(query):
        rows = [_person_line(person) for person in people[:6]]
        return ComposedAnswer(
            text=_text_for_language(
                language,
                "👤 İİBF akademik kadrosu resmi personel sayfasında yayımlanmaktadır. Öne çıkan isimler:\n" + "\n".join(rows),
                "👤 The FEAS academic staff is published on the official personnel page. Highlighted names:\n" + "\n".join(rows),
            ),
            sources=_build_link_sources([("İİBF Akademik Personel", "https://www.kafkas.edu.tr/iibf/tr/akademikpersonel")]),
        )

    administrative_people = [
        person
        for person in people
        if any(role in normalize_for_matching(" ".join(person.get("roles", []))) for role in ("dekan", "yardimci", "bolum baskani"))
    ]
    if not administrative_people:
        administrative_people = people[:6]

    rows = [_person_role_line(person) for person in administrative_people[:6]]
    return ComposedAnswer(
        text=_text_for_language(
            language,
            "👤 İİBF sayfasında görünen idari görevlerden bazıları şöyledir:\n" + "\n".join(rows),
            "👤 Some of the administrative roles shown on the FEAS page are:\n" + "\n".join(rows),
        ),
        sources=_build_link_sources([("İİBF Akademik Personel", "https://www.kafkas.edu.tr/iibf/tr/akademikpersonel")]),
    )


def _official_department_listing_answer(snapshot: dict, language: str) -> ComposedAnswer | None:
    ordered_keys = snapshot.get("department_order") or list(snapshot.get("departments", {}))
    rows = []
    sources = []
    for key in ordered_keys[:8]:
        department = snapshot.get("departments", {}).get(key, {})
        name_tr = department.get("name_tr")
        root_url = department.get("root_url")
        if not name_tr or not root_url:
            continue
        rows.append(f"• {name_tr}")
        sources.append((name_tr, root_url))

    if not rows:
        return None

    return ComposedAnswer(
        text=_text_for_language(
            language,
            "📌 İİBF bünyesindeki bölümler şöyledir:\n" + "\n".join(rows),
            "📌 The departments under FEAS are:\n" + "\n".join(rows),
        ),
        sources=_build_link_sources(sources[:4]),
    )


def _official_department_content_answer(department: dict, topic: str, language: str) -> ComposedAnswer | None:
    items = department.get(topic, [])
    label = _content_label(topic, language)
    department_name = department.get("name_tr", "Bölüm")
    page_url = department.get("important_links", {}).get(topic) or department.get("root_url", "")

    if not items:
        if not page_url:
            return None
        return ComposedAnswer(
            text=_text_for_language(
                language,
                f"{_content_emoji(topic)} {department_name} için güncel {label.lower()} resmi bölüm sayfasından takip edilebilir.",
                f"{_content_emoji(topic)} The latest {label.lower()} for {department_name} can be followed on the official department page.",
            ),
            sources=_build_link_sources([(f"{department_name} { _content_label(topic, 'tr') }", page_url)]),
        )

    rows = [_official_item_row(item) for item in items[:3]]
    return ComposedAnswer(
        text=_text_for_language(
            language,
            f"{_content_emoji(topic)} {department_name} için öne çıkan { _content_label(topic, 'tr').lower() }:\n" + "\n".join(rows),
            f"{_content_emoji(topic)} Highlighted { _content_label(topic, 'en').lower() } for {department_name}:\n" + "\n".join(rows),
        ),
        sources=_official_item_sources(items[:3], fallback_title=f"{department_name} {_content_label(topic, 'tr')}"),
    )


def _official_department_heads_answer(department: dict, language: str) -> ComposedAnswer | None:
    people = department.get("personnel", [])
    if not people:
        return None

    head = next(
        (
            person
            for person in people
            if any("bolum baskani" in normalize_for_matching(role) for role in person.get("roles", []))
        ),
        None,
    )
    assistants = [
        person
        for person in people
        if any("bolum baskan yardimcisi" in normalize_for_matching(role) for role in person.get("roles", []))
    ]

    if not head and not assistants:
        return None

    rows = []
    if head:
        rows.append(f"• Bölüm Başkanı: {_normalize_person_name(head.get('name', ''))}")
    for person in assistants[:3]:
        rows.append(f"• Başkan Yardımcısı: {_normalize_person_name(person.get('name', ''))}")

    department_name = department.get("name_tr", "Bölüm")
    return ComposedAnswer(
        text=_text_for_language(
            language,
            f"👤 {department_name} için resmi sayfada görünen yönetim bilgileri:\n" + "\n".join(rows),
            f"👤 The management information shown on the official page for {department_name} is:\n" + "\n".join(rows),
        ),
        sources=_build_link_sources([(f"{department_name} Akademik Personel", department.get("important_links", {}).get("academic_staff") or department.get("root_url", ""))]),
    )


def _official_department_staff_shortcut(department: dict, query: str, language: str) -> ComposedAnswer | None:
    people = department.get("personnel", [])
    if not people:
        return None

    if _is_administrative_roles_query(query):
        rows = [_person_role_line(person) for person in people if person.get("roles")]
        rows = rows[:6]
        if not rows:
            return None
        return ComposedAnswer(
            text=_text_for_language(
                language,
                f"👤 {department.get('name_tr', 'Bölüm')} için sayfada görünen idari görevler:\n" + "\n".join(rows),
                f"👤 Administrative roles shown for {department.get('name_tr', 'the department')} are:\n" + "\n".join(rows),
            ),
            sources=_build_link_sources([(f"{department.get('name_tr', 'Bölüm')} Akademik Personel", department.get("important_links", {}).get("academic_staff") or department.get("root_url", ""))]),
        )

    rows = [_person_line(person) for person in people[:8]]
    count = len(people)
    return ComposedAnswer(
        text=_text_for_language(
            language,
            f"👤 {department.get('name_tr', 'Bölüm')} akademik kadrosunda resmi sayfada {count} kişi listelenmektedir. Öne çıkan isimler:\n" + "\n".join(rows),
            f"👤 The official page lists {count} people in the academic staff of {department.get('name_tr', 'the department')}. Highlighted names:\n" + "\n".join(rows),
        ),
        sources=_build_link_sources([(f"{department.get('name_tr', 'Bölüm')} Akademik Personel", department.get("important_links", {}).get("academic_staff") or department.get("root_url", ""))]),
    )


def _official_department_info_answer(department: dict, language: str) -> ComposedAnswer | None:
    name_tr = department.get("name_tr", "")
    if not name_tr:
        return None

    links = department.get("important_links", {})
    source_pairs = [(name_tr, department.get("root_url", ""))]
    for key in ("academic_staff", "announcements", "news", "events"):
        url = links.get(key)
        if url:
            source_pairs.append((f"{name_tr} {_content_label(key, 'tr') if key in {'announcements', 'news', 'events'} else 'Akademik Personel'}", url))

    return ComposedAnswer(
        text=_text_for_language(
            language,
            f"📌 {name_tr} hakkında resmi sayfada bölüm bilgisi, akademik kadro, duyurular, haberler ve etkinlik bağlantıları yer almaktadır.",
            f"📌 The official page for {name_tr} includes department information, academic staff, announcements, news, and event links.",
        ),
        sources=_build_link_sources(source_pairs[:4]),
    )


def _official_item_row(item: dict) -> str:
    title = clean_text(item.get("title", ""))
    date = clean_text(item.get("date", ""))
    summary = _clean_official_summary(item.get("summary", ""), title)
    if date and summary:
        return f"• {title} - {date}: {_truncate(summary, 110)}"
    if date:
        return f"• {title} - {date}"
    if summary:
        return f"• {title}: {_truncate(summary, 110)}"
    return f"• {title}"


def _official_item_sources(items: list[dict], fallback_title: str) -> list[SearchResult]:
    pairs = []
    for item in items:
        title = clean_text(item.get("title", "")) or fallback_title
        url = clean_text(item.get("url", ""))
        if url:
            pairs.append((title, url))
    return _build_link_sources(pairs[:3])


def _clean_official_summary(summary: str, title: str = "") -> str:
    cleaned = clean_text(summary)
    normalized = normalize_for_matching(cleaned)
    if any(
        term in normalized
        for term in (
            "bir daha gosterme",
            "akilli kart",
            "konuk evi",
            "internet erisim",
            "universitemiz",
            "kurumsal yonetim",
        )
    ):
        return ""
    if title and normalize_for_matching(title) == normalized:
        return ""
    return cleaned


def _content_source_url(topic: str) -> str:
    return {
        "announcements": FACULTY_ANNOUNCEMENTS_URL,
        "news": FACULTY_NEWS_URL,
        "events": FACULTY_EVENTS_URL,
    }.get(topic, FACULTY_ANNOUNCEMENTS_URL)


def _content_label(topic: str, language: str) -> str:
    translations = {
        "announcements": {"tr": "Duyurular", "en": "Announcements"},
        "news": {"tr": "Haberler", "en": "News"},
        "events": {"tr": "Etkinlikler", "en": "Events"},
    }
    entry = translations.get(topic, {"tr": "İçerikler", "en": "Content"})
    return entry["en"] if language == "en" else entry["tr"]


def _content_emoji(topic: str) -> str:
    return {
        "announcements": "📢",
        "news": "📌",
        "events": "📅",
    }.get(topic, "📌")


def _person_line(person: dict) -> str:
    academic_title = _display_academic_title(person.get("academic_title", ""))
    name = _normalize_person_name(person.get("name", ""))
    if academic_title:
        return f"• {academic_title} {name}"
    return f"• {name}"


def _person_role_line(person: dict) -> str:
    name = _normalize_person_name(person.get("name", ""))
    role = clean_text(", ".join(person.get("roles", [])))
    if role:
        return f"• {name}: {role}"
    return f"• {name}"


def _display_academic_title(value: str) -> str:
    normalized = normalize_for_matching(value)
    mapping = {
        "profesor": "Prof.",
        "docent": "Doç.",
        "doktor ogretim uyesi": "Dr. Öğr. Üyesi",
        "ogretim gorevlisi": "Öğr. Gör.",
        "arastirma gorevlisi": "Arş. Gör.",
        "doktor": "Dr.",
    }
    return mapping.get(normalized, clean_text(value))


def _official_content_topic(query: str) -> str | None:
    normalized = _query_key(query)
    if any(term in normalized for term in ("duyuru", "duyurular", "announcement", "announcements")):
        return "announcements"
    if any(term in normalized for term in ("haber", "haberler", "news")):
        return "news"
    if any(term in normalized for term in ("etkinlik", "etkinlikler", "event", "events")):
        return "events"
    return None


def _should_use_official_data(query: str) -> bool:
    normalized = _query_key(query)
    return any(
        condition
        for condition in (
            _is_dean_query(query),
            _is_department_listing_query(query),
            _is_faculty_staff_query(query),
            _is_faculty_department_heads_query(query),
            bool(department_keys_for_query(query)),
            bool(_official_content_topic(query)),
            normalized in {"ybs", "akademik kadro", "duyurular", "haberler", "etkinlikler", "bolumler"},
        )
    )


def _is_dean_query(query: str) -> bool:
    normalized = _query_key(query)
    return ("dekan" in normalized or "dean" in normalized or "عميد" in normalized) and (
        _is_faculty_query(query)
        or "fakulte" in normalized
        or "faculty" in normalized
        or "feas" in normalized
        or normalized in {"dekan kim", "dekan kimdir", "dean", "who is the dean", "من هو العميد"}
    )


def _is_department_head_query(query: str) -> bool:
    normalized = _query_key(query)
    return any(
        term in normalized
        for term in (
            "bolum baskani",
            "bolum baskan yardimcisi",
            "baskan yardimcisi",
            "chair",
            "head of department",
        )
    )


def _is_department_listing_query(query: str) -> bool:
    normalized = _query_key(query)
    return "bolumler" in normalized or normalized == "bolumler" or normalized == "departments"


def _is_department_info_query(query: str) -> bool:
    normalized = _query_key(query)
    return any(term in normalized for term in ("hakkinda", "bolumu hakkinda", "about")) or bool(department_keys_for_query(query))


def _is_faculty_department_heads_query(query: str) -> bool:
    normalized = _query_key(query)
    return _is_faculty_query(query) and any(
        term in normalized for term in ("bolum baskanlari", "chairs", "department heads")
    )


def _is_faculty_staff_query(query: str) -> bool:
    normalized = _query_key(query)
    return _is_faculty_query(query) and any(
        term in normalized
        for term in (
            "akademik kadro",
            "akademik personel",
            "personel",
            "idari gorev",
            "idari gorevliler",
            "staff",
            "academic staff",
        )
    )


def _is_short_faculty_staff_query(query: str) -> bool:
    normalized = _query_key(query)
    return normalized in {
        "akademik kadro",
        "akademik personel",
        "personel",
        "idari gorevler",
        "idari gorevliler",
    }


def _is_department_staff_query(query: str) -> bool:
    normalized = _query_key(query)
    return any(
        term in normalized
        for term in (
            "akademik kadro",
            "akademik personel",
            "personel",
            "idari gorev",
            "idari gorevliler",
            "staff",
            "academic staff",
        )
    )


def _is_administrative_roles_query(query: str) -> bool:
    normalized = _query_key(query)
    return any(term in normalized for term in ("idari gorev", "idari gorevliler", "administrative"))


def _is_academic_staff_query(query: str) -> bool:
    normalized = _query_key(query)
    return any(term in normalized for term in ("akademik kadro", "akademik personel", "academic staff"))


def _smalltalk_response(query: str, language: str, user_memory: dict[str, object] | None = None) -> str:
    normalized = _query_key(query)
    display_name = user_display_name(user_memory or {})
    for pattern, response in SMALLTALK_RESPONSES.items():
        if pattern in normalized:
            base_response = response.get(language, response.get("en", response["tr"]))
            return f"{display_name}, {base_response}" if display_name else base_response
    fallback_response = _text_for_language(
        language,
        "😊 Elbette, sohbet edilebilir. İstenirse günlük bir konuya ya da bilgi sorusuna birlikte devam edilebilir.",
        "😊 Of course, we can chat. If you'd like, we can continue with a casual topic or an information question.",
        "😊 بالطبع، يمكننا الدردشة. وإذا رغبت، يمكننا المتابعة في موضوع يومي أو سؤال معلوماتي.",
    )
    return f"{display_name}, {fallback_response}" if display_name else fallback_response


def _composition_shortcut(query: str, language: str) -> ComposedAnswer | None:
    normalized = _query_key(query)
    if not _is_composition_request(query):
        return None

    if "mail" in normalized or "e posta" in normalized or "email" in normalized:
        return ComposedAnswer(
            text=_text_for_language(
                language,
                "✅ Kısa resmi e-posta taslağı:\n"
                "Konu: Bilgi Talebi\n"
                "Sayın Yetkili,\n"
                "İlgili konu hakkında bilgi paylaşılmasını rica ederim.\n"
                "İyi çalışmalar dilerim.",
                "✅ Short formal email draft:\n"
                "Subject: Information Request\n"
                "Dear Sir/Madam,\n"
                "I kindly request information regarding the related matter.\n"
                "Best regards.",
                "✅ مسودة بريد رسمي قصيرة:\n"
                "الموضوع: طلب معلومات\n"
                "السادة الكرام،\n"
                "أرجو التكرم بمشاركة المعلومات المتعلقة بالموضوع.\n"
                "مع خالص التقدير.",
            ),
            sources=[],
        )

    if "dilekce" in normalized or "dilekçe" in normalized or "petition" in normalized:
        return ComposedAnswer(
            text=_text_for_language(
                language,
                "✅ Kısa dilekçe taslağı:\n"
                "İlgili makama,\n"
                "Aşağıda belirtilen konuda gereğinin yapılmasını arz ederim.\n"
                "Bilgilerinize sunarım.",
                "✅ Short petition draft:\n"
                "To the relevant authority,\n"
                "I respectfully request the necessary action regarding the matter stated below.\n"
                "Submitted for your consideration.",
                "✅ مسودة طلب قصيرة:\n"
                "إلى الجهة المختصة،\n"
                "أرجو اتخاذ اللازم بخصوص الموضوع الموضح أدناه.\n"
                "وتفضلوا بقبول الاحترام.",
            ),
            sources=[],
        )

    if "mesaj" in normalized or "message" in normalized:
        return ComposedAnswer(
            text=_text_for_language(
                language,
                "✅ Kısa mesaj taslağı:\n"
                "Merhaba, ilgili konu hakkında kısa bir bilgilendirme rica ediyorum. Uygun olduğunuzda dönüş sağlayabilir misiniz?",
                "✅ Short message draft:\n"
                "Hello, I would appreciate a brief update on the related matter. Could you get back to me when convenient?",
                "✅ مسودة رسالة قصيرة:\n"
                "مرحبًا، أرجو تزويدي بإفادة مختصرة حول الموضوع. هل يمكنكم الرد عند توفر الوقت؟",
            ),
            sources=[],
        )

    return None


def _should_answer_with_general_knowledge(query: str) -> bool:
    normalized = _query_key(query)
    if not normalized:
        return False
    if _is_composition_request(query):
        return True
    if looks_actionable(normalized):
        return False
    if any(
        checker(query)
        for checker in (
            _is_faculty_query,
            _is_contact_query,
            _is_personnel_query,
            _is_department_query,
            _is_announcement_query,
            _is_exam_query,
            _is_academic_calendar_query,
            _is_menu_query,
            _is_location_query,
            _is_management_query,
        )
    ):
        return False

    tokens = [token for token in normalized.split() if token]
    has_general_signal = any(
        term in normalized
        for term in (
            "nedir",
            "nasil",
            "neden",
            "kimdir",
            "kac",
            "duzelt",
            "gelistir",
            "iyilestir",
            "arastir",
            "araştir",
            "olustur",
            "hazirla",
            "yaz",
            "mail yaz",
            "mesaj yaz",
            "dilekce",
            "dilekçe",
            "ozetle",
            "çevir",
            "what",
            "how",
            "why",
            "who",
            "write",
            "fix",
            "improve",
            "create",
            "draft",
            "summarize",
            "research",
            "matematik",
            "tarih",
            "yazilim",
            "python",
            "kod",
            "code",
            "bug",
            "error",
            "fix",
            "مرحبا",
            "كيف",
            "اكتب",
            "اصلح",
            "حسن",
            "ابحث",
            "لخص",
            "ترجم",
        )
    )
    has_math_signal = any(char in query for char in "+-*/=")
    return bool(tokens) and (
        len(tokens) >= 2
        or has_general_signal
        or has_math_signal
        or is_coding_query(query)
        or len(tokens[0]) >= 3
        or is_arabic_query(query)
    )


def _solve_basic_math(query: str, language: str) -> str | None:
    expression = _math_expression_from_query(query)
    if not expression:
        return None
    try:
        result = _evaluate_math_expression(expression)
    except Exception:
        return None

    if isinstance(result, float) and result.is_integer():
        result = int(result)
    if isinstance(result, float):
        result = round(result, 4)
    return _text_for_language(
        language,
        f"✅ Sonuç: {expression} = {result}",
        f"✅ Result: {expression} = {result}",
    )


def _math_expression_from_query(query: str) -> str:
    raw_expression = re.sub(r"[^0-9+\-*/(). ]", " ", query)
    raw_expression = re.sub(r"\s+", "", raw_expression)
    if raw_expression and any(symbol in raw_expression for symbol in "+-*/"):
        if re.fullmatch(r"[0-9+\-*/().]+", raw_expression):
            return raw_expression

    normalized = _query_key(query)
    if not normalized:
        return ""

    working = f" {normalized} "
    replacements = (
        ("kac eder", " "),
        ("kac yapar", " "),
        ("sonuc", " "),
        ("nedir", " "),
        ("hesapla", " "),
        ("equals", " "),
        ("what is", " "),
        ("calculate", " "),
        ("toplam", " + "),
        ("arti", " + "),
        ("topla", " + "),
        ("plus", " + "),
        ("add", " + "),
        ("eksi", " - "),
        ("cikar", " - "),
        ("farki", " - "),
        ("minus", " - "),
        ("subtract", " - "),
        ("carpi", " * "),
        ("carp", " * "),
        ("times", " * "),
        ("multiply", " * "),
        ("bolu", " / "),
        ("bol", " / "),
        ("divided by", " / "),
        ("divide", " / "),
    )
    for old, new in replacements:
        working = working.replace(old, new)

    working = re.sub(r"(\d+)\s+ile\s+(\d+)\s+\+", r"\1 + \2", working)
    working = re.sub(r"(\d+)\s+ve\s+(\d+)\s+\+", r"\1 + \2", working)
    working = re.sub(r"(\d+)\s+ile\s+(\d+)\s+\-", r"\1 - \2", working)
    working = re.sub(r"(\d+)\s+ve\s+(\d+)\s+\-", r"\1 - \2", working)
    working = re.sub(r"(\d+)\s+ile\s+(\d+)\s+\*", r"\1 * \2", working)
    working = re.sub(r"(\d+)\s+ve\s+(\d+)\s+\*", r"\1 * \2", working)
    working = re.sub(r"(\d+)\s+ile\s+(\d+)\s+/", r"\1 / \2", working)
    working = re.sub(r"(\d+)\s+ve\s+(\d+)\s+/", r"\1 / \2", working)

    expression = re.sub(r"[^0-9+\-*/(). ]", " ", working)
    expression = re.sub(r"\s+", "", expression)
    if not expression or not any(symbol in expression for symbol in "+-*/"):
        return ""
    if not re.fullmatch(r"[0-9+\-*/().]+", expression):
        return ""
    return expression


def _evaluate_math_expression(expression: str) -> int | float:
    tree = ast.parse(expression, mode="eval")
    return _evaluate_math_node(tree.body)


def _evaluate_math_node(node: ast.AST) -> int | float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.Num):
        return node.n
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_evaluate_math_node(node.operand)
    if isinstance(node, ast.BinOp) and type(node.op) in MATH_BINARY_OPERATORS:
        left = _evaluate_math_node(node.left)
        right = _evaluate_math_node(node.right)
        return MATH_BINARY_OPERATORS[type(node.op)](left, right)
    raise ValueError("Unsupported expression")


@lru_cache(maxsize=6)
def _fetch_remote_page(url: str) -> str:
    response = requests.get(
        url,
        timeout=6,
        headers={
            "User-Agent": "KAUCAN/1.0 (+https://www.kafkas.edu.tr)",
        },
    )
    response.raise_for_status()
    return response.text


def _fetch_rector_name() -> str:
    try:
        html = _fetch_remote_page(RECTOR_PAGE[1])
    except requests.RequestException:
        return ""

    match = re.search(
        r"<strong>\s*(Prof\.?\s*Dr\.?\s*[^<]+?)\s*</strong>",
        html,
        flags=re.IGNORECASE,
    )
    if not match:
        return ""
    return _normalize_person_name(match.group(1))


def _fetch_rector_assistant_names() -> list[str]:
    try:
        html = _fetch_remote_page(RECTOR_ASSISTANTS_PAGE[1])
    except requests.RequestException:
        return []

    names = re.findall(
        r"/rektorluk/tr/sayfaYeni\d+'>\s*(Prof\.?\s*Dr\.?\s*[^<]+?)\s*</a>",
        html,
        flags=re.IGNORECASE,
    )
    normalized_names: list[str] = []
    for name in names:
        cleaned = _normalize_person_name(name)
        if cleaned and cleaned not in normalized_names:
            normalized_names.append(cleaned)
    return normalized_names[:5]


def _normalize_person_name(value: str) -> str:
    cleaned = unescape(clean_text(value))
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -")
    return cleaned


def _extract_link_pairs(text: str) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for match in LINK_PATTERN.finditer(text):
        label = clean_text(match.group(1))
        url = match.group(2).strip()
        if not label or not url:
            continue
        if (label, url) not in entries:
            entries.append((label, url))
    return entries


def _display_title(result: SearchResult, language: str = "tr") -> str:
    title = clean_text(result.chunk.title)
    return title or _text_for_language(language, "İlgili Sayfa", "Related Page")


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def _dedupe_results_by_url(results: list[SearchResult]) -> list[SearchResult]:
    deduped: list[SearchResult] = []
    seen_urls: set[str] = set()
    for result in results:
        if result.chunk.url in seen_urls:
            continue
        deduped.append(result)
        seen_urls.add(result.chunk.url)
    return deduped


def _generator_for_settings(settings: Settings):
    if settings.llm_provider == "ollama":
        return OllamaAnswerGenerator(settings)
    if settings.llm_provider == "openai":
        return OpenAIAnswerGenerator(settings)
    return LocalOnlyGenerator()


def _general_generator_for_settings(settings: Settings):
    openai_generator = OpenAIAnswerGenerator(settings)
    if openai_generator.is_configured:
        return openai_generator
    return _generator_for_settings(settings)


def _general_generators_for_settings(settings: Settings):
    generators = []
    openai_generator = OpenAIAnswerGenerator(settings)
    if openai_generator.is_configured:
        generators.append(openai_generator)

    primary_generator = _generator_for_settings(settings)
    if not any(type(generator) is type(primary_generator) for generator in generators):
        generators.append(primary_generator)

    if not generators:
        generators.append(LocalOnlyGenerator())
    return generators


class LocalOnlyGenerator:
    @property
    def is_configured(self) -> bool:
        return False

    def generate(self, query: str, results: list[SearchResult]) -> str | None:
        return None

    def generate_general(self, query: str, memory_context: str = "") -> str | None:
        return None


def _sanitize_answer_text(answer: str) -> str:
    if not answer:
        return ""

    lines: list[str] = []
    for raw_line in answer.splitlines():
        line = raw_line.strip()
        if not line:
            if lines and lines[-1] != "":
                lines.append("")
            continue

        line = line.replace("**", "").replace("__", "")
        line = re.sub(r"\[([^\]]+)\]\((https?://[^\)]+)\)", r"\1", line)
        line = _strip_technical_label(line)
        if not line:
            continue

        normalized = normalize_for_matching(line)
        if any(term in normalized for term in ("metadata", "chunk aciklamasi", "description")):
            continue
        if normalized.startswith("kaynak") or normalized.startswith("source"):
            continue
        if re.match(r"^\d+\s+kaynagi ac\b", normalized):
            continue

        line = re.sub(r"https?://\S+", "", line).strip()
        if re.fullmatch(r"\d+[.)]?", line):
            continue
        if line:
            lines.append(line)

    sanitized = "\n".join(lines)
    sanitized = re.sub(r"\n{3,}", "\n\n", sanitized).strip()
    if not sanitized:
        return ""
    if FALLBACK_RESPONSE in sanitized:
        return FALLBACK_RESPONSE
    if "lütfen akademik ve uygun bir dil kullanınız" in sanitized.lower():
        return POLITE_LANGUAGE_RESPONSE
    return sanitized


def _strip_technical_label(line: str) -> str:
    patterns = (
        r"^(?:[^\w\s]+\s*)?(açıklama|aciklama|detaylar?|description)\s*:\s*(.+)$",
        r"^(?:[^\w\s]+\s*)?(sonuç|sonuc)\s*:\s*(.+)$",
    )
    for pattern in patterns:
        match = re.match(pattern, line, flags=re.IGNORECASE)
        if match:
            return match.group(2).strip()

    blocker_patterns = (
        r"^(?:[^\w\s]+\s*)?(metadata|chunk açıklaması|chunk aciklamasi)\s*:?.*$",
        r"^(?:[^\w\s]+\s*)?(kaynak|source|sources)\s*:?.*$",
    )
    for pattern in blocker_patterns:
        if re.match(pattern, line, flags=re.IGNORECASE):
            return ""
    return line


def _build_search_query(query: str) -> str:
    additions: list[str] = []
    if _is_contact_query(query):
        additions.extend(["telefon rehberi", "dekana sor", "e-posta", "adres", "contact", "phone"])
    if _is_announcement_query(query):
        additions.extend(["duyuru", "tüm duyurular", "haber", "announcement", "news"])
    if _is_exam_query(query):
        additions.extend(["sınav programı", "ara sınav", "vize", "final", "bütünleme", "exam schedule"])
    if _is_department_query(query):
        additions.extend(["bölüm", "department", *DEPARTMENT_TERMS[:6]])
    if _is_personnel_query(query):
        additions.extend(["akademik kadro", "akademikpersonel", "öğretim elemanı", "staff"])
    if _is_academic_calendar_query(query):
        additions.extend(["takvim", "akademik", "ders programı", "calendar"])
    if _is_menu_query(query):
        additions.extend(["yemek", "yemekhane", "menü", "cafeteria"])

    unique_additions: list[str] = []
    normalized_query = normalize_for_matching(query)
    for addition in additions:
        if normalize_for_matching(addition) not in normalized_query and addition not in unique_additions:
            unique_additions.append(addition)
    if not unique_additions:
        return query
    return f"{query} {' '.join(unique_additions)}"


def _passes_context_requirements(query: str, result: SearchResult) -> bool:
    if _is_faculty_query(query) and not _is_faculty_related(result):
        return False
    if _is_contact_query(query) and not _is_contact_related(query, result):
        return False
    if _is_personnel_query(query) and not _is_personnel_related(result):
        return False
    if _is_department_query(query) and not _is_department_related(result):
        return False
    if _is_announcement_query(query) and not _is_announcement_related(result):
        return False
    if _is_exam_query(query) and not _is_exam_related(result):
        return False
    if _is_academic_calendar_query(query) and not _is_academic_calendar_related(result):
        return False
    if _is_menu_query(query) and not _is_menu_related(result):
        return False
    return True


def _context_priority(query: str, result: SearchResult) -> int:
    priority = 0
    haystack = _haystack(result)
    query_key = _query_key(query)

    if _is_personnel_query(query):
        if "akademikpersonel" in result.chunk.url.lower():
            priority += 10
        if any(term in haystack for term in ("profesor", "docent", "arastirma gorevlisi")):
            priority += 5

    if _is_department_query(query):
        priority += min(sum(1 for term in DEPARTMENT_TERMS if normalize_for_matching(term) in haystack), 8)

    if _is_announcement_query(query):
        if "/duyuru2/" in result.chunk.url.lower():
            priority += 10
        if any(term in haystack for term in ("duyuru", "guncel", "haber")):
            priority += 4

    if _is_exam_query(query):
        if "/duyuru2/" in result.chunk.url.lower():
            priority += 6
        if any(term in haystack for term in ("sinav programi", "vize", "ara sinav", "butunleme")):
            priority += 5
        if "ara" in query_key or "vize" in query_key:
            if "ara sinav" in haystack or "vize" in haystack:
                priority += 4
            if "butunleme" in haystack and "ara sinav" not in haystack and "vize" not in haystack:
                priority -= 3

    if _is_contact_query(query):
        if any(term in haystack for term in ("telefon rehberi", "dekana sor", "kurumsal iletisim")):
            priority += 8
        if "akademikpersonel" in result.chunk.url.lower() and _is_faculty_query(query):
            priority -= 4

    if _is_academic_calendar_query(query) and "takvim" in haystack:
        priority += 5

    return priority


def _prefer_local_answer(query: str) -> bool:
    return any(
        checker(query)
        for checker in (
            _is_contact_query,
            _is_personnel_query,
            _is_department_query,
            _is_announcement_query,
            _is_exam_query,
            _is_academic_calendar_query,
        )
    )


def _query_key(query: str) -> str:
    return normalize_for_matching(query)


def _is_composition_request(query: str) -> bool:
    normalized = _query_key(query)
    return any(
        term in normalized
        for term in (
            "yaz",
            "duzelt",
            "düzelt",
            "gelistir",
            "geliştir",
            "iyilestir",
            "araştır",
            "arastir",
            "olustur",
            "oluştur",
            "hazirla",
            "hazırla",
            "rewrite",
            "write",
            "draft",
            "create",
            "compose",
            "fix",
            "improve",
            "summarize",
            "research",
            "اكتب",
            "اصلح",
            "حسن",
            "ابحث",
            "أنشئ",
            "لخص",
        )
    )


def _haystack(result: SearchResult) -> str:
    return normalize_for_matching(f"{result.chunk.url} {result.chunk.title} {result.chunk.text}")


def _response_emoji(query: str) -> str:
    if _is_announcement_query(query):
        return "📢"
    if _is_exam_query(query) or _is_academic_calendar_query(query):
        return "📅"
    if _is_personnel_query(query):
        return "👤"
    if _is_contact_query(query):
        return "📞"
    return "📌"


def _is_faculty_query(query: str) -> bool:
    normalized = _query_key(query)
    return any(
        term in normalized
        for term in (
            "iibf",
            "iktisadi ve idari bilimler",
            "iktisadi",
            "idari bilimler",
            "bilimler fakultesi",
            "fakulte",
            "dekan",
            "feas",
            "faculty of economics and administrative sciences",
            "faculty of economics",
            "economics and administrative sciences",
            "iibf faculty",
            "جامعة قفقاس",
            "كلية",
            "العلوم الادارية",
            "الاقتصاد",
            "عميد",
        )
    )


def _is_contact_query(query: str) -> bool:
    normalized = _query_key(query)
    if _is_composition_request(query):
        return False
    return any(
        term in normalized
        for term in (
            "adres",
            "e posta",
            "email",
            "iletisim",
            "mail",
            "telefon",
            "rehber",
            "numara",
            "contact",
            "phone",
            "تواصل",
            "اتصال",
            "هاتف",
            "بريد",
            "ايميل",
        )
    )


def _is_personnel_query(query: str) -> bool:
    normalized = _query_key(query)
    return any(
        term in normalized
        for term in (
            "akademik kadro",
            "akademik personel",
            "idari gorevliler",
            "idari gorev",
            "bolum baskani",
            "idari personel",
            "personel",
            "ogretim elemani",
            "ogretim uyesi",
            "arastirma gorevlisi",
            "staff",
            "academic staff",
            "faculty members",
            "كادر",
            "هيئة التدريس",
            "موظفين",
        )
    )


def _is_department_query(query: str) -> bool:
    normalized = _query_key(query)
    return any(
        term in normalized
        for term in (
            "bolum",
            "bolumler",
            "akademik program",
            "department",
            "departments",
            "ybs",
            "iktisat",
            "isletme",
            "sbky",
            "sbui",
            "utl",
            "قسم",
            "الاقسام",
            "نظم المعلومات",
        )
    )


def _is_announcement_query(query: str) -> bool:
    normalized = _query_key(query)
    return any(
        term in normalized
        for term in (
            "duyuru",
            "duyurular",
            "haber",
            "haberler",
            "etkinlik",
            "etkinlikler",
            "announcement",
            "announcements",
            "news",
            "event",
            "events",
            "اعلان",
            "اعلانات",
            "اخبار",
            "فعاليات",
        )
    )


def _is_exam_query(query: str) -> bool:
    normalized = _query_key(query)
    return any(
        term in normalized
        for term in ("sinav", "vize", "final", "butunleme", "mazeret", "exam", "midterm", "makeup", "امتحان", "اختبار")
    )


def _is_academic_calendar_query(query: str) -> bool:
    normalized = _query_key(query)
    return (
        "akademik takvim" in normalized
        or ("akademik" in normalized and "takvim" in normalized)
        or "academic calendar" in normalized
        or "التقويم الاكاديمي" in normalized
    )


def _is_menu_query(query: str) -> bool:
    normalized = _query_key(query)
    return any(
        term in normalized
        for term in ("yemek", "menu", "menusu", "yemekhane", "cafeteria", "food", "dining", "طعام", "مقصف", "قائمة")
    )


def _is_location_query(query: str) -> bool:
    normalized = _query_key(query)
    return any(
        term in normalized
        for term in ("nerede", "konum", "adres", "harita", "maps", "location", "where", "map", "اين", "موقع", "خريطة")
    )


def _is_management_query(query: str) -> bool:
    normalized = _query_key(query)
    return any(
        term in normalized
        for term in (
            "rektor",
            "senato",
            "dekanlik",
            "dekanliklar",
            "rektor yardimci",
            "rector",
            "vice rector",
            "senate",
            "deans",
            "عميد",
            "السناتور",
            "رئيس الجامعة",
        )
    )


def _is_faculty_related(result: SearchResult) -> bool:
    haystack = _haystack(result)
    return any(
        term in haystack
        for term in (
            "/iibf",
            "iibf",
            "iktisadi ve idari bilimler",
            "faculty of economics",
        )
    )


def _is_contact_related(query: str, result: SearchResult) -> bool:
    haystack = _haystack(result)
    if _is_faculty_query(query) and "akademikpersonel" in result.chunk.url.lower():
        return False
    if any(term in haystack for term in ("telefon rehberi", "dekana sor", "kurumsal iletisim")):
        return True
    return bool(
        re.search(r"[\w.+-]+@[\w.-]+\.\w+", result.chunk.text)
        or re.search(r"\b0?\s*\(?474\)?", result.chunk.text)
    )


def _is_personnel_related(result: SearchResult) -> bool:
    haystack = _haystack(result)
    return "akademikpersonel" in result.chunk.url.lower() or any(
        term in haystack
        for term in (
            "profesor",
            "docent",
            "doktor ogretim uyesi",
            "arastirma gorevlisi",
        )
    )


def _is_department_related(result: SearchResult) -> bool:
    haystack = _haystack(result)
    return "bolum" in haystack or any(
        normalize_for_matching(term) in haystack for term in DEPARTMENT_TERMS
    )


def _is_announcement_related(result: SearchResult) -> bool:
    haystack = _haystack(result)
    return "/duyuru2/" in result.chunk.url.lower() or any(
        term in haystack for term in ("duyuru", "haber", "etkinlik")
    )


def _is_exam_related(result: SearchResult) -> bool:
    haystack = _haystack(result)
    return any(term in haystack for term in ("sinav", "vize", "final", "butunleme", "mazeret"))


def _is_academic_calendar_related(result: SearchResult) -> bool:
    haystack = _haystack(result)
    return "takvim" in haystack or ("akademik" in haystack and "ders programi" in haystack)


def _is_menu_related(result: SearchResult) -> bool:
    haystack = _haystack(result)
    return any(term in haystack for term in ("yemek", "menu", "yemekhane"))


DEPARTMENT_TERMS = (
    "iktisat",
    "işletme",
    "siyaset bilimi",
    "kamu yönetimi",
    "uluslararası ilişkiler",
    "uluslararasi iliskiler",
    "sağlık yönetimi",
    "saglik yonetimi",
    "yönetim bilişim",
    "yonetim bilisim",
    "elektronik ticaret",
    "uluslararası ticaret",
    "uluslararasi ticaret",
    "lojistik",
)
