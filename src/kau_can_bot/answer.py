from __future__ import annotations

import ast
import operator
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from functools import lru_cache
from html import unescape
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo

import requests

from .config import (
    FALLBACK_RESPONSE,
    INDEX_PATH,
    POLITE_LANGUAGE_RESPONSE,
    Settings,
    WELCOME_MESSAGE,
)
from .indexer import SearchIndex
from .learning import expand_query, log_interaction, log_query
from .llm import OllamaAnswerGenerator, OpenAIAnswerGenerator
from .memory import (
    build_user_summary,
    find_relevant_user_fact,
    get_user_memory,
    learn_from_user_message,
    touch_user,
    user_department_name,
    user_display_name,
    user_role_name,
)
from .models import AssistantResponse, Chunk, SearchResult
from .official_data import (
    department_keys_for_query,
    ensure_department_content,
    ensure_faculty_content,
    ensure_faculty_page,
    find_faculty_navigation_matches,
    get_official_snapshot,
)
from .live_support import build_live_support
from .query_normalizer import (
    is_arabic_query,
    is_coding_query,
    is_english_query,
    is_greeting_query,
    is_smalltalk_query,
    looks_actionable,
    normalize_for_matching,
    normalize_query,
)
from .safety import has_harmful_intent, has_inappropriate_language, is_ambiguous
from .utils import clean_text, stable_id


