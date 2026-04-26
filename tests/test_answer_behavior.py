from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from kau_can_bot.answer import WELCOME_MESSAGE, WebsiteGroundedAssistant, _sanitize_answer_text
from kau_can_bot.config import Settings
from kau_can_bot.live_support import LiveSupportResult
from kau_can_bot.models import Chunk, SearchResult
from kau_can_bot.utils import stable_id


class DummyIndex:
    def __init__(self, results: list[SearchResult]) -> None:
        self.results = results
        self.searched_query = None

    def search(self, query: str, top_k: int = 3) -> list[SearchResult]:
        self.searched_query = query
        return self.results


class BrokenGenerator:
    is_configured = True

    def generate_general(self, query: str, memory_context: str = "", support_context: str = "") -> str | None:
        raise RuntimeError("broken")


class GoodGenerator:
    is_configured = True

    def generate_general(self, query: str, memory_context: str = "", support_context: str = "") -> str | None:
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
                    ],
                    "announcements": [],
                    "news": [],
                    "events": [],
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
    def test_smalltalk_is_supported(self, _log_query, _log_interaction) -> None:
        assistant = WebsiteGroundedAssistant(index=DummyIndex([]), settings=self.settings)

        response = assistant.answer_with_context("merhaba nasılsın")
        english_response = assistant.answer_with_context("how r u", preferred_language="en")
        arabic_response = assistant.answer_with_context("شلونك", preferred_language="ar")

        self.assertEqual(response.status, "smalltalk")
        self.assertTrue("yardımcı" in response.answer or "iyiyim" in response.answer.lower())
        self.assertEqual(english_response.status, "smalltalk")
        self.assertTrue("chat" in english_response.answer.lower() or "question" in english_response.answer.lower())
        self.assertEqual(arabic_response.status, "smalltalk")
        self.assertTrue("الدردشة" in arabic_response.answer or "بخير" in arabic_response.answer)

    @patch("kau_can_bot.answer._fetch_rector_name", return_value="Prof. Dr. Hüsnü KAPU")
    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_management_shortcuts_are_returned(self, _log_query, _log_interaction, _fetch_rector_name) -> None:
        assistant = WebsiteGroundedAssistant(index=DummyIndex([]), settings=self.settings)

        response = assistant.answer_with_context("rektör kim")

        self.assertEqual(response.status, "direct_link")
        self.assertIn("Hüsnü KAPU", response.answer)
        self.assertEqual(response.sources[0].chunk.url, "https://www.kafkas.edu.tr/rektorluk/tr/sayfaYeni655")

    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_location_shortcut_is_returned(self, _log_query, _log_interaction) -> None:
        assistant = WebsiteGroundedAssistant(index=DummyIndex([]), settings=self.settings)

        response = assistant.answer_with_context("iibf nerede")

        self.assertEqual(response.status, "direct_link")
        self.assertEqual(response.sources[0].chunk.url, "https://maps.app.goo.gl/HMYYaxbZBcZVisbN7")

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

    @patch("kau_can_bot.answer.WebsiteGroundedAssistant._generate_general_with_llm", return_value="Resmi ve kısa bir e-posta taslağı hazırlanmıştır.")
    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_composition_request_is_not_misread_as_contact_lookup(self, _log_query, _log_interaction, _general_answer) -> None:
        assistant = WebsiteGroundedAssistant(index=DummyIndex([]), settings=self.settings)

        response = assistant.answer_with_context("İİBF için resmi bir mail yaz")

        self.assertEqual(response.status, "general")
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


if __name__ == "__main__":
    unittest.main()
