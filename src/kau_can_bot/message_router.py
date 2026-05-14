from __future__ import annotations

from typing import List, Optional

from .code_helper import build_code_help_response, is_code_help_query
from .conversation_manager import handle_pre_router
from .document_generator import generate_document_response
from .math_solver import solve_math
from .models import AssistantResponse, UiAction, UiCard, UiTable
from .query_normalizer import normalize_for_matching
from .response_formatter import join_sections, make_bullets, maybe_prefix_with_address
from .safety_filter import apply_safety_filter
from .scraper_manager import OIDB_FORMS_URL, fetch_document_catalog
from .source_manager import build_source_results
from .static_knowledge import get_transport_network, search_city_places, search_dormitories
from .text_normalizer import normalize_user_message
from .user_session import get_preferred_address
from .utils import clean_text


class HybridMessageRouter:
    def route(
        self,
        query: str,
        language: str,
        client_id: str = "",
        user_memory: Optional[dict] = None,
    ) -> Optional[AssistantResponse]:
        normalized = normalize_user_message(query)

        safety = apply_safety_filter(query, language, client_id=client_id)
        if safety is not None and safety.blocked:
            return AssistantResponse(
                answer=safety.answer,
                status=safety.status,
                normalized_query=normalized.normalized,
            )

        conversation_response = handle_pre_router(
            query,
            session=None,
            language=language,
            client_id=client_id,
        )
        if conversation_response is not None:
            conversation_response.normalized_query = normalized.normalized
            return conversation_response

        if self._is_form_lookup_query(normalized.normalized_for_matching):
            return self._document_catalog_response(normalized.normalized, user_memory or {}, client_id)

        math_solution = solve_math(normalized.normalized, language)
        if math_solution is not None:
            return AssistantResponse(
                answer=maybe_prefix_with_address(
                    math_solution.answer,
                    get_preferred_address(client_id, user_memory),
                ),
                status="general",
                normalized_query=normalized.normalized,
            )

        if is_code_help_query(query):
            code_help = build_code_help_response(query, language)
            if code_help is not None:
                return AssistantResponse(
                    answer=maybe_prefix_with_address(
                        code_help.answer,
                        get_preferred_address(client_id, user_memory),
                    ),
                    status="general",
                    normalized_query=normalized.normalized,
                )

        document_response = generate_document_response(query, language)
        if document_response is not None:
            return AssistantResponse(
                answer=document_response.answer,
                status="general",
                normalized_query=normalized.normalized,
            )

        if self._is_dormitory_query(normalized.normalized_for_matching):
            return self._dormitory_response(normalized.normalized, user_memory or {}, client_id)

        if self._is_transport_query(normalized.normalized_for_matching):
            return self._transport_response(normalized.normalized, user_memory or {}, client_id)

        if self._is_city_query(normalized.normalized_for_matching):
            return self._city_response(normalized.normalized, user_memory or {}, client_id)

        return None

    def _document_catalog_response(
        self,
        normalized_query: str,
        user_memory: dict,
        client_id: str,
    ) -> AssistantResponse:
        entries = fetch_document_catalog(force_refresh=False)
        query_key = normalize_user_message(normalized_query).normalized_for_matching
        filtered = [
            entry
            for entry in entries
            if any(token in normalize_for_matching(entry.title) for token in query_key.split() if len(token) > 2)
        ]
        if not filtered:
            filtered = entries[:8]

        cards = [
            UiCard(
                title=entry.title,
                body="Resmi belge/form kaydı",
                meta="Öğrenci İşleri / Formlar",
                url=entry.url,
                actions=[
                    UiAction(label="📄 Dosyayı Aç", url=entry.url, kind="link"),
                    UiAction(label="⬇️ İndir", url=entry.url, kind="download"),
                ],
            )
            for entry in filtered[:8]
        ]
        actions = [UiAction(label="Öğrenci İşleri Formları Sayfasını Aç", url=OIDB_FORMS_URL, kind="link")]
        answer = join_sections(
            [
                "📄 Resmi belge ve form kayıtlarını aşağıda listeledim.",
                "Doğrudan dosya açma/indirme bağlantıları kartlarda yer alıyor.",
            ]
        )

        return AssistantResponse(
            answer=maybe_prefix_with_address(answer, get_preferred_address(client_id, user_memory)),
            status="documents",
            cards=cards,
            actions=actions,
            sources=build_source_results(
                [{"title": entry.title, "url": entry.url} for entry in filtered[:8]]
                + [{"title": "Öğrenci İşleri Form Sayfası", "url": OIDB_FORMS_URL}],
                source_type="document",
            ),
            normalized_query=normalized_query,
        )

    def _dormitory_response(self, normalized_query: str, user_memory: dict, client_id: str) -> AssistantResponse:
        matches = search_dormitories(normalized_query)
        if not matches:
            return AssistantResponse(
                answer="Kars yurtları için güvenilir bir kayıt bulamadım. Yanlış yönlendirme yapmamak adına ilgili yurtlarla doğrudan iletişime geçmeniz önerilir.",
                status="fallback",
                normalized_query=normalized_query,
            )

        focus = matches[0]
        asks_phone = any(term in normalized_query.lower() for term in ("telefon", "iletişim", "iletisim"))
        asks_price = "fiyat" in normalized_query.lower() or "ucret" in normalize_user_message(normalized_query).normalized_for_matching
        wants_detail = any(term in normalized_query.lower() for term in ("hakkinda", "hakkında", "kaç kişilik", "kapasite", "wifi", "internet"))
        exact_name = any(
            normalize_for_matching(clean_text(match.get("name", ""))) in normalize_user_message(normalized_query).normalized_for_matching
            for match in matches[:3]
        )

        if exact_name or asks_phone or asks_price or wants_detail:
            detail_lines = [
                f"Tür: {'KYK / devlet yurdu' if focus.get('type') == 'kyk' else 'Özel yurt'}",
                f"Cinsiyet: {self._gender_label(focus.get('gender', ''))}",
                f"Adres: {focus.get('address') or 'Bu bilgi kaynakta açıkça belirtilmemiştir.'}",
                f"Telefon: {focus.get('phone') or 'Bu bilgi kaynakta açıkça belirtilmemiştir.'}",
                f"Kapasite: {focus.get('capacity') or 'Bu bilgi kaynakta açıkça belirtilmemiştir.'}",
                f"Oda bilgisi: {focus.get('room_capacity') or 'Bu bilgi kaynakta açıkça belirtilmemiştir.'}",
                f"İnternet: {focus.get('internet_info') or 'Bu bilgi kaynakta açıkça belirtilmemiştir.'}",
                f"Başvuru: {focus.get('application_info') or 'Bu bilgi kaynakta açıkça belirtilmemiştir.'}",
                f"Üniversiteye uzaklık: {focus.get('distance_to_kau') or 'Bu bilgi kaynakta açıkça belirtilmemiştir.'}",
            ]
            if asks_price:
                detail_lines.append(
                    f"Fiyat: {focus.get('price_info') or 'Bu bilgi kaynakta açıkça belirtilmemiştir.'}"
                )

            answer = join_sections(
                [
                    f"🏠 {focus.get('name')} için özet bilgi:",
                    make_bullets(detail_lines),
                    "⚠️ Yurt fiyatları ve kontenjan bilgileri dönemsel olarak değişebilir. Kesin bilgi için ilgili yurtla iletişime geçmeniz önerilir.",
                ]
            )
            return AssistantResponse(
                answer=maybe_prefix_with_address(answer, get_preferred_address(client_id, user_memory)),
                status="dormitory",
                cards=[
                    UiCard(
                        title=focus.get("name", "Yurt Bilgisi"),
                        body=(focus.get("address") or "Adres bilgisi kaynakta net görünmüyor."),
                        meta=self._gender_label(focus.get("gender", "")),
                        url=(focus.get("source_urls") or [""])[0],
                        actions=[
                            UiAction(label="🔗 Kaynağı Aç", url=url, kind="link")
                            for url in focus.get("source_urls", [])[:2]
                        ],
                    )
                ],
                sources=build_source_results(
                    [{"title": focus.get("name", "Yurt Kaynağı"), "url": url} for url in focus.get("source_urls", [])],
                    source_type="dormitory",
                ),
                normalized_query=normalized_query,
            )

        table = UiTable(
            caption="Kars yurt özeti",
            columns=["Yurt", "Tür", "Cinsiyet", "Adres", "Telefon"],
            rows=[
                [
                    str(entry.get("name", "")),
                    "KYK" if entry.get("type") == "kyk" else "Özel",
                    self._gender_label(entry.get("gender", "")),
                    str(entry.get("address") or "Belirtilmemiş"),
                    str(entry.get("phone") or "Belirtilmemiş"),
                ]
                for entry in matches[:8]
            ],
        )
        answer = join_sections(
            [
                "🏠 Kars’taki uygun yurt kayıtlarını aşağıda özetledim.",
                "⚠️ Fiyat, kontenjan ve oda tipi gibi değişken bilgiler için ilgili yurtla ayrıca teyit alınması önerilir.",
            ]
        )
        return AssistantResponse(
            answer=maybe_prefix_with_address(answer, get_preferred_address(client_id, user_memory)),
            status="dormitory",
            table=table,
            sources=build_source_results(
                [
                    {"title": entry.get("name", "Yurt Kaynağı"), "url": url}
                    for entry in matches[:8]
                    for url in entry.get("source_urls", [])[:1]
                ],
                source_type="dormitory",
            ),
            normalized_query=normalized_query,
        )

    def _transport_response(self, normalized_query: str, user_memory: dict, client_id: str) -> AssistantResponse:
        network = get_transport_network()
        outbound = network.get("outbound_stops", [])
        inbound = network.get("inbound_stops", [])
        query_key = normalize_user_message(normalized_query).normalized_for_matching
        asks_schedule = "saat" in query_key
        asks_return = any(term in query_key for term in ("donus", "dönüş", "geri"))
        asks_veterinary = "veteriner" in query_key
        asks_fef = any(term in query_key for term in ("fen edebiyat", "kafkas fen edebiyat"))

        if asks_schedule:
            answer = "🚌 Saat bilgisi mevcut kaynakta belirtilmemiştir. Güncel sefer bilgisi için belediye veya kampüs birimleriyle iletişime geçmeniz önerilir."
        elif asks_return:
            answer = join_sections(
                [
                    "🚌 Kampüsten dönüş güzergahı:",
                    make_bullets(inbound),
                ]
            )
        elif asks_veterinary:
            answer = join_sections(
                [
                    "🚌 Veteriner Fakültesi için kampüs içindeki temel iniş noktası:",
                    "📍 Veteriner Fakültesi - Dekanlık Önü",
                ]
            )
        elif asks_fef:
            answer = join_sections(
                [
                    "🚌 Fen-Edebiyat erişimi için öne çıkan hat:",
                    "📍 Kafkas Fen Edebiyat",
                    "Gidiş güzergahındaki ana duraklar:",
                    make_bullets(outbound[:7]),
                ]
            )
        else:
            answer = join_sections(
                [
                    "🚌 Kampüs / üniversite ulaşımı için kullanılan hatlar:",
                    make_bullets(network.get("route_names", [])),
                    "📍 Kampüs içi temel iniş noktası: " + str(network.get("campus_drop_points", {}).get("general", "")),
                ]
            )

        table = UiTable(
            caption="Kampüs ulaşım durakları",
            columns=["Gidiş", "Dönüş"],
            rows=[
                [
                    outbound[index] if index < len(outbound) else "",
                    inbound[index] if index < len(inbound) else "",
                ]
                for index in range(max(len(outbound), len(inbound)))
            ],
        )
        return AssistantResponse(
            answer=maybe_prefix_with_address(answer, get_preferred_address(client_id, user_memory)),
            status="transport",
            table=table,
            sources=build_source_results(
                [{"title": "Kars Kampüs Ulaşım Kaynağı", "url": url} for url in network.get("source_urls", [])],
                source_type="transport",
            ),
            normalized_query=normalized_query,
        )

    def _city_response(self, normalized_query: str, user_memory: dict, client_id: str) -> Optional[AssistantResponse]:
        places = search_city_places(normalized_query)
        if not places:
            return None

        top_places = places[:4]
        answer = join_sections(
            [
                "📍 Kars için öne çıkan bilgi ve gezi önerileri:",
                make_bullets(
                    [
                        f"{item.get('title')}: {item.get('summary')}"
                        for item in top_places
                    ]
                ),
            ]
        )
        cards = [
            UiCard(
                title=str(item.get("title", "")),
                body=str(item.get("summary", "")),
                meta=str(item.get("student_tip", "")),
                url=str(item.get("source_url", "")),
                actions=[UiAction(label="🔗 Kaynağı Aç", url=str(item.get("source_url", "")), kind="link")],
            )
            for item in top_places
        ]
        return AssistantResponse(
            answer=maybe_prefix_with_address(answer, get_preferred_address(client_id, user_memory)),
            status="city",
            cards=cards,
            sources=build_source_results(
                [{"title": item.get("title", "Kars Kaynağı"), "url": item.get("source_url", "")} for item in top_places],
                source_type="city",
            ),
            normalized_query=normalized_query,
        )

    def _is_form_lookup_query(self, normalized_query: str) -> bool:
        return any(
            term in normalized_query
            for term in (
                "hazir dilekce",
                "hazır dilekçe",
                "form indir",
                "formlar",
                "belge indir",
                "ogrenci isleri formlari",
                "öğrenci işleri formları",
                "mazeret sinavi basvuru formu",
                "kayıt dondurma formu",
                "kayit dondurma formu",
            )
        )

    def _is_dormitory_query(self, normalized_query: str) -> bool:
        return any(
            self._contains_phrase(normalized_query, term)
            for term in (
                "yurt",
                "yurdu",
                "yurtlar",
                "yurtlari",
                "kyk",
                "kredi yurtlar kurumu",
                "tugva",
                "barinma",
                "barınma",
            )
        )

    def _is_transport_query(self, normalized_query: str) -> bool:
        transport_terms = (
            "otobus",
            "otobusu",
            "ulasim",
            "kampuse nasil gider",
            "kampuse nasil giderim",
            "universiteye nasil gider",
            "universiteye nasil giderim",
            "hangi durak",
            "guzergah",
            "donus",
            "durak",
            "belediye otobusu",
            "eski garaj",
            "sefer",
            "kampus ici",
            "kampus ici nerede inerim",
        )
        location_terms = (
            "veteriner fakultesi",
            "fen edebiyat",
            "kyk kiz yurdu",
            "toplu konutlar",
            "pasacayir",
            "toki digor",
        )
        movement_terms = ("otobus", "otobusu", "gider", "gidilir", "nasil gider", "durak", "ulasim", "guzergah", "geciyor", "gectigi")
        return self._contains_any_phrase(normalized_query, transport_terms) or (
            self._contains_any_phrase(normalized_query, location_terms)
            and self._contains_any_phrase(normalized_query, movement_terms)
        )

    def _is_city_query(self, normalized_query: str) -> bool:
        tourism_terms = (
            "kars tarihi",
            "kars kulturu",
            "kars mutfagi",
            "ogrenciler icin kars",
            "hafta sonu oner",
            "gezilecek yerler",
            "turistik",
            "ani harabeleri",
            "ani",
            "kars kalesi",
            "cildir golu",
            "sarikamis",
            "tas kopru",
            "fethiye camii",
            "kumbet camii",
            "kaz eti",
            "gravyer",
            "kasar",
        )
        return self._contains_any_phrase(normalized_query, tourism_terms)

    def _gender_label(self, value: str) -> str:
        mapping = {
            "female": "Kız",
            "male": "Erkek",
            "mixed": "Kız / Erkek",
        }
        return mapping.get(value, value or "Belirtilmemiş")

    def _contains_any_phrase(self, normalized_query: str, terms: tuple[str, ...]) -> bool:
        return any(self._contains_phrase(normalized_query, term) for term in terms)

    def _contains_phrase(self, normalized_query: str, term: str) -> bool:
        needle = normalize_for_matching(term)
        haystack = f" {normalized_query} "
        return f" {needle} " in haystack

    def _clean_address_value(self, value: str) -> str:
        cleaned = clean_text(value)
        if not cleaned:
            return ""
        cleaned = re.sub(r"(?i)\b(bana|artik|artık|diye|hitap|et)\b", " ", cleaned)
        cleaned = clean_text(cleaned)
        return cleaned.title()