MIN_RELIABLE_SCORE = 0.035
MAX_SUMMARY_ITEMS = 3
LINK_PATTERN = re.compile(r"Bağlantı:\s*([^|\n]+?)\s*\|\s*URL:\s*(\S+)", re.IGNORECASE)
DATE_PATTERN = re.compile(r"\b\d{1,2}\s+[A-Za-zÇĞİÖŞÜçğıöşü]+\s+\d{4}\b")
NOISE_PATTERNS = (
    r"Yeni Pencerede Aç",
    r"\d+\s*kez görüntülendi\.?",
    r"Duyuruyu Paylaş:?",
    r"DEVAMINI OKU",
)
DIRECT_SERVICE_LINKS = (
    {
        "key": "yemek-menusu",
        "title": "Yemekhane Menüsü",
        "url": "https://www.kafkas.edu.tr/skdb",
        "message_tr": "🍽️ Yemekhane menüsüne SKDB sayfası üzerinden erişilebilir.",
        "message_en": "🍽️ The cafeteria menu can be accessed through the SKDB page.",
        "message_ar": "🍽️ يمكن الوصول إلى قائمة الطعام عبر صفحة إدارة الخدمات الصحية والثقافية.",
        "terms": ("yemek", "yemekhane", "menü", "menu", "yemek menusu", "cafeteria", "food", "dining"),
    },
    {
        "key": "akademik-takvim",
        "title": "Akademik Takvim",
        "url": "https://www.kafkas.edu.tr/oidb/tr/sayfaYeni6016",
        "message_tr": "📅 Akademik takvime Öğrenci İşleri sayfası üzerinden erişilebilir.",
        "message_en": "📅 The academic calendar can be accessed through the Student Affairs page.",
        "message_ar": "📅 يمكن الوصول إلى التقويم الأكاديمي عبر صفحة شؤون الطلاب.",
        "terms": ("akademik takvim", "egitim takvimi", "öğretim takvimi", "ders takvimi", "academic calendar"),
    },
    {
        "key": "obs",
        "title": "OBS",
        "url": "https://obsyeni.kafkas.edu.tr",
        "message_tr": "✅ OBS sistemine aşağıdaki bağlantı üzerinden erişilebilir.",
        "message_en": "✅ The OBS system can be accessed through the link below.",
        "message_ar": "✅ يمكن الوصول إلى نظام معلومات الطلاب عبر الرابط التالي.",
        "terms": ("obs", "ogrenci bilgi sistemi", "öğrenci bilgi sistemi", "student information system"),
    },
    {
        "key": "wifi",
        "title": "Okul İnternet Erişimi",
        "url": "https://captive.kafkas.edu.tr:6082/php/uid.php?vsys=1&rule=4&url=https://www.yok.gov.tr",
        "message_tr": "🌐 Kampüs internet erişimi için aşağıdaki bağlantı kullanılabilir.",
        "message_en": "🌐 The campus internet access page can be opened from the link below.",
        "message_ar": "🌐 يمكن فتح صفحة الوصول إلى إنترنت الحرم الجامعي من الرابط التالي.",
        "terms": (
            "wifi",
            "wi fi",
            "kablosuz",
            "okul interneti",
            "kampus interneti",
            "internete baglan",
            "internet baglantisi",
            "internet access",
            "campus internet",
            "wireless",
        ),
    },
    {
        "key": "kutuphane",
        "title": "Kütüphane",
        "url": "https://www.kafkas.edu.tr/kddb/TR/default.aspx",
        "message_tr": "📚 Kütüphane hizmetlerine aşağıdaki bağlantı üzerinden erişilebilir.",
        "message_en": "📚 Library services can be accessed through the link below.",
        "message_ar": "📚 يمكن الوصول إلى خدمات المكتبة عبر الرابط التالي.",
        "terms": ("kutuphane", "kütüphane", "library", "lib"),
    },
    {
        "key": "ebys",
        "title": "EBYS",
        "url": "https://ebys.kafkas.edu.tr/DYS/documentmanagement/",
        "message_tr": "🗂️ EBYS sistemine aşağıdaki bağlantı üzerinden erişilebilir.",
        "message_en": "🗂️ The EBYS system can be accessed through the link below.",
        "message_ar": "🗂️ يمكن الوصول إلى نظام إدارة المستندات EBYS عبر الرابط التالي.",
        "terms": ("ebys", "evrak", "belge yonetim", "document management"),
    },
    {
        "key": "telefon-rehberi",
        "title": "Telefon Rehberi",
        "url": "https://www.kafkas.edu.tr/kau/rehber2",
        "message_tr": "📞 Telefon rehberine aşağıdaki bağlantı üzerinden erişilebilir.",
        "message_en": "📞 The phone directory can be accessed through the link below.",
        "message_ar": "📞 يمكن الوصول إلى دليل الهاتف عبر الرابط التالي.",
        "terms": ("telefon rehberi", "rehber", "telefon listesi", "phone directory", "directory"),
    },
)
CLASSROOM_LOCATION_GROUPS = (
    {
        "codes": ("101", "102", "103", "104"),
        "label": "101-102-103-104",
        "tr": "📌 101-102-103-104 nolu derslikler 1. katta, Uluslararası Ticaret ve Lojistik Bölüm Başkanlığının karşısındadır.",
        "en": "📌 Classrooms 101-102-103-104 are on the 1st floor, opposite the Department Chair of International Trade and Logistics.",
        "ar": "📌 القاعات 101-102-103-104 تقع في الطابق الأول مقابل رئاسة قسم التجارة الدولية واللوجستيات.",
    },
    {
        "codes": ("105", "106", "107", "108"),
        "label": "105-106-107-108",
        "tr": "📌 105-106-107-108 nolu derslikler 1. katta, İktisat Bölüm Başkanlığının karşısındadır.",
        "en": "📌 Classrooms 105-106-107-108 are on the 1st floor, opposite the Department Chair of Economics.",
        "ar": "📌 القاعات 105-106-107-108 تقع في الطابق الأول مقابل رئاسة قسم الاقتصاد.",
    },
    {
        "codes": ("201", "202", "203", "204"),
        "label": "201-202-203-204",
        "tr": "📌 201-202-203-204 nolu derslikler 2. katta, Yönetim Bilişim Sistemleri Bölüm Başkanlığının karşısındadır.",
        "en": "📌 Classrooms 201-202-203-204 are on the 2nd floor, opposite the Department Chair of Management Information Systems.",
        "ar": "📌 القاعات 201-202-203-204 تقع في الطابق الثاني مقابل رئاسة قسم نظم المعلومات الإدارية.",
    },
    {
        "codes": ("205", "206", "207", "208"),
        "label": "205-206-207-208",
        "tr": "📌 205-206-207-208 nolu derslikler 2. katta, İşletme Bölüm Başkanlığının karşısındadır.",
        "en": "📌 Classrooms 205-206-207-208 are on the 2nd floor, opposite the Department Chair of Business Administration.",
        "ar": "📌 القاعات 205-206-207-208 تقع في الطابق الثاني مقابل رئاسة قسم إدارة الأعمال.",
    },
    {
        "codes": ("301",),
        "label": "301",
        "tr": "📌 301 nolu derslik 3. katta, Siyaset Bilimi ve Kamu Yönetimi Bölüm Başkanlığının karşısındadır.",
        "en": "📌 Classroom 301 is on the 3rd floor, opposite the Department Chair of Political Science and Public Administration.",
        "ar": "📌 القاعة 301 تقع في الطابق الثالث مقابل رئاسة قسم العلوم السياسية والإدارة العامة.",
    },
)
NAMED_CLASSROOM_LOCATIONS = (
    {
        "terms": ("huseyin aytemiz konferans salonu", "hüseyin aytemiz konferans salonu", "huseyin aytemiz", "hüseyin aytemiz"),
        "tr": "📌 Hüseyin Aytemiz Konferans Salonu 3. katta, Siyaset Bilimi ve Kamu Yönetimi Bölümü karşısındadır.",
        "en": "📌 The Huseyin Aytemiz Conference Hall is on the 3rd floor, opposite the Department of Political Science and Public Administration.",
        "ar": "📌 تقع قاعة حسين أيتميز للمؤتمرات في الطابق الثالث مقابل قسم العلوم السياسية والإدارة العامة.",
    },
)
FACULTY_CONTACT_PAGE = "https://kafkas.edu.tr/iibf/tr/sayfaYeni18034"
MAPS_LINK = ("Maps'te Aç", "https://maps.app.goo.gl/HMYYaxbZBcZVisbN7")
RECTOR_PAGE = ("Rektör", "https://www.kafkas.edu.tr/rektorluk/tr/sayfaYeni655")
RECTOR_ASSISTANTS_PAGE = ("Rektör Yardımcıları", "https://www.kafkas.edu.tr/rektorluk/TR/sayfaYeni652")
SENATE_PAGE = ("Senato ve Dekanlıklar", "https://www.kafkas.edu.tr/rektorluk/TR/sayfaYeni651")
SMALLTALK_RESPONSES = {
    "naber": {
        "tr": "😊 İyiyim, teşekkür ederim. Akademik ya da genel bir konuda yardımcı olmam istenirse memnuniyetle destek sunabilirim.",
        "en": "😊 I'm doing well, thank you. I can gladly help with campus topics or general questions.",
        "ar": "😊 أنا بخير، شكرًا لك. يمكن المساعدة في موضوع جامعي أو عام بكل سرور.",
    },
    "ne haber": {
        "tr": "😊 Her şey yolunda görünüyor. İİBF, genel bilgi ya da günlük bir konuda yardımcı olabilirim.",
        "en": "😊 Everything looks good. I can help with IIBF, general information, or casual conversation.",
        "ar": "😊 كل شيء بخير. يمكن المساعدة في شؤون الكلية أو في الأسئلة العامة أو في دردشة يومية قصيرة.",
    },
    "nasilsin": {
        "tr": "😊 Teşekkür ederim, gayet iyiyim. İstenirse sohbet edebilir ya da herhangi bir konuda bilgi paylaşabilirim.",
        "en": "😊 I'm well, thank you. We can chat or continue with any question you'd like.",
        "ar": "😊 أنا بخير، شكرًا لك. يمكننا الدردشة أو متابعة أي سؤال ترغب به.",
    },
    "iyi misin": {
        "tr": "😊 Teşekkür ederim, iyiyim. İstenirse hemen bir soruya geçilebilir.",
        "en": "😊 Thank you, I'm doing well. We can move straight to your next question.",
        "ar": "😊 شكرًا لك، أنا بخير. يمكننا الانتقال مباشرة إلى سؤالك التالي.",
    },
    "ne yapiyorsun": {
        "tr": "😊 Sorulara yanıt vermek ve birlikte çözüm üretmek için hazır durumdayım. İstenirse kampüs, dersler ya da genel bilgi konularında devam edilebilir.",
        "en": "😊 I'm here to answer questions and help work through problems. We can continue with campus, coursework, or general topics.",
        "ar": "😊 أنا جاهز للإجابة عن الأسئلة والمساعدة في إيجاد الحلول. يمكننا المتابعة في موضوع جامعي أو عام أو تقني.",
    },
    "nasil gidiyor": {
        "tr": "😊 Gayet iyi gidiyor. İstenirse sohbet edilebilir ya da hemen bir soruya geçilebilir.",
        "en": "😊 It's going well. We can keep chatting or move straight to your next question.",
        "ar": "😊 الأمور تسير بشكل جيد. يمكننا متابعة الدردشة أو الانتقال مباشرة إلى سؤالك التالي.",
    },
    "ne var ne yok": {
        "tr": "😊 Şu an her şey yolunda. İstenirse günlük bir sohbet yapılabilir ya da doğrudan bir konuya geçilebilir.",
        "en": "😊 Everything is fine at the moment. We can chat casually or jump into a specific topic.",
        "ar": "😊 كل شيء على ما يرام حاليًا. يمكننا الدردشة قليلًا أو الانتقال إلى موضوع محدد.",
    },
    "gunun nasil geciyor": {
        "tr": "😊 Yoğun ama verimli geçiyor. Sohbet etmek ya da bir konuda birlikte ilerlemek memnuniyetle mümkün.",
        "en": "😊 It's busy but productive. I'm happy to chat or help move a topic forward.",
        "ar": "😊 اليوم مزدحم لكنه جيد. يسعدني أن أدردش أو أساعد في أي موضوع.",
    },
    "tesekkurler": {
        "tr": "😊 Rica ederim. Yeni bir soru olduğunda yardımcı olmaktan memnuniyet duyarım.",
        "en": "😊 You're welcome. I'd be happy to help again whenever you have another question.",
        "ar": "😊 على الرحب والسعة. يسعدني أن أساعد مرة أخرى متى احتجت.",
    },
    "merhaba": {
        "tr": "👋 Merhaba. Hazır durumdayım; istenirse bilgi verilebilir, metin yazılabilir veya bir konu birlikte araştırılabilir.",
        "en": "👋 Hello. I'm ready to help with information, writing, coding, or short research tasks.",
        "ar": "👋 مرحبًا. أنا جاهز للمساعدة في المعلومات والكتابة والبرمجة والمهام البحثية القصيرة.",
    },
    "adın ne": {
        "tr": "👋 Ben KAÜCAN Beta. Kafkas Üniversitesi İİBF için bilgi, yazım desteği ve genel yapay zeka yardımı sunabilirim.",
        "en": "👋 I am KAUCAN Beta. I can help with FEAS information, writing support, and general AI assistance.",
        "ar": "👋 أنا KAÜCAN Beta. يمكنني المساعدة في معلومات الكلية والكتابة والدعم الذكي العام.",
    },
    "ne yapabilirsin": {
        "tr": "✅ İİBF bilgileri, duyurular, personel, iletişim, konum, kod soruları, metin düzeltme, mail ve dilekçe yazımı gibi konularda destek sunabilirim.",
        "en": "✅ I can help with FEAS information, announcements, staff, contact, location, coding, text correction, emails, and petition drafting.",
        "ar": "✅ يمكنني المساعدة في معلومات الكلية والإعلانات والكوادر والاتصال والموقع والبرمجة وتصحيح النصوص وكتابة الرسائل والطلبات.",
    },
    "كيف حالك": {
        "tr": "😊 İyiyim, teşekkür ederim. İstenirse sohbete ya da bir soruya hemen geçilebilir.",
        "en": "😊 I'm doing well, thank you. We can move straight to chatting or to your next question.",
        "ar": "😊 أنا بخير، شكرًا لك. يمكننا الانتقال مباشرة إلى الدردشة أو إلى سؤالك التالي.",
    },
    "شكرا": {
        "tr": "😊 Rica ederim. Yeni bir soru olduğunda yardımcı olmaktan memnuniyet duyarım.",
        "en": "😊 You're welcome. I'd be happy to help again whenever you have another question.",
        "ar": "😊 على الرحب والسعة. يسعدني أن أساعدك في أي وقت.",
    },
}
ISTANBUL_TZ = ZoneInfo("Europe/Istanbul")
FACULTY_ALIAS_MAP = {
    "iibf": (
        "iibf",
        "iktisadi ve idari bilimler",
        "iktisadi idari bilimler",
        "feas",
        "faculty of economics and administrative sciences",
    ),
    "fen-edebiyat": (
        "fen edebiyat",
        "fen-edebiyat",
        "arts and sciences",
        "faculty of arts and sciences",
    ),
    "egitim": (
        "egitim",
        "dede korkut egitim",
        "education faculty",
        "faculty of education",
    ),
    "guzel-sanatlar": (
        "guzel sanatlar",
        "fine arts",
        "faculty of fine arts",
    ),
    "ilahiyat": (
        "ilahiyat",
        "theology",
        "faculty of theology",
    ),
    "dis-hekimligi": (
        "dis hekimligi",
        "diş hekimliği",
        "dentistry",
        "faculty of dentistry",
    ),
    "muhendislik-mimarlik": (
        "muhendislik mimarlik",
        "mühendislik mimarlık",
        "engineering architecture",
        "engineering and architecture",
        "faculty of engineering and architecture",
    ),
    "saglik-bilimleri": (
        "saglik bilimleri",
        "sağlık bilimleri",
        "health sciences",
        "faculty of health sciences",
    ),
    "spor-bilimleri": (
        "spor bilimleri",
        "sarikamis spor bilimleri",
        "sports sciences",
        "faculty of sports sciences",
    ),
    "turizm": (
        "sarikamis turizm",
        "turizm",
        "tourism",
        "faculty of tourism",
    ),
    "tip": (
        "tip fakultesi",
        "tıp fakültesi",
        "medical faculty",
        "faculty of medicine",
    ),
    "veteriner": (
        "veteriner",
        "veterinary",
        "faculty of veterinary medicine",
    ),
}
WEEKDAY_NAMES = {
    "tr": ("Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"),
    "en": ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"),
    "ar": ("الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"),
}
MONTH_NAMES_TR = {
    "ocak": 1,
    "subat": 2,
    "şubat": 2,
    "mart": 3,
    "nisan": 4,
    "mayis": 5,
    "mayıs": 5,
    "haziran": 6,
    "temmuz": 7,
    "agustos": 8,
    "ağustos": 8,
    "eylul": 9,
    "eylül": 9,
    "ekim": 10,
    "kasim": 11,
    "kasım": 11,
    "aralik": 12,
    "aralık": 12,
}
MONTH_NAMES_EN = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}
SPECIAL_DAY_BUILDERS = {
    "yilbasi": lambda year: date(year, 1, 1),
    "new year": lambda year: date(year, 1, 1),
    "sevgililer gunu": lambda year: date(year, 2, 14),
    "valentine": lambda year: date(year, 2, 14),
    "8 mart": lambda year: date(year, 3, 8),
    "kadinlar gunu": lambda year: date(year, 3, 8),
    "dunya kadinlar gunu": lambda year: date(year, 3, 8),
    "18 mart": lambda year: date(year, 3, 18),
    "canakkale zaferi": lambda year: date(year, 3, 18),
    "23 nisan": lambda year: date(year, 4, 23),
    "ulusal egemenlik ve cocuk bayrami": lambda year: date(year, 4, 23),
    "1 mayis": lambda year: date(year, 5, 1),
    "emek ve dayanisma gunu": lambda year: date(year, 5, 1),
    "anneler gunu": lambda year: _nth_weekday_of_month(year, 5, 6, 2),
    "mother's day": lambda year: _nth_weekday_of_month(year, 5, 6, 2),
    "mothers day": lambda year: _nth_weekday_of_month(year, 5, 6, 2),
    "19 mayis": lambda year: date(year, 5, 19),
    "ataturk u anma genclik ve spor bayrami": lambda year: date(year, 5, 19),
    "genclik ve spor bayrami": lambda year: date(year, 5, 19),
    "babalar gunu": lambda year: _nth_weekday_of_month(year, 6, 6, 3),
    "father's day": lambda year: _nth_weekday_of_month(year, 6, 6, 3),
    "fathers day": lambda year: _nth_weekday_of_month(year, 6, 6, 3),
    "15 temmuz": lambda year: date(year, 7, 15),
    "demokrasi ve milli birlik gunu": lambda year: date(year, 7, 15),
    "30 agustos": lambda year: date(year, 8, 30),
    "zafer bayrami": lambda year: date(year, 8, 30),
    "29 ekim": lambda year: date(year, 10, 29),
    "cumhuriyet bayrami": lambda year: date(year, 10, 29),
    "10 kasim": lambda year: date(year, 11, 10),
    "ataturk u anma": lambda year: date(year, 11, 10),
    "24 kasim": lambda year: date(year, 11, 24),
    "ogretmenler gunu": lambda year: date(year, 11, 24),
    "teachers day": lambda year: date(year, 11, 24),
}
SPECIAL_DAY_DEFINITIONS = (
    {"key": "new_year", "labels": {"tr": "Yılbaşı", "en": "New Year's Day"}, "aliases": ("yilbasi", "new year", "new year's day"), "builder": lambda year: date(year, 1, 1)},
    {"key": "world_braille_day", "labels": {"tr": "Dünya Braille Günü", "en": "World Braille Day"}, "aliases": ("braille gunu", "world braille day"), "builder": lambda year: date(year, 1, 4)},
    {"key": "world_cancer_day", "labels": {"tr": "Dünya Kanser Günü", "en": "World Cancer Day"}, "aliases": ("kanser gunu", "world cancer day"), "builder": lambda year: date(year, 2, 4)},
    {"key": "women_in_science_day", "labels": {"tr": "Bilimde Kadınlar ve Kız Çocukları Günü", "en": "International Day of Women and Girls in Science"}, "aliases": ("bilimde kadinlar", "women and girls in science", "science day for women"), "builder": lambda year: date(year, 2, 11)},
    {"key": "valentines_day", "labels": {"tr": "Sevgililer Günü", "en": "Valentine's Day"}, "aliases": ("sevgililer gunu", "valentine", "valentines day"), "builder": lambda year: date(year, 2, 14)},
    {"key": "social_justice_day", "labels": {"tr": "Dünya Sosyal Adalet Günü", "en": "World Day of Social Justice"}, "aliases": ("sosyal adalet gunu", "world day of social justice"), "builder": lambda year: date(year, 2, 20)},
    {"key": "world_wildlife_day", "labels": {"tr": "Dünya Yaban Hayatı Günü", "en": "World Wildlife Day"}, "aliases": ("yaban hayati gunu", "world wildlife day"), "builder": lambda year: date(year, 3, 3)},
    {"key": "womens_day", "labels": {"tr": "Dünya Kadınlar Günü", "en": "International Women's Day"}, "aliases": ("8 mart", "kadinlar gunu", "dunya kadinlar gunu", "women's day", "womens day"), "builder": lambda year: date(year, 3, 8)},
    {"key": "pi_day", "labels": {"tr": "Pi Günü", "en": "Pi Day"}, "aliases": ("pi gunu", "pi day"), "builder": lambda year: date(year, 3, 14)},
    {"key": "canakkale_victory", "labels": {"tr": "Çanakkale Zaferi", "en": "Canakkale Victory and Martyrs' Memorial Day"}, "aliases": ("18 mart", "canakkale zaferi"), "builder": lambda year: date(year, 3, 18)},
    {"key": "happiness_day", "labels": {"tr": "Uluslararası Mutluluk Günü", "en": "International Day of Happiness"}, "aliases": ("mutluluk gunu", "international day of happiness"), "builder": lambda year: date(year, 3, 20)},
    {"key": "forests_day", "labels": {"tr": "Dünya Ormancılık Günü", "en": "International Day of Forests"}, "aliases": ("orman gunu", "ormancilik gunu", "international day of forests"), "builder": lambda year: date(year, 3, 21)},
    {"key": "poetry_day", "labels": {"tr": "Dünya Şiir Günü", "en": "World Poetry Day"}, "aliases": ("siir gunu", "world poetry day"), "builder": lambda year: date(year, 3, 21)},
    {"key": "racial_discrimination_day", "labels": {"tr": "Irk Ayrımcılığı ile Mücadele Günü", "en": "International Day for the Elimination of Racial Discrimination"}, "aliases": ("irk ayrimciligi", "racial discrimination day"), "builder": lambda year: date(year, 3, 21)},
    {"key": "down_syndrome_day", "labels": {"tr": "Dünya Down Sendromu Günü", "en": "World Down Syndrome Day"}, "aliases": ("down sendromu gunu", "world down syndrome day"), "builder": lambda year: date(year, 3, 21)},
    {"key": "water_day", "labels": {"tr": "Dünya Su Günü", "en": "World Water Day"}, "aliases": ("su gunu", "world water day"), "builder": lambda year: date(year, 3, 22)},
    {"key": "meteorological_day", "labels": {"tr": "Dünya Meteoroloji Günü", "en": "World Meteorological Day"}, "aliases": ("meteoroloji gunu", "world meteorological day"), "builder": lambda year: date(year, 3, 23)},
    {"key": "autism_day", "labels": {"tr": "Dünya Otizm Farkındalık Günü", "en": "World Autism Awareness Day"}, "aliases": ("otizm gunu", "autism day"), "builder": lambda year: date(year, 4, 2)},
    {"key": "health_day", "labels": {"tr": "Dünya Sağlık Günü", "en": "World Health Day"}, "aliases": ("saglik gunu", "world health day"), "builder": lambda year: date(year, 4, 7)},
    {"key": "national_sovereignty_day", "labels": {"tr": "Ulusal Egemenlik ve Çocuk Bayramı", "en": "National Sovereignty and Children's Day"}, "aliases": ("23 nisan", "ulusal egemenlik ve cocuk bayrami"), "builder": lambda year: date(year, 4, 23)},
    {"key": "book_day", "labels": {"tr": "Dünya Kitap ve Telif Hakkı Günü", "en": "World Book and Copyright Day"}, "aliases": ("kitap gunu", "world book day"), "builder": lambda year: date(year, 4, 23)},
    {"key": "labour_day", "labels": {"tr": "Emek ve Dayanışma Günü", "en": "International Workers' Day"}, "aliases": ("1 mayis", "emek ve dayanisma gunu", "labour day", "workers day"), "builder": lambda year: date(year, 5, 1)},
    {"key": "red_cross_day", "labels": {"tr": "Dünya Kızılay ve Kızılhaç Günü", "en": "World Red Cross and Red Crescent Day"}, "aliases": ("kizilay gunu", "red cross day"), "builder": lambda year: date(year, 5, 8)},
    {"key": "mothers_day", "labels": {"tr": "Anneler Günü", "en": "Mother's Day"}, "aliases": ("anneler gunu", "mother's day", "mothers day"), "builder": lambda year: _nth_weekday_of_month(year, 5, 6, 2)},
    {"key": "families_day", "labels": {"tr": "Uluslararası Aile Günü", "en": "International Day of Families"}, "aliases": ("aile gunu", "day of families"), "builder": lambda year: date(year, 5, 15)},
    {"key": "telecommunication_day", "labels": {"tr": "Dünya Telekomünikasyon ve Bilgi Toplumu Günü", "en": "World Telecommunication and Information Society Day"}, "aliases": ("telekomunikasyon gunu", "bilgi toplumu gunu"), "builder": lambda year: date(year, 5, 17)},
    {"key": "museum_day", "labels": {"tr": "Uluslararası Müzeler Günü", "en": "International Museum Day"}, "aliases": ("muzeler gunu", "museum day"), "builder": lambda year: date(year, 5, 18)},
    {"key": "youth_and_sports_day", "labels": {"tr": "Atatürk'ü Anma, Gençlik ve Spor Bayramı", "en": "Commemoration of Atatürk, Youth and Sports Day"}, "aliases": ("19 mayis", "genclik ve spor bayrami", "ataturk u anma genclik ve spor bayrami"), "builder": lambda year: date(year, 5, 19)},
    {"key": "bee_day", "labels": {"tr": "Dünya Arı Günü", "en": "World Bee Day"}, "aliases": ("ari gunu", "world bee day"), "builder": lambda year: date(year, 5, 20)},
    {"key": "no_tobacco_day", "labels": {"tr": "Dünya Tütünsüz Günü", "en": "World No Tobacco Day"}, "aliases": ("tutunsuz gunu", "no tobacco day"), "builder": lambda year: date(year, 5, 31)},
    {"key": "environment_day", "labels": {"tr": "Dünya Çevre Günü", "en": "World Environment Day"}, "aliases": ("cevre gunu", "environment day"), "builder": lambda year: date(year, 6, 5)},
    {"key": "oceans_day", "labels": {"tr": "Dünya Okyanus Günü", "en": "World Oceans Day"}, "aliases": ("okyanus gunu", "oceans day"), "builder": lambda year: date(year, 6, 8)},
    {"key": "child_labour_day", "labels": {"tr": "Çocuk İşçiliği ile Mücadele Günü", "en": "World Day Against Child Labour"}, "aliases": ("cocuk isciligi", "child labour day"), "builder": lambda year: date(year, 6, 12)},
    {"key": "blood_donor_day", "labels": {"tr": "Dünya Gönüllü Kan Bağışçıları Günü", "en": "World Blood Donor Day"}, "aliases": ("kan bagiscilari gunu", "blood donor day"), "builder": lambda year: date(year, 6, 14)},
    {"key": "fathers_day", "labels": {"tr": "Babalar Günü", "en": "Father's Day"}, "aliases": ("babalar gunu", "father's day", "fathers day"), "builder": lambda year: _nth_weekday_of_month(year, 6, 6, 3)},
    {"key": "refugee_day", "labels": {"tr": "Dünya Mülteciler Günü", "en": "World Refugee Day"}, "aliases": ("multeciler gunu", "refugee day"), "builder": lambda year: date(year, 6, 20)},
    {"key": "yoga_day", "labels": {"tr": "Uluslararası Yoga Günü", "en": "International Day of Yoga"}, "aliases": ("yoga gunu", "international day of yoga"), "builder": lambda year: date(year, 6, 21)},
    {"key": "music_day", "labels": {"tr": "Dünya Müzik Günü", "en": "World Music Day"}, "aliases": ("muzik gunu", "music day"), "builder": lambda year: date(year, 6, 21)},
    {"key": "democracy_day_tr", "labels": {"tr": "Demokrasi ve Milli Birlik Günü", "en": "Democracy and National Unity Day"}, "aliases": ("15 temmuz", "demokrasi ve milli birlik gunu"), "builder": lambda year: date(year, 7, 15)},
    {"key": "friendship_day", "labels": {"tr": "Uluslararası Dostluk Günü", "en": "International Day of Friendship"}, "aliases": ("dostluk gunu", "friendship day"), "builder": lambda year: date(year, 7, 30)},
    {"key": "indigenous_day", "labels": {"tr": "Dünya Yerli Halklar Günü", "en": "International Day of the World's Indigenous Peoples"}, "aliases": ("yerli halklar gunu", "indigenous peoples day"), "builder": lambda year: date(year, 8, 9)},
    {"key": "youth_day", "labels": {"tr": "Uluslararası Gençlik Günü", "en": "International Youth Day"}, "aliases": ("genclik gunu", "international youth day"), "builder": lambda year: date(year, 8, 12)},
    {"key": "humanitarian_day", "labels": {"tr": "Dünya İnsani Yardım Günü", "en": "World Humanitarian Day"}, "aliases": ("insani yardim gunu", "humanitarian day"), "builder": lambda year: date(year, 8, 19)},
    {"key": "victory_day_tr", "labels": {"tr": "Zafer Bayramı", "en": "Victory Day"}, "aliases": ("30 agustos", "zafer bayrami"), "builder": lambda year: date(year, 8, 30)},
    {"key": "literacy_day", "labels": {"tr": "Dünya Okuryazarlık Günü", "en": "International Literacy Day"}, "aliases": ("okuryazarlik gunu", "literacy day"), "builder": lambda year: date(year, 9, 8)},
    {"key": "democracy_day", "labels": {"tr": "Uluslararası Demokrasi Günü", "en": "International Day of Democracy"}, "aliases": ("demokrasi gunu", "day of democracy"), "builder": lambda year: date(year, 9, 15)},
    {"key": "peace_day", "labels": {"tr": "Dünya Barış Günü", "en": "International Day of Peace"}, "aliases": ("baris gunu", "peace day"), "builder": lambda year: date(year, 9, 21)},
    {"key": "tourism_day", "labels": {"tr": "Dünya Turizm Günü", "en": "World Tourism Day"}, "aliases": ("turizm gunu", "world tourism day"), "builder": lambda year: date(year, 9, 27)},
    {"key": "older_persons_day", "labels": {"tr": "Dünya Yaşlılar Günü", "en": "International Day of Older Persons"}, "aliases": ("yaslilar gunu", "older persons day"), "builder": lambda year: date(year, 10, 1)},
    {"key": "animal_day", "labels": {"tr": "Dünya Hayvanları Koruma Günü", "en": "World Animal Day"}, "aliases": ("hayvanlari koruma gunu", "animal day"), "builder": lambda year: date(year, 10, 4)},
    {"key": "teachers_day_world", "labels": {"tr": "Dünya Öğretmenler Günü", "en": "World Teachers' Day"}, "aliases": ("dunya ogretmenler gunu", "world teachers day"), "builder": lambda year: date(year, 10, 5)},
    {"key": "mental_health_day", "labels": {"tr": "Dünya Ruh Sağlığı Günü", "en": "World Mental Health Day"}, "aliases": ("ruh sagligi gunu", "mental health day"), "builder": lambda year: date(year, 10, 10)},
    {"key": "girl_child_day", "labels": {"tr": "Dünya Kız Çocukları Günü", "en": "International Day of the Girl Child"}, "aliases": ("kiz cocuklari gunu", "girl child day"), "builder": lambda year: date(year, 10, 11)},
    {"key": "food_day", "labels": {"tr": "Dünya Gıda Günü", "en": "World Food Day"}, "aliases": ("gida gunu", "food day"), "builder": lambda year: date(year, 10, 16)},
    {"key": "republic_day", "labels": {"tr": "Cumhuriyet Bayramı", "en": "Republic Day"}, "aliases": ("29 ekim", "cumhuriyet bayrami"), "builder": lambda year: date(year, 10, 29)},
    {"key": "halloween", "labels": {"tr": "Cadılar Bayramı", "en": "Halloween"}, "aliases": ("cadilar bayrami", "halloween"), "builder": lambda year: date(year, 10, 31)},
    {"key": "science_day", "labels": {"tr": "Bilim Günü", "en": "World Science Day for Peace and Development"}, "aliases": ("bilim gunu", "world science day"), "builder": lambda year: date(year, 11, 10)},
    {"key": "ataturk_memorial_day", "labels": {"tr": "Atatürk'ü Anma Günü", "en": "Ataturk Memorial Day"}, "aliases": ("10 kasim", "ataturk u anma"), "builder": lambda year: date(year, 11, 10)},
    {"key": "kindness_day", "labels": {"tr": "Dünya İyilik Günü", "en": "World Kindness Day"}, "aliases": ("iyilik gunu", "kindness day"), "builder": lambda year: date(year, 11, 13)},
    {"key": "tolerance_day", "labels": {"tr": "Uluslararası Hoşgörü Günü", "en": "International Day for Tolerance"}, "aliases": ("hosgoru gunu", "tolerance day"), "builder": lambda year: date(year, 11, 16)},
    {"key": "mens_day", "labels": {"tr": "Dünya Erkekler Günü", "en": "International Men's Day"}, "aliases": ("erkekler gunu", "international men's day", "mens day"), "builder": lambda year: date(year, 11, 19)},
    {"key": "toilet_day", "labels": {"tr": "Dünya Tuvalet Günü", "en": "World Toilet Day"}, "aliases": ("tuvalet gunu", "world toilet day"), "builder": lambda year: date(year, 11, 19)},
    {"key": "childrens_day_world", "labels": {"tr": "Dünya Çocuk Günü", "en": "Universal Children's Day"}, "aliases": ("dunya cocuk gunu", "universal children's day", "universal childrens day"), "builder": lambda year: date(year, 11, 20)},
    {"key": "violence_against_women_day", "labels": {"tr": "Kadına Yönelik Şiddete Karşı Mücadele Günü", "en": "International Day for the Elimination of Violence against Women"}, "aliases": ("kadina siddetle mucadele gunu", "violence against women day"), "builder": lambda year: date(year, 11, 25)},
    {"key": "teachers_day_tr", "labels": {"tr": "Öğretmenler Günü", "en": "Teachers' Day in Türkiye"}, "aliases": ("24 kasim", "ogretmenler gunu", "teachers day"), "builder": lambda year: date(year, 11, 24)},
    {"key": "disability_day", "labels": {"tr": "Dünya Engelliler Günü", "en": "International Day of Persons with Disabilities"}, "aliases": ("engelliler gunu", "disability day"), "builder": lambda year: date(year, 12, 3)},
    {"key": "volunteer_day", "labels": {"tr": "Dünya Gönüllüler Günü", "en": "International Volunteer Day"}, "aliases": ("gonulluler gunu", "volunteer day"), "builder": lambda year: date(year, 12, 5)},
    {"key": "human_rights_day", "labels": {"tr": "İnsan Hakları Günü", "en": "Human Rights Day"}, "aliases": ("insan haklari gunu", "human rights day"), "builder": lambda year: date(year, 12, 10)},
    {"key": "migrants_day", "labels": {"tr": "Uluslararası Göçmenler Günü", "en": "International Migrants Day"}, "aliases": ("gocmenler gunu", "migrants day"), "builder": lambda year: date(year, 12, 18)},
    {"key": "christmas_eve", "labels": {"tr": "Noel Arifesi", "en": "Christmas Eve"}, "aliases": ("noel arifesi", "christmas eve"), "builder": lambda year: date(year, 12, 24)},
    {"key": "christmas", "labels": {"tr": "Noel", "en": "Christmas Day"}, "aliases": ("noel", "christmas", "christmas day"), "builder": lambda year: date(year, 12, 25)},
)
DIYANET_RELIGIOUS_CALENDAR_URL = "https://vakithesaplama.diyanet.gov.tr/dinigunler.php?yil={year}"
DIYANET_RELIGIOUS_SCHEDULES = {
    2026: {
        "uc_aylar_baslangici": date(2026, 12, 10),
        "regaib_kandili": date(2026, 12, 10),
        "mirac_kandili": date(2026, 1, 15),
        "berat_kandili": date(2026, 2, 2),
        "ramazan_baslangici": date(2026, 2, 19),
        "kadir_gecesi": date(2026, 3, 16),
        "ramazan_arefesi": date(2026, 3, 19),
        "ramazan_bayrami": date(2026, 3, 20),
        "kurban_arefesi": date(2026, 5, 26),
        "kurban_bayrami": date(2026, 5, 27),
        "hicri_yilbasi": date(2026, 6, 16),
        "asure_gunu": date(2026, 6, 25),
        "mevlid_kandili": date(2026, 8, 24),
    }
}
RELIGIOUS_SPECIAL_DAY_DEFINITIONS = (
    {
        "key": "uc_aylar_baslangici",
        "labels": {"tr": "Üç Ayların Başlangıcı", "en": "Beginning of the Three Holy Months", "ar": "بداية الأشهر الحرم الثلاثة"},
        "aliases": ("uc aylar", "üç aylar", "uc aylarin baslangici", "üç ayların başlangıcı", "three holy months"),
        "builder": lambda year: _religious_day_date("uc_aylar_baslangici", year),
        "source_title": "Diyanet Dini Günler Takvimi",
        "source_url": DIYANET_RELIGIOUS_CALENDAR_URL,
        "religious": True,
    },
    {
        "key": "regaib_kandili",
        "labels": {"tr": "Regaib Kandili", "en": "Regaib Kandili", "ar": "ليلة الرغائب"},
        "aliases": ("regaib kandili", "regaip kandili", "regaib", "regaip"),
        "builder": lambda year: _religious_day_date("regaib_kandili", year),
        "source_title": "Diyanet Dini Günler Takvimi",
        "source_url": DIYANET_RELIGIOUS_CALENDAR_URL,
        "religious": True,
    },
    {
        "key": "mirac_kandili",
        "labels": {"tr": "Miraç Kandili", "en": "Miraj Kandili", "ar": "ليلة المعراج"},
        "aliases": ("mirac kandili", "miraç kandili", "mirac gecesi", "miraç gecesi"),
        "builder": lambda year: _religious_day_date("mirac_kandili", year),
        "source_title": "Diyanet Dini Günler Takvimi",
        "source_url": DIYANET_RELIGIOUS_CALENDAR_URL,
        "religious": True,
    },
    {
        "key": "berat_kandili",
        "labels": {"tr": "Berat Kandili", "en": "Berat Kandili", "ar": "ليلة البراءة"},
        "aliases": ("berat kandili", "beraat kandili", "berat gecesi"),
        "builder": lambda year: _religious_day_date("berat_kandili", year),
        "source_title": "Diyanet Dini Günler Takvimi",
        "source_url": DIYANET_RELIGIOUS_CALENDAR_URL,
        "religious": True,
    },
    {
        "key": "ramazan_baslangici",
        "labels": {"tr": "Ramazan Başlangıcı", "en": "Beginning of Ramadan", "ar": "بداية رمضان"},
        "aliases": ("ramazan baslangici", "ramazan başlangıcı", "ramazan ne zaman", "ramadan starts", "start of ramadan"),
        "builder": lambda year: _religious_day_date("ramazan_baslangici", year),
        "source_title": "Diyanet Dini Günler Takvimi",
        "source_url": DIYANET_RELIGIOUS_CALENDAR_URL,
        "religious": True,
    },
    {
        "key": "kadir_gecesi",
        "labels": {"tr": "Kadir Gecesi", "en": "Laylat al-Qadr", "ar": "ليلة القدر"},
        "aliases": ("kadir gecesi", "kadir gecesi ne zaman", "laylat al qadr", "night of power"),
        "builder": lambda year: _religious_day_date("kadir_gecesi", year),
        "source_title": "Diyanet Dini Günler Takvimi",
        "source_url": DIYANET_RELIGIOUS_CALENDAR_URL,
        "religious": True,
    },
    {
        "key": "ramazan_arefesi",
        "labels": {"tr": "Ramazan Bayramı Arefesi", "en": "Eid al-Fitr Eve", "ar": "وقفة عيد الفطر"},
        "aliases": ("ramazan arefesi", "ramazan bayrami arefesi", "ramazan bayramı arefesi", "eid al-fitr eve"),
        "builder": lambda year: _religious_day_date("ramazan_arefesi", year),
        "source_title": "Diyanet Dini Günler Takvimi",
        "source_url": DIYANET_RELIGIOUS_CALENDAR_URL,
        "religious": True,
    },
    {
        "key": "ramazan_bayrami",
        "labels": {"tr": "Ramazan Bayramı", "en": "Eid al-Fitr", "ar": "عيد الفطر"},
        "aliases": ("ramazan bayrami", "ramazan bayramı", "seker bayrami", "şeker bayramı", "eid al-fitr", "eid ul fitr"),
        "builder": lambda year: _religious_day_date("ramazan_bayrami", year),
        "source_title": "Diyanet Dini Günler Takvimi",
        "source_url": DIYANET_RELIGIOUS_CALENDAR_URL,
        "religious": True,
        "duration_days": 3,
    },
    {
        "key": "kurban_arefesi",
        "labels": {"tr": "Kurban Bayramı Arefesi", "en": "Eid al-Adha Eve", "ar": "وقفة عيد الأضحى"},
        "aliases": ("kurban arefesi", "kurban bayrami arefesi", "kurban bayramı arefesi", "eid al-adha eve"),
        "builder": lambda year: _religious_day_date("kurban_arefesi", year),
        "source_title": "Diyanet Dini Günler Takvimi",
        "source_url": DIYANET_RELIGIOUS_CALENDAR_URL,
        "religious": True,
    },
    {
        "key": "kurban_bayrami",
        "labels": {"tr": "Kurban Bayramı", "en": "Eid al-Adha", "ar": "عيد الأضحى"},
        "aliases": ("kurban bayrami", "kurban bayramı", "eid al-adha", "eid ul adha"),
        "builder": lambda year: _religious_day_date("kurban_bayrami", year),
        "source_title": "Diyanet Dini Günler Takvimi",
        "source_url": DIYANET_RELIGIOUS_CALENDAR_URL,
        "religious": True,
        "duration_days": 4,
    },
    {
        "key": "hicri_yilbasi",
        "labels": {"tr": "Hicri Yılbaşı", "en": "Islamic New Year", "ar": "رأس السنة الهجرية"},
        "aliases": ("hicri yilbasi", "hicri yılbaşı", "islamic new year", "hijri new year"),
        "builder": lambda year: _religious_day_date("hicri_yilbasi", year),
        "source_title": "Diyanet Dini Günler Takvimi",
        "source_url": DIYANET_RELIGIOUS_CALENDAR_URL,
        "religious": True,
    },
    {
        "key": "asure_gunu",
        "labels": {"tr": "Aşure Günü", "en": "Ashura", "ar": "يوم عاشوراء"},
        "aliases": ("asure gunu", "aşure günü", "asure", "aşure", "ashura"),
        "builder": lambda year: _religious_day_date("asure_gunu", year),
        "source_title": "Diyanet Dini Günler Takvimi",
        "source_url": DIYANET_RELIGIOUS_CALENDAR_URL,
        "religious": True,
    },
    {
        "key": "mevlid_kandili",
        "labels": {"tr": "Mevlid Kandili", "en": "Mawlid al-Nabi", "ar": "ليلة المولد النبوي"},
        "aliases": ("mevlid kandili", "mevlit kandili", "mawlid", "mawlid al nabi"),
        "builder": lambda year: _religious_day_date("mevlid_kandili", year),
        "source_title": "Diyanet Dini Günler Takvimi",
        "source_url": DIYANET_RELIGIOUS_CALENDAR_URL,
        "religious": True,
    },
)
SPECIAL_DAY_DEFINITIONS = SPECIAL_DAY_DEFINITIONS + RELIGIOUS_SPECIAL_DAY_DEFINITIONS
MATH_BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}


