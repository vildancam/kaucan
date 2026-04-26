from __future__ import annotations

import unittest
from unittest.mock import patch

from kau_can_bot.official_data import _hydrate_snapshot


class OfficialDataTests(unittest.TestCase):
    @patch("kau_can_bot.official_data._persist_snapshot", return_value=None)
    @patch("kau_can_bot.official_data._fetch_html", return_value="<html></html>")
    def test_manual_navigation_and_department_overrides_are_hydrated(self, _fetch_html, _persist_snapshot) -> None:
        snapshot = {
            "sources": {},
            "senate_people": [],
            "faculty_personnel": [],
            "faculty_navigation": [],
            "departments": {},
            "faculty_pages": {},
            "faculty_content": {"announcements": [], "news": [], "events": []},
        }

        hydrated = _hydrate_snapshot(snapshot)

        self.assertEqual(
            hydrated["departments"]["sbui"]["root_url"],
            "https://www.kafkas.edu.tr/iibfsbui/tr/sayfaYeni16932",
        )
        navigation_urls = {entry["url"] for entry in hydrated["faculty_navigation"]}
        self.assertIn("https://www.kafkas.edu.tr/iibf/tr/sayfaYeni17988", navigation_urls)
        self.assertIn("https://www.kafkas.edu.tr/iibf/tr/sayfaYeni18044", navigation_urls)


if __name__ == "__main__":
    unittest.main()
