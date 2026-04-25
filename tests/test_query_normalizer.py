from __future__ import annotations

import unittest

from kau_can_bot.query_normalizer import (
    is_coding_query,
    is_english_query,
    is_greeting_query,
    looks_actionable,
    normalize_query,
)


class QueryNormalizerTests(unittest.TestCase):
    def test_common_typos_are_normalized(self) -> None:
        samples = {
            "mrbb": "merhaba",
            "merhb": "merhaba",
            "mrb": "merhaba",
            "slm": "merhaba",
            "iibf": "iktisadi ve idari bilimler fakültesi",
            "ııbf": "iktisadi ve idari bilimler fakültesi",
            " ibf ": "iktisadi ve idari bilimler fakültesi",
            "duyrular": "duyurular",
            "duyrulari": "duyurular",
            "snav": "sınav",
            "sinav": "sınav",
            "sınv": "sınav",
            "akademk takvim": "akademik takvim",
            "ybs": "yönetim bilişim sistemleri",
        }

        for raw, expected in samples.items():
            with self.subTest(raw=raw):
                self.assertEqual(normalize_query(raw), expected)

    def test_greeting_query_is_detected(self) -> None:
        self.assertTrue(is_greeting_query("mrbb"))
        self.assertTrue(is_greeting_query("hello"))
        self.assertFalse(is_greeting_query("duyrular"))

    def test_actionable_topic_is_preserved(self) -> None:
        self.assertTrue(looks_actionable("duyrular"))
        self.assertTrue(looks_actionable("iibf iletişim"))

    def test_english_and_coding_queries_are_detected(self) -> None:
        self.assertTrue(is_english_query("iibf contact"))
        self.assertTrue(is_coding_query("fix this python error"))
        self.assertFalse(is_english_query("python nedir"))


if __name__ == "__main__":
    unittest.main()