@dataclass(frozen=True)
class ComposedAnswer:
    text: str
    sources: list[SearchResult]


def _response_language(query: str, preferred_language: str | None = None) -> str:
    preferred = clean_text(preferred_language or "").lower()
    if preferred in {"tr", "en", "ar"}:
        return preferred
    if is_arabic_query(query):
        return "ar"
    return "en" if is_english_query(query) else "tr"


def _text_for_language(language: str, tr_text: str, en_text: str, ar_text: str | None = None) -> str:
    if language == "ar":
        return ar_text or en_text
    return en_text if language == "en" else tr_text


def _welcome_message(language: str, user_memory: dict[str, object] | None = None) -> str:
    return _text_for_language(
        language,
        WELCOME_MESSAGE,
        "👋 Hello, I am KAUCAN Beta - the Digital Assistant of Kafkas University. I can help with IIBF announcements, academic information, staff, contact, exams, cafeteria menu, writing, coding, and many other topics.",
        "👋 مرحبًا، أنا KAÜCAN Beta، المساعد الرقمي لجامعة قفقاس. يمكنني المساعدة في إعلانات الكلية والمعلومات الأكاديمية والكوادر والاتصال والامتحانات وقائمة الطعام والكتابة والبرمجة وغيرها.",
    )


class WebsiteGroundedAssistant:
    def __init__(
        self,
        index: SearchIndex | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or Settings()
        self.index = index or SearchIndex.load(INDEX_PATH)

    def answer(
        self,
        query: str,
        client_id: str | None = None,
        preferred_language: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
    ) -> str:
        return self.answer_with_context(
            query,
            client_id=client_id,
            preferred_language=preferred_language,
            latitude=latitude,
            longitude=longitude,
        ).answer

    def answer_with_context(
        self,
        query: str,
        client_id: str | None = None,
        preferred_language: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
    ) -> AssistantResponse:
        original_query = clean_text(query)
        normalized_query = normalize_query(original_query) or original_query
        general_query = original_query or normalized_query
        language = _response_language(general_query, preferred_language)
        client_key = clean_text(client_id or "")
        if client_key:
            touch_user(client_key)
        memory_update = learn_from_user_message(client_key, original_query) if client_key else None
        user_memory = get_user_memory(client_key) if client_key else {}

        if has_inappropriate_language(normalized_query):
            return AssistantResponse(
                answer=_text_for_language(
                    language,
                    POLITE_LANGUAGE_RESPONSE,
                    "⚠️ Please use academic and appropriate language. I would be glad to assist.",
                    "⚠️ يُرجى استخدام لغة أكاديمية ومناسبة. يسعدني مساعدتك.",
                ),
                status="blocked_language",
            )

        if has_harmful_intent(normalized_query):
            return AssistantResponse(
                answer=_text_for_language(
                    language,
                    "Bu talebe yardımcı olamam.",
                    "I cannot help with that request.",
                    "لا يمكنني المساعدة في هذا الطلب.",
                ),
                status="blocked_safety",
            )

        memory_recall_response = _memory_recall_shortcut(original_query or normalized_query, language, user_memory, client_key)
        if memory_recall_response is not None:
            interaction = log_interaction(
                original_query or normalized_query,
                memory_recall_response.text,
                memory_recall_response.sources,
                "memory_recall",
            )
            return AssistantResponse(
                answer=memory_recall_response.text,
                sources=memory_recall_response.sources,
                interaction_id=interaction.id,
                status="memory_recall",
            )

        if memory_update and memory_update.saved and memory_update.memory_only:
            memory_saved_response = _memory_saved_shortcut(memory_update, language, user_memory)
            interaction = log_interaction(
                original_query or normalized_query,
                memory_saved_response.text,
                [],
                "memory_saved",
            )
            return AssistantResponse(
                answer=memory_saved_response.text,
                interaction_id=interaction.id,
                status="memory_saved",
            )

        if is_greeting_query(normalized_query):
            answer = _welcome_message(language, user_memory)
            interaction = log_interaction(original_query or normalized_query, answer, [], "greeting")
            return AssistantResponse(
                answer=answer,
                interaction_id=interaction.id,
                status="greeting",
            )

        management_response = _management_shortcut(normalized_query, language)
        if management_response is not None:
            interaction = log_interaction(
                original_query or normalized_query,
                management_response.text,
                management_response.sources,
                "direct_link",
            )
            return AssistantResponse(
                answer=management_response.text,
                sources=management_response.sources,
                interaction_id=interaction.id,
                status="direct_link",
            )

        faculty_contact_response = _faculty_contact_shortcut(normalized_query, language)
        if faculty_contact_response is not None:
            interaction = log_interaction(
                original_query or normalized_query,
                faculty_contact_response.text,
                faculty_contact_response.sources,
                "direct_link",
            )
            return AssistantResponse(
                answer=faculty_contact_response.text,
                sources=faculty_contact_response.sources,
                interaction_id=interaction.id,
                status="direct_link",
            )

        classroom_response = _classroom_location_shortcut(original_query or normalized_query, language)
        if classroom_response is not None:
            interaction = log_interaction(
                original_query or normalized_query,
                classroom_response.text,
                classroom_response.sources,
                "direct_answer",
            )
            return AssistantResponse(
                answer=classroom_response.text,
                sources=classroom_response.sources,
                interaction_id=interaction.id,
                status="direct_answer",
            )

        location_response = _location_shortcut(normalized_query, language)
        if location_response is not None:
            interaction = log_interaction(
                original_query or normalized_query,
                location_response.text,
                location_response.sources,
                "direct_link",
            )
            return AssistantResponse(
                answer=location_response.text,
                sources=location_response.sources,
                interaction_id=interaction.id,
                status="direct_link",
            )

        datetime_response = _datetime_shortcut(original_query or normalized_query, language)
        if datetime_response is not None:
            interaction = log_interaction(
                original_query or normalized_query,
                datetime_response.text,
                datetime_response.sources,
                "general",
            )
            return AssistantResponse(
                answer=datetime_response.text,
                sources=datetime_response.sources,
                interaction_id=interaction.id,
                status="general",
            )

        direct_link_response = _match_direct_service_link(normalized_query, language)
        if direct_link_response is not None:
            interaction = log_interaction(
                original_query or normalized_query,
                direct_link_response.text,
                direct_link_response.sources,
                "direct_link",
            )
            return AssistantResponse(
                answer=direct_link_response.text,
                sources=direct_link_response.sources,
                interaction_id=interaction.id,
                status="direct_link",
            )

        official_response = _official_data_shortcut(general_query, language)
        if official_response is not None:
            interaction = log_interaction(
                original_query or normalized_query,
                official_response.text,
                official_response.sources,
                "official",
            )
            return AssistantResponse(
                answer=official_response.text,
                sources=official_response.sources,
                interaction_id=interaction.id,
                status="official",
            )

        custom_memory_response = _custom_memory_fact_shortcut(original_query or normalized_query, language, user_memory, client_key)
        if custom_memory_response is not None:
            interaction = log_interaction(
                original_query or normalized_query,
                custom_memory_response.text,
                [],
                "memory_fact",
            )
            return AssistantResponse(
                answer=custom_memory_response.text,
                interaction_id=interaction.id,
                status="memory_fact",
            )

        composition_response = _composition_shortcut(general_query, language)
        if composition_response is not None:
            interaction = log_interaction(
                original_query or normalized_query,
                composition_response.text,
                composition_response.sources,
                "general",
            )
            return AssistantResponse(
                answer=composition_response.text,
                sources=composition_response.sources,
                interaction_id=interaction.id,
                status="general",
            )

        live_support = build_live_support(
            general_query,
            language,
            latitude=latitude,
            longitude=longitude,
        )
        if live_support is not None and live_support.prefer_direct:
            interaction = log_interaction(
                original_query or normalized_query,
                live_support.answer,
                _build_link_sources(live_support.sources),
                "general",
            )
            return AssistantResponse(
                answer=live_support.answer,
                sources=_build_link_sources(live_support.sources),
                interaction_id=interaction.id,
                status="general",
            )

        if is_smalltalk_query(normalized_query):
            answer = _smalltalk_response(normalized_query, language, user_memory)
            interaction = log_interaction(
                original_query or normalized_query,
                answer,
                _general_support_sources(original_query or normalized_query, language, include_google=False),
                "smalltalk",
            )
            return AssistantResponse(
                answer=answer,
                sources=_general_support_sources(original_query or normalized_query, language, include_google=False),
                interaction_id=interaction.id,
                status="smalltalk",
            )

        math_answer = _solve_basic_math(general_query, language)
        if math_answer:
            general_sources = _general_support_sources(original_query or normalized_query, language)
            interaction = log_interaction(original_query or normalized_query, math_answer, general_sources, "general")
            return AssistantResponse(
                answer=math_answer,
                sources=general_sources,
                interaction_id=interaction.id,
                status="general",
            )

        if _should_answer_with_general_knowledge(general_query) or live_support is not None:
            general_answer = self._generate_general_with_llm(
                general_query,
                user_memory,
                preferred_language=language,
                support_context=live_support.context if live_support is not None else "",
            )
            if general_answer:
                answer = _sanitize_answer_text(general_answer)
                if answer:
                    general_sources = _merge_source_results(
                        _build_link_sources(live_support.sources) if live_support is not None else [],
                        _general_support_sources(original_query or normalized_query, language),
                    )
                    interaction = log_interaction(original_query or normalized_query, answer, general_sources, "general")
                    return AssistantResponse(
                        answer=answer,
                        sources=general_sources,
                        interaction_id=interaction.id,
                        status="general",
                    )

        if live_support is not None and live_support.answer:
            live_sources = _merge_source_results(
                _build_link_sources(live_support.sources),
                _general_support_sources(original_query or normalized_query, language, include_google=False),
            )
            interaction = log_interaction(original_query or normalized_query, live_support.answer, live_sources, "general")
            return AssistantResponse(
                answer=live_support.answer,
                sources=live_sources,
                interaction_id=interaction.id,
                status="general",
            )

        if _should_answer_with_general_knowledge(general_query) or _looks_like_code_request(general_query):
            answer = _unknown_answer_text(language)
            interaction = log_interaction(original_query or normalized_query, answer, [], "fallback")
            return AssistantResponse(
                answer=answer,
                interaction_id=interaction.id,
                status="fallback",
            )

        if is_ambiguous(normalized_query) and not looks_actionable(normalized_query):
            answer = _text_for_language(
                language,
                "📌 Sorunun daha doğru yanıtlanabilmesi için konu başlığının biraz daha netleştirilmesi rica olunur. Bölüm, duyuru, akademik personel, iletişim, sınav, akademik takvim veya yemek menüsü gibi bir başlık belirtilebilir.",
                "📌 Please make the topic a little more specific so that I can answer more accurately. You may mention a department, announcement, academic staff, contact, exam, academic calendar, or cafeteria menu.",
                "📌 يُرجى توضيح الموضوع قليلًا حتى أتمكن من الإجابة بدقة أكبر. يمكن ذكر قسم أو إعلان أو كادر أكاديمي أو تواصل أو امتحان أو تقويم أكاديمي أو قائمة طعام.",
            )
            interaction = log_interaction(original_query or normalized_query, answer, [], "ambiguous")
            return AssistantResponse(answer=answer, interaction_id=interaction.id, status="ambiguous")

        candidate_count = max(self.settings.top_k * 4, 12)
        search_query = _build_search_query(normalized_query)
        if self.settings.use_learning_expansion:
            search_query = expand_query(search_query)

        results = self.index.search(search_query, top_k=candidate_count)
        log_query(original_query or normalized_query, results)

        reliable_results = [
            result
            for result in results
            if result.score >= MIN_RELIABLE_SCORE and _passes_context_requirements(normalized_query, result)
        ]
        reliable_results.sort(
            key=lambda result: (_context_priority(normalized_query, result), result.score),
            reverse=True,
        )

        if not reliable_results:
            fallback_text = _fallback_text_for_query(general_query, language)
            interaction = log_interaction(original_query or normalized_query, fallback_text, [], "fallback")
            return AssistantResponse(
                answer=fallback_text,
                interaction_id=interaction.id,
                status="fallback",
            )

        top_results = _dedupe_results_by_url(reliable_results)[: self.settings.top_k]

        if _prefer_local_answer(normalized_query):
            local_answer = _build_local_answer(normalized_query, top_results, language)
            interaction = log_interaction(
                original_query or normalized_query,
                local_answer.text,
                local_answer.sources,
                "local",
            )
            return AssistantResponse(
                answer=local_answer.text,
                sources=local_answer.sources,
                interaction_id=interaction.id,
                status="local",
            )

        llm_answer = self._generate_with_llm(normalized_query, top_results)
        if llm_answer:
            answer = _sanitize_answer_text(llm_answer)
            if answer:
                interaction = log_interaction(original_query or normalized_query, answer, top_results, "llm")
                return AssistantResponse(
                    answer=answer,
                    sources=top_results,
                    interaction_id=interaction.id,
                    status="llm",
                )

        local_answer = _build_local_answer(normalized_query, top_results, language)
        interaction = log_interaction(
            original_query or normalized_query,
            local_answer.text,
            local_answer.sources,
            "local",
        )
        return AssistantResponse(
            answer=local_answer.text,
            sources=local_answer.sources,
            interaction_id=interaction.id,
            status="local",
        )

    def _generate_with_llm(self, query: str, results: list[SearchResult]) -> str | None:
        for generator in _grounded_generators_for_settings(self.settings):
            if not generator.is_configured:
                continue
            try:
                answer = generator.generate(query, results)
            except Exception:
                continue
            if answer:
                return answer
        return None

    def _generate_general_with_llm(
        self,
        query: str,
        user_memory: dict[str, object] | None = None,
        preferred_language: str | None = None,
        support_context: str = "",
    ) -> str | None:
        memory_context = _general_memory_context(user_memory or {}, _response_language(query, preferred_language))
        for generator in _general_generators_for_settings(self.settings):
            if not generator.is_configured:
                continue
            try:
                answer = generator.generate_general(query, memory_context=memory_context, support_context=support_context)
            except Exception:
                continue
            if answer:
                return answer
        return None


def _build_local_answer(query: str, results: list[SearchResult], language: str) -> ComposedAnswer:
    if _is_department_query(query):
        answer = _format_department_answer(results, language)
        if answer:
            return answer
    if _is_contact_query(query):
        answer = _format_contact_answer(results, language)
        if answer:
            return answer
    if _is_personnel_query(query):
        return _format_personnel_answer(query, results, language)
    if _is_announcement_query(query):
        answer = _format_announcement_answer(results, language)
        if answer:
            return answer
    if _is_exam_query(query):
        answer = _format_exam_answer(results, language)
        if answer:
            return answer
    if _is_academic_calendar_query(query):
        answer = _format_academic_calendar_answer(results, language)
        if answer:
            return answer
    return _format_general_answer(query, results, language)


def _format_department_answer(results: list[SearchResult], language: str) -> ComposedAnswer | None:
    entries: list[tuple[str, str]] = []
    for result in results:
        for label, url in _extract_link_pairs(result.chunk.text):
            normalized_label = normalize_for_matching(label)
            if "bolum" in normalized_label or any(
                term in normalized_label for term in map(normalize_for_matching, DEPARTMENT_TERMS)
            ):
                if (label, url) not in entries:
                    entries.append((label, url))

    if not entries:
        return None

    bullets = "\n".join(f"• {label}" for label, _ in entries[:8])
    return ComposedAnswer(
        text=_text_for_language(
            language,
            "📌 İİBF bünyesinde erişilebilen bölüm bağlantıları aşağıdadır:\n" + bullets,
            "📌 The department links available under IIBF are listed below:\n" + bullets,
        ),
        sources=_build_link_sources(entries),
    )


def _format_contact_answer(results: list[SearchResult], language: str) -> ComposedAnswer | None:
    entries: list[tuple[str, str]] = []
    for result in results:
        for label, url in _extract_link_pairs(result.chunk.text):
            normalized_label = normalize_for_matching(label)
            if any(term in normalized_label for term in ("telefon", "rehber", "dekana sor", "iletisim")):
                if (label, url) not in entries:
                    entries.append((label, url))

    if entries:
        unique_labels: list[str] = []
        observed: set[str] = set()
        unique_entries: list[tuple[str, str]] = []
        for label, _ in entries:
            normalized_label = normalize_for_matching(label)
            if normalized_label in observed:
                continue
            unique_labels.append(label)
            observed.add(normalized_label)
        observed.clear()
        for label, url in entries:
            normalized_label = normalize_for_matching(label)
            if normalized_label in observed:
                continue
            unique_entries.append((label, url))
            observed.add(normalized_label)

        bullets = "\n".join(f"• {label}" for label in unique_labels[:4])
        return ComposedAnswer(
            text=_text_for_language(
                language,
                "📞 İletişim için fakülte sayfasında öne çıkan başlıklar aşağıdadır:\n" + bullets,
                "📞 The highlighted contact links on the faculty page are listed below:\n" + bullets,
            ),
            sources=_build_link_sources(unique_entries),
        )

    first_source = _dedupe_results_by_url(results)[:2]
    if not first_source:
        return None

    return ComposedAnswer(
        text=_text_for_language(
            language,
            "📞 İletişim bilgileri ilgili fakülte sayfalarında yayımlanmaktadır. Güncel telefon, e-posta ve rehber bağlantıları kaynak kısmından incelenebilir.",
            "📞 Contact information is published on the related faculty pages. Current phone, email, and directory links can be reviewed from the source section.",
        ),
        sources=first_source,
    )


def _format_personnel_answer(query: str, results: list[SearchResult], language: str) -> ComposedAnswer:
    source = _dedupe_results_by_url(results)[:1]
    profile_label = _text_for_language(
        language,
        "akademik personel" if "akademik" in _query_key(query) else "personel",
        "academic staff" if "akademik" in _query_key(query) else "staff",
    )
    display_title = _display_title(source[0], language) if source else _text_for_language(language, "ilgili personel sayfası", "the related staff page")
    return ComposedAnswer(
        text=_text_for_language(
            language,
            f"👤 {profile_label.capitalize()} bilgileri fakültenin \"{display_title}\" sayfasında yayımlanmaktadır. Güncel isim ve iletişim bilgileri kaynak bağlantısından incelenebilir.",
            f"👤 {profile_label.capitalize()} information is published on the faculty page titled \"{display_title}\". Current names and contact details can be reviewed from the source link.",
        ),
        sources=source,
    )


def _format_announcement_answer(results: list[SearchResult], language: str) -> ComposedAnswer | None:
    candidates = [
        result
        for result in _dedupe_results_by_url(results)
        if "/duyuru2/" in result.chunk.url.lower()
        or any(term in normalize_for_matching(result.chunk.title) for term in ("duyuru", "haber", "etkinlik"))
    ]
    rows = [_build_titled_row(result, language) for result in candidates]
    rows = [row for row in rows if row][:MAX_SUMMARY_ITEMS]
    if not rows:
        return None
    return ComposedAnswer(
        text=_text_for_language(
            language,
            "📢 Web sitesindeki ilgili kayıtlara göre öne çıkan duyurular:\n" + "\n".join(rows),
            "📢 According to the related records on the website, the highlighted announcements are:\n" + "\n".join(rows),
        ),
        sources=candidates[:MAX_SUMMARY_ITEMS],
    )


def _format_exam_answer(results: list[SearchResult], language: str) -> ComposedAnswer | None:
    candidates = [
        result
        for result in _dedupe_results_by_url(results)
        if "/duyuru2/" in result.chunk.url.lower() or _is_exam_related(result)
    ]
    rows = [_build_titled_row(result, language) for result in candidates]
    rows = [row for row in rows if row][:MAX_SUMMARY_ITEMS]
    if not rows:
        return None
    return ComposedAnswer(
        text=_text_for_language(
            language,
            "📅 İlgili sınav kayıtlarında öne çıkan başlıklar:\n" + "\n".join(rows),
            "📅 The highlighted titles in the related exam records are:\n" + "\n".join(rows),
        ),
        sources=candidates[:MAX_SUMMARY_ITEMS],
    )


def _format_academic_calendar_answer(results: list[SearchResult], language: str) -> ComposedAnswer | None:
    rows = [_build_titled_row(result, language) for result in _dedupe_results_by_url(results)]
    rows = [row for row in rows if row][:MAX_SUMMARY_ITEMS]
    if not rows:
        return None
    return ComposedAnswer(
        text=_text_for_language(
            language,
            "📅 Akademik takvimle ilişkili erişilebilen kayıtlar:\n" + "\n".join(rows),
            "📅 The accessible records related to the academic calendar are:\n" + "\n".join(rows),
        ),
        sources=_dedupe_results_by_url(results)[:MAX_SUMMARY_ITEMS],
    )


def _format_general_answer(query: str, results: list[SearchResult], language: str) -> ComposedAnswer:
    lines = [_build_summary_line(result, language) for result in _dedupe_results_by_url(results)]
    lines = [line for line in lines if line][:MAX_SUMMARY_ITEMS]
    if not lines:
        lines = [_text_for_language(language, "• İlgili bilgi kaynak bağlantılarında yer almaktadır.", "• The related information is available in the source links.")]
    return ComposedAnswer(
        text=_text_for_language(
            language,
            f"{_response_emoji(query)} İlgili web içeriklerine göre öne çıkan bilgiler:\n" + "\n".join(lines),
            f"{_response_emoji(query)} According to the related web content, the key points are:\n" + "\n".join(lines),
        ),
        sources=_dedupe_results_by_url(results)[:MAX_SUMMARY_ITEMS],
    )


def _build_summary_line(result: SearchResult, language: str) -> str:
    title = _display_title(result, language)
    summary = _extract_summary_sentence(result.chunk.text, title)
    if summary:
        return f"• {title}: {summary}"
    return f"• {title}"


def _build_titled_row(result: SearchResult, language: str = "tr") -> str:
    title = _display_title(result, language)
    date = _extract_date(result.chunk.text)
    summary = _extract_summary_sentence(result.chunk.text, title, max_chars=130)

    if date and summary:
        return f"• {title} - {date}: {summary}"
    if date:
        return f"• {title} - {date}"
    if summary:
        return f"• {title}: {summary}"
    return f"• {title}"


def _extract_summary_sentence(text: str, title: str, max_chars: int = 180) -> str:
    cleaned = _strip_noise(text)
    if cleaned.lower().startswith(title.lower()):
        cleaned = cleaned[len(title) :].strip(" .:-")
    sentences = [
        clean_text(part)
        for part in re.split(r"(?<=[.!?])\s+|\n+", cleaned)
        if clean_text(part)
    ]
    for sentence in sentences:
        normalized = normalize_for_matching(sentence)
        if len(sentence) < 20:
            continue
        if any(term in normalized for term in ("baglanti", "url", "kaynak", "metadata", "chunk")):
            continue
        if sentence.lower() == title.lower():
            continue
        return _truncate(sentence, max_chars)
    return ""


def _strip_noise(text: str) -> str:
    cleaned = text.replace("\u200b", " ")
    cleaned = LINK_PATTERN.sub(" ", cleaned)
    for pattern in NOISE_PATTERNS:
        cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"https?://\S+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _extract_date(text: str) -> str:
    match = DATE_PATTERN.search(text)
    if not match:
        return ""
    return clean_text(match.group(0))


def _build_link_sources(entries: list[tuple[str, str]]) -> list[SearchResult]:
    sources: list[SearchResult] = []
    for index, (label, url) in enumerate(entries[:8], start=1):
        sources.append(
            SearchResult(
                chunk=Chunk(
                    id=stable_id(label, url),
                    url=url,
                    title=label,
                    text=label,
                    ordinal=index,
                    metadata={"derived": True},
                ),
                score=max(0.1, 1 - (index * 0.05)),
            )
        )
    return sources


def _general_support_sources(query: str, language: str, include_google: bool = True) -> list[SearchResult]:
    normalized = _query_key(query)
    entries: list[tuple[str, str]] = []

    if any(term in normalized for term in ("hava", "weather", "forecast", "sicaklik", "sıcaklık", "طقس", "الطقس")):
        entries.append(("wttr.in Weather", f"https://wttr.in/{quote_plus(query)}?format=j1"))

    if any(term in normalized for term in ("makale", "article", "paper", "research", "tez", "thesis", "بحث", "مقال", "اطروحة")):
        entries.append(("Crossref Works", f"https://api.crossref.org/works?query.bibliographic={quote_plus(query)}"))
        entries.append(("YÖK Ulusal Tez Merkezi", "https://tez.yok.gov.tr/UlusalTezMerkezi/"))

    if is_coding_query(query):
        if "python" in normalized:
            entries.append(("Python Docs", "https://docs.python.org/3/"))
        if any(term in normalized for term in ("javascript", "js", "html", "css")):
            entries.append(("MDN Web Docs", "https://developer.mozilla.org/"))
        if "react" in normalized:
            entries.append(("React Docs", "https://react.dev/"))
        if "fastapi" in normalized:
            entries.append(("FastAPI Docs", "https://fastapi.tiangolo.com/"))
        if "flask" in normalized:
            entries.append(("Flask Docs", "https://flask.palletsprojects.com/"))
        if not entries:
            entries.append(("Stack Overflow", "https://stackoverflow.com/"))

    if include_google:
        entries.append(
            (
                _text_for_language(language, "Google'da Ara", "Search on Google", "ابحث في Google"),
                f"https://www.google.com/search?q={quote_plus(query)}",
            )
        )

    deduped: list[tuple[str, str]] = []
    seen_urls: set[str] = set()
    for title, url in entries:
        if url in seen_urls:
            continue
        deduped.append((title, url))
        seen_urls.add(url)
    return _build_link_sources(deduped[:3])


def _match_direct_service_link(query: str, language: str) -> ComposedAnswer | None:
    normalized = _query_key(query)
    for item in DIRECT_SERVICE_LINKS:
        if any(normalize_for_matching(term) in normalized for term in item["terms"]):
            return ComposedAnswer(
                text=_text_for_language(language, item["message_tr"], item["message_en"], item.get("message_ar")),
                sources=_build_link_sources([(item["title"], item["url"])]),
            )
    return None


def _management_shortcut(query: str, language: str) -> ComposedAnswer | None:
    normalized = _query_key(query)
    if not normalized:
        return None

    if "rektor yardimci" in normalized or "vice rector" in normalized or (
        any(term in normalized for term in ("rektor", "rector"))
        and any(term in normalized for term in ("yardimci", "yardimcilari", "vice"))
    ):
        names = _fetch_rector_assistant_names()
        if names:
            joined_names = ", ".join(names[:3])
            text = _text_for_language(
                language,
                f"👤 Güncel rektör yardımcıları resmi sayfada {joined_names} olarak yayımlanmaktadır.",
                f"👤 The current vice rectors are listed on the official page as {joined_names}.",
            )
        else:
            text = _text_for_language(
                language,
                "👤 Güncel rektör yardımcıları bilgisi resmi sayfada yayımlanmaktadır.",
                "👤 Current vice rector information is published on the official page.",
            )
        return ComposedAnswer(
            text=text,
            sources=_build_link_sources([RECTOR_ASSISTANTS_PAGE]),
        )

    if any(term in normalized for term in ("senato", "dekanlik", "dekanliklar", "dekanlar", "senate", "deans")):
        return ComposedAnswer(
            text=_text_for_language(
                language,
                "👤 Üniversite senatosu ve dekanlık bilgileri resmi yönetim sayfasında yayımlanmaktadır.",
                "👤 Senate and dean's office information is published on the official management page.",
            ),
            sources=_build_link_sources([SENATE_PAGE]),
        )

    if "rektor" in normalized or "rector" in normalized:
        rector_name = _fetch_rector_name()
        if rector_name:
            text = _text_for_language(
                language,
                f"👤 Kafkas Üniversitesi Rektörü resmi sayfada {rector_name} olarak yayımlanmaktadır.",
                f"👤 The official page lists the Rector of Kafkas University as {rector_name}.",
            )
        else:
            text = _text_for_language(
                language,
                "👤 Güncel rektör bilgisi resmi rektörlük sayfasında yayımlanmaktadır.",
                "👤 Current rector information is published on the official rectorate page.",
            )
        return ComposedAnswer(
            text=text,
            sources=_build_link_sources([RECTOR_PAGE]),
        )

    return None


def _faculty_contact_shortcut(query: str, language: str) -> ComposedAnswer | None:
    normalized = _query_key(query)
    if not _is_contact_query(query):
        return None
    if not (
        _is_faculty_query(query)
        or "faculty" in normalized
        or "college" in normalized
        or "كلية" in normalized
    ):
        return None

    return ComposedAnswer(
        text=_text_for_language(
            language,
            "📞 İİBF iletişim bilgileri:\n"
            "• E-posta: iibf@kafkas.edu.tr\n"
            "• Telefon: 0474 225 12 50\n"
            "• Fax: 0474 225 12 57\n"
            "• Dekanımıza Ulaşmak İçin: dozyakisir@gmail.com",
            "📞 IIBF contact information:\n"
            "• Email: iibf@kafkas.edu.tr\n"
            "• Phone: 0474 225 12 50\n"
            "• Fax: 0474 225 12 57\n"
            "• To Reach the Dean: dozyakisir@gmail.com",
            "📞 معلومات التواصل لكلية الاقتصاد والعلوم الإدارية:\n"
            "• البريد الإلكتروني: iibf@kafkas.edu.tr\n"
            "• الهاتف: 0474 225 12 50\n"
            "• الفاكس: 0474 225 12 57\n"
            "• للتواصل مع العميد: dozyakisir@gmail.com",
        ),
        sources=_build_link_sources(
            [
                ("İİBF İletişim Sayfası", FACULTY_CONTACT_PAGE),
                ("Telefon: 0474 225 12 50", "tel:+904742251250"),
                ("E-posta: iibf@kafkas.edu.tr", "mailto:iibf@kafkas.edu.tr"),
                ("Dekana Ulaşın: dozyakisir@gmail.com", "mailto:dozyakisir@gmail.com"),
                ("Telefon Rehberi", "https://www.kafkas.edu.tr/kau/rehber2"),
            ]
        ),
    )


def _location_shortcut(query: str, language: str) -> ComposedAnswer | None:
    normalized = _query_key(query)
    if not normalized:
        return None
    if not _is_location_query(query):
        return None

    destination = _extract_route_destination(query)
    if destination:
        maps_url = f"https://www.google.com/maps/dir/?api=1&destination={quote_plus(destination)}"
        return ComposedAnswer(
            text=_text_for_language(
                language,
                f"📌 {destination} için yol tarifi aşağıdaki harita bağlantısından açılabilir.",
                f"📌 Directions to {destination} can be opened from the map link below.",
                f"📌 يمكن فتح الاتجاهات إلى {destination} من رابط الخريطة التالي.",
            ),
            sources=_build_link_sources([("Yol Tarifi", maps_url)]),
        )

    if not (
        _query_targets_iibf(query)
        or "kafkas universitesi" in normalized
        or "kau" in normalized
        or "universite" in normalized
        or "university" in normalized
    ):
        return ComposedAnswer(
            text=_text_for_language(
                language,
                "📌 Yol tarifi oluşturabilmem için gidilmek istenen konum biraz daha açık yazılmalıdır. Örnek: Kafkas Üniversitesi İİBF'ye nasıl giderim?",
                "📌 Please specify the destination more clearly so I can provide directions. Example: How do I get to Kafkas University FEAS?",
                "📌 يُرجى تحديد الوجهة بشكل أوضح حتى أتمكن من مشاركة الاتجاهات. مثال: كيف أصل إلى كلية الاقتصاد والعلوم الإدارية في جامعة قفقاس؟",
            ),
            sources=[],
        )

    return ComposedAnswer(
        text=_text_for_language(
            language,
            "📌 Konum bilgisi için aşağıdaki harita bağlantısı kullanılabilir. Bağlantı Maps uygulamasında açılabilir.",
            "📌 The map link below can be used for location information. It can be opened directly in the Maps application.",
            "📌 يمكن استخدام رابط الخريطة التالي لمعرفة الموقع، ويمكن فتحه مباشرة في تطبيق الخرائط.",
        ),
        sources=_build_link_sources([MAPS_LINK]),
    )


def _classroom_location_shortcut(query: str, language: str) -> ComposedAnswer | None:
    normalized = _query_key(query)
    if not normalized:
        return None
    if not _is_classroom_context_query(normalized):
        return None

    for entry in NAMED_CLASSROOM_LOCATIONS:
        if any(_query_key(term) in normalized for term in entry["terms"]):
            return ComposedAnswer(
                text=_text_for_language(language, entry["tr"], entry["en"], entry["ar"]),
                sources=[],
            )

    codes = set(re.findall(r"\b(?:101|102|103|104|105|106|107|108|201|202|203|204|205|206|207|208|301)\b", normalized))
    for entry in CLASSROOM_LOCATION_GROUPS:
        if codes.intersection(entry["codes"]):
            return ComposedAnswer(
                text=_text_for_language(language, entry["tr"], entry["en"], entry["ar"]),
                sources=[],
            )

    if re.search(r"\b[123]\d{2}\b", normalized) or "konferans salonu" in normalized or "conference hall" in normalized:
        return ComposedAnswer(text=_unknown_answer_text(language), sources=[])

    return None


def _is_classroom_context_query(normalized_query: str) -> bool:
    return any(
        term in normalized_query
        for term in (
            "derslik",
            "sinif",
            "sınıf",
            "classroom",
            "classrooms",
            "konferans salonu",
            "conference hall",
            "salon",
            "nerede",
            "konum",
            "kat",
            "katta",
        )
    )


def _memory_saved_shortcut(memory_update, language: str, user_memory: dict[str, object]) -> ComposedAnswer:
    display_name = user_display_name(user_memory)
    saved_labels: list[str] = []
    profile_label_map = {
        "name": _text_for_language(language, "ad", "name"),
        "preferred_name": _text_for_language(language, "hitap adı", "preferred name"),
        "department": _text_for_language(language, "bölüm", "department"),
        "role": _text_for_language(language, "rol", "role"),
    }
    for key in ("name", "preferred_name", "department", "role"):
        value = clean_text(memory_update.profile_updates.get(key, ""))
        if value:
            saved_labels.append(f"{profile_label_map[key]}: {value}")

    saved_labels.extend(memory_update.facts[:2])
    summary = ", ".join(saved_labels[:3])

    if display_name:
        return ComposedAnswer(
            text=_text_for_language(
                language,
                f"✅ Tamam {display_name}, bu bilgi belleğe kaydedildi." + (f" {summary}" if summary else ""),
                f"✅ Alright {display_name}, I saved that to memory." + (f" {summary}" if summary else ""),
            ),
            sources=[],
        )

    return ComposedAnswer(
        text=_text_for_language(
            language,
            "✅ Paylaşılan bilgi belleğe kaydedildi." + (f" {summary}" if summary else ""),
            "✅ The shared information has been saved to memory." + (f" {summary}" if summary else ""),
        ),
        sources=[],
    )


def _memory_recall_shortcut(
    query: str,
    language: str,
    user_memory: dict[str, object],
    client_id: str,
) -> ComposedAnswer | None:
    if not client_id or not user_memory:
        return None

    normalized = _query_key(query)
    display_name = user_display_name(user_memory)
    department = user_department_name(user_memory, language)
    role = user_role_name(user_memory, language)
    summary = build_user_summary(user_memory, language)

    if any(term in normalized for term in ("adim ne", "ismim ne", "what is my name", "my name")):
        if not display_name:
            return _missing_memory_answer(language)
        return ComposedAnswer(
            text=_text_for_language(
                language,
                f"👤 Daha önce paylaşılan bilgiye göre adı {display_name} olarak kayıtlı.",
                f"👤 According to the saved information, the name is recorded as {display_name}.",
            ),
            sources=[],
        )

    if any(term in normalized for term in ("hangi bolumdeyim", "bolumum ne", "what do i study", "which department")):
        if not department:
            return _missing_memory_answer(language)
        return ComposedAnswer(
            text=_text_for_language(
                language,
                f"📌 Kayıtlı bilgiye göre {department} bölümünde {role or 'kişi'} olarak yer alıyor.",
                f"📌 According to the saved information, the user is recorded as a {role or 'member'} in {department}.",
            ),
            sources=[],
        )

    if any(term in normalized for term in ("bana nasil hitap", "beni nasil cagir", "what should you call me", "call me what")):
        if not display_name:
            return _missing_memory_answer(language)
        return ComposedAnswer(
            text=_text_for_language(
                language,
                f"😊 Kayıtlı bilgiye göre {display_name} diye hitap edilmesi uygun olur.",
                f"😊 According to the saved information, it would be appropriate to address the user as {display_name}.",
            ),
            sources=[],
        )

    if any(term in normalized for term in ("beni taniyor musun", "ben kimim", "do you know me", "who am i", "do you remember me")):
        if not summary:
            return _missing_memory_answer(language)
        return ComposedAnswer(
            text=_text_for_language(
                language,
                f"😊 Evet, bellekte şu bilgiler bulunuyor: {summary}.",
                f"😊 Yes, the following information is stored in memory: {summary}.",
            ),
            sources=[],
        )

    return None


def _custom_memory_fact_shortcut(
    query: str,
    language: str,
    user_memory: dict[str, object],
    client_id: str,
) -> ComposedAnswer | None:
    if not client_id:
        return None

    fact = find_relevant_user_fact(client_id, query)
    if not fact:
        return None

    fact_text = clean_text(fact.get("text", ""))
    if not fact_text:
        return None

    return ComposedAnswer(
        text=_text_for_language(
            language,
            f"📌 Daha önce paylaşılan bilgiye göre: {fact_text}",
            f"📌 Based on the previously shared information: {fact_text}",
        ),
        sources=[],
    )


def _general_memory_context(user_memory: dict[str, object], language: str) -> str:
    summary = build_user_summary(user_memory, language)
    if not summary:
        return ""
    return _text_for_language(
        language,
        f"Kullanıcı hakkında daha önce paylaşılan bilgiler: {summary}. Gerekmedikçe kullanıcıya adıyla hitap edilmemeli; bu bilgi yalnızca bağlam için kullanılmalı.",
        f"Previously shared information about the user: {summary}. Do not address the user by name unless explicitly requested; use this only as context.",
    )


def _missing_memory_answer(language: str) -> ComposedAnswer:
    return ComposedAnswer(
        text=_text_for_language(
            language,
            "⚠️ Bu konuda bellekte yeterli kişisel bilgi bulunmuyor. İstenirse ad, bölüm veya özel bilgi paylaşılabilir.",
            "⚠️ There is not enough personal information in memory yet. The user may share a name, department, or another detail.",
        ),
        sources=[],
    )


def _official_data_shortcut(query: str, language: str) -> ComposedAnswer | None:
    normalized = _query_key(query)
    if not normalized:
        return None

    if not _should_use_official_data(query):
        return None

    try:
        snapshot = get_official_snapshot()
    except Exception:
        return None

    if _is_dean_query(query):
        answer = _official_dean_answer(snapshot, query, language)
        if answer is not None:
            return answer

    if _other_faculty_requested(query):
        return None

    navigation_answer = _official_navigation_answer(snapshot, query, language)
    if navigation_answer is not None:
        return navigation_answer

    department_keys = department_keys_for_query(query)
    topic = _official_content_topic(query)

    if topic and not department_keys:
        snapshot = ensure_faculty_content(snapshot, (topic,))
        answer = _official_faculty_content_answer(snapshot, topic, language)
        if answer is not None:
            return answer

    if department_keys:
        department_key = department_keys[0]
        answer = _official_department_answer(snapshot, department_key, query, language, topic)
        if answer is not None:
            return answer

    if _is_faculty_department_heads_query(query):
        answer = _official_faculty_heads_answer(snapshot, language)
        if answer is not None:
            return answer

    if _is_faculty_staff_query(query):
        answer = _official_faculty_staff_answer(snapshot, query, language)
        if answer is not None:
            return answer

    if _is_short_faculty_staff_query(query):
        answer = _official_faculty_staff_answer(snapshot, f"iibf {query}", language)
        if answer is not None:
            return answer

    if _is_department_listing_query(query):
        answer = _official_department_listing_answer(snapshot, language)
        if answer is not None:
            return answer

    return None


def _official_dean_answer(snapshot: dict, query: str, language: str) -> ComposedAnswer | None:
    dean = _find_dean_for_query(snapshot, query)
    if not dean:
        return None

    dean_name = clean_text(dean.get("name", ""))
    designation = clean_text(dean.get("designation", ""))
    source_url = clean_text(dean.get("source_url", "")) or SENATE_PAGE[1]
    detail_url = clean_text(dean.get("detail_url", "")) or source_url

    if not dean_name:
        return None

    faculty_label = _faculty_label_from_designation(designation) or "İİBF"
    return ComposedAnswer(
        text=_text_for_language(
            language,
            f"👤 Resmi senato sayfasına göre {faculty_label} için dekan bilgisi {dean_name} olarak yer almaktadır. {designation}".strip(),
            f"👤 According to the official senate page, the dean information for {faculty_label} is listed as {dean_name}. {designation}".strip(),
            f"👤 وفقًا لصفحة مجلس الجامعة الرسمية، فإن معلومات العميد الخاصة بـ {faculty_label} منشورة باسم {dean_name}.",
        ),
        sources=_build_link_sources(
            [
                ("Senato ve Dekanlıklar", source_url),
                ("Dekan Profili", detail_url),
            ]
        ),
    )


def _official_faculty_content_answer(snapshot: dict, topic: str, language: str) -> ComposedAnswer | None:
    items = snapshot.get("faculty_content", {}).get(topic, [])
    if not items:
        label = _content_label(topic, language)
        return ComposedAnswer(
            text=_text_for_language(
                language,
                f"{_content_emoji(topic)} Güncel {label.lower()} için resmi fakülte sayfası kullanılabilir.",
                f"{_content_emoji(topic)} The official faculty page can be used for the latest {label.lower()}.",
            ),
            sources=_build_link_sources([(_content_label(topic, "tr"), _content_source_url(topic))]),
        )

    rows = [_official_item_row(item) for item in items[:3]]
    return ComposedAnswer(
        text=_text_for_language(
            language,
            f"{_content_emoji(topic)} İİBF için öne çıkan {_content_label(topic, 'tr').lower()}:\n" + "\n".join(rows),
            f"{_content_emoji(topic)} Highlighted {_content_label(topic, 'en').lower()} for FEAS:\n" + "\n".join(rows),
        ),
        sources=_official_item_sources(items[:3], fallback_title=_content_label(topic, "tr")),
    )


def _official_department_answer(
    snapshot: dict,
    department_key: str,
    query: str,
    language: str,
    topic: str | None,
) -> ComposedAnswer | None:
    department = snapshot.get("departments", {}).get(department_key)
    if not department:
        return None

    if topic:
        snapshot = ensure_department_content(snapshot, department_key, (topic,))
        department = snapshot.get("departments", {}).get(department_key, department)
        answer = _official_department_content_answer(department, topic, language)
        if answer is not None:
            return answer

    if _is_department_head_query(query):
        answer = _official_department_heads_answer(department, language)
        if answer is not None:
            return answer

    if _is_department_staff_query(query):
        answer = _official_department_staff_shortcut(department, query, language)
        if answer is not None:
            return answer

    if _is_department_info_query(query):
        answer = _official_department_info_answer(department, language)
        if answer is not None:
            return answer

    if normalize_for_matching(query) in {department_key, normalize_for_matching(department.get("name_tr", ""))}:
        return _official_department_info_answer(department, language)

    return None


def _official_faculty_heads_answer(snapshot: dict, language: str) -> ComposedAnswer | None:
    people = snapshot.get("faculty_personnel", [])
    department_heads = []
    for person in people:
        if any("bolum baskani" in normalize_for_matching(role) for role in person.get("roles", [])):
            department_heads.append(person)

    if not department_heads:
        return None

    rows = []
    for person in department_heads[:8]:
        department_name = clean_text(person.get("department", ""))
        person_name = _normalize_person_name(person.get("name", ""))
        rows.append(f"• {department_name}: {person_name}")

    return ComposedAnswer(
        text=_text_for_language(
            language,
            "👤 İİBF bölüm başkanları resmi akademik personel sayfasına göre şöyledir:\n" + "\n".join(rows),
            "👤 According to the official academic staff page, the department chairs of FEAS are:\n" + "\n".join(rows),
        ),
        sources=_build_link_sources([("İİBF Akademik Personel", "https://www.kafkas.edu.tr/iibf/tr/akademikpersonel")]),
    )


def _official_faculty_staff_answer(snapshot: dict, query: str, language: str) -> ComposedAnswer | None:
    people = snapshot.get("faculty_personnel", [])
    if not people:
        return None

    if _is_academic_staff_query(query):
        rows = [_person_line(person) for person in people[:6]]
        return ComposedAnswer(
            text=_text_for_language(
                language,
                "👤 İİBF akademik kadrosu resmi personel sayfasında yayımlanmaktadır. Öne çıkan isimler:\n" + "\n".join(rows),
                "👤 The FEAS academic staff is published on the official personnel page. Highlighted names:\n" + "\n".join(rows),
            ),
            sources=_build_link_sources([("İİBF Akademik Personel", "https://www.kafkas.edu.tr/iibf/tr/akademikpersonel")]),
        )

    administrative_people = [
        person
        for person in people
        if any(role in normalize_for_matching(" ".join(person.get("roles", []))) for role in ("dekan", "yardimci", "bolum baskani"))
    ]
    if not administrative_people:
        administrative_people = people[:6]

    rows = [_person_role_line(person) for person in administrative_people[:6]]
    return ComposedAnswer(
        text=_text_for_language(
            language,
            "👤 İİBF sayfasında görünen idari görevlerden bazıları şöyledir:\n" + "\n".join(rows),
            "👤 Some of the administrative roles shown on the FEAS page are:\n" + "\n".join(rows),
        ),
        sources=_build_link_sources([("İİBF Akademik Personel", "https://www.kafkas.edu.tr/iibf/tr/akademikpersonel")]),
    )


def _official_department_listing_answer(snapshot: dict, language: str) -> ComposedAnswer | None:
    ordered_keys = snapshot.get("department_order") or list(snapshot.get("departments", {}))
    rows = []
    sources = []
    for key in ordered_keys[:8]:
        department = snapshot.get("departments", {}).get(key, {})
        name_tr = department.get("name_tr")
        root_url = department.get("root_url")
        if not name_tr or not root_url:
            continue
        rows.append(f"• {name_tr}")
        sources.append((name_tr, root_url))

    if not rows:
        return None

    return ComposedAnswer(
        text=_text_for_language(
            language,
            "📌 İİBF bünyesindeki bölümler şöyledir:\n" + "\n".join(rows),
            "📌 The departments under FEAS are:\n" + "\n".join(rows),
        ),
        sources=_build_link_sources(sources[:4]),
    )


def _official_department_content_answer(department: dict, topic: str, language: str) -> ComposedAnswer | None:
    items = department.get(topic, [])
    label = _content_label(topic, language)
    department_name = department.get("name_tr", "Bölüm")
    page_url = department.get("important_links", {}).get(topic) or department.get("root_url", "")

    if not items:
        if not page_url:
            return None
        return ComposedAnswer(
            text=_text_for_language(
                language,
                f"{_content_emoji(topic)} {department_name} için güncel {label.lower()} resmi bölüm sayfasından takip edilebilir.",
                f"{_content_emoji(topic)} The latest {label.lower()} for {department_name} can be followed on the official department page.",
            ),
            sources=_build_link_sources([(f"{department_name} { _content_label(topic, 'tr') }", page_url)]),
        )

    rows = [_official_item_row(item) for item in items[:3]]
    return ComposedAnswer(
        text=_text_for_language(
            language,
            f"{_content_emoji(topic)} {department_name} için öne çıkan { _content_label(topic, 'tr').lower() }:\n" + "\n".join(rows),
            f"{_content_emoji(topic)} Highlighted { _content_label(topic, 'en').lower() } for {department_name}:\n" + "\n".join(rows),
        ),
        sources=_official_item_sources(items[:3], fallback_title=f"{department_name} {_content_label(topic, 'tr')}"),
    )


def _official_department_heads_answer(department: dict, language: str) -> ComposedAnswer | None:
    people = department.get("personnel", [])
    if not people:
        return None

    head = next(
        (
            person
            for person in people
            if any("bolum baskani" in normalize_for_matching(role) for role in person.get("roles", []))
        ),
        None,
    )
    assistants = [
        person
        for person in people
        if any("bolum baskan yardimcisi" in normalize_for_matching(role) for role in person.get("roles", []))
    ]

    if not head and not assistants:
        return None

    rows = []
    if head:
        rows.append(f"• Bölüm Başkanı: {_normalize_person_name(head.get('name', ''))}")
    for person in assistants[:3]:
        rows.append(f"• Başkan Yardımcısı: {_normalize_person_name(person.get('name', ''))}")

    department_name = department.get("name_tr", "Bölüm")
    return ComposedAnswer(
        text=_text_for_language(
            language,
            f"👤 {department_name} için resmi sayfada görünen yönetim bilgileri:\n" + "\n".join(rows),
            f"👤 The management information shown on the official page for {department_name} is:\n" + "\n".join(rows),
        ),
        sources=_build_link_sources([(f"{department_name} Akademik Personel", department.get("important_links", {}).get("academic_staff") or department.get("root_url", ""))]),
    )


def _official_department_staff_shortcut(department: dict, query: str, language: str) -> ComposedAnswer | None:
    people = department.get("personnel", [])
    if not people:
        return None

    if _is_administrative_roles_query(query):
        rows = [_person_role_line(person) for person in people if person.get("roles")]
        rows = rows[:6]
        if not rows:
            return None
        return ComposedAnswer(
            text=_text_for_language(
                language,
                f"👤 {department.get('name_tr', 'Bölüm')} için sayfada görünen idari görevler:\n" + "\n".join(rows),
                f"👤 Administrative roles shown for {department.get('name_tr', 'the department')} are:\n" + "\n".join(rows),
            ),
            sources=_build_link_sources([(f"{department.get('name_tr', 'Bölüm')} Akademik Personel", department.get("important_links", {}).get("academic_staff") or department.get("root_url", ""))]),
        )

    rows = [_person_line(person) for person in people[:8]]
    count = len(people)
    return ComposedAnswer(
        text=_text_for_language(
            language,
            f"👤 {department.get('name_tr', 'Bölüm')} akademik kadrosunda resmi sayfada {count} kişi listelenmektedir. Öne çıkan isimler:\n" + "\n".join(rows),
            f"👤 The official page lists {count} people in the academic staff of {department.get('name_tr', 'the department')}. Highlighted names:\n" + "\n".join(rows),
        ),
        sources=_build_link_sources([(f"{department.get('name_tr', 'Bölüm')} Akademik Personel", department.get("important_links", {}).get("academic_staff") or department.get("root_url", ""))]),
    )


def _official_department_info_answer(department: dict, language: str) -> ComposedAnswer | None:
    name_tr = department.get("name_tr", "")
    if not name_tr:
        return None

    links = department.get("important_links", {})
    source_pairs = [(name_tr, department.get("root_url", ""))]
    for key in ("academic_staff", "announcements", "news", "events"):
        url = links.get(key)
        if url:
            source_pairs.append((f"{name_tr} {_content_label(key, 'tr') if key in {'announcements', 'news', 'events'} else 'Akademik Personel'}", url))

    return ComposedAnswer(
        text=_text_for_language(
            language,
            f"📌 {name_tr} hakkında resmi sayfada bölüm bilgisi, akademik kadro, duyurular, haberler ve etkinlik bağlantıları yer almaktadır.",
            f"📌 The official page for {name_tr} includes department information, academic staff, announcements, news, and event links.",
        ),
        sources=_build_link_sources(source_pairs[:4]),
    )


def _official_navigation_answer(snapshot: dict, query: str, language: str) -> ComposedAnswer | None:
    if not _query_targets_iibf(query) and not _looks_like_iibf_menu_query(query):
        return None

    matches = find_faculty_navigation_matches(snapshot, query, limit=3)
    if not matches:
        return None

    best = matches[0]
    snapshot = ensure_faculty_page(snapshot, clean_text(best.get("url", "")))
    page = snapshot.get("faculty_pages", {}).get(best.get("url", ""), {})
    title = clean_text(page.get("title", "")) or clean_text(best.get("title", ""))
    summary = _clean_official_summary(page.get("summary", ""), title)
    body_excerpt = clean_text(page.get("body_excerpt", ""))

    if not summary and body_excerpt:
        summary = _extract_summary_sentence(body_excerpt, title, max_chars=220)

    if not title:
        return None

    if summary:
        text = _text_for_language(
            language,
            f"📌 İİBF {title} sayfasına göre: {summary}",
            f"📌 According to the FEAS page titled {title}: {summary}",
            f"📌 وفقًا لصفحة الكلية بعنوان {title}: {summary}",
        )
    else:
        text = _text_for_language(
            language,
            f"📌 İİBF {title} bilgisi resmi fakülte sayfasında yer almaktadır.",
            f"📌 The FEAS information for {title} is available on the official faculty page.",
            f"📌 تتوفر معلومات {title} في صفحة الكلية الرسمية.",
        )

    return ComposedAnswer(
        text=text,
        sources=_build_link_sources([(title, clean_text(best.get("url", "")))]),
    )


def _official_item_row(item: dict) -> str:
    title = clean_text(item.get("title", ""))
    date = clean_text(item.get("date", ""))
    summary = _clean_official_summary(item.get("summary", ""), title)
    if date and summary:
        return f"• {title} - {date}: {_truncate(summary, 110)}"
    if date:
        return f"• {title} - {date}"
    if summary:
        return f"• {title}: {_truncate(summary, 110)}"
    return f"• {title}"


def _official_item_sources(items: list[dict], fallback_title: str) -> list[SearchResult]:
    pairs = []
    for item in items:
        title = clean_text(item.get("title", "")) or fallback_title
        url = clean_text(item.get("url", ""))
        if url:
            pairs.append((title, url))
    return _build_link_sources(pairs[:3])


def _clean_official_summary(summary: str, title: str = "") -> str:
    cleaned = clean_text(summary)
    normalized = normalize_for_matching(cleaned)
    if any(
        term in normalized
        for term in (
            "bir daha gosterme",
            "akilli kart",
            "konuk evi",
            "internet erisim",
            "universitemiz",
            "kurumsal yonetim",
        )
    ):
        return ""
    if title and normalize_for_matching(title) == normalized:
        return ""
    return cleaned


def _content_source_url(topic: str) -> str:
    return {
        "announcements": FACULTY_ANNOUNCEMENTS_URL,
        "news": FACULTY_NEWS_URL,
        "events": FACULTY_EVENTS_URL,
    }.get(topic, FACULTY_ANNOUNCEMENTS_URL)


def _content_label(topic: str, language: str) -> str:
    translations = {
        "announcements": {"tr": "Duyurular", "en": "Announcements"},
        "news": {"tr": "Haberler", "en": "News"},
        "events": {"tr": "Etkinlikler", "en": "Events"},
    }
    entry = translations.get(topic, {"tr": "İçerikler", "en": "Content"})
    return entry["en"] if language == "en" else entry["tr"]


def _content_emoji(topic: str) -> str:
    return {
        "announcements": "📢",
        "news": "📌",
        "events": "📅",
    }.get(topic, "📌")


def _person_line(person: dict) -> str:
    academic_title = _display_academic_title(person.get("academic_title", ""))
    name = _normalize_person_name(person.get("name", ""))
    if academic_title:
        return f"• {academic_title} {name}"
    return f"• {name}"


def _person_role_line(person: dict) -> str:
    name = _normalize_person_name(person.get("name", ""))
    role = clean_text(", ".join(person.get("roles", [])))
    if role:
        return f"• {name}: {role}"
    return f"• {name}"


def _display_academic_title(value: str) -> str:
    normalized = normalize_for_matching(value)
    mapping = {
        "profesor": "Prof.",
        "docent": "Doç.",
        "doktor ogretim uyesi": "Dr. Öğr. Üyesi",
        "ogretim gorevlisi": "Öğr. Gör.",
        "arastirma gorevlisi": "Arş. Gör.",
        "doktor": "Dr.",
    }
    return mapping.get(normalized, clean_text(value))


def _official_content_topic(query: str) -> str | None:
    normalized = _query_key(query)
    if any(term in normalized for term in ("duyuru", "duyurular", "announcement", "announcements")):
        return "announcements"
    if any(term in normalized for term in ("haber", "haberler", "news")):
        return "news"
    if any(term in normalized for term in ("etkinlik", "etkinlikler", "event", "events")):
        return "events"
    return None


def _should_use_official_data(query: str) -> bool:
    normalized = _query_key(query)
    return any(
        condition
        for condition in (
            _is_dean_query(query),
            _is_department_listing_query(query),
            _is_faculty_staff_query(query),
            _is_faculty_department_heads_query(query),
            bool(department_keys_for_query(query)),
            bool(_official_content_topic(query)),
            _looks_like_iibf_menu_query(query),
            normalized in {"ybs", "akademik kadro", "duyurular", "haberler", "etkinlikler", "bolumler"},
        )
    )


def _is_dean_query(query: str) -> bool:
    normalized = _query_key(query)
    return ("dekan" in normalized or "dean" in normalized or "عميد" in normalized) and (
        _is_faculty_query(query)
        or "fakulte" in normalized
        or "faculty" in normalized
        or "feas" in normalized
        or normalized in {"dekan kim", "dekan kimdir", "dean", "who is the dean", "من هو العميد"}
    )


def _is_department_head_query(query: str) -> bool:
    normalized = _query_key(query)
    return any(
        term in normalized
        for term in (
            "bolum baskani",
            "bolum baskan yardimcisi",
            "baskan yardimcisi",
            "chair",
            "head of department",
        )
    )


def _is_department_listing_query(query: str) -> bool:
    normalized = _query_key(query)
    return "bolumler" in normalized or normalized == "bolumler" or normalized == "departments"


def _is_department_info_query(query: str) -> bool:
    normalized = _query_key(query)
    return any(term in normalized for term in ("hakkinda", "bolumu hakkinda", "about")) or bool(department_keys_for_query(query))


def _is_faculty_department_heads_query(query: str) -> bool:
    normalized = _query_key(query)
    return _is_faculty_query(query) and any(
        term in normalized for term in ("bolum baskanlari", "chairs", "department heads")
    )


def _is_faculty_staff_query(query: str) -> bool:
    normalized = _query_key(query)
    return _is_faculty_query(query) and any(
        term in normalized
        for term in (
            "akademik kadro",
            "akademik personel",
            "personel",
            "idari gorev",
            "idari gorevliler",
            "staff",
            "academic staff",
        )
    )


def _is_short_faculty_staff_query(query: str) -> bool:
    normalized = _query_key(query)
    return normalized in {
        "akademik kadro",
        "akademik personel",
        "personel",
        "idari gorevler",
        "idari gorevliler",
    }


def _is_department_staff_query(query: str) -> bool:
    normalized = _query_key(query)
    return any(
        term in normalized
        for term in (
            "akademik kadro",
            "akademik personel",
            "personel",
            "idari gorev",
            "idari gorevliler",
            "staff",
            "academic staff",
        )
    )


def _is_administrative_roles_query(query: str) -> bool:
    normalized = _query_key(query)
    return any(term in normalized for term in ("idari gorev", "idari gorevliler", "administrative"))


def _is_academic_staff_query(query: str) -> bool:
    normalized = _query_key(query)
    return any(term in normalized for term in ("akademik kadro", "akademik personel", "academic staff"))


def _smalltalk_response(query: str, language: str, user_memory: dict[str, object] | None = None) -> str:
    normalized = _query_key(query)
    for pattern, response in SMALLTALK_RESPONSES.items():
        if pattern in normalized:
            return response.get(language, response.get("en", response["tr"]))
    return _text_for_language(
        language,
        "😊 Elbette, sohbet edilebilir. İstenirse günlük bir konuya ya da bilgi sorusuna birlikte devam edilebilir.",
        "😊 Of course, we can chat. If you'd like, we can continue with a casual topic or an information question.",
        "😊 بالطبع، يمكننا الدردشة. وإذا رغبت، يمكننا المتابعة في موضوع يومي أو سؤال معلوماتي.",
    )


def _composition_shortcut(query: str, language: str) -> ComposedAnswer | None:
    normalized = _query_key(query)
    if not _is_composition_request(query):
        return None
    if _looks_like_code_request(query):
        return None

    if "mail" in normalized or "e posta" in normalized or "email" in normalized:
        return ComposedAnswer(
            text=_compose_email_draft(query, language),
            sources=[],
        )

    if "dilekce" in normalized or "dilekçe" in normalized or "petition" in normalized:
        return ComposedAnswer(
            text=_compose_petition_draft(query, language),
            sources=[],
        )

    if "mesaj" in normalized or "message" in normalized:
        return ComposedAnswer(
            text=_compose_message_draft(query, language),
            sources=[],
        )

    if any(term in normalized for term in ("duzelt", "düzelt", "rewrite", "improve text", "metni duzelt", "metni düzelt", "اصلح", "حسن")):
        corrected_text = _compose_corrected_text(query, language)
        if corrected_text:
            return ComposedAnswer(text=corrected_text, sources=[])

    return None


def _compose_email_draft(query: str, language: str) -> str:
    normalized = _query_key(query)
    payload = _extract_task_payload(query)

    if language == "en":
        if "internship" in normalized:
            return (
                "✅ Email draft:\n"
                "Subject: Internship Information Request\n"
                "Hello,\n"
                "I would like to request information about current internship opportunities and the application process. "
                "If possible, could you please share the requirements and available dates?\n"
                "Best regards,\n"
                "[Your Name]"
            )
        subject = _infer_subject(payload, language)
        body = payload or "I would like to request information regarding the related matter."
        return (
            "✅ Email draft:\n"
            f"Subject: {subject}\n"
            "Hello,\n"
            f"I would like to ask for support regarding {body.lower().rstrip('.')}.\n"
            "Thank you for your time.\n"
            "Best regards,\n"
            "[Your Name]"
        )

    if language == "ar":
        subject = _infer_subject(payload, language)
        body = payload or "الموضوع المطلوب"
        return (
            "✅ مسودة بريد إلكتروني:\n"
            f"الموضوع: {subject}\n"
            "مرحبًا،\n"
            f"أرغب في طلب إفادة بخصوص {body}.\n"
            "شاكرًا تعاونكم.\n"
            "مع خالص التحية،\n"
            "[الاسم]"
        )

    if any(term in normalized for term in ("toplanti", "meeting")):
        greeting = "Merhaba Hocam," if any(term in normalized for term in ("hocam", "danisman", "danışman")) else "Merhaba,"
        return (
            "✅ E-posta taslağı:\n"
            "Konu: Toplantı Talebi\n"
            f"{greeting}\n"
            "Yarın uygun olduğunuz bir saatte kısa bir toplantı gerçekleştirmek isterim. "
            "Müsait olduğunuz saat aralığını paylaşabilirseniz memnun olurum.\n"
            "İyi çalışmalar dilerim.\n"
            "[Ad Soyad]"
        )

    if "staj" in normalized:
        return (
            "✅ E-posta taslağı:\n"
            "Konu: Staj Bilgisi Talebi\n"
            "Merhaba,\n"
            "Staj olanakları ve başvuru süreci hakkında bilgi rica ediyorum. "
            "Uygun koşullar ve tarih aralıkları paylaşılabilirse memnun olurum.\n"
            "İyi çalışmalar dilerim.\n"
            "[Ad Soyad]"
        )

    subject = _infer_subject(payload, language)
    body = payload or "ilgili konu hakkında bilgi talebi"
    return (
        "✅ E-posta taslağı:\n"
        f"Konu: {subject}\n"
        "Merhaba,\n"
        f"{body} konusunda bilgi rica ediyorum.\n"
        "İyi çalışmalar dilerim.\n"
        "[Ad Soyad]"
    )


def _compose_petition_draft(query: str, language: str) -> str:
    payload = _extract_task_payload(query) or _text_for_language(
        language,
        "ilgili konu",
        "the related matter",
        "الموضوع المطلوب",
    )
    topic = clean_text(payload).strip(" .")
    if language == "tr":
        if topic.endswith("için"):
            body = f"{topic} gerekli işlemin yapılmasını arz ederim."
        elif topic.endswith(("hakkında", "konusunda")):
            body = f"{topic} gereğinin yapılmasını arz ederim."
        else:
            body = f"{topic} konusunda gereğinin yapılmasını arz ederim."
        return (
            "✅ Dilekçe taslağı:\n"
            "İlgili Makama,\n"
            f"{body}\n"
            "Bilgilerinize sunarım.\n"
            "[Ad Soyad]"
        )

    if language == "en":
        body = (
            f"I respectfully request the necessary action regarding {topic}."
            if topic != "the related matter"
            else "I respectfully request the necessary action regarding the related matter."
        )
        return (
            "✅ Petition draft:\n"
            "To the Relevant Authority,\n"
            f"{body}\n"
            "Submitted for your consideration.\n"
            "[Your Name]"
        )

    return _text_for_language(
        language,
        "✅ Dilekçe taslağı:\n"
        "İlgili Makama,\n"
        f"{topic or payload} konusunda gereğinin yapılmasını arz ederim.\n"
        "Bilgilerinize sunarım.\n"
        "[Ad Soyad]",
        "✅ Petition draft:\n"
        "To the Relevant Authority,\n"
        f"I respectfully request the necessary action regarding {topic or payload}.\n"
        "Submitted for your consideration.\n"
        "[Your Name]",
        "✅ مسودة طلب:\n"
        "إلى الجهة المختصة،\n"
        f"أرجو اتخاذ اللازم بخصوص {topic or payload}.\n"
        "وتفضلوا بقبول الاحترام.\n"
        "[الاسم]",
    )


def _compose_message_draft(query: str, language: str) -> str:
    payload = _extract_task_payload(query)
    return _text_for_language(
        language,
        "✅ Mesaj taslağı:\n"
        + (f"Merhaba, {payload} konusunda kısa bir dönüş rica ediyorum. Uygun olduğunuzda bilgi verebilir misiniz?" if payload else "Merhaba, ilgili konu hakkında kısa bir dönüş rica ediyorum. Uygun olduğunuzda bilgi verebilir misiniz?"),
        "✅ Message draft:\n"
        + (f"Hello, I would appreciate a short update regarding {payload}. Could you please respond when convenient?" if payload else "Hello, I would appreciate a short update on the related matter. Could you please respond when convenient?"),
        "✅ مسودة رسالة:\n"
        + (f"مرحبًا، أرجو إفادة مختصرة بخصوص {payload}. هل يمكنكم الرد عند توفر الوقت؟" if payload else "مرحبًا، أرجو إفادة مختصرة حول الموضوع. هل يمكنكم الرد عند توفر الوقت؟"),
    )


def _compose_corrected_text(query: str, language: str) -> str:
    payload = _extract_task_payload(query)
    if not payload:
        return ""

    corrected = payload.strip()
    if language == "tr":
        replacements = {
            " bugun ": " bugün ",
            " cunku ": " çünkü ",
            " hastaym ": " hastayım ",
            " gelemedm ": " gelemedim ",
            " gelmedm ": " gelemedim ",
            " okla ": " okula ",
            " oklaa ": " okula ",
            " yarin ": " yarın ",
            " hocamlaa ": " hocamla ",
            " noktlama ": " noktalama ",
            " yazim ": " yazım ",
            " bi ": " bir ",
        }
        corrected = f" {corrected.lower()} "
        for old, new in replacements.items():
            corrected = corrected.replace(old, new)
        corrected = re.sub(r"\s+", " ", corrected).strip()
        corrected = re.sub(r"\s+([,.;!?])", r"\1", corrected)
        corrected = re.sub(r"([,.;!?])([^\s])", r"\1 \2", corrected)
        corrected = _capitalize_sentences(corrected)
        if corrected and corrected[-1] not in ".!?":
            corrected += "."
        return "✅ Düzeltilmiş metin:\n" + corrected

    if language == "en":
        corrected = re.sub(r"\s+", " ", corrected).strip()
        corrected = re.sub(r"\s+([,.;!?])", r"\1", corrected)
        corrected = re.sub(r"([,.;!?])([^\s])", r"\1 \2", corrected)
        corrected = _capitalize_sentences(corrected)
        if corrected and corrected[-1] not in ".!?":
            corrected += "."
        return "✅ Corrected text:\n" + corrected

    corrected = re.sub(r"\s+", " ", corrected).strip()
    return "✅ النص المصحح:\n" + corrected


def _extract_task_payload(query: str) -> str:
    cleaned = clean_text(query)
    quoted_match = re.search(r"[\"“](.+?)[\"”]", cleaned)
    if quoted_match:
        return clean_text(quoted_match.group(1))
    if ":" in cleaned:
        return clean_text(cleaned.split(":", 1)[1])
    if "\n" in cleaned:
        lines = [clean_text(line) for line in cleaned.splitlines() if clean_text(line)]
        if len(lines) >= 2:
            return lines[-1]
    command_patterns = (
        r"(?i)^(?:bu\s+)?kodu?\s+d[üu]zelt[:\s-]*",
        r"(?i)^kodu?\s+iyilestir[:\s-]*",
        r"(?i)^kodu?\s+geli[sş]tir[:\s-]*",
        r"(?i)^mail\s+yaz[:\s-]*",
        r"(?i)^e[-\s]?posta\s+yaz[:\s-]*",
        r"(?i)^mesaj\s+yaz[:\s-]*",
        r"(?i)^dilek[çc]e(?:\s+olustur|\s+olu[sş]tur|\s+hazirla|\s+yaz)?[:\s-]*",
        r"(?i)^(?:bu\s+)?metni\s+d[üu]zelt[:\s-]*",
        r"(?i)^yaz[ıi]m(?:\s+ve\s+noktalama)?\s+hatalar[ıi]n[ıi]\s+d[üu]zelt[:\s-]*",
        r"(?i)^noktalama(?:\s+isaretleri| işaretleri)?(?:ni)?\s+d[üu]zelt[:\s-]*",
        r"(?i)^metin(?:i)?\s+d[üu]zenle[:\s-]*",
        r"(?i)^rewrite(?:\s+this\s+text)?[:\s-]*",
        r"(?i)^correct(?:\s+this\s+text)?[:\s-]*",
        r"(?i)^improve(?:\s+this\s+text)?[:\s-]*",
        r"(?i)^اصلح(?:\s+هذا\s+النص)?[:\s-]*",
        r"(?i)^حسن(?:\s+هذا\s+النص)?[:\s-]*",
    )
    for pattern in command_patterns:
        stripped = re.sub(pattern, "", cleaned).strip()
        if stripped and stripped != cleaned:
            return stripped
    return ""


def _looks_like_code_request(query: str) -> bool:
    normalized = _query_key(query)
    if is_coding_query(query):
        return True
    if "```" in query:
        return True
    if any(
        term in normalized
        for term in (
            "syntaxerror",
            "typeerror",
            "valueerror",
            "traceback",
            "exception",
            "kod",
            "code",
            "hata veriyor",
            "calismiyor",
        )
    ):
        return True
    return bool(
        re.search(
            r"\b(def|class|return|import|from|print\s*\(|console\.log|function|const|let|var|if\s*\(|for\s*\(|while\s*\()",
            query,
            flags=re.IGNORECASE,
        )
    )


def _infer_subject(payload: str, language: str) -> str:
    normalized = _query_key(payload)
    if any(term in normalized for term in ("toplanti", "meeting", "اجتماع")):
        return _text_for_language(language, "Toplantı Talebi", "Meeting Request", "طلب اجتماع")
    if any(term in normalized for term in ("staj", "internship", "تدريب")):
        return _text_for_language(language, "Staj Bilgisi Talebi", "Internship Information Request", "طلب معلومات عن التدريب")
    return _text_for_language(language, "Bilgi Talebi", "Information Request", "طلب معلومات")


def _datetime_shortcut(query: str, language: str) -> ComposedAnswer | None:
    normalized = _query_key(query)
    if _is_composition_request(query):
        return None
    if not (_is_datetime_query(query) or _is_special_day_query(query)):
        return None

    now = datetime.now(ISTANBUL_TZ)
    explicit_date = _parse_explicit_date(query, now.year)
    relative_target = _resolve_relative_date(normalized, now.date())
    target_special_days = _resolve_special_days(query, now.year)
    special_day_listing_query = _is_special_day_listing_query(query)
    religious_schedule_query = _is_religious_schedule_query(query)
    day_name_query = _is_day_name_query(query)

    if target_special_days:
        return _build_special_day_response(target_special_days, language)

    if religious_schedule_query and explicit_date is None and relative_target is None:
        target_year = _extract_requested_year(query) or now.year
        religious_entries = _religious_schedule_entries(target_year)
        if religious_entries:
            return _build_religious_schedule_response(target_year, religious_entries, language)
        return ComposedAnswer(
            text=_text_for_language(
                language,
                f"⚠️ {target_year} yılı için resmi dini gün takvimi verisine ulaşamadım.",
                f"⚠️ I could not reach the official religious calendar data for {target_year}.",
                f"⚠️ لم أتمكن من الوصول إلى بيانات التقويم الديني الرسمية لعام {target_year}.",
            ),
            sources=[],
        )

    if special_day_listing_query:
        target_date = explicit_date or relative_target or now.date()
        same_day_specials = _special_days_on_date(target_date)
        if same_day_specials:
            return _build_special_day_listing_response(target_date, same_day_specials, language)
        return ComposedAnswer(
            text=_text_for_language(
                language,
                f"📅 {_format_date_with_weekday(target_date, language)} tarihinde katalogda eşleşen özel gün bulunmuyor.",
                f"📅 No matching special day is listed in the catalog for {_format_date_with_weekday(target_date, language)}.",
                f"📅 لا يوجد يوم خاص مطابق في القائمة بتاريخ {_format_date_with_weekday(target_date, language)}.",
            ),
            sources=[],
        )

    if explicit_date is not None and day_name_query:
        formatted = _format_date_with_weekday(explicit_date, language)
        return ComposedAnswer(
            text=_text_for_language(
                language,
                f"📅 {formatted} gününe denk geliyor.",
                f"📅 It falls on {formatted}.",
                f"📅 يوافق {formatted}.",
            ),
            sources=[],
        )

    if any(term in normalized for term in ("saat", "time", "clock", "الساعة")):
        return ComposedAnswer(
            text=_text_for_language(
                language,
                f"🕒 İstanbul saatine göre şu an {_format_date_with_weekday(now.date(), language)}, saat {now.strftime('%H:%M')}.",
                f"🕒 According to Istanbul time, it is now {_format_date_with_weekday(now.date(), language)} at {now.strftime('%H:%M')}.",
                f"🕒 حسب توقيت إسطنبول الآن {_format_date_with_weekday(now.date(), language)} والساعة {now.strftime('%H:%M')}.",
            ),
            sources=[],
        )

    if relative_target is not None:
        return ComposedAnswer(
            text=_text_for_language(
                language,
                f"📅 {_relative_date_label(normalized, language)} {_format_date_with_weekday(relative_target, language)}.",
                f"📅 {_relative_date_label(normalized, language)} {_format_date_with_weekday(relative_target, language)}.",
                f"📅 {_relative_date_label(normalized, language)} {_format_date_with_weekday(relative_target, language)}.",
            ),
            sources=[],
        )

    if day_name_query:
        return ComposedAnswer(
            text=_text_for_language(
                language,
                f"📅 Bugün günlerden {WEEKDAY_NAMES['tr'][now.date().weekday()]}.",
                f"📅 Today is {WEEKDAY_NAMES['en'][now.date().weekday()]}.",
                f"📅 اليوم هو {WEEKDAY_NAMES['ar'][now.date().weekday()]}.",
            ),
            sources=[],
        )

    if explicit_date is not None:
        return ComposedAnswer(
            text=_text_for_language(
                language,
                f"📅 Tarih bilgisi: {_format_date_with_weekday(explicit_date, language)}.",
                f"📅 Date information: {_format_date_with_weekday(explicit_date, language)}.",
                f"📅 معلومات التاريخ: {_format_date_with_weekday(explicit_date, language)}.",
            ),
            sources=[],
        )

    return ComposedAnswer(
        text=_text_for_language(
            language,
            f"📅 İstanbul saatine göre bugün {_format_date_with_weekday(now.date(), language)}.",
            f"📅 According to Istanbul time, today is {_format_date_with_weekday(now.date(), language)}.",
            f"📅 وفقًا لتوقيت إسطنبول فإن اليوم هو {_format_date_with_weekday(now.date(), language)}.",
        ),
        sources=[],
    )


def _is_datetime_query(query: str) -> bool:
    normalized = _query_key(query)
    return any(
        term in normalized
        for term in (
            "bugun",
            "bugün",
            "yarin",
            "yarın",
            "dun",
            "dün",
            "tarih",
            "saat",
            "gunlerden ne",
            "günlerden ne",
            "hangi gun",
            "hangi gün",
            "hangi gun bugun",
            "hangi gün bugün",
            "what day",
            "what date",
            "what time",
            "today",
            "tomorrow",
            "yesterday",
            "date",
            "time",
            "clock",
            "اليوم",
            "غدا",
            "تاريخ",
            "الساعة",
            "اي يوم",
        )
    ) or bool(_parse_explicit_date(query, datetime.now(ISTANBUL_TZ).year))


def _is_special_day_query(query: str) -> bool:
    normalized = _query_key(query)
    return _is_special_day_listing_query(query) or _is_religious_schedule_query(query) or any(
        any(alias in normalized for alias in entry["aliases"])
        for entry in SPECIAL_DAY_DEFINITIONS
    )


def _resolve_relative_date(normalized_query: str, reference: date) -> date | None:
    if any(term in normalized_query for term in ("yarin", "yarın", "tomorrow", "غدا")):
        return reference + timedelta(days=1)
    if any(term in normalized_query for term in ("dun", "dün", "yesterday", "امس")):
        return reference - timedelta(days=1)
    if any(term in normalized_query for term in ("bugun", "bugün", "today", "اليوم")):
        return reference
    return None


def _relative_date_label(normalized_query: str, language: str) -> str:
    if any(term in normalized_query for term in ("yarin", "yarın", "tomorrow", "غدا")):
        return _text_for_language(language, "Yarın", "Tomorrow is", "غدًا")
    if any(term in normalized_query for term in ("dun", "dün", "yesterday", "امس")):
        return _text_for_language(language, "Dün", "Yesterday was", "أمس")
    return _text_for_language(language, "Bugün", "Today is", "اليوم")


def _parse_explicit_date(query: str, default_year: int) -> date | None:
    cleaned = clean_text(query)

    numeric_match = re.search(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})\b", cleaned)
    if numeric_match:
        day, month, year = map(int, numeric_match.groups())
        year = 2000 + year if year < 100 else year
        return _safe_date(year, month, day)

    month_match = re.search(r"\b(\d{1,2})\s+([A-Za-zÇĞİÖŞÜçğıöşü]+)\s*(\d{4})?\b", cleaned)
    if month_match:
        day = int(month_match.group(1))
        month_name = clean_text(month_match.group(2)).lower()
        year = int(month_match.group(3)) if month_match.group(3) else default_year
        month = MONTH_NAMES_TR.get(month_name) or MONTH_NAMES_EN.get(month_name)
        if month:
            return _safe_date(year, month, day)
    return None


