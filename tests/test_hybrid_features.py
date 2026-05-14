from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kau_can_bot.message_router import HybridMessageRouter
from kau_can_bot.safety_filter import apply_safety_filter
from kau_can_bot.scraper_manager import DocumentCatalogEntry
from kau_can_bot.text_normalizer import normalize_user_message
from kau_can_bot.user_session import get_session_state, remember_turn


class HybridFeatureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.session_path = Path(self.temp_dir.name) / "user_sessions.json"
        self.session_patcher = patch("kau_can_bot.user_session.SESSION_STATE_PATH", self.session_path)
        self.session_patcher.start()
        self.router = HybridMessageRouter()

    def tearDown(self) -> None:
        self.session_patcher.stop()
        self.temp_dir.cleanup()

    def test_text_normalizer_expands_common_student_abbreviations(self) -> None:
        normalized = normalize_user_message("kyk kız yurdu nerede la")

        self.assertIn("kredi yurtlar kurumu", normalized.normalized)
        self.assertIn("kız öğrenci yurdu", normalized.normalized)
        self.assertNotIn(" la ", f" {normalized.normalized_for_matching} ")

    def test_safety_filter_escalates_repeated_targeted_abuse(self) -> None:
        first = apply_safety_filter("Rektör gerizekalı", "tr", client_id="user-1")
        second = apply_safety_filter("Rektör gerizekalı", "tr", client_id="user-1")

        self.assertIsNotNone(first)
        self.assertTrue(first.blocked)
        self.assertIn("saygılı", first.answer.lower())
        self.assertIsNotNone(second)
        self.assertIn("bu şekilde devam ederse", second.answer.lower())

    def test_address_preference_is_saved_and_used_in_follow_up_answer(self) -> None:
        saved = self.router.route("Bana Mustafa diye hitap et", "tr", client_id="user-2")
        solved = self.router.route("450'nin yüzde 20'si kaç?", "tr", client_id="user-2")

        self.assertIsNotNone(saved)
        self.assertEqual(saved.status, "memory_saved")
        self.assertIn("Mustafa", saved.answer)
        self.assertIsNotNone(solved)
        self.assertEqual(solved.status, "general")
        self.assertTrue(solved.answer.startswith("Mustafa,"))
        self.assertIn("90", solved.answer)

    def test_address_correction_is_not_sent_to_rag(self) -> None:
        remember_turn(
            "user-2b",
            user_message="bana bir dilekçe yaz",
            user_intent="document",
            bot_response="Ahmet, aşağıda dilekçe taslağını paylaşıyorum.",
            bot_intent="document",
            document_type="petition",
            topic="bana bir dilekçe yaz",
        )

        response = self.router.route("ahmet deme", "tr", client_id="user-2b")

        self.assertIsNotNone(response)
        self.assertEqual(response.status, "address_correction")
        self.assertIn("o isimle hitap etmeyeceğim", response.answer)

    def test_revision_request_uses_previous_context(self) -> None:
        remember_turn(
            "user-2c",
            user_message="öğrenci işleri için mail yaz",
            user_intent="document",
            bot_response="Resmi e-posta taslağı:\n\nKonu: Bilgi Talebi\n\nMerhaba,\n\nBilgi rica ediyorum.",
            bot_intent="document",
            document_type="email",
            topic="öğrenci işleri için mail yaz",
        )

        response = self.router.route("daha resmi yaz", "tr", client_id="user-2c")

        self.assertIsNotNone(response)
        self.assertIn("yeniden düzenledim", response.answer)
        self.assertIn("Konu:", response.answer)

    def test_name_usage_preference_is_saved(self) -> None:
        response = self.router.route("ismimi kullanma", "tr", client_id="user-2d")
        session = get_session_state("user-2d")

        self.assertIsNotNone(response)
        self.assertEqual(response.status, "address_correction")
        self.assertFalse(session.get("user_name_allowed", True))

    def test_name_rejection_adds_disallowed_name(self) -> None:
        response = self.router.route("ismim Ahmet değil", "tr", client_id="user-2e")
        session = get_session_state("user-2e")

        self.assertIsNotNone(response)
        self.assertEqual(response.status, "address_correction")
        self.assertIn("Ahmet", " ".join(session.get("disallowed_names", [])))

    @patch("kau_can_bot.message_router.fetch_document_catalog")
    def test_document_lookup_returns_cards_and_actions(self, mock_catalog) -> None:
        mock_catalog.return_value = [
            DocumentCatalogEntry(
                id="1",
                title="Mazeret Sınavı Başvuru Formu",
                url="https://example.com/form.docx",
                category="oidb_form",
                source_page="https://www.kafkas.edu.tr/oidb/tr/sayfaYeni11090",
                source_type="document",
                fetched_at="2026-05-10T00:00:00+00:00",
            )
        ]

        response = self.router.route("Hazır dilekçeler nerede?", "tr", client_id="user-3")

        self.assertIsNotNone(response)
        self.assertEqual(response.status, "documents")
        self.assertTrue(response.cards)
        self.assertEqual(response.cards[0].title, "Mazeret Sınavı Başvuru Formu")
        self.assertTrue(response.actions)

    def test_dormitory_query_returns_structured_table(self) -> None:
        response = self.router.route("Kars'ta KYK yurtları var mı?", "tr", client_id="user-4")

        self.assertIsNotNone(response)
        self.assertEqual(response.status, "dormitory")
        self.assertIsNotNone(response.table)
        self.assertGreater(len(response.table.rows), 0)
        self.assertIn("KYK", " ".join(response.table.rows[0]))

    def test_transport_query_returns_route_table(self) -> None:
        response = self.router.route("Kampüse nasıl giderim?", "tr", client_id="user-5")

        self.assertIsNotNone(response)
        self.assertEqual(response.status, "transport")
        self.assertIsNotNone(response.table)
        self.assertGreater(len(response.table.rows), 0)

    def test_city_query_returns_cards_with_sources(self) -> None:
        response = self.router.route("Ani Harabeleri hakkında bilgi ver", "tr", client_id="user-6")

        self.assertIsNotNone(response)
        self.assertEqual(response.status, "city")
        self.assertTrue(response.cards)
        self.assertTrue(response.sources)


if __name__ == "__main__":
    unittest.main()
