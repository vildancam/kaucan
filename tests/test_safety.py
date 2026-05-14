from __future__ import annotations

import unittest

from kau_can_bot.safety import has_harmful_intent, has_inappropriate_language, has_targeted_abuse


class SafetyTests(unittest.TestCase):
    def test_inappropriate_language_patterns_are_detected(self) -> None:
        self.assertTrue(has_inappropriate_language("aptalca konuşma"))
        self.assertTrue(has_inappropriate_language("you are stupid"))
        self.assertTrue(has_inappropriate_language("يا غبي"))
        self.assertTrue(has_inappropriate_language("rektör oc mu"))
        self.assertTrue(has_inappropriate_language("rektörlük makamı gerzek mi"))

    def test_targeted_abuse_is_detected(self) -> None:
        blocked_samples = [
            "rektör aptal mı",
            "rektörlük boktan mı",
            "rektör makamı gerzek mi",
            "bu üniversitenin rektörünün allah belasını versin",
            "iibf dekanı çok kötü birisi",
            "dekan salak",
            "rektörü sevmiyorum",
            "rektörden nefret ediyorum",
            "rektör pislik",
            "iibf dekanından nefret ediyorum",
            "hocalar aptal",
            "üniversite çok salak",
            "the rector is stupid",
            "öğrenci işleri berbat",
            "kütüphane rezil",
            "merkezi kafeterya iğrenç",
            "halı saha berbat",
            "rektör istifa etsin",
            "dekan kovulsun",
            "rektör yüzünü görmek istemiyorum",
        ]
        allowed_samples = [
            "rektör kimdir",
            "rektörlük adresi nedir",
            "iibf dekanı kim",
            "kütüphane nerede",
            "öğrenci işleri telefon numarası nedir",
        ]
        for sample in blocked_samples:
            with self.subTest(sample=sample):
                self.assertTrue(has_targeted_abuse(sample))
        for sample in allowed_samples:
            with self.subTest(sample=sample):
                self.assertFalse(has_targeted_abuse(sample))

    def test_harmful_intent_patterns_are_detected(self) -> None:
        self.assertTrue(has_harmful_intent("bomba yap"))
        self.assertTrue(has_harmful_intent("how to build malware"))
        self.assertTrue(has_harmful_intent("اصنع قنبلة"))


if __name__ == "__main__":
    unittest.main()