def _religious_day_date(key: str, year: int) -> date:
    year_schedule = DIYANET_RELIGIOUS_SCHEDULES.get(year)
    if not year_schedule or key not in year_schedule:
        raise ValueError(f"Religious day schedule is unavailable for {year}.")
    return year_schedule[key]


def _is_religious_schedule_query(query: str) -> bool:
    normalized = _query_key(query)
    return any(
        term in normalized
        for term in (
            "dini gun",
            "dini gün",
            "dini gunler",
            "dini günler",
            "dini geceler",
            "kandil tarihleri",
            "kandiller",
            "religious holidays",
            "religious days",
            "muslim holidays",
            "islamic holidays",
            "الايام الدينية",
            "الأيام الدينية",
            "المناسبات الدينية",
        )
    )


def _religious_schedule_entries(year: int) -> list[tuple[dict, date]]:
    entries: list[tuple[dict, date]] = []
    for entry in RELIGIOUS_SPECIAL_DAY_DEFINITIONS:
        try:
            entries.append((entry, entry["builder"](year)))
        except ValueError:
            continue
    return entries


def _resolve_special_days(query: str, default_year: int) -> list[tuple[dict, date]]:
    normalized = _query_key(query)
    year = _extract_requested_year(query) or default_year
    matches: list[tuple[dict, date]] = []
    seen: set[str] = set()
    for entry in SPECIAL_DAY_DEFINITIONS:
        if not any(alias in normalized for alias in entry["aliases"]):
            continue
        if entry["key"] in seen:
            continue
        try:
            target_date = entry["builder"](year)
        except ValueError:
            continue
        matches.append((entry, target_date))
        seen.add(entry["key"])
    return matches


