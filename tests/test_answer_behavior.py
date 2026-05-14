from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import List, Optional
from unittest.mock import patch

from kau_can_bot.answer import ISTANBUL_TZ, WEEKDAY_NAMES, WELCOME_MESSAGE, WebsiteGroundedAssistant, _sanitize_answer_text
from kau_can_bot.config import Settings
from kau_can_bot.live_support import LiveSupportResult
from kau_can_bot.models import Chunk, SearchResult
from kau_can_bot.user_session import get_session_state
from kau_can_bot.utils import stable_id


class DummyIndex:
    def __init__(self, results: List[SearchResult]) -> None:
        self.results = results
        self.searched_query = None

    def search(self, query: str, top_k: int = 3) -> List[SearchResult]:
        self.searched_query = query
        return self.results


class BrokenGenerator:
    is_configured = True

    def generate_general(self, query: str, memory_context: str = "", support_context: str = "") -> Optional[str]:
        raise RuntimeError("broken")


class GoodGenerator:
    is_configured = True

    def generate_general(self, query: str, memory_context: str = "", support_context: str = "") -> Optional[str]:
        return "Python, genel amaçlı bir programlama dilidir."


def build_result(title: str, url: str, text: str, score: float = 0.35) -> SearchResult:
    return SearchResult(
        chunk=Chunk(
            id=stable_id(title, url),
            title=title,
            url=url,
            text=text,
            ordinal=1,
        ),
        score=score,
    )


class AnswerBehaviorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = Settings(llm_provider="local", use_openai=False, top_k=3)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.session_path = Path(self.temp_dir.name) / "user_sessions.json"
        self.session_patcher = patch("kau_can_bot.user_session.SESSION_STATE_PATH", self.session_path)
        self.session_patcher.start()

    def tearDown(self) -> None:
        self.session_patcher.stop()
        self.temp_dir.cleanup()

    def build_official_snapshot(self) -> dict:
        return {
            "faculty_dean": {
                "name": "Prof. Dr. Deniz ÖZYAKIŞIR",
                "designation": "İktisadi ve İdari Bilimler Fakültesi Dekanı",
                "source_url": "https://www.kafkas.edu.tr/rektorluk/TR/sayfaYeni651",
                "detail_url": "https://unis.kafkas.edu.tr/akademisyen/denizozyakisir",
            },
            "faculty_personnel": [
                {
                    "name": "GÖKHAN KERSE",
                    "academic_title": "Doçent",
                    "roles": ["BÖLÜM BAŞKANI"],
                    "department": "Yönetim Bilişim Sistemleri",
                },
                {
                    "name": "MUHAMMED AKİF YENİKAYA",
                    "academic_title": "Doktor Öğretim Üyesi",
                    "roles": ["BÖLÜM BAŞKAN YARDIMCISI"],
                    "department": "Yönetim Bilişim Sistemleri",
                },
                {
                    "name": "SEYHAN ÖZTÜRK",
                    "academic_title": "Profesör",
                    "roles": ["BÖLÜM BAŞKANI"],
                    "department": "İşletme",
                },
            ],
            "senate_people": [
                {
                    "name": "Prof. Dr. Deniz ÖZYAKIŞIR",
                    "designation": "İktisadi ve İdari Bilimler Fakültesi Dekanı",
                    "source_url": "https://www.kafkas.edu.tr/rektorluk/TR/sayfaYeni651",
                    "detail_url": "https://unis.kafkas.edu.tr/akademisyen/denizozyakisir",
                },
                {
                    "name": "Prof. Dr. Adem BALKAYA",
                    "designation": "Fen-Edebiyat Fakültesi Dekanı",
                    "source_url": "https://www.kafkas.edu.tr/rektorluk/TR/sayfaYeni651",
                    "detail_url": "https://unis.kafkas.edu.tr/akademisyen/adembalkaya",
                },
            ],
            "faculty_navigation": [
                {
                    "title": "Misyon & Vizyon",
                    "url": "https://www.kafkas.edu.tr/iibf/tr/sayfaYeni17979",
                    "normalized_title": "misyon vizyon",
                },
                {
                    "title": "Formlar",
                    "url": "https://www.kafkas.edu.tr/iibf/tr/sayfaYeni17988",
                    "normalized_title": "formlar",
                },
                {
                    "title": "Kurumsal İletişim Komisyonu",
                    "url": "https://www.kafkas.edu.tr/iibf/tr/sayfaYeni18049",
                    "normalized_title": "kurumsal iletisim komisyonu",
                },
                {
                    "title": "Dijital Dönüşüm Komisyonu",
                    "url": "https://www.kafkas.edu.tr/iibf/tr/sayfaYeni18050",
                    "normalized_title": "dijital donusum komisyonu",
                },
                {
                    "title": "KAÜİİBF Dergisi",
                    "url": "https://www.kafkas.edu.tr/iibf/tr/sayfaYeni18063",
                    "normalized_title": "kauiibf dergisi",
                },
                {
                    "title": "Fakülte Bülteni",
                    "url": "https://www.kafkas.edu.tr/iibf/tr/sayfaYeni18180",
                    "normalized_title": "fakulte bulteni",
                },
                {
                    "title": "Birim Faaliyet Raporu",
                    "url": "https://www.kafkas.edu.tr/iibf/tr/sayfaYeni18001",
                    "normalized_title": "birim faaliyet raporu",
                },
            ],
            "faculty_pages": {
                "https://www.kafkas.edu.tr/iibf/tr/sayfaYeni17979": {
                    "title": "Misyon & Vizyon",
                    "url": "https://www.kafkas.edu.tr/iibf/tr/sayfaYeni17979",
                    "summary": "Fakülte; bilimsel, yenilikçi ve toplumsal katkı odaklı eğitim anlayışını benimsemektedir.",
                    "body_excerpt": "Fakülte; bilimsel, yenilikçi ve toplumsal katkı odaklı eğitim anlayışını benimsemektedir.",
                }
            },
            "department_order": ["ybs", "isletme"],
            "departments": {
                "ybs": {
                    "key": "ybs",
                    "name_tr": "Yönetim Bilişim Sistemleri",
                    "name_en": "Management Information Systems",
                    "root_url": "https://www.kafkas.edu.tr/iibfybs",
                    "important_links": {
                        "academic_staff": "https://www.kafkas.edu.tr/iibfybs/tr/akademikpersonel",
                        "announcements": "https://www.kafkas.edu.tr/iibfybs/tr/tumduyurular2",
                        "news": "https://www.kafkas.edu.tr/iibfybs/tr/tumHaberler",
                        "events": "https://www.kafkas.edu.tr/iibfybs/tr/tumEtkinlikler2",
                        "management": "https://www.kafkas.edu.tr/iibfybs/tr/sayfaYeni17874",
                        "journal": "https://www.kafkas.edu.tr/iibfybs/tr/sayfaYeni17891",
                        "advising": "https://www.kafkas.edu.tr/dosyalar/iibfybs/a794b8fe-ccb5-45f3-8f61-b3823c2cef48.pdf",
                        "clubs": "https://www.kafkas.edu.tr/iibfybs/tr/sayfaYeni17976",
                    },
                    "overview": "Yönetim Bilişim Sistemleri bölüm sayfasında akademik kadro, duyurular, haberler, etkinlikler bağlantıları yer almaktadır.",
                    "personnel": [
                        {
                            "name": "GÖKHAN KERSE",
                            "academic_title": "Doçent",
                            "roles": ["BÖLÜM BAŞKANI"],
                            "department": "Yönetim Bilişim Sistemleri",
                        },
                        {
                            "name": "MUHAMMED AKİF YENİKAYA",
                            "academic_title": "Doktor Öğretim Üyesi",
                            "roles": ["BÖLÜM BAŞKAN YARDIMCISI"],
                            "department": "Yönetim Bilişim Sistemleri",
                        },
                        {
                            "name": "KAMİLE MERİÇ",
                            "academic_title": "Doktor Öğretim Üyesi",
                            "roles": ["Öğretim Üyesi"],
                            "department": "Yönetim Bilişim Sistemleri",
                        },
                        {
                            "name": "ONUR OKTAYSOY",
                            "academic_title": "Doktor Öğretim Üyesi",
                            "roles": ["Öğretim Üyesi"],
                            "department": "Yönetim Bilişim Sistemleri",
                        },
                        {
                            "name": "SEVGÜL EKİNCİ",
                            "academic_title": "Doktor Öğretim Üyesi",
                            "roles": ["Öğretim Üyesi"],
                            "department": "Yönetim Bilişim Sistemleri",
                        },
                    ],
                    "announcements": [],
                    "news": [],
                    "events": [],
                    "special_pages": {
                        "management": {
                            "title": "YBS Bölüm Yönetimi",
                            "url": "https://www.kafkas.edu.tr/iibfybs/tr/sayfaYeni17874",
                            "people": [
                                {"name": "Gökhan KERSE", "role": "Bölüm Başkanı"},
                                {"name": "M. Akif YENİKAYA", "role": "Bölüm Başkan Yardımcısı"},
                            ],
                        },
                        "journal": {
                            "title": "YBS Bölüm Dergisi",
                            "url": "https://www.kafkas.edu.tr/iibfybs/tr/sayfaYeni17891",
                            "journal_name": "Kafkas Üniversitesi Yönetim ve Bilişim Dergisi (KAÜYÖNBİD)",
                            "purpose": "Yönetim Bilişim Sistemleri alanında akademik bilgi üretimini desteklemek amacıyla bölüm bünyesinde yayımlanmaktadır.",
                            "scope": "Açık erişimli ve hakemli bir akademik dergidir.",
                            "links": [
                                {"label": "KAÜYÖNBİD", "url": "https://dergipark.org.tr/tr/pub/kaujomi"},
                            ],
                        },
                        "advising": {
                            "title": "YBS Akademik Danışmanlıklar",
                            "url": "https://www.kafkas.edu.tr/dosyalar/iibfybs/a794b8fe-ccb5-45f3-8f61-b3823c2cef48.pdf",
                            "class_advisors": [
                                {
                                    "class_label": "1. Sınıf",
                                    "advisors": [
                                        {"academic_title": "Prof. Dr.", "name": "GÖKHAN KERSE", "schedule": "Pazartesi 09:30-11:30"},
                                        {"academic_title": "Dr. Öğr. Üyesi", "name": "KAMİLE MERİÇ", "schedule": "Pazartesi 13.15-16.00"},
                                    ],
                                },
                                {
                                    "class_label": "2. Sınıf",
                                    "advisors": [
                                        {"academic_title": "Prof. Dr.", "name": "GÖKHAN KERSE", "schedule": "Pazartesi 09:30-11:30"},
                                    ],
                                },
                            ],
                        },
                        "clubs": {
                            "title": "YBS Öğrenci Kulüpleri",
                            "url": "https://www.kafkas.edu.tr/iibfybs/tr/sayfaYeni17976",
                            "clubs": [
                                {"name": "Techno Bilişim Kulübü", "advisor_role": "Akademik Danışman", "advisor_name": "Dr. Öğr. Üyesi M. Akif YENİKAYA"},
                                {"name": "Teknofest Kulübü", "advisor_role": "Akademik Danışman", "advisor_name": "Dr. Öğr. Üyesi Onur OKTAYSOY"},
                            ],
                        },
                    },
                },
            },
            "faculty_content": {
                "announcements": [
                    {
                        "title": "Ara Sınav Duyurusu",
                        "date": "22 Nisan 2026",
                        "summary": "Vize mazeret sınavları ilan edilmiştir.",
                        "url": "https://www.kafkas.edu.tr/iibf/tr/duyuru2/ara-sinav",
                    }
                ],
                "news": [],
                "events": [],
            },
        }

    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_greeting_short_circuits_search(self, _log_query, _log_interaction) -> None:
        index = DummyIndex([])
        assistant = WebsiteGroundedAssistant(index=index, settings=self.settings)

        response = assistant.answer_with_context("mrbb")

        self.assertEqual(response.status, "greeting")
        self.assertEqual(response.answer, WELCOME_MESSAGE)
        self.assertIsNone(index.searched_query)

    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_add_drop_petition_uses_placeholders_without_random_name(self, _log_query, _log_interaction) -> None:
        assistant = WebsiteGroundedAssistant(index=DummyIndex([]), settings=self.settings)

        response = assistant.answer_with_context(
            "bana bir ders ekle bırak için dilekçe yaz",
            client_id="user-document-1",
        )

        self.assertEqual(response.status, "document")
        self.assertIn("Ders Ekle-Bırak Talebi", response.answer)
        self.assertIn("[Ad Soyad]", response.answer)
        self.assertNotIn("Ahmet", response.answer)
        self.assertFalse(response.show_google_button)

    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_address_correction_is_treated_as_contextual_fix(self, _log_query, _log_interaction) -> None:
        assistant = WebsiteGroundedAssistant(index=DummyIndex([]), settings=self.settings)

        assistant.answer_with_context(
            "bana bir ders ekle bırak için dilekçe yaz",
            client_id="user-document-2",
        )
        response = assistant.answer_with_context("ahmet deme", client_id="user-document-2")

        self.assertEqual(response.status, "address_correction")
        self.assertIn("o isimle hitap etmeyeceğim", response.answer)
        self.assertIn("[Ad Soyad]", response.answer)
        self.assertNotIn("hocanızın", response.answer.lower())
        self.assertFalse(response.show_google_button)

    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_name_rejection_does_not_save_rejected_name(self, _log_query, _log_interaction) -> None:
        assistant = WebsiteGroundedAssistant(index=DummyIndex([]), settings=self.settings)

        response = assistant.answer_with_context("ismim Ahmet değil", client_id="user-document-2b")
        session = get_session_state("user-document-2b")

        self.assertEqual(response.status, "address_correction")
        self.assertIn("o isimle hitap etmeyeceğim", response.answer)
        self.assertIn("Ahmet", " ".join(session.get("disallowed_names", [])))
        self.assertNotEqual(session.get("user_name"), "Ahmet")
        self.assertFalse(response.show_google_button)

    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_style_revision_keeps_document_context(self, _log_query, _log_interaction) -> None:
        assistant = WebsiteGroundedAssistant(index=DummyIndex([]), settings=self.settings)

        assistant.answer_with_context(
            "bana bir ders ekle bırak için dilekçe yaz",
            client_id="user-document-3",
        )
        assistant.answer_with_context("ismimi kullanma", client_id="user-document-3")
        response = assistant.answer_with_context("daha resmi yaz", client_id="user-document-3")

        self.assertIn("yeniden düzenledim", response.answer)
        self.assertIn("Ders Ekle-Bırak Talebi", response.answer)
        self.assertIn("[Ad Soyad]", response.answer)
        self.assertNotIn("Google", " ".join(source.chunk.title for source in response.sources))

    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_thanks_response_does_not_show_search_sources(self, _log_query, _log_interaction) -> None:
        assistant = WebsiteGroundedAssistant(index=DummyIndex([]), settings=self.settings)

        response = assistant.answer_with_context("teşekkür ederim", client_id="user-thanks-1")

        self.assertEqual(response.status, "smalltalk")
        self.assertFalse(response.sources)
        self.assertFalse(response.show_google_button)

    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_contact_answer_exposes_clean_sources(self, _log_query, _log_interaction) -> None:
        result = build_result(
            title="İKTİSADİ VE İDARİ BİLİMLER FAKÜLTESİ",
            url="https://kafkas.edu.tr/iibf/tr",
            text=(
                "Bağlantı: Dekana Sor | URL: https://kafkas.edu.tr/iibf/tr/sayfaYeni18817 "
                "Bağlantı: Telefon Rehberi | URL: https://kafkas.edu.tr/kau/rehber2"
            ),
        )
        assistant = WebsiteGroundedAssistant(index=DummyIndex([result]), settings=self.settings)

        response = assistant.answer_with_context("ııbf iletişim")

        self.assertEqual(response.status, "direct_link")
        self.assertIn("📞", response.answer)
        self.assertTrue(any("sayfaYeni18034" in source.chunk.url for source in response.sources))
        self.assertTrue(any(source.chunk.url.startswith("tel:") for source in response.sources))
        self.assertTrue(any(source.chunk.url.startswith("mailto:") for source in response.sources))

    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_contact_typo_in_english_like_query_is_normalized(self, _log_query, _log_interaction) -> None:
        assistant = WebsiteGroundedAssistant(index=DummyIndex([]), settings=self.settings)

        response = assistant.answer_with_context("iibf contcat")

        self.assertEqual(response.status, "direct_link")
        self.assertIn("contact", response.answer.lower())

    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_direct_service_links_are_returned(self, _log_query, _log_interaction) -> None:
        assistant = WebsiteGroundedAssistant(index=DummyIndex([]), settings=self.settings)

        menu_response = assistant.answer_with_context("yemekhane menüsü")
        self.assertEqual(menu_response.status, "direct_link")
        self.assertEqual(menu_response.sources[0].chunk.url, "https://www.kafkas.edu.tr/skdb")

        obs_response = assistant.answer_with_context("OBS")
        self.assertEqual(obs_response.status, "direct_link")
        self.assertEqual(obs_response.sources[0].chunk.url, "https://obsyeni.kafkas.edu.tr")

        library_response = assistant.answer_with_context("kütüphane")
        self.assertEqual(library_response.status, "direct_link")
        self.assertEqual(library_response.sources[0].chunk.url, "https://www.kafkas.edu.tr/kddb/TR/default.aspx")

        english_contact = assistant.answer_with_context("iibf contact")
        self.assertEqual(english_contact.status, "direct_link")
        self.assertIn("contact", english_contact.answer.lower())

        faculty_contact = assistant.answer_with_context("What are the faculty contact details?", preferred_language="en")
        self.assertEqual(faculty_contact.status, "direct_link")
        self.assertTrue(any(source.chunk.url.startswith("tel:") for source in faculty_contact.sources))

    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_library_faq_shortcut_returns_hours(self, _log_query, _log_interaction) -> None:
        assistant = WebsiteGroundedAssistant(index=DummyIndex([]), settings=self.settings)

        response = assistant.answer_with_context("Kütüphane hangi saatlerde açık?")

        self.assertEqual(response.status, "direct_answer")
        self.assertIn("08:00-20:00", response.answer)
        self.assertTrue(any("kddb" in source.chunk.url.lower() for source in response.sources))

    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_faculty_form_shortcut_returns_forms_page(self, _log_query, _log_interaction) -> None:
        assistant = WebsiteGroundedAssistant(index=DummyIndex([]), settings=self.settings)

        response = assistant.answer_with_context("Kayıt dondurma başvuru formu")

        self.assertEqual(response.status, "direct_answer")
        self.assertIn("Kayıt Dondurma Başvuru Formu", response.answer)
        self.assertTrue(any("sayfaYeni17988" in source.chunk.url for source in response.sources))

    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_smalltalk_is_supported(self, _log_query, _log_interaction) -> None:
        assistant = WebsiteGroundedAssistant(index=DummyIndex([]), settings=self.settings)

        response = assistant.answer_with_context("merhaba nasılsın")
        short_response = assistant.answer_with_context("nbr")
        gratitude_response = assistant.answer_with_context("saool")
        farewell_response = assistant.answer_with_context("gorusuruz")
        english_response = assistant.answer_with_context("how r u", preferred_language="en")
        arabic_response = assistant.answer_with_context("شلونك", preferred_language="ar")

        self.assertEqual(response.status, "smalltalk")
        self.assertTrue("yardımcı" in response.answer or "iyiyim" in response.answer.lower())
        self.assertEqual(short_response.status, "smalltalk")
        self.assertIsNone(getattr(assistant.index, "searched_query", None))
        self.assertEqual(gratitude_response.status, "smalltalk")
        self.assertIn("Rica ederim", gratitude_response.answer)
        self.assertEqual(farewell_response.status, "smalltalk")
        self.assertIn("Görüşmek üzere", farewell_response.answer)
        self.assertEqual(english_response.status, "smalltalk")
        self.assertTrue("chat" in english_response.answer.lower() or "question" in english_response.answer.lower())
        self.assertEqual(arabic_response.status, "smalltalk")
        self.assertTrue("الدردشة" in arabic_response.answer or "بخير" in arabic_response.answer)

    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_mixed_language_identity_prefers_english_response(self, _log_query, _log_interaction) -> None:
        assistant = WebsiteGroundedAssistant(index=DummyIndex([]), settings=self.settings)

        response = assistant.answer_with_context("merhaba what can you do")

        self.assertEqual(response.status, "smalltalk")
        self.assertIn("I am KAUCAN Beta", response.answer)

    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_religious_greeting_variant_is_detected(self, _log_query, _log_interaction) -> None:
        assistant = WebsiteGroundedAssistant(index=DummyIndex([]), settings=self.settings)

        response = assistant.answer_with_context("selamun aleyküm")

        self.assertEqual(response.status, "greeting")
        self.assertIn("KAÜCAN Beta", response.answer)

    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_assistant_identity_questions_use_chatbot_intro(self, _log_query, _log_interaction) -> None:
        assistant = WebsiteGroundedAssistant(index=DummyIndex([]), settings=self.settings)

        response = assistant.answer_with_context("sen kimsin")
        capability_response = assistant.answer_with_context("ne yapabilirsin")

        self.assertEqual(response.status, "smalltalk")
        self.assertIn("KAÜCAN Beta", response.answer)
        self.assertIn("Kafkas Üniversitesi", response.answer)
        self.assertIn("İİBF", response.answer)
        self.assertNotIn("Tolga", response.answer)
        self.assertEqual(capability_response.status, "smalltalk")
        self.assertIn("kampüs", capability_response.answer.lower())
        self.assertIn("duyurular", capability_response.answer.lower())
        self.assertIn("akademik kadro", capability_response.answer.lower())

    @patch("kau_can_bot.answer._fetch_rector_name", return_value="Prof. Dr. Hüsnü KAPU")
    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_management_shortcuts_are_returned(self, _log_query, _log_interaction, _fetch_rector_name) -> None:
        assistant = WebsiteGroundedAssistant(index=DummyIndex([]), settings=self.settings)

        response = assistant.answer_with_context("rektör kim")

        self.assertEqual(response.status, "direct_link")
        self.assertIn("Hüsnü KAPU", response.answer)
        self.assertEqual(response.sources[0].chunk.url, "https://www.kafkas.edu.tr/rektorluk/tr/sayfaYeni655")

    @patch("kau_can_bot.answer._fetch_rector_name", return_value="Prof. Dr. Hüsnü KAPU")
    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_targeted_abuse_blocks_management_answers(self, _log_query, _log_interaction, _fetch_rector_name) -> None:
        assistant = WebsiteGroundedAssistant(index=DummyIndex([]), settings=self.settings)

        response = assistant.answer_with_context("rektör aptal mı")
        rectorate_response = assistant.answer_with_context("rektörlük makamı gerzek mi")
        curse_response = assistant.answer_with_context("bu üniversitenin rektörünün allah belasını versin")
        dislike_response = assistant.answer_with_context("rektörü sevmiyorum")
        hate_response = assistant.answer_with_context("rektörden nefret ediyorum")
        dirt_response = assistant.answer_with_context("rektör pislik")
        resign_response = assistant.answer_with_context("rektör istifa etsin")

        self.assertEqual(response.status, "blocked_abuse")
        self.assertEqual(response.answer, "Bu soruyu yanıtlayamam.")
        self.assertNotIn("Hüsnü KAPU", response.answer)
        self.assertEqual(rectorate_response.status, "blocked_abuse")
        self.assertEqual(rectorate_response.answer, "Bu soruyu yanıtlayamam.")
        self.assertNotIn("Hüsnü KAPU", rectorate_response.answer)
        self.assertEqual(curse_response.status, "blocked_abuse")
        self.assertEqual(curse_response.answer, "Bu soruyu yanıtlayamam.")
        self.assertNotIn("Hüsnü KAPU", curse_response.answer)
        self.assertEqual(dislike_response.status, "blocked_abuse")
        self.assertEqual(dislike_response.answer, "Bu soruyu yanıtlayamam.")
        self.assertNotIn("Hüsnü KAPU", dislike_response.answer)
        self.assertEqual(hate_response.status, "blocked_abuse")
        self.assertEqual(hate_response.answer, "Bu soruyu yanıtlayamam.")
        self.assertNotIn("Hüsnü KAPU", hate_response.answer)
        self.assertEqual(dirt_response.status, "blocked_abuse")
        self.assertEqual(dirt_response.answer, "Bu soruyu yanıtlayamam.")
        self.assertNotIn("Hüsnü KAPU", dirt_response.answer)
        self.assertEqual(resign_response.status, "blocked_abuse")
        self.assertEqual(resign_response.answer, "Bu soruyu yanıtlayamam.")
        self.assertNotIn("Hüsnü KAPU", resign_response.answer)

    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_targeted_abuse_blocks_dean_answers(self, _log_query, _log_interaction) -> None:
        assistant = WebsiteGroundedAssistant(index=DummyIndex([]), settings=self.settings)

        response = assistant.answer_with_context("iibf dekanı çok kötü birisi")
        insult_response = assistant.answer_with_context("dekan salak")
        hate_response = assistant.answer_with_context("iibf dekanından nefret ediyorum")
        expel_response = assistant.answer_with_context("dekan kovulsun")

        self.assertEqual(response.status, "blocked_abuse")
        self.assertEqual(response.answer, "Bu soruyu yanıtlayamam.")
        self.assertNotIn("Deniz ÖZYAKIŞIR", response.answer)
        self.assertEqual(insult_response.status, "blocked_abuse")
        self.assertEqual(insult_response.answer, "Bu soruyu yanıtlayamam.")
        self.assertEqual(hate_response.status, "blocked_abuse")
        self.assertEqual(hate_response.answer, "Bu soruyu yanıtlayamam.")
        self.assertNotIn("Deniz ÖZYAKIŞIR", hate_response.answer)
        self.assertEqual(expel_response.status, "blocked_abuse")
        self.assertEqual(expel_response.answer, "Bu soruyu yanıtlayamam.")
        self.assertNotIn("Deniz ÖZYAKIŞIR", expel_response.answer)

    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_targeted_abuse_blocks_campus_service_answers(self, _log_query, _log_interaction) -> None:
        assistant = WebsiteGroundedAssistant(index=DummyIndex([]), settings=self.settings)

        faculty_response = assistant.answer_with_context("hocalar aptal")
        library_response = assistant.answer_with_context("kütüphane rezil")
        student_affairs_response = assistant.answer_with_context("öğrenci işleri berbat")

        self.assertEqual(faculty_response.status, "blocked_abuse")
        self.assertEqual(faculty_response.answer, "Bu soruyu yanıtlayamam.")
        self.assertEqual(library_response.status, "blocked_abuse")
        self.assertEqual(library_response.answer, "Bu soruyu yanıtlayamam.")
        self.assertEqual(student_affairs_response.status, "blocked_abuse")
        self.assertEqual(student_affairs_response.answer, "Bu soruyu yanıtlayamam.")

    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_short_iibf_queries_request_clarification(self, _log_query, _log_interaction) -> None:
        assistant = WebsiteGroundedAssistant(index=DummyIndex([]), settings=self.settings)

        response = assistant.answer_with_context("ibf")

        self.assertEqual(response.status, "clarification")
        self.assertIn("İktisadi ve İdari Bilimler Fakültesi", response.answer)
        self.assertIn("duyurular", response.answer.lower())

    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_short_ambiguous_queries_request_clarification(self, _log_query, _log_interaction) -> None:
        assistant = WebsiteGroundedAssistant(index=DummyIndex([]), settings=self.settings)

        response = assistant.answer_with_context("personel")

        self.assertEqual(response.status, "clarification")
        self.assertIn("biraz detaylandırır", response.answer.lower())

    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_location_shortcut_is_returned(self, _log_query, _log_interaction) -> None:
        assistant = WebsiteGroundedAssistant(index=DummyIndex([]), settings=self.settings)

        response = assistant.answer_with_context("iibf nerede")
        route_response = assistant.answer_with_context("hayır yani iibf ye nasıl giderim yol tarifi ver")
        typo_route_response = assistant.answer_with_context("iibf ye naslı gidem?")
        ibf_route_response = assistant.answer_with_context("ibf ye nasıl gidilir")

        self.assertEqual(response.status, "direct_link")
        self.assertEqual(response.sources[0].chunk.url, "https://maps.app.goo.gl/HMYYaxbZBcZVisbN7")
        self.assertEqual(route_response.status, "direct_link")
        self.assertIn("Kafkas Üniversitesi İİBF için yol tarifi", route_response.answer)
        self.assertNotIn("ye için", route_response.answer)
        self.assertIn("destination=Kafkas+%C3%9Cniversitesi+%C4%B0%C4%B0BF", route_response.sources[0].chunk.url)
        self.assertEqual(typo_route_response.status, "direct_link")
        self.assertIn("Kafkas Üniversitesi İİBF için yol tarifi", typo_route_response.answer)
        self.assertEqual(ibf_route_response.status, "direct_link")
        self.assertIn("Kafkas Üniversitesi İİBF için yol tarifi", ibf_route_response.answer)

    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_classroom_location_shortcut_uses_defined_layout(self, _log_query, _log_interaction) -> None:
        assistant = WebsiteGroundedAssistant(index=DummyIndex([]), settings=self.settings)

        response = assistant.answer_with_context("201 nolu derslik nerede?")
        hall_response = assistant.answer_with_context("Hüseyin Aytemiz Konferans Salonu nerede?")
        ybs_response = assistant.answer_with_context("YBS bölümü nerede?")
        deanery_response = assistant.answer_with_context("dekanlık nerede nasıl giderim")
        prayer_response = assistant.answer_with_context("mescid nerede")

        self.assertEqual(response.status, "direct_answer")
        self.assertIn("2. katta", response.answer)
        self.assertIn("Yönetim Bilişim Sistemleri", response.answer)
        self.assertEqual(hall_response.status, "direct_answer")
        self.assertIn("3. katta", hall_response.answer)
        self.assertEqual(ybs_response.status, "direct_answer")
        self.assertIn("2. kattadır", ybs_response.answer)
        self.assertEqual(deanery_response.status, "direct_answer")
        self.assertIn("3. kattadır", deanery_response.answer)
        self.assertEqual(prayer_response.status, "direct_answer")
        self.assertIn("bodrum", prayer_response.answer.lower())

    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_basic_math_is_solved(self, _log_query, _log_interaction) -> None:
        assistant = WebsiteGroundedAssistant(index=DummyIndex([]), settings=self.settings)

        response = assistant.answer_with_context("2 artı 2 kaç eder")

        self.assertEqual(response.status, "general")
        self.assertIn("= 4", response.answer)

    @patch("kau_can_bot.answer.ensure_faculty_content", side_effect=lambda snapshot, *_: snapshot)
    @patch("kau_can_bot.answer.get_official_snapshot")
    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_dean_queries_use_official_sources(
        self,
        _log_query,
        _log_interaction,
        mock_snapshot,
        _ensure_faculty_content,
    ) -> None:
        mock_snapshot.return_value = self.build_official_snapshot()
        assistant = WebsiteGroundedAssistant(index=DummyIndex([]), settings=self.settings)

        response = assistant.answer_with_context("İİBF dekanı kim?")

        self.assertEqual(response.status, "official")
        self.assertIn("Deniz ÖZYAKIŞIR", response.answer)
        self.assertTrue(any("sayfaYeni651" in source.chunk.url for source in response.sources))

    @patch("kau_can_bot.answer.ensure_department_content", side_effect=lambda snapshot, *_: snapshot)
    @patch("kau_can_bot.answer.get_official_snapshot")
    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_department_staff_queries_use_official_snapshot(
        self,
        _log_query,
        _log_interaction,
        mock_snapshot,
        _ensure_department_content,
    ) -> None:
        mock_snapshot.return_value = self.build_official_snapshot()
        assistant = WebsiteGroundedAssistant(index=DummyIndex([]), settings=self.settings)

        response = assistant.answer_with_context("YBS akademik kadro")

        self.assertEqual(response.status, "official")
        self.assertIn("Yönetim Bilişim Sistemleri", response.answer)
        self.assertTrue(any("iibfybs/tr/akademikpersonel" in source.chunk.url for source in response.sources))

    @patch("kau_can_bot.answer.find_unis_person_profile", return_value=None)
    @patch("kau_can_bot.answer.ensure_department_special_pages", side_effect=lambda snapshot, *_: snapshot)
    @patch("kau_can_bot.answer.get_official_snapshot")
    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_ybs_management_queries_use_ybs_management_page(
        self,
        _log_query,
        _log_interaction,
        mock_snapshot,
        _ensure_special_pages,
        _find_person,
    ) -> None:
        mock_snapshot.return_value = self.build_official_snapshot()
        assistant = WebsiteGroundedAssistant(index=DummyIndex([]), settings=self.settings)

        response = assistant.answer_with_context("YBS bölüm başkanı kim?")

        self.assertEqual(response.status, "official")
        self.assertIn("Bölüm Başkanı", response.answer)
        self.assertTrue(any("sayfaYeni17874" in source.chunk.url for source in response.sources))

    @patch("kau_can_bot.answer.ensure_department_special_pages", side_effect=lambda snapshot, *_: snapshot)
    @patch("kau_can_bot.answer.get_official_snapshot")
    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_ybs_journal_queries_return_journal_details(
        self,
        _log_query,
        _log_interaction,
        mock_snapshot,
        _ensure_special_pages,
    ) -> None:
        mock_snapshot.return_value = self.build_official_snapshot()
        assistant = WebsiteGroundedAssistant(index=DummyIndex([]), settings=self.settings)

        response = assistant.answer_with_context("YBS bölüm dergisi")

        self.assertEqual(response.status, "official")
        self.assertIn("KAÜYÖNBİD", response.answer)
        self.assertTrue(any("dergipark.org.tr" in source.chunk.url or "sayfaYeni17891" in source.chunk.url for source in response.sources))

    @patch("kau_can_bot.answer.ensure_department_special_pages", side_effect=lambda snapshot, *_: snapshot)
    @patch("kau_can_bot.answer.get_official_snapshot")
    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_ybs_advising_queries_return_pdf_and_class_guidance(
        self,
        _log_query,
        _log_interaction,
        mock_snapshot,
        _ensure_special_pages,
    ) -> None:
        mock_snapshot.return_value = self.build_official_snapshot()
        assistant = WebsiteGroundedAssistant(index=DummyIndex([]), settings=self.settings)

        generic_response = assistant.answer_with_context("YBS akademik danışmanlıklar")
        class_response = assistant.answer_with_context("YBS 1. sınıf danışmanları")

        self.assertEqual(generic_response.status, "official")
        self.assertIn("PDF", generic_response.answer)
        self.assertTrue(any(source.chunk.url.endswith(".pdf") for source in generic_response.sources))
        self.assertEqual(class_response.status, "official")
        self.assertIn("1. Sınıf", class_response.answer)
        self.assertIn("GÖKHAN KERSE", class_response.answer)

    @patch("kau_can_bot.answer.ensure_department_special_pages", side_effect=lambda snapshot, *_: snapshot)
    @patch("kau_can_bot.answer.get_official_snapshot")
    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_ybs_club_queries_return_official_club_list(
        self,
        _log_query,
        _log_interaction,
        mock_snapshot,
        _ensure_special_pages,
    ) -> None:
        mock_snapshot.return_value = self.build_official_snapshot()
        assistant = WebsiteGroundedAssistant(index=DummyIndex([]), settings=self.settings)

        response = assistant.answer_with_context("YBS öğrenci kulüpleri")

        self.assertEqual(response.status, "official")
        self.assertIn("Techno Bilişim Kulübü", response.answer)
        self.assertTrue(any("sayfaYeni17976" in source.chunk.url for source in response.sources))

    @patch("kau_can_bot.answer.ensure_faculty_content", side_effect=lambda snapshot, *_: snapshot)
    @patch("kau_can_bot.answer.get_official_snapshot")
    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_english_dean_query_returns_english_answer(
        self,
        _log_query,
        _log_interaction,
        mock_snapshot,
        _ensure_faculty_content,
    ) -> None:
        mock_snapshot.return_value = self.build_official_snapshot()
        assistant = WebsiteGroundedAssistant(index=DummyIndex([]), settings=self.settings)

        response = assistant.answer_with_context("Who is the dean of FEAS?")

        self.assertEqual(response.status, "official")
        self.assertIn("According to the official senate page", response.answer)

    @patch("kau_can_bot.answer.get_official_snapshot")
    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_other_faculty_dean_query_uses_matching_senate_person(
        self,
        _log_query,
        _log_interaction,
        mock_snapshot,
    ) -> None:
        mock_snapshot.return_value = self.build_official_snapshot()
        assistant = WebsiteGroundedAssistant(index=DummyIndex([]), settings=self.settings)

        response = assistant.answer_with_context("Fen Edebiyat Fakültesi dekanı kim?")

        self.assertEqual(response.status, "official")
        self.assertIn("Adem BALKAYA", response.answer)
        self.assertNotIn("Deniz ÖZYAKIŞIR", response.answer)

    @patch("kau_can_bot.answer.ensure_faculty_page", side_effect=lambda snapshot, *_: snapshot)
    @patch("kau_can_bot.answer.get_official_snapshot")
    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_iibf_menu_query_returns_navigation_page_summary(
        self,
        _log_query,
        _log_interaction,
        mock_snapshot,
        _ensure_faculty_page,
    ) -> None:
        mock_snapshot.return_value = self.build_official_snapshot()
        assistant = WebsiteGroundedAssistant(index=DummyIndex([]), settings=self.settings)

        response = assistant.answer_with_context("iibf misyon")

        self.assertEqual(response.status, "official")
        self.assertIn("bilimsel", response.answer.lower())
        self.assertTrue(any("sayfaYeni17979" in source.chunk.url for source in response.sources))

    @patch("kau_can_bot.answer.ensure_faculty_page", side_effect=lambda snapshot, *_: snapshot)
    @patch("kau_can_bot.answer.get_official_snapshot")
    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_iibf_publication_queries_return_expected_navigation_links(
        self,
        _log_query,
        _log_interaction,
        mock_snapshot,
        _ensure_faculty_page,
    ) -> None:
        mock_snapshot.return_value = self.build_official_snapshot()
        assistant = WebsiteGroundedAssistant(index=DummyIndex([]), settings=self.settings)

        expectations = {
            "iibf dergisi linki": "sayfaYeni18063",
            "fakülte bülteni linki": "sayfaYeni18180",
            "birim faaliyet raporu linki": "sayfaYeni18001",
        }

        for query, url_fragment in expectations.items():
            with self.subTest(query=query):
                response = assistant.answer_with_context(query)
                self.assertEqual(response.status, "official")
                self.assertTrue(any(url_fragment in source.chunk.url for source in response.sources))

    @patch("kau_can_bot.answer.get_official_snapshot")
    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_generic_commission_query_does_not_fall_back_to_forms(
        self,
        _log_query,
        _log_interaction,
        mock_snapshot,
    ) -> None:
        mock_snapshot.return_value = self.build_official_snapshot()
        assistant = WebsiteGroundedAssistant(index=DummyIndex([]), settings=self.settings)

        response = assistant.answer_with_context("komisyonlar")

        self.assertEqual(response.status, "official")
        self.assertIn("komisyon", response.answer.lower())
        self.assertFalse(any("sayfaYeni17988" in source.chunk.url for source in response.sources))
        self.assertTrue(any("sayfaYeni18049" in source.chunk.url or "sayfaYeni18050" in source.chunk.url for source in response.sources))

    @patch("kau_can_bot.answer.WebsiteGroundedAssistant._generate_general_with_llm", return_value="Python, genel amaçlı bir programlama dilidir.")
    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_general_knowledge_uses_llm(self, _log_query, _log_interaction, _general_answer) -> None:
        assistant = WebsiteGroundedAssistant(index=DummyIndex([]), settings=self.settings)

        response = assistant.answer_with_context("python nedir")

        self.assertEqual(response.status, "general")
        self.assertIn("programlama dilidir", response.answer)
        self.assertTrue(response.sources)

    @patch("kau_can_bot.answer.WebsiteGroundedAssistant._generate_general_with_llm", return_value="Use a loop and validate null values before returning the response.")
    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_coding_answers_expose_reference_sources(self, _log_query, _log_interaction, _general_answer) -> None:
        assistant = WebsiteGroundedAssistant(index=DummyIndex([]), settings=self.settings)

        response = assistant.answer_with_context("fix this python error")

        self.assertEqual(response.status, "general")
        self.assertTrue(any("docs.python.org" in source.chunk.url for source in response.sources))

    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_text_correction_works_without_colon(self, _log_query, _log_interaction) -> None:
        assistant = WebsiteGroundedAssistant(index=DummyIndex([]), settings=self.settings)

        response = assistant.answer_with_context("bu metni düzelt ben bugun okula gelemedm cunku hastaym")

        self.assertIn("Düzeltilmiş metin", response.answer)
        self.assertIn("bugün", response.answer.lower())
        self.assertIn("gelemedim", response.answer.lower())

    @patch("kau_can_bot.answer.WebsiteGroundedAssistant._generate_general_with_llm", return_value="Sorun `print(name)` satırında; `name` tanımlanmadan kullanılıyor. Önce değişkeni tanımlayın.")
    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_code_fix_request_uses_general_coding_flow(self, _log_query, _log_interaction, _general_answer) -> None:
        assistant = WebsiteGroundedAssistant(index=DummyIndex([]), settings=self.settings)

        response = assistant.answer_with_context("Bu python kodunu düzelt: print(name)")

        self.assertEqual(response.status, "general")
        self.assertIn("name", response.answer)
        self.assertNotIn("Düzeltilmiş metin", response.answer)

    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_explicit_date_query_returns_weekday(self, _log_query, _log_interaction) -> None:
        assistant = WebsiteGroundedAssistant(index=DummyIndex([]), settings=self.settings)

        response = assistant.answer_with_context("29 Ekim 2026 hangi gün?")

        self.assertEqual(response.status, "general")
        self.assertIn("Perşembe", response.answer)

    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_today_day_name_query_uses_current_istanbul_weekday(self, _log_query, _log_interaction) -> None:
        assistant = WebsiteGroundedAssistant(index=DummyIndex([]), settings=self.settings)

        response = assistant.answer_with_context("Bugün hangi gün?")
        expected_weekday = WEEKDAY_NAMES["tr"][datetime.now(ISTANBUL_TZ).date().weekday()]

        self.assertEqual(response.status, "general")
        self.assertIn(expected_weekday, response.answer)

    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_special_day_listing_returns_all_matching_days(self, _log_query, _log_interaction) -> None:
        assistant = WebsiteGroundedAssistant(index=DummyIndex([]), settings=self.settings)

        response = assistant.answer_with_context("21 Mart 2026 özel günler neler?")

        self.assertEqual(response.status, "general")
        self.assertIn("Dünya Ormancılık Günü", response.answer)
        self.assertIn("Dünya Şiir Günü", response.answer)

    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_named_special_day_returns_its_date(self, _log_query, _log_interaction) -> None:
        assistant = WebsiteGroundedAssistant(index=DummyIndex([]), settings=self.settings)

        response = assistant.answer_with_context("Öğretmenler günü ne zaman?")

        self.assertEqual(response.status, "general")
        self.assertIn("24 Kasım", response.answer)

    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_religious_day_answer_uses_diyanet_source(self, _log_query, _log_interaction) -> None:
        assistant = WebsiteGroundedAssistant(index=DummyIndex([]), settings=self.settings)

        response = assistant.answer_with_context("Kadir gecesi ne zaman?")

        self.assertEqual(response.status, "general")
        self.assertIn("16 Mart 2026", response.answer)
        self.assertTrue(any("vakithesaplama.diyanet.gov.tr/dinigunler.php?yil=2026" in source.chunk.url for source in response.sources))

    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_religious_schedule_query_lists_current_year_entries(self, _log_query, _log_interaction) -> None:
        assistant = WebsiteGroundedAssistant(index=DummyIndex([]), settings=self.settings)

        response = assistant.answer_with_context("2026 dini günler")

        self.assertEqual(response.status, "general")
        self.assertIn("Ramazan Bayramı", response.answer)
        self.assertIn("Kurban Bayramı", response.answer)
        self.assertTrue(any("vakithesaplama.diyanet.gov.tr/dinigunler.php?yil=2026" in source.chunk.url for source in response.sources))

    @patch("kau_can_bot.answer.WebsiteGroundedAssistant._generate_general_with_llm", return_value="Resmi ve kısa bir e-posta taslağı hazırlanmıştır.")
    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_composition_request_is_not_misread_as_contact_lookup(self, _log_query, _log_interaction, _general_answer) -> None:
        assistant = WebsiteGroundedAssistant(index=DummyIndex([]), settings=self.settings)

        response = assistant.answer_with_context("İİBF için resmi bir mail yaz")

        self.assertEqual(response.status, "document")
        self.assertIn("taslağı", response.answer)

    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_arabic_greeting_uses_arabic_welcome(self, _log_query, _log_interaction) -> None:
        assistant = WebsiteGroundedAssistant(index=DummyIndex([]), settings=self.settings)

        response = assistant.answer_with_context("مرحبا", preferred_language="ar")

        self.assertEqual(response.status, "greeting")
        self.assertIn("KAÜCAN Beta", response.answer)
        self.assertIn("جامعة", response.answer)

    def test_generated_answer_is_sanitized(self) -> None:
        raw = (
            "📖 Açıklama: Fakülte duyuruları günceldir.\n\n"
            "metadata: internal\n"
            "🔗 Kaynak:\n"
            "1. https://example.com"
        )

        self.assertEqual(_sanitize_answer_text(raw), "Fakülte duyuruları günceldir.")

    def test_broken_fallback_text_is_canonicalized_in_turkish(self) -> None:
        raw = "⚠️ Bu konuda güvenilir bir bilgiye ula Shamadım. En doğru bilgi için fakülte ile iletişime geçmenizi öneririm."

        self.assertEqual(
            _sanitize_answer_text(raw, "tr"),
            "⚠️ Bu konuda güvenilir bir bilgiye ulaşamadım. En doğru bilgi için fakülte ile iletişime geçmenizi öneririm.",
        )

    def test_mixed_language_text_is_filtered_to_expected_language(self) -> None:
        raw = "📌 Bu konuda güvenilir bilgi bulunamadı. I can help with another question if needed."

        self.assertEqual(
            _sanitize_answer_text(raw, "tr"),
            "📌 Bu konuda güvenilir bilgi bulunamadı.",
        )

    def test_inline_foreign_glitch_is_repaired_in_turkish(self) -> None:
        raw = "Bu sistem, sana matematik, tarih, yazılım veya genel bilgi soruları yanıtlamak için here'dir."

        self.assertEqual(
            _sanitize_answer_text(raw, "tr"),
            "Bu sistem, sana matematik, tarih, yazılım veya genel bilgi soruları yanıtlamak için buradadır.",
        )

    @patch("kau_can_bot.answer._general_generators_for_settings", return_value=[BrokenGenerator(), GoodGenerator()])
    def test_general_generator_chain_falls_back_to_next_provider(self, _generators) -> None:
        assistant = WebsiteGroundedAssistant(index=DummyIndex([]), settings=self.settings)

        answer = assistant._generate_general_with_llm("python nedir")

        self.assertIn("programlama dilidir", answer)

    @patch("kau_can_bot.answer.build_live_support")
    @patch("kau_can_bot.answer.WebsiteGroundedAssistant._generate_general_with_llm", return_value=None)
    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_live_support_answers_when_llm_is_unavailable(
        self,
        _log_query,
        _log_interaction,
        _general_answer,
        mock_live_support,
    ) -> None:
        mock_live_support.return_value = LiveSupportResult(
            answer="🌤️ Kars için güncel hava açık, sıcaklık 12°C.",
            context="Current weather data for Kars.",
            sources=[("wttr.in Weather", "https://wttr.in/Kars?format=j1")],
            prefer_direct=True,
        )
        assistant = WebsiteGroundedAssistant(index=DummyIndex([]), settings=self.settings)

        response = assistant.answer_with_context("Kars hava durumu")

        self.assertEqual(response.status, "general")
        self.assertIn("Kars", response.answer)
        self.assertTrue(any("wttr.in" in source.chunk.url for source in response.sources))

    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_unknown_general_questions_return_unknown_fallback(self, _log_query, _log_interaction) -> None:
        assistant = WebsiteGroundedAssistant(index=DummyIndex([]), settings=self.settings)

        response = assistant.answer_with_context("kuantum gergedanı neden görünmez olur")

        self.assertEqual(response.status, "fallback")
        self.assertIn("henüz bilmiyorum", response.answer.lower())

    @patch("kau_can_bot.answer.find_unis_person_profile")
    @patch("kau_can_bot.answer.get_official_snapshot")
    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_person_mail_address_queries_use_official_profile(
        self,
        _log_query,
        _log_interaction,
        mock_snapshot,
        mock_person,
    ) -> None:
        mock_snapshot.return_value = self.build_official_snapshot()
        mock_person.return_value = {
            "name": "Deniz ÖZYAKIŞIR",
            "academic_title": "Prof. Dr.",
            "faculty": "İktisadi ve İdari Bilimler Fakültesi",
            "department": "İktisat Bölümü",
            "unit": "Uluslararası İktisat ve İktisadi Gelişme Ana Bilim Dalı",
            "roles": ["Dekan"],
            "email": "denizozyakisir@kafkas.edu.tr",
            "phone": "(474)225-1257",
            "detail_url": "https://unis.kafkas.edu.tr/akademisyen-detay/denizozyakisir",
            "works_url": "https://unis.kafkas.edu.tr/akademisyen-detay/calismalar/denizozyakisir",
            "source_url": "https://unis.kafkas.edu.tr/akademisyen-detay/denizozyakisir",
            "profile_tabs": {
                "Kronolojik Özgeçmiş": "https://unis.kafkas.edu.tr/akademisyen-detay/ozgecmis/denizozyakisir",
            },
            "external_links": [],
            "research_areas": [],
            "work_counts": {},
        }
        assistant = WebsiteGroundedAssistant(index=DummyIndex([]), settings=self.settings)

        response = assistant.answer_with_context("Deniz Özyakışır mail adresi")

        self.assertEqual(response.status, "official")
        self.assertIn("denizozyakisir@kafkas.edu.tr", response.answer)
        self.assertTrue(any("akademisyen-detay/denizozyakisir" in source.chunk.url for source in response.sources))

    @patch("kau_can_bot.answer.find_unis_person_profile")
    @patch("kau_can_bot.answer.get_official_snapshot")
    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_generic_yok_academic_links_are_not_treated_as_verified_profiles(
        self,
        _log_query,
        _log_interaction,
        mock_snapshot,
        mock_person,
    ) -> None:
        mock_snapshot.return_value = self.build_official_snapshot()
        mock_person.return_value = {
            "name": "Doç. Dr. İlyas TOPÇU",
            "academic_title": "Doç. Dr.",
            "faculty": "İktisadi ve İdari Bilimler Fakültesi",
            "department": "Siyaset Bilimi ve Kamu Yönetimi Bölümü",
            "unit": "",
            "roles": ["Öğretim Üyesi"],
            "email": "",
            "phone": "",
            "detail_url": "https://unis.kafkas.edu.tr/akademisyen-detay/ilyastopcu",
            "works_url": "https://unis.kafkas.edu.tr/akademisyen-detay/calismalar/ilyastopcu",
            "source_url": "https://unis.kafkas.edu.tr/akademisyen-detay/ilyastopcu",
            "profile_tabs": {},
            "external_links": [
                {"label": "YÖK Akademik", "url": "https://akademik.yok.gov.tr/AkademikArama/view/viewAuthor.jsp"},
            ],
            "research_areas": [],
            "work_counts": {},
        }
        assistant = WebsiteGroundedAssistant(index=DummyIndex([]), settings=self.settings)

        response = assistant.answer_with_context("İlyas Topçu YÖK Akademik profili")

        self.assertEqual(response.status, "official")
        self.assertIn("doğrudan doğrulanamadı", response.answer.lower())
        self.assertFalse(any("view/viewAuthor.jsp" in source.chunk.url for source in response.sources))

    @patch("kau_can_bot.answer.find_unis_person_profile")
    @patch("kau_can_bot.answer.get_official_snapshot")
    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_administrative_staff_name_queries_use_management_fallback(
        self,
        _log_query,
        _log_interaction,
        mock_snapshot,
        mock_person,
    ) -> None:
        snapshot = self.build_official_snapshot()
        snapshot["faculty_management"] = [
            {
                "name": "Günay YILAN",
                "roles": ["Fakülte Sekreteri"],
                "faculty": "İktisadi ve İdari Bilimler Fakültesi",
                "source_url": "https://unis.kafkas.edu.tr/birim/yonetim/iktisadi-ve-idari-bilimler-fakultesi/id=2_CZa_54",
            }
        ]
        mock_snapshot.return_value = snapshot
        mock_person.return_value = snapshot["faculty_management"][0]
        assistant = WebsiteGroundedAssistant(index=DummyIndex([]), settings=self.settings)

        response = assistant.answer_with_context("Günay Yılan kimdir")

        self.assertEqual(response.status, "official")
        self.assertIn("Fakülte Sekreteri", response.answer)
        self.assertTrue(any("birim/yonetim" in source.chunk.url for source in response.sources))

    @patch("kau_can_bot.answer.get_official_snapshot")
    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_manual_personnel_queries_use_verified_record_before_rag(
        self,
        _log_query,
        _log_interaction,
        mock_snapshot,
    ) -> None:
        mock_snapshot.return_value = self.build_official_snapshot()
        index = DummyIndex([])
        assistant = WebsiteGroundedAssistant(index=index, settings=self.settings)

        response = assistant.answer_with_context("Erkan Günerhan hangi bölümdedir?")

        self.assertEqual(response.status, "official")
        self.assertIn("Öğr. Gör. Erkan Günerhan", response.answer)
        self.assertIn("Kağızman Meslek Yüksekokulu", response.answer)
        self.assertIn("Eczane Hizmetleri Bölümü", response.answer)
        self.assertIn("Eczane Hizmetleri Ana Bilim Dalı", response.answer)
        self.assertTrue(any("erkan.gunerhan" in source.chunk.url for source in response.sources))
        self.assertIsNone(index.searched_query)

    @patch("kau_can_bot.answer.get_official_snapshot")
    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_manual_personnel_name_matches_are_recognized_for_short_official_queries(
        self,
        _log_query,
        _log_interaction,
        mock_snapshot,
    ) -> None:
        mock_snapshot.return_value = self.build_official_snapshot()
        assistant = WebsiteGroundedAssistant(index=DummyIndex([]), settings=self.settings)

        response = assistant.answer_with_context("Erkan Günerhan eczane hizmetlerinde mi?")

        self.assertEqual(response.status, "official")
        self.assertIn("Eczane Hizmetleri Bölümü", response.answer)
        self.assertIn("Eczane Hizmetleri Ana Bilim Dalı", response.answer)


if __name__ == "__main__":
    unittest.main()
