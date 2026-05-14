from __future__ import annotations

import unittest
from unittest.mock import patch

from bs4 import BeautifulSoup

from kau_can_bot.official_data import (
    YBS_MANAGEMENT_URL,
    _hydrate_snapshot,
    _extract_ybs_class_advisors,
    _parse_unis_management_cards,
    _parse_unis_person_profile_html,
    _parse_unis_search_result_row,
    _parse_ybs_clubs_page,
    _parse_ybs_journal_page,
    _parse_ybs_management_page,
    find_unis_person_profile,
)


class OfficialDataTests(unittest.TestCase):
    @patch("kau_can_bot.official_data._fetch_unis_person_profile")
    @patch("kau_can_bot.official_data._search_unis_people")
    def test_manual_personnel_records_are_returned_before_unis_lookup(
        self,
        mock_search,
        mock_fetch_profile,
    ) -> None:
        person = find_unis_person_profile("Erkan Günerhan hangi bölümde görev yapıyor?", {"senate_people": [], "faculty_personnel": [], "faculty_management": [], "departments": {}})

        self.assertIsNotNone(person)
        self.assertEqual(person["name"], "Erkan Günerhan")
        self.assertEqual(person["unit"], "Kağızman Meslek Yüksekokulu")
        self.assertEqual(person["department"], "Eczane Hizmetleri Bölümü")
        self.assertEqual(person["division"], "Eczane Hizmetleri Ana Bilim Dalı")
        self.assertTrue(person["manual_verified"])
        mock_search.assert_not_called()
        mock_fetch_profile.assert_not_called()

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
        self.assertEqual(
            hydrated["departments"]["ybs"]["important_links"]["management"],
            YBS_MANAGEMENT_URL,
        )
        navigation_urls = {entry["url"] for entry in hydrated["faculty_navigation"]}
        self.assertIn("https://www.kafkas.edu.tr/iibf/tr/sayfaYeni17988", navigation_urls)
        self.assertIn("https://www.kafkas.edu.tr/iibf/tr/sayfaYeni18044", navigation_urls)

    def test_parse_unis_search_result_row_extracts_profile_metadata(self) -> None:
        row = [
            "Kisi-1",
            "Prof. Dr. Filiz ASLAN ÇETİN",
            "Akademisyen",
            "akademisyen-detay/filizaslan",
            (
                "<div>"
                "<a class='customer-name' href='akademisyen-detay/filizaslan'></a>"
                "<span class='fw-semibold'>Iktisadi ve Idari Bilimler Fakültesi</span>"
                "<small class='text-gray'>Işletme / Üretim Yönetimi ve Pazarlama</small>"
                "<span class='badge'>Anabilim Dalı Başkanı</span>"
                "<div class='calismalar'><a href='akademisyen-detay/calismalar/filizaslan/Tur=Yayin'>80 Yayın</a></div>"
                "</div>"
            ),
        ]

        parsed = _parse_unis_search_result_row(row, "https://unis.kafkas.edu.tr/search/sorgu=filiz+aslan")

        self.assertEqual(parsed["name"], "Filiz ASLAN ÇETİN")
        self.assertEqual(parsed["academic_title"], "Prof. Dr.")
        self.assertEqual(parsed["faculty"], "Iktisadi ve Idari Bilimler Fakültesi")
        self.assertEqual(parsed["department"], "Işletme")
        self.assertEqual(parsed["unit"], "Üretim Yönetimi ve Pazarlama")
        self.assertIn("Anabilim Dalı Başkanı", parsed["roles"])
        self.assertEqual(parsed["works_url"], "https://unis.kafkas.edu.tr/akademisyen-detay/calismalar/filizaslan/Tur=Yayin")

    def test_parse_unis_profile_html_extracts_contact_and_research(self) -> None:
        html = """
        <html>
          <head><title>Prof. Dr. Filiz ASLAN ÇETİN - UNIS</title></head>
          <body>
            <div class="user-avatar-section">
              <h5 class="my-0">Prof. Dr.</h5>
              <h3>Filiz ASLAN ÇETİN</h3>
              <div class="birimler">
                <a>Iktisadi ve Idari Bilimler Fakültesi</a>
                <a>Işletme Bölümü</a>
                <a>Üretim Yönetimi ve Pazarlama Ana Bilim Dalı</a>
              </div>
              <a class="Contact" data-bs-title="filizaslan@kafkas.edu.tr"><i class="fa fa-envelope"></i></a>
              <a class="Contact" data-bs-title="(474)225-1250"><i class="fa fa-phone"></i></a>
              <span class="yetkiAd">Üretim Yönetimi ve Pazarlama Anabilim Dalı Başkanı</span>
              <div class="calismalar">
                <a href="akademisyen-detay/calismalar/filizaslan/Tur=Yayin">80 Yayın</a>
                <a href="akademisyen-detay/calismalar/filizaslan/Tur=KisiProje">0 Projeler</a>
              </div>
              <div class="academic-link">
                <a href="https://orcid.org/0000-0002-8210-799X" tool-title="OrcID"></a>
              </div>
            </div>
            <div class="accordion-body">
              <div class="child">Pazarlama İletişimi</div>
              <div class="child">Hizmet Pazarlaması</div>
            </div>
            <ul id="mobileDropdownMenu">
              <li><a href="akademisyen-detay/calismalar/filizaslan">Akademik Çalışmalar</a></li>
              <li><a href="akademisyen-detay/ozgecmis/filizaslan">Kronolojik Özgeçmiş</a></li>
            </ul>
          </body>
        </html>
        """

        parsed = _parse_unis_person_profile_html(html, "https://unis.kafkas.edu.tr/akademisyen-detay/filizaslan")

        self.assertEqual(parsed["name"], "Filiz ASLAN ÇETİN")
        self.assertEqual(parsed["email"], "filizaslan@kafkas.edu.tr")
        self.assertEqual(parsed["phone"], "(474)225-1250")
        self.assertEqual(parsed["department"], "Işletme Bölümü")
        self.assertIn("Pazarlama İletişimi", parsed["research_areas"])
        self.assertEqual(parsed["work_counts"]["Yayın"], 80)
        self.assertEqual(parsed["profile_tabs"]["Akademik Çalışmalar"], "https://unis.kafkas.edu.tr/akademisyen-detay/calismalar/filizaslan")

    def test_parse_unis_management_cards_extracts_faculty_secretary(self) -> None:
        html = """
        <div id="tab-yonetim">
          <div class="card w-px-300">
            <a>
              <div class="card-body text-center">
                <h5 class="fw-bold">Fakülte Sekreteri</h5>
                <img src="app_files/2025/09/kisi.webp" />
                <h5 class="mb-3 card-title"><br/>Günay YILAN</h5>
              </div>
            </a>
          </div>
        </div>
        """

        people = _parse_unis_management_cards(
            BeautifulSoup(html, "html.parser"),
            "https://unis.kafkas.edu.tr/birim/yonetim/iktisadi-ve-idari-bilimler-fakultesi/id=2_CZa_54",
        )

        self.assertEqual(people[0]["name"], "Günay YILAN")
        self.assertEqual(people[0]["roles"], ["Fakülte Sekreteri"])

    def test_parse_ybs_management_page_extracts_people(self) -> None:
        html = """
        <div class="post-content">
          <div class="c-padding">
            <div class="section-header"><h2 class="title">Yönetim</h2></div>
            <div>
              <h2>Prof. Dr. Gökhan KERSE</h2>
              <h3>Bölüm Başkanı</h3>
              <h2>Dr. Öğr. Üyesi M. Akif YENİKAYA</h2>
              <h3>Bölüm Başkan Yardımcısı</h3>
            </div>
          </div>
        </div>
        """

        parsed = _parse_ybs_management_page(html, "https://www.kafkas.edu.tr/iibfybs/tr/sayfaYeni17874")

        self.assertEqual(parsed["people"][0]["name"], "Prof. Dr. Gökhan KERSE")
        self.assertEqual(parsed["people"][0]["role"], "Bölüm Başkanı")
        self.assertEqual(parsed["people"][1]["role"], "Bölüm Başkan Yardımcısı")

    def test_parse_ybs_journal_page_extracts_name_and_link(self) -> None:
        html = """
        <div class="post-content">
          <div class="c-padding">
            <div class="section-header"><h2 class="title">Bölüm Dergisi</h2></div>
            <p>Yönetim Bilişim Sistemleri alanında akademik bilgi üretimini desteklemek amacıyla
            <strong>Kafkas Üniversitesi Yönetim ve Bilişim Dergisi (KAÜYÖNBİD)</strong> yayımlanmaktadır.</p>
            <p>Dergimiz; yönetim, bilişim teknolojileri ve bilgi sistemleri alanlarında açık erişimli ve hakemli bir akademik dergidir.</p>
            <a href="https://dergipark.org.tr/tr/pub/kaujomi">KAÜYÖNBİD</a>
          </div>
        </div>
        """

        parsed = _parse_ybs_journal_page(html, "https://www.kafkas.edu.tr/iibfybs/tr/sayfaYeni17891")

        self.assertEqual(parsed["journal_name"], "Kafkas Üniversitesi Yönetim ve Bilişim Dergisi (KAÜYÖNBİD)")
        self.assertIn("açık erişimli", parsed["scope"].lower())
        self.assertTrue(any("dergipark.org.tr" in link["url"] for link in parsed["links"]))

    def test_parse_ybs_clubs_page_extracts_clubs(self) -> None:
        html = """
        <div class="post-content">
          <div class="c-padding">
            <div class="club-card">
              <h3>Techno Bilişim Kulübü</h3>
              <div class="advisor-label"><strong>Akademik Danışman</strong></div>
              <div class="advisor-name">Dr. Öğr. Üyesi M. Akif YENİKAYA</div>
            </div>
            <div class="club-card">
              <h3>Teknofest Kulübü</h3>
              <div class="advisor-name">Dr. Öğr. Üyesi Onur OKTAYSOY</div>
            </div>
          </div>
        </div>
        """

        parsed = _parse_ybs_clubs_page(html, "https://www.kafkas.edu.tr/iibfybs/tr/sayfaYeni17976")

        self.assertEqual(parsed["clubs"][0]["name"], "Techno Bilişim Kulübü")
        self.assertEqual(parsed["clubs"][0]["advisor_name"], "Dr. Öğr. Üyesi M. Akif YENİKAYA")
        self.assertEqual(len(parsed["clubs"]), 2)

    def test_extract_ybs_class_advisors_resolves_masked_names(self) -> None:
        text = (
            "I.SINIF 1 25****018 AH**** BA**** 1 Prof. Dr. GÖ**** KE**** YBS Pazartesi 09:30-11:30 "
            "11 25****060 AY**** CA**** 1 Dr. Öğr. Üyesi KA**** ME**** YBS Pazartesi 13.15-16.00 "
            "27 25****087 FA**** GÖ**** 1 Dr. Öğr. Üyesi ON**** OK**** YBS Çarşamba 13:15-16:00 "
            "43 25****063 ME**** NA**** 1 Dr. Öğr. Üyesi MU** AK** YE** YBS Pazartesi 13:15-16:00 "
            "59 25****057 SI**** SA**** 1 Dr. Öğr. Üyesi SE**** EK**** YBS Pazartesi 13:15-16:00 "
            "II.SINIF 1 24****052 AB**** İR**** 2 Prof. Dr. GÖ**** KE**** YBS Pazartesi 09:30-11:30 "
        )
        people = [
            {"name": "GÖKHAN KERSE"},
            {"name": "KAMİLE MERİÇ"},
            {"name": "ONUR OKTAYSOY"},
            {"name": "MUHAMMED AKİF YENİKAYA"},
            {"name": "SEVGÜL EKİNCİ"},
        ]

        class_advisors = _extract_ybs_class_advisors(text, people)

        self.assertEqual(class_advisors[0]["class_label"], "1. Sınıf")
        advisor_names = [entry["name"] for entry in class_advisors[0]["advisors"]]
        self.assertIn("GÖKHAN KERSE", advisor_names)
        self.assertIn("MUHAMMED AKİF YENİKAYA", advisor_names)
        self.assertTrue(any("Pazartesi 09:30-11:30" in entry["schedule"] for entry in class_advisors[0]["advisors"]))


if __name__ == "__main__":
    unittest.main()