def _is_special_day_listing_query(query: str) -> bool:
    normalized = _query_key(query)
    return any(
        term in normalized
        for term in (
            "ozel gun",
            "özel gün",
            "ozel gunler",
            "özel günler",
            "ne gunu",
            "ne günü",
            "hangi ozel gunler",
            "hangi özel günler",
            "bugun hangi ozel gunler var",
            "bugün hangi özel günler var",
            "bugun hangi gunler kutlaniyor",
            "bugün hangi günler kutlanıyor",
            "special day",
            "special days",
            "international day",
            "world day",
            "observance",
            "observances",
            "what is celebrated",
            "hangi kutlama",
            "what special day",
            "what special days",
            "ما هي المناسبات",
            "اليوم العالمي",
        )
    )


def _is_day_name_query(query: str) -> bool:
    normalized = _query_key(query)
    return any(
        term in normalized
        for term in (
            "hangi gun",
            "hangi gün",
            "bugun hangi gun",
            "bugün hangi gün",
            "gunlerden ne",
            "günlerden ne",
            "what day",
            "what day is today",
            "day of week",
            "اي يوم",
        )
    )


def _extract_requested_year(query: str) -> int | None:
    match = re.search(r"\b(20\d{2})\b", query)
    if not match:
        return None
    return int(match.group(1))


