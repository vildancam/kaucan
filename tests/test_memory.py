from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from kau_can_bot.answer import WebsiteGroundedAssistant
from kau_can_bot.config import Settings


class DummyIndex:
    def search(self, query: str, top_k: int = 3) -> list:
        return []


class MemoryBehaviorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = Settings(llm_provider="local", use_openai=False, top_k=3)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.memory_path = Path(self.temp_dir.name) / "user_memory.json"
        self.memory_patcher = patch("kau_can_bot.memory.USER_MEMORY_PATH", self.memory_path)
        self.memory_patcher.start()

    def tearDown(self) -> None:
        self.memory_patcher.stop()
        self.temp_dir.cleanup()

    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_name_is_saved_and_recalled(self, _log_query, _log_interaction) -> None:
        assistant = WebsiteGroundedAssistant(index=DummyIndex(), settings=self.settings)

        saved = assistant.answer_with_context("Benim adım Ayşe", client_id="user-1")
        recalled = assistant.answer_with_context("Adım ne?", client_id="user-1")

        self.assertEqual(saved.status, "memory_saved")
        self.assertNotIn("Ayşe", saved.answer)
        self.assertIn("ad bilgisi", saved.answer.lower())
        self.assertEqual(recalled.status, "memory_recall")
        self.assertIn("Ayşe", recalled.answer)

    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_department_is_saved_and_recalled(self, _log_query, _log_interaction) -> None:
        assistant = WebsiteGroundedAssistant(index=DummyIndex(), settings=self.settings)

        assistant.answer_with_context("Ben YBS öğrencisiyim", client_id="user-2")
        recalled = assistant.answer_with_context("Hangi bölümdeyim?", client_id="user-2")

        self.assertEqual(recalled.status, "memory_recall")
        self.assertIn("Yönetim Bilişim Sistemleri", recalled.answer)

    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_custom_fact_is_learned(self, _log_query, _log_interaction) -> None:
        assistant = WebsiteGroundedAssistant(index=DummyIndex(), settings=self.settings)

        saved = assistant.answer_with_context("Bunu hatırla: en sevdiğim ders yapay zeka", client_id="user-3")
        recalled = assistant.answer_with_context("En sevdiğim ders ne?", client_id="user-3")

        self.assertEqual(saved.status, "memory_saved")
        self.assertEqual(recalled.status, "memory_fact")
        self.assertIn("yapay zeka", recalled.answer.lower())

    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_smalltalk_does_not_force_name_after_learning(self, _log_query, _log_interaction) -> None:
        assistant = WebsiteGroundedAssistant(index=DummyIndex(), settings=self.settings)

        assistant.answer_with_context("Bana Vildan diye hitap et", client_id="user-4")
        response = assistant.answer_with_context("Nasılsın?", client_id="user-4")
        greeting = assistant.answer_with_context("Merhaba", client_id="user-4")

        self.assertEqual(response.status, "smalltalk")
        self.assertNotIn("Vildan", response.answer)
        self.assertEqual(greeting.status, "greeting")
        self.assertNotIn("Vildan", greeting.answer)

    @patch("kau_can_bot.answer.log_interaction", return_value=SimpleNamespace(id="test-id"))
    @patch("kau_can_bot.answer.log_query", return_value=None)
    def test_memory_save_and_generic_recall_do_not_echo_name(self, _log_query, _log_interaction) -> None:
        assistant = WebsiteGroundedAssistant(index=DummyIndex(), settings=self.settings)

        saved = assistant.answer_with_context("Benim adım Mustafa", client_id="user-5")
        recalled = assistant.answer_with_context("Beni tanıyor musun?", client_id="user-5")

        self.assertEqual(saved.status, "memory_saved")
        self.assertNotIn("Mustafa", saved.answer)
        self.assertIn("belle", saved.answer.lower())
        self.assertIn(recalled.status, {"memory_recall", "memory_fact"})
        self.assertNotIn("Mustafa", recalled.answer)


if __name__ == "__main__":
    unittest.main()
