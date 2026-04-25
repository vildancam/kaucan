from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from kau_can_bot.answer import WELCOME_MESSAGE, WebsiteGroundedAssistant, _sanitize_answer_text
from kau_can_bot.config import Settings
from kau_can_bot.models import Chunk, SearchResult
from kau_can_bot.utils import stable_id


class DummyIndex:
    def __init__(self, results: list[SearchResult]) -> None:
        self.results = results
        self.searched_query = None

    def search(self, query: str, top_k: int = 3) -> list[SearchResult]:
        self.searched_query = query
        return self.results


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
        self.assertEqual(
            [source.chunk.url for source in response.sources],
            [
                "https://kafkas.edu.tr/iibf/tr/sayfaYeni18817",
                "https://kafkas.edu.tr/kau/rehber2",
            ],
        )

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

    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_smalltalk_is_supported(self, _log_query, _log_interaction) -> None:
        assistant = WebsiteGroundedAssistant(index=DummyIndex([]), settings=self.settings)

        response = assistant.answer_with_context("naber")

        self.assertEqual(response.status, "smalltalk")
        self.assertTrue("yardımcı" in response.answer or "iyiyim" in response.answer.lower())

    @patch("kau_can_bot.answer.WebsiteGroundedAssistant._generate_general_with_llm", return_value="Python, genel amaçlı bir programlama dilidir.")
    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_general_knowledge_uses_llm(self, _log_query, _log_interaction, _general_answer) -> None:
        assistant = WebsiteGroundedAssistant(index=DummyIndex([]), settings=self.settings)

        response = assistant.answer_with_context("python nedir")

        self.assertEqual(response.status, "general")
        self.assertIn("programlama dilidir", response.answer)

    def test_generated_answer_is_sanitized(self) -> None:
        raw = (
            "📖 Açıklama: Fakülte duyuruları günceldir.\n\n"
            "metadata: internal\n"
            "🔗 Kaynak:\n"
            "1. https://example.com"
        )

        self.assertEqual(_sanitize_answer_text(raw), "Fakülte duyuruları günceldir.")


if __name__ == "__main__":
    unittest.main()