def _special_days_on_date(target_date: date) -> list[dict]:
    matches: list[dict] = []
    for entry in SPECIAL_DAY_DEFINITIONS:
        try:
            special_date = entry["builder"](target_date.year)
        except ValueError:
            continue
        if special_date == target_date:
            matches.append(entry)
    return matches


def _special_day_display_name(entry: dict, language: str) -> str:
    labels = entry.get("labels", {})
    if language == "ar":
        return clean_text(labels.get("ar", labels.get("en", labels.get("tr", ""))))
    if language == "en":
        return clean_text(labels.get("en", labels.get("tr", "")))
    return clean_text(labels.get("tr", labels.get("en", "")))


def _special_day_sources(entries: list[dict]) -> list[SearchResult]:
    seen: set[str] = set()
    sources: list[SearchResult] = []
    for entry in entries:
        source_template = clean_text(entry.get("source_url", ""))
        if not source_template:
            continue
        source_url = source_template.format(year="{year}") if "{year}" not in source_template else source_template
        # If the template still expects a year, skip it here and let callers pass a concrete URL.
        if "{year}" in source_url:
            continue
        if source_url in seen:
            continue
        title = clean_text(entry.get("source_title", "Özel Gün Kaynağı")) or "Özel Gün Kaynağı"
        sources.append(
            SearchResult(
                chunk=Chunk(
                    id=stable_id(title, source_url),
                    title=title,
                    url=source_url,
                    text=title,
                    ordinal=1,
                ),
                score=1.0,
            )
        )
        seen.add(source_url)
    return sources


