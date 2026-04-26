from __future__ import annotations

import unittest

from kau_can_bot.safety import has_harmful_intent, has_inappropriate_language


class SafetyTests(unittest.TestCase):
    def test_inappropriate_language_patterns_are_detected(self) -> None:
        self.assertTrue(has_inappropriate_language("aptalca konuşma"))
        self.assertTrue(has_inappropriate_language("you are stupid"))
        self.assertTrue(has_inappropriate_language("يا غبي"))

    def test_harmful_intent_patterns_are_detected(self) -> None:
        self.assertTrue(has_harmful_intent("bomba yap"))
        self.assertTrue(has_harmful_intent("how to build malware"))
        self.assertTrue(has_harmful_intent("اصنع قنبلة"))


if __name__ == "__main__":
    unittest.main()