def _special_day_sources_for_year(entries: list[dict], year: int) -> list[SearchResult]:
    seen: set[str] = set()
    sources: list[SearchResult] = []
    for entry in entries:
        source_template = clean_text(entry.get("source_url", ""))
        if not source_template:
            continue
        source_url = source_template.format(year=year)
        if source_url in seen:
            continue
        title = clean_text(entry.get("source_title", "Özel Gün Kaynağı")) or "Özel Gün Kaynağı"
        sources.append(
            SearchResult(
                chunk=Chunk(
                    id=stable_id(title, source_url),
                    title=title,
                    url=source_url,
                    text=title,
                    ordinal=1,
                ),
                score=1.0,
            )
        )
        seen.add(source_url)
    return sources


def _build_special_day_response(entries: list[tuple[dict, date]], language: str) -> ComposedAnswer:
    if len(entries) == 1:
        entry, target_date = entries[0]
        label = _special_day_display_name(entry, language)
        formatted = _format_date_with_weekday(target_date, language)
        return ComposedAnswer(
            text=_text_for_language(
                language,
                f"📅 {label} {target_date.year} yılında {formatted} gününe denk geliyor.",
                f"📅 {label} in {target_date.year} falls on {formatted}.",
                f"📅 {label} في عام {target_date.year} يوافق {formatted}.",
            ),
            sources=_special_day_sources_for_year([entry], target_date.year),
        )

    rows = [f"• {_special_day_display_name(entry, language)} - {_format_date_with_weekday(target_date, language)}" for entry, target_date in entries]
    return ComposedAnswer(
        text=_text_for_language(
            language,
            "📅 Eşleşen özel günler:\n" + "\n".join(rows),
            "📅 Matching special days:\n" + "\n".join(rows),
            "📅 الأيام الخاصة المطابقة:\n" + "\n".join(rows),
        ),
        sources=_special_day_sources_for_year([entry for entry, _ in entries], entries[0][1].year),
    )


def _build_special_day_listing_response(target_date: date, entries: list[dict], language: str) -> ComposedAnswer:
    rows = [f"• {_special_day_display_name(entry, language)}" for entry in entries]
    return ComposedAnswer(
        text=_text_for_language(
            language,
            f"📅 {_format_date_with_weekday(target_date, language)} tarihinde öne çıkan özel günler:\n" + "\n".join(rows),
            f"📅 The highlighted special days on {_format_date_with_weekday(target_date, language)} are:\n" + "\n".join(rows),
            f"📅 الأيام الخاصة البارزة بتاريخ {_format_date_with_weekday(target_date, language)} هي:\n" + "\n".join(rows),
        ),
        sources=_special_day_sources_for_year(entries, target_date.year),
    )


def _build_religious_schedule_response(year: int, entries: list[tuple[dict, date]], language: str) -> ComposedAnswer:
    rows = [f"• {_special_day_display_name(entry, language)} - {_format_date_with_weekday(target_date, language)}" for entry, target_date in entries]
    return ComposedAnswer(
        text=_text_for_language(
            language,
            f"🕌 {year} yılı resmi dini günler takvimi:\n" + "\n".join(rows),
            f"🕌 Official religious calendar for {year}:\n" + "\n".join(rows),
            f"🕌 التقويم الرسمي للمناسبات الدينية لعام {year}:\n" + "\n".join(rows),
        ),
        sources=_special_day_sources_for_year([entry for entry, _ in entries], year),
    )


def _format_date_with_weekday(target: date, language: str) -> str:
    weekday_name = WEEKDAY_NAMES.get(language, WEEKDAY_NAMES["tr"])[target.weekday()]
    if language == "en":
        month_name = target.strftime("%B")
        return f"{weekday_name}, {month_name} {target.day}, {target.year}"
    if language == "ar":
        return f"{weekday_name} {target.day}/{target.month}/{target.year}"
    month_names_tr = (
        "",
        "Ocak",
        "Şubat",
        "Mart",
        "Nisan",
        "Mayıs",
        "Haziran",
        "Temmuz",
        "Ağustos",
        "Eylül",
        "Ekim",
        "Kasım",
        "Aralık",
    )
    month_name_tr = month_names_tr[target.month]
    return f"{target.day} {month_name_tr} {target.year} {weekday_name}"


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _nth_weekday_of_month(year: int, month: int, weekday: int, occurrence: int) -> date:
    first_day = date(year, month, 1)
    offset = (weekday - first_day.weekday()) % 7
    day_number = 1 + offset + (occurrence - 1) * 7
    return date(year, month, day_number)


def _capitalize_sentences(text: str) -> str:
    sentence = text.strip()
    if not sentence:
        return ""

    pieces = re.split(r"([.!?]\s+)", sentence)
    rebuilt: list[str] = []
    for piece in pieces:
        if not piece:
            continue
        if re.fullmatch(r"[.!?]\s+", piece):
            rebuilt.append(piece)
            continue
        rebuilt.append(piece[:1].upper() + piece[1:] if piece else piece)
    return "".join(rebuilt).strip()


def _unknown_answer_text(language: str) -> str:
    return _text_for_language(
        language,
        "⚠️ Bu sorunun yanıtını henüz bilmiyorum. Daha net bilgi veya farklı bir ifade ile yeniden sorulursa tekrar yardımcı olabilirim.",
        "⚠️ I do not know the answer to this question yet. If it is asked with clearer details or a different phrasing, I can try again.",
        "⚠️ لا أعرف إجابة هذا السؤال بعد. إذا تمت إعادة صياغته بشكل أوضح، يمكنني المحاولة مرة أخرى.",
    )


def _fallback_text_for_query(query: str, language: str) -> str:
    if _should_answer_with_general_knowledge(query) or _looks_like_code_request(query):
        return _unknown_answer_text(language)
    return _text_for_language(
        language,
        FALLBACK_RESPONSE,
        "⚠️ I could not reach reliable information on this topic. For the most accurate information, please contact the faculty directly.",
        "⚠️ لم أتمكن من الوصول إلى معلومات موثوقة حول هذا الموضوع. للحصول على أدق معلومة، يُنصح بالتواصل مع الكلية مباشرة.",
    )


def _should_answer_with_general_knowledge(query: str) -> bool:
    normalized = _query_key(query)
    if not normalized:
        return False
    if _is_composition_request(query):
        return True
    if looks_actionable(normalized):
        return False
    if any(
        checker(query)
        for checker in (
            _is_faculty_query,
            _is_contact_query,
            _is_personnel_query,
            _is_department_query,
            _is_announcement_query,
            _is_exam_query,
            _is_academic_calendar_query,
            _is_menu_query,
            _is_location_query,
            _is_management_query,
        )
    ):
        return False

    tokens = [token for token in normalized.split() if token]
    has_general_signal = any(
        term in normalized
        for term in (
            "nedir",
            "nasil",
            "neden",
            "kimdir",
            "kac",
            "duzelt",
            "gelistir",
            "iyilestir",
            "arastir",
            "araştir",
            "olustur",
            "hazirla",
            "yaz",
            "mail yaz",
            "mesaj yaz",
            "dilekce",
            "dilekçe",
            "ozetle",
            "çevir",
            "what",
            "how",
            "why",
            "who",
            "write",
            "fix",
            "improve",
            "create",
            "draft",
            "summarize",
            "research",
            "matematik",
            "tarih",
            "yazilim",
            "python",
            "kod",
            "code",
            "bug",
            "error",
            "fix",
            "مرحبا",
            "كيف",
            "اكتب",
            "اصلح",
            "حسن",
            "ابحث",
            "لخص",
            "ترجم",
        )
    )
    has_math_signal = any(char in query for char in "+-*/=")
    return bool(tokens) and (
        len(tokens) >= 2
        or has_general_signal
        or has_math_signal
        or is_coding_query(query)
        or len(tokens[0]) >= 3
        or is_arabic_query(query)
    )


def _solve_basic_math(query: str, language: str) -> str | None:
    expression = _math_expression_from_query(query)
    if not expression:
        return None
    try:
        result = _evaluate_math_expression(expression)
    except Exception:
        return None

    if isinstance(result, float) and result.is_integer():
        result = int(result)
    if isinstance(result, float):
        result = round(result, 4)
    return _text_for_language(
        language,
        f"✅ Sonuç: {expression} = {result}",
        f"✅ Result: {expression} = {result}",
    )


def _math_expression_from_query(query: str) -> str:
    raw_expression = re.sub(r"[^0-9+\-*/(). ]", " ", query)
    raw_expression = re.sub(r"\s+", "", raw_expression)
    if raw_expression and any(symbol in raw_expression for symbol in "+-*/"):
        if re.fullmatch(r"[0-9+\-*/().]+", raw_expression):
            return raw_expression

    normalized = _query_key(query)
    if not normalized:
        return ""

    working = f" {normalized} "
    replacements = (
        ("kac eder", " "),
        ("kac yapar", " "),
        ("sonuc", " "),
        ("nedir", " "),
        ("hesapla", " "),
        ("equals", " "),
        ("what is", " "),
        ("calculate", " "),
        ("toplam", " + "),
        ("arti", " + "),
        ("topla", " + "),
        ("plus", " + "),
        ("add", " + "),
        ("eksi", " - "),
        ("cikar", " - "),
        ("farki", " - "),
        ("minus", " - "),
        ("subtract", " - "),
        ("carpi", " * "),
        ("carp", " * "),
        ("times", " * "),
        ("multiply", " * "),
        ("bolu", " / "),
        ("bol", " / "),
        ("divided by", " / "),
        ("divide", " / "),
    )
    for old, new in replacements:
        working = working.replace(old, new)

    working = re.sub(r"(\d+)\s+ile\s+(\d+)\s+\+", r"\1 + \2", working)
    working = re.sub(r"(\d+)\s+ve\s+(\d+)\s+\+", r"\1 + \2", working)
    working = re.sub(r"(\d+)\s+ile\s+(\d+)\s+\-", r"\1 - \2", working)
    working = re.sub(r"(\d+)\s+ve\s+(\d+)\s+\-", r"\1 - \2", working)
    working = re.sub(r"(\d+)\s+ile\s+(\d+)\s+\*", r"\1 * \2", working)
    working = re.sub(r"(\d+)\s+ve\s+(\d+)\s+\*", r"\1 * \2", working)
    working = re.sub(r"(\d+)\s+ile\s+(\d+)\s+/", r"\1 / \2", working)
    working = re.sub(r"(\d+)\s+ve\s+(\d+)\s+/", r"\1 / \2", working)

    expression = re.sub(r"[^0-9+\-*/(). ]", " ", working)
    expression = re.sub(r"\s+", "", expression)
    if not expression or not any(symbol in expression for symbol in "+-*/"):
        return ""
    if not re.fullmatch(r"[0-9+\-*/().]+", expression):
        return ""
    return expression


def _evaluate_math_expression(expression: str) -> int | float:
    tree = ast.parse(expression, mode="eval")
    return _evaluate_math_node(tree.body)


def _evaluate_math_node(node: ast.AST) -> int | float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.Num):
        return node.n
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_evaluate_math_node(node.operand)
    if isinstance(node, ast.BinOp) and type(node.op) in MATH_BINARY_OPERATORS:
        left = _evaluate_math_node(node.left)
        right = _evaluate_math_node(node.right)
        return MATH_BINARY_OPERATORS[type(node.op)](left, right)
    raise ValueError("Unsupported expression")


@lru_cache(maxsize=6)
def _fetch_remote_page(url: str) -> str:
    response = requests.get(
        url,
        timeout=6,
        headers={
            "User-Agent": "KAUCAN/1.0 (+https://www.kafkas.edu.tr)",
        },
    )
    response.raise_for_status()
    return response.text


def _fetch_rector_name() -> str:
    try:
        html = _fetch_remote_page(RECTOR_PAGE[1])
    except requests.RequestException:
        return ""

    match = re.search(
        r"<strong>\s*(Prof\.?\s*Dr\.?\s*[^<]+?)\s*</strong>",
        html,
        flags=re.IGNORECASE,
    )
    if not match:
        return ""
    return _normalize_person_name(match.group(1))


def _fetch_rector_assistant_names() -> list[str]:
    try:
        html = _fetch_remote_page(RECTOR_ASSISTANTS_PAGE[1])
    except requests.RequestException:
        return []

    names = re.findall(
        r"/rektorluk/tr/sayfaYeni\d+'>\s*(Prof\.?\s*Dr\.?\s*[^<]+?)\s*</a>",
        html,
        flags=re.IGNORECASE,
    )
    normalized_names: list[str] = []
    for name in names:
        cleaned = _normalize_person_name(name)
        if cleaned and cleaned not in normalized_names:
            normalized_names.append(cleaned)
    return normalized_names[:5]


def _normalize_person_name(value: str) -> str:
    cleaned = unescape(clean_text(value))
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -")
    return cleaned


def _extract_link_pairs(text: str) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for match in LINK_PATTERN.finditer(text):
        label = clean_text(match.group(1))
        url = match.group(2).strip()
        if not label or not url:
            continue
        if (label, url) not in entries:
            entries.append((label, url))
    return entries


def _display_title(result: SearchResult, language: str = "tr") -> str:
    title = clean_text(result.chunk.title)
    return title or _text_for_language(language, "İlgili Sayfa", "Related Page")


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def _dedupe_results_by_url(results: list[SearchResult]) -> list[SearchResult]:
    deduped: list[SearchResult] = []
    seen_urls: set[str] = set()
    for result in results:
        if result.chunk.url in seen_urls:
            continue
        deduped.append(result)
        seen_urls.add(result.chunk.url)
    return deduped


def _merge_source_results(*groups: list[SearchResult]) -> list[SearchResult]:
    merged: list[SearchResult] = []
    seen_urls: set[str] = set()
    for group in groups:
        for result in group:
            url = result.chunk.url
            if not url or url in seen_urls:
                continue
            merged.append(result)
            seen_urls.add(url)
    return merged


def _generator_for_settings(settings: Settings):
    if settings.llm_provider == "ollama":
        return OllamaAnswerGenerator(settings)
    if settings.llm_provider == "openai":
        return OpenAIAnswerGenerator(settings)
    return LocalOnlyGenerator()


def _general_generator_for_settings(settings: Settings):
    openai_generator = OpenAIAnswerGenerator(settings)
    if openai_generator.is_configured:
        return openai_generator
    return _generator_for_settings(settings)


def _grounded_generators_for_settings(settings: Settings):
    generators = []
    primary_generator = _generator_for_settings(settings)
    if primary_generator.is_configured:
        generators.append(primary_generator)

    openai_generator = OpenAIAnswerGenerator(settings)
    if openai_generator.is_configured and not any(type(generator) is type(openai_generator) for generator in generators):
        generators.append(openai_generator)

    if not generators:
        generators.append(LocalOnlyGenerator())
    return generators


def _general_generators_for_settings(settings: Settings):
    generators = []
    primary_generator = _generator_for_settings(settings)
    if primary_generator.is_configured:
        generators.append(primary_generator)

    openai_generator = OpenAIAnswerGenerator(settings)
    if openai_generator.is_configured and not any(type(generator) is type(openai_generator) for generator in generators):
        generators.append(openai_generator)

    if not generators:
        generators.append(LocalOnlyGenerator())
    return generators


class LocalOnlyGenerator:
    @property
    def is_configured(self) -> bool:
        return False

    def generate(self, query: str, results: list[SearchResult]) -> str | None:
        return None

    def generate_general(self, query: str, memory_context: str = "") -> str | None:
        return None


def _sanitize_answer_text(answer: str) -> str:
    if not answer:
        return ""

    lines: list[str] = []
    for raw_line in answer.splitlines():
        line = raw_line.strip()
        if not line:
            if lines and lines[-1] != "":
                lines.append("")
            continue

        line = line.replace("**", "").replace("__", "")
        line = re.sub(r"\[([^\]]+)\]\((https?://[^\)]+)\)", r"\1", line)
        line = _strip_technical_label(line)
        if not line:
            continue

        normalized = normalize_for_matching(line)
        if any(term in normalized for term in ("metadata", "chunk aciklamasi", "description")):
            continue
        if normalized.startswith("kaynak") or normalized.startswith("source"):
            continue
        if re.match(r"^\d+\s+kaynagi ac\b", normalized):
            continue

        line = re.sub(r"https?://\S+", "", line).strip()
        if re.fullmatch(r"\d+[.)]?", line):
            continue
        if line:
            lines.append(line)

    sanitized = "\n".join(lines)
    sanitized = re.sub(r"\n{3,}", "\n\n", sanitized).strip()
    if not sanitized:
        return ""
    if FALLBACK_RESPONSE in sanitized:
        return FALLBACK_RESPONSE
    if "lütfen akademik ve uygun bir dil kullanınız" in sanitized.lower():
        return POLITE_LANGUAGE_RESPONSE
    return sanitized


def _strip_technical_label(line: str) -> str:
    patterns = (
        r"^(?:[^\w\s]+\s*)?(açıklama|aciklama|detaylar?|description)\s*:\s*(.+)$",
        r"^(?:[^\w\s]+\s*)?(sonuç|sonuc)\s*:\s*(.+)$",
    )
    for pattern in patterns:
        match = re.match(pattern, line, flags=re.IGNORECASE)
        if match:
            return match.group(2).strip()

    blocker_patterns = (
        r"^(?:[^\w\s]+\s*)?(metadata|chunk açıklaması|chunk aciklamasi)\s*:?.*$",
        r"^(?:[^\w\s]+\s*)?(kaynak|source|sources)\s*:?.*$",
    )
    for pattern in blocker_patterns:
        if re.match(pattern, line, flags=re.IGNORECASE):
            return ""
    return line


def _build_search_query(query: str) -> str:
    additions: list[str] = []
    if _is_contact_query(query):
        additions.extend(["telefon rehberi", "dekana sor", "e-posta", "adres", "contact", "phone"])
    if _is_announcement_query(query):
        additions.extend(["duyuru", "tüm duyurular", "haber", "announcement", "news"])
    if _is_exam_query(query):
        additions.extend(["sınav programı", "ara sınav", "vize", "final", "bütünleme", "exam schedule"])
    if _is_department_query(query):
        additions.extend(["bölüm", "department", *DEPARTMENT_TERMS[:6]])
    if _is_personnel_query(query):
        additions.extend(["akademik kadro", "akademikpersonel", "öğretim elemanı", "staff"])
    if _is_academic_calendar_query(query):
        additions.extend(["takvim", "akademik", "ders programı", "calendar"])
    if _is_menu_query(query):
        additions.extend(["yemek", "yemekhane", "menü", "cafeteria"])

    unique_additions: list[str] = []
    normalized_query = normalize_for_matching(query)
    for addition in additions:
        if normalize_for_matching(addition) not in normalized_query and addition not in unique_additions:
            unique_additions.append(addition)
    if not unique_additions:
        return query
    return f"{query} {' '.join(unique_additions)}"


def _passes_context_requirements(query: str, result: SearchResult) -> bool:
    if _is_faculty_query(query) and not _is_faculty_related(result):
        return False
    if _is_contact_query(query) and not _is_contact_related(query, result):
        return False
    if _is_personnel_query(query) and not _is_personnel_related(result):
        return False
    if _is_department_query(query) and not _is_department_related(result):
        return False
    if _is_announcement_query(query) and not _is_announcement_related(result):
        return False
    if _is_exam_query(query) and not _is_exam_related(result):
        return False
    if _is_academic_calendar_query(query) and not _is_academic_calendar_related(result):
        return False
    if _is_menu_query(query) and not _is_menu_related(result):
        return False
    return True


def _context_priority(query: str, result: SearchResult) -> int:
    priority = 0
    haystack = _haystack(result)
    query_key = _query_key(query)

    if _is_personnel_query(query):
        if "akademikpersonel" in result.chunk.url.lower():
            priority += 10
        if any(term in haystack for term in ("profesor", "docent", "arastirma gorevlisi")):
            priority += 5

    if _is_department_query(query):
        priority += min(sum(1 for term in DEPARTMENT_TERMS if normalize_for_matching(term) in haystack), 8)

    if _is_announcement_query(query):
        if "/duyuru2/" in result.chunk.url.lower():
            priority += 10
        if any(term in haystack for term in ("duyuru", "guncel", "haber")):
            priority += 4

    if _is_exam_query(query):
        if "/duyuru2/" in result.chunk.url.lower():
            priority += 6
        if any(term in haystack for term in ("sinav programi", "vize", "ara sinav", "butunleme")):
            priority += 5
        if "ara" in query_key or "vize" in query_key:
            if "ara sinav" in haystack or "vize" in haystack:
                priority += 4
            if "butunleme" in haystack and "ara sinav" not in haystack and "vize" not in haystack:
                priority -= 3

    if _is_contact_query(query):
        if any(term in haystack for term in ("telefon rehberi", "dekana sor", "kurumsal iletisim")):
            priority += 8
        if "akademikpersonel" in result.chunk.url.lower() and _is_faculty_query(query):
            priority -= 4

    if _is_academic_calendar_query(query) and "takvim" in haystack:
        priority += 5

    return priority


def _prefer_local_answer(query: str) -> bool:
    return any(
        checker(query)
        for checker in (
            _is_contact_query,
            _is_personnel_query,
            _is_department_query,
            _is_announcement_query,
            _is_exam_query,
            _is_academic_calendar_query,
        )
    )


def _query_key(query: str) -> str:
    return normalize_for_matching(query)


def _is_composition_request(query: str) -> bool:
    normalized = _query_key(query)
    return any(
        term in normalized
        for term in (
            "yaz",
            "duzelt",
            "düzelt",
            "gelistir",
            "geliştir",
            "iyilestir",
            "araştır",
            "arastir",
            "olustur",
            "oluştur",
            "hazirla",
            "hazırla",
            "rewrite",
            "write",
            "draft",
            "create",
            "compose",
            "fix",
            "improve",
            "summarize",
            "research",
            "اكتب",
            "اصلح",
            "حسن",
            "ابحث",
            "أنشئ",
            "لخص",
        )
    )


def _haystack(result: SearchResult) -> str:
    return normalize_for_matching(f"{result.chunk.url} {result.chunk.title} {result.chunk.text}")


def _response_emoji(query: str) -> str:
    if _is_announcement_query(query):
        return "📢"
    if _is_exam_query(query) or _is_academic_calendar_query(query):
        return "📅"
    if _is_personnel_query(query):
        return "👤"
    if _is_contact_query(query):
        return "📞"
    return "📌"


def _query_targets_iibf(query: str) -> bool:
    normalized = _query_key(query)
    return any(
        term in normalized
        for term in (
            "iibf",
            "iktisadi ve idari bilimler",
            "iktisadi idari bilimler",
            "feas",
            "faculty of economics and administrative sciences",
            "economics and administrative sciences",
            "الاقتصاد والعلوم الادارية",
        )
    )


def _matched_faculty_key(query: str) -> str:
    normalized = _query_key(query)
    for key, aliases in FACULTY_ALIAS_MAP.items():
        if any(_query_key(alias) in normalized for alias in aliases):
            return key
    return ""


def _other_faculty_requested(query: str) -> bool:
    faculty_key = _matched_faculty_key(query)
    return bool(faculty_key and faculty_key != "iibf")


def _find_dean_for_query(snapshot: dict, query: str) -> dict:
    senate_people = snapshot.get("senate_people", [])
    faculty_key = _matched_faculty_key(query) or "iibf"

    for item in senate_people:
        if _senate_designation_matches(clean_text(item.get("designation", "")), faculty_key):
            return item

    if faculty_key == "iibf":
        return snapshot.get("faculty_dean") or {}
    return {}


def _senate_designation_matches(designation: str, faculty_key: str) -> bool:
    designation_key = normalize_for_matching(designation)
    aliases = FACULTY_ALIAS_MAP.get(faculty_key, ())
    if not aliases:
        return False
    return "dekan" in designation_key and any(_query_key(alias) in designation_key for alias in aliases)


def _faculty_label_from_designation(designation: str) -> str:
    cleaned = clean_text(designation)
    if not cleaned:
        return ""
    return re.sub(r"\s+Dekan(?:ı|i| V\.)?$", "", cleaned, flags=re.IGNORECASE).strip()


def _looks_like_iibf_menu_query(query: str) -> bool:
    normalized = _query_key(query)
    if _other_faculty_requested(query):
        return False
    return any(
        term in normalized
        for term in (
            "misyon",
            "vizyon",
            "tanitim",
            "tanıtım",
            "dekanimizin mesaji",
            "dekanımızın mesajı",
            "yonetim",
            "yönetim",
            "sss",
            "sikca sorulan sorular",
            "sıkça sorulan sorular",
            "fakulte kurulu",
            "fakulte yonetim kurulu",
            "danisma kurulu",
            "kurulu",
            "kurul",
            "komisyon",
            "formlar",
            "mezun",
            "mevzuat",
            "organizasyon",
            "iletisim",
            "iletişim",
            "dekana sor",
            "iibf misyon",
        )
    )


def _extract_route_destination(query: str) -> str:
    cleaned = clean_text(query)
    patterns = (
        r"(?i)\b(.+?)\s+(?:nasil giderim|nasil gidebilirim|yol tarifi)\b",
        r"(?i)\bhow do i get to\s+(.+)$",
        r"(?i)\bhow can i get to\s+(.+)$",
        r"(?i)\bdirections to\s+(.+)$",
        r"(?i)\b(.+?)\s+(?:adresi|adresi)\b",
        r"(?i)\b(?:كيف اذهب الى|كيف اصل الى)\s+(.+)$",
    )
    for pattern in patterns:
        match = re.search(pattern, cleaned)
        if match:
            return clean_text(match.group(1).strip(" ?"))

    lowered = _query_key(query)
    if any(term in lowered for term in ("iibf", "kafkas universitesi", "kampus", "kampus", "feas")):
        return "Kafkas Üniversitesi İİBF"
    return ""


def _is_faculty_query(query: str) -> bool:
    normalized = _query_key(query)
    if _other_faculty_requested(query):
        return False
    return _query_targets_iibf(query) or any(
        term in normalized
        for term in (
            "fakulte",
            "faculty",
            "جامعة قفقاس",
            "كلية",
        )
    )


def _is_contact_query(query: str) -> bool:
    normalized = _query_key(query)
    if _is_composition_request(query):
        return False
    return any(
        term in normalized
        for term in (
            "adres",
            "e posta",
            "email",
            "iletisim",
            "mail",
            "telefon",
            "rehber",
            "numara",
            "contact",
            "phone",
            "تواصل",
            "اتصال",
            "هاتف",
            "بريد",
            "ايميل",
        )
    )


def _is_personnel_query(query: str) -> bool:
    normalized = _query_key(query)
    return any(
        term in normalized
        for term in (
            "akademik kadro",
            "akademik personel",
            "idari gorevliler",
            "idari gorev",
            "bolum baskani",
            "idari personel",
            "personel",
            "ogretim elemani",
            "ogretim uyesi",
            "arastirma gorevlisi",
            "staff",
            "academic staff",
            "faculty members",
            "كادر",
            "هيئة التدريس",
            "موظفين",
        )
    )


def _is_department_query(query: str) -> bool:
    normalized = _query_key(query)
    return any(
        term in normalized
        for term in (
            "bolum",
            "bolumler",
            "akademik program",
            "department",
            "departments",
            "ybs",
            "iktisat",
            "isletme",
            "sbky",
            "sbui",
            "utl",
            "قسم",
            "الاقسام",
            "نظم المعلومات",
        )
    )


def _is_announcement_query(query: str) -> bool:
    normalized = _query_key(query)
    return any(
        term in normalized
        for term in (
            "duyuru",
            "duyurular",
            "haber",
            "haberler",
            "etkinlik",
            "etkinlikler",
            "announcement",
            "announcements",
            "news",
            "event",
            "events",
            "اعلان",
            "اعلانات",
            "اخبار",
            "فعاليات",
        )
    )


def _is_exam_query(query: str) -> bool:
    normalized = _query_key(query)
    return any(
        term in normalized
        for term in ("sinav", "vize", "final", "butunleme", "mazeret", "exam", "midterm", "makeup", "امتحان", "اختبار")
    )


def _is_academic_calendar_query(query: str) -> bool:
    normalized = _query_key(query)
    return (
        "akademik takvim" in normalized
        or ("akademik" in normalized and "takvim" in normalized)
        or "academic calendar" in normalized
        or "التقويم الاكاديمي" in normalized
    )


def _is_menu_query(query: str) -> bool:
    normalized = _query_key(query)
    return any(
        term in normalized
        for term in ("yemek", "menu", "menusu", "yemekhane", "cafeteria", "food", "dining", "طعام", "مقصف", "قائمة")
    )


def _is_location_query(query: str) -> bool:
    normalized = _query_key(query)
    return any(
        term in normalized
        for term in (
            "nerede",
            "konum",
            "adres",
            "harita",
            "maps",
            "location",
            "where",
            "map",
            "nasil giderim",
            "nasil gidebilirim",
            "yol tarifi",
            "route",
            "directions",
            "how do i get",
            "how can i get",
            "get to",
            "اين",
            "موقع",
            "خريطة",
            "كيف اذهب",
            "كيف اصل",
        )
    )


def _is_management_query(query: str) -> bool:
    normalized = _query_key(query)
    return any(
        term in normalized
        for term in (
            "rektor",
            "senato",
            "dekanlik",
            "dekanliklar",
            "rektor yardimci",
            "rector",
            "vice rector",
            "senate",
            "deans",
            "عميد",
            "السناتور",
            "رئيس الجامعة",
        )
    )


def _is_faculty_related(result: SearchResult) -> bool:
    haystack = _haystack(result)
    return any(
        term in haystack
        for term in (
            "/iibf",
            "iibf",
            "iktisadi ve idari bilimler",
            "faculty of economics",
        )
    )


def _is_contact_related(query: str, result: SearchResult) -> bool:
    haystack = _haystack(result)
    if _is_faculty_query(query) and "akademikpersonel" in result.chunk.url.lower():
        return False
    if any(term in haystack for term in ("telefon rehberi", "dekana sor", "kurumsal iletisim")):
        return True
    return bool(
        re.search(r"[\w.+-]+@[\w.-]+\.\w+", result.chunk.text)
        or re.search(r"\b0?\s*\(?474\)?", result.chunk.text)
    )


def _is_personnel_related(result: SearchResult) -> bool:
    haystack = _haystack(result)
    return "akademikpersonel" in result.chunk.url.lower() or any(
        term in haystack
        for term in (
            "profesor",
            "docent",
            "doktor ogretim uyesi",
            "arastirma gorevlisi",
        )
    )


def _is_department_related(result: SearchResult) -> bool:
    haystack = _haystack(result)
    return "bolum" in haystack or any(
        normalize_for_matching(term) in haystack for term in DEPARTMENT_TERMS
    )


def _is_announcement_related(result: SearchResult) -> bool:
    haystack = _haystack(result)
    return "/duyuru2/" in result.chunk.url.lower() or any(
        term in haystack for term in ("duyuru", "haber", "etkinlik")
    )


def _is_exam_related(result: SearchResult) -> bool:
    haystack = _haystack(result)
    return any(term in haystack for term in ("sinav", "vize", "final", "butunleme", "mazeret"))


def _is_academic_calendar_related(result: SearchResult) -> bool:
    haystack = _haystack(result)
    return "takvim" in haystack or ("akademik" in haystack and "ders programi" in haystack)


def _is_menu_related(result: SearchResult) -> bool:
    haystack = _haystack(result)
    return any(term in haystack for term in ("yemek", "menu", "yemekhane"))


DEPARTMENT_TERMS = (
    "iktisat",
    "işletme",
    "siyaset bilimi",
    "kamu yönetimi",
    "uluslararası ilişkiler",
    "uluslararasi iliskiler",
    "sağlık yönetimi",
    "saglik yonetimi",
    "yönetim bilişim",
    "yonetim bilisim",
    "elektronik ticaret",
    "uluslararası ticaret",
    "uluslararasi ticaret",
    "lojistik",
)
