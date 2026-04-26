(function () {
  var STORAGE_KEY = "kaucan-conversations-v3";
  var THEME_KEY = "kaucan-theme";
  var CLIENT_ID_KEY = "kaucan-client-id";
  var LANGUAGE_KEY = "kaucan-language";
  var WELCOME_MESSAGES = {
    tr: "👋 Merhaba, ben KAÜCAN Beta - Kafkas Üniversitesi Dijital Asistanı. İİBF hakkında duyurular, akademik bilgiler, personel, iletişim, sınavlar, yemek menüsü, yazım desteği ve genel konularda yardımcı olabilirim.",
    en: "👋 Hello, I am KAUCAN Beta - the Digital Assistant of Kafkas University. I can help with announcements, academic information, staff, contact, exams, cafeteria menu, writing, and general questions.",
    ar: "👋 مرحبًا، أنا KAÜCAN Beta، المساعد الرقمي لجامعة قفقاس. يمكنني المساعدة في الإعلانات والمعلومات الأكاديمية والكوادر والاتصال والامتحانات وقائمة الطعام والكتابة والأسئلة العامة.",
  };
  var FALLBACK_MESSAGES = {
    tr: "⚠️ Bu konuda güvenilir bir bilgiye ulaşamadım. En doğru bilgi için fakülte ile iletişime geçmenizi öneririm.",
    en: "⚠️ I could not reach reliable information on this topic. For the most accurate information, please contact the faculty directly.",
    ar: "⚠️ لم أتمكن من الوصول إلى معلومة موثوقة حول هذا الموضوع. للحصول على أدق معلومة، يُنصح بالتواصل مع الكلية مباشرة.",
  };
  var INPUT_PLACEHOLDERS = {
    tr: "Sorunuzu yazınız veya sesli yazmayı kullanınız...",
    en: "Type your question or use voice dictation...",
    ar: "اكتب سؤالك أو استخدم الإملاء الصوتي...",
  };
  var UI_TEXTS = {
    tr: {
      documentTitle: "KAÜCAN | Kafkas Üniversitesi Dijital Asistanı",
      brandHeading: "Kafkas Üniversitesi İktisadi ve İdari Bilimler Fakültesi",
      languageNames: {
        tr: "Türkçe",
        en: "English",
        ar: "العربية",
      },
      languageLabel: "Sohbet dili seçin",
      historyEyebrow: "Geçmiş",
      historyTitle: "Konuşma Geçmişi",
      historySearchLabel: "Sohbetlerde ara",
      historySearchPlaceholder: "Sohbetlerde ara",
      historyOpen: "Konuşma geçmişi",
      historyClose: "Geçmişi kapat",
      newChat: "Yeni Sohbet",
      deleteAll: "Tümünü Sil",
      chatEyebrow: "Sohbet",
      chatTitle: "KAÜCAN CHATBOT",
      clear: "Temizle",
      quickPromptsTitle: "Hızlı Sorular",
      chips: {
        announcements: "📢 Güncel duyurular nelerdir?",
        exams: "📅 Sınav programı hakkında bilgi verir misiniz?",
        staff: "👤 Akademik personel hakkında bilgi verir misiniz?",
        contact: "📞 Fakülte iletişim bilgileri nelerdir?",
      },
      quickLinks: {
        menu: "🍽️ Yemekhane Menüsü",
        calendar: "📅 Akademik Takvim",
        obs: "✅ OBS",
        wifi: "🌐 Okul İnterneti",
        library: "📚 Kütüphane",
        ebys: "🗂️ EBYS",
        directory: "📞 Telefon Rehberi",
      },
      highlights: {
        announcements: "Duyurular",
        news: "Haberler",
        events: "Etkinlikler",
      },
      status: {
        loading: "Hazırlanıyor",
        ready: "Hazır",
        preparing: "Yanıt hazırlanıyor",
        requestingLocation: "Konum izni isteniyor",
        locationDenied: "Konum izni verilmedi",
        locationUnavailable: "Konum alınamadı",
        error: "Hata",
        connection: "Bağlantı hatası",
        indexing: "İndeks bekleniyor",
        serviceReady: "Servis hazır",
        listening: "Dinleniyor",
        micPermission: "Mikrofon izni gerekli",
        voiceStopped: "Sesli yazma durdu",
        micFailed: "Mikrofon başlatılamadı",
      },
      history: {
        empty: "Aranan başlıkla eşleşen sohbet bulunamadı.",
        share: "Paylaş",
        edit: "Başlığı düzenle",
        delete: "Sil",
        editPrompt: "Sohbet başlığını düzenleyin:",
      },
      feedback: {
        up: "Yararlı",
        down: "Geliştirilmeli",
      },
      share: {
        title: "KAÜCAN Sohbeti",
        userLabel: "Kullanıcı",
        botLabel: "KAÜCAN",
      },
      voice: {
        start: "Sesli yazma",
        stop: "Dikteyi durdur",
        unsupported: "Tarayıcı sesli yazmayı desteklemiyor",
      },
      theme: {
        label: "Temayı değiştir",
      },
      send: {
        label: "Mesaj gönder",
      },
      copy: {
        label: "Kodu kopyala",
        success: "Kod kopyalandı",
        failure: "Kod kopyalanamadı",
      },
      typingLabel: "KAÜCAN yazıyor",
      defaultTitle: "Yeni Sohbet",
    },
    en: {
      documentTitle: "KAUCAN | Kafkas University Digital Assistant",
      brandHeading: "Kafkas University Faculty of Economics and Administrative Sciences",
      languageNames: {
        tr: "Turkish",
        en: "English",
        ar: "Arabic",
      },
      languageLabel: "Select chat language",
      historyEyebrow: "History",
      historyTitle: "Conversation History",
      historySearchLabel: "Search conversations",
      historySearchPlaceholder: "Search conversations",
      historyOpen: "Conversation history",
      historyClose: "Close history",
      newChat: "New Chat",
      deleteAll: "Delete All",
      chatEyebrow: "Chat",
      chatTitle: "KAUCAN CHATBOT",
      clear: "Clear",
      quickPromptsTitle: "Quick Questions",
      chips: {
        announcements: "📢 What are the current announcements?",
        exams: "📅 Could you share the exam schedule?",
        staff: "👤 Could you provide academic staff information?",
        contact: "📞 What are the faculty contact details?",
      },
      quickLinks: {
        menu: "🍽️ Cafeteria Menu",
        calendar: "📅 Academic Calendar",
        obs: "✅ OBS",
        wifi: "🌐 Campus Internet",
        library: "📚 Library",
        ebys: "🗂️ EBYS",
        directory: "📞 Phone Directory",
      },
      highlights: {
        announcements: "Announcements",
        news: "News",
        events: "Events",
      },
      status: {
        loading: "Loading",
        ready: "Ready",
        preparing: "Preparing answer",
        requestingLocation: "Requesting location permission",
        locationDenied: "Location permission denied",
        locationUnavailable: "Location could not be retrieved",
        error: "Error",
        connection: "Connection error",
        indexing: "Index pending",
        serviceReady: "Service ready",
        listening: "Listening",
        micPermission: "Microphone permission required",
        voiceStopped: "Voice input stopped",
        micFailed: "Microphone could not start",
      },
      history: {
        empty: "No conversation matches the current search.",
        share: "Share",
        edit: "Edit title",
        delete: "Delete",
        editPrompt: "Edit the conversation title:",
      },
      feedback: {
        up: "Helpful",
        down: "Needs work",
      },
      share: {
        title: "KAUCAN Chat",
        userLabel: "User",
        botLabel: "KAUCAN",
      },
      voice: {
        start: "Voice dictation",
        stop: "Stop dictation",
        unsupported: "This browser does not support voice dictation",
      },
      theme: {
        label: "Change theme",
      },
      send: {
        label: "Send message",
      },
      copy: {
        label: "Copy code",
        success: "Code copied",
        failure: "Code could not be copied",
      },
      typingLabel: "KAUCAN is typing",
      defaultTitle: "New Chat",
    },
    ar: {
      documentTitle: "KAÜCAN | المساعد الرقمي لجامعة قفقاس",
      brandHeading: "جامعة قفقاس كلية الاقتصاد والعلوم الإدارية",
      languageNames: {
        tr: "التركية",
        en: "الإنجليزية",
        ar: "العربية",
      },
      languageLabel: "اختر لغة المحادثة",
      historyEyebrow: "السجل",
      historyTitle: "سجل المحادثات",
      historySearchLabel: "ابحث في المحادثات",
      historySearchPlaceholder: "ابحث في المحادثات",
      historyOpen: "سجل المحادثات",
      historyClose: "إغلاق السجل",
      newChat: "دردشة جديدة",
      deleteAll: "حذف الكل",
      chatEyebrow: "المحادثة",
      chatTitle: "KAÜCAN CHATBOT",
      clear: "مسح",
      quickPromptsTitle: "أسئلة سريعة",
      chips: {
        announcements: "📢 ما هي الإعلانات الحالية؟",
        exams: "📅 هل يمكن مشاركة برنامج الامتحانات؟",
        staff: "👤 هل يمكن تقديم معلومات عن الكادر الأكاديمي؟",
        contact: "📞 ما هي معلومات التواصل مع الكلية؟",
      },
      quickLinks: {
        menu: "🍽️ قائمة الطعام",
        calendar: "📅 التقويم الأكاديمي",
        obs: "✅ نظام OBS",
        wifi: "🌐 إنترنت الجامعة",
        library: "📚 المكتبة",
        ebys: "🗂️ نظام EBYS",
        directory: "📞 دليل الهاتف",
      },
      highlights: {
        announcements: "الإعلانات",
        news: "الأخبار",
        events: "الفعاليات",
      },
      status: {
        loading: "جارٍ التحضير",
        ready: "جاهز",
        preparing: "جارٍ إعداد الإجابة",
        requestingLocation: "جارٍ طلب إذن الموقع",
        locationDenied: "تم رفض إذن الموقع",
        locationUnavailable: "تعذر الحصول على الموقع",
        error: "خطأ",
        connection: "خطأ في الاتصال",
        indexing: "الفهرس قيد الانتظار",
        serviceReady: "الخدمة جاهزة",
        listening: "جارٍ الاستماع",
        micPermission: "مطلوب إذن الميكروفون",
        voiceStopped: "تم إيقاف الإملاء الصوتي",
        micFailed: "تعذر تشغيل الميكروفون",
      },
      history: {
        empty: "لا توجد محادثة مطابقة لبحثك.",
        share: "مشاركة",
        edit: "تعديل العنوان",
        delete: "حذف",
        editPrompt: "عدّل عنوان المحادثة:",
      },
      feedback: {
        up: "مفيد",
        down: "بحاجة لتحسين",
      },
      share: {
        title: "محادثة KAÜCAN",
        userLabel: "المستخدم",
        botLabel: "KAÜCAN",
      },
      voice: {
        start: "إملاء صوتي",
        stop: "إيقاف الإملاء",
        unsupported: "هذا المتصفح لا يدعم الإملاء الصوتي",
      },
      theme: {
        label: "تغيير النمط",
      },
      send: {
        label: "إرسال الرسالة",
      },
      copy: {
        label: "نسخ الكود",
        success: "تم نسخ الكود",
        failure: "تعذر نسخ الكود",
      },
      typingLabel: "KAÜCAN يكتب الآن",
      defaultTitle: "دردشة جديدة",
    },
  };
  var HIGHLIGHT_FALLBACKS = {
    announcements: {
      title: "İİBF Duyuruları",
      url: "https://www.kafkas.edu.tr/iibf/tr/tumduyurular2",
      summary: "Güncel duyurular için resmi İİBF duyuru sayfasını açabilirsiniz.",
    },
    news: {
      title: "İİBF Haberleri",
      url: "https://www.kafkas.edu.tr/iibf/tr/tumHaberler",
      summary: "Güncel haberler için resmi İİBF haberler sayfasını açabilirsiniz.",
    },
    events: {
      title: "İİBF Etkinlikleri",
      url: "https://www.kafkas.edu.tr/iibf/tr/tumEtkinlikler2",
      summary: "Güncel etkinlikler için resmi İİBF etkinlikler sayfasını açabilirsiniz.",
    },
  };

  var form = document.getElementById("askForm");
  var input = document.getElementById("questionInput");
  var messages = document.getElementById("messages");
  var submitButton = document.getElementById("submitButton");
  var clearButton = document.getElementById("clearButton");
  var voiceButton = document.getElementById("voiceButton");
  var quickPromptsShell = document.getElementById("quickPromptsShell");
  var statusBadge = document.getElementById("statusBadge");
  var typingRow = document.getElementById("typingRow");
  var ambientCanvas = document.getElementById("ambientCanvas");
  var cursorLayer = document.getElementById("cursorLayer");
  var cursorRing = document.getElementById("cursorRing");
  var cursorDot = document.getElementById("cursorDot");
  var chips = document.querySelectorAll(".query-chip");
  var brandLogo = document.getElementById("brandLogo");
  var brandFacultyLogo = document.getElementById("brandFacultyLogo");
  var brandFallback = document.getElementById("brandFallback");
  var initialChatLogo = document.getElementById("initialChatLogo");
  var typingChatLogo = document.getElementById("typingChatLogo");
  var historyPanel = document.getElementById("historyPanel");
  var historyBackdrop = document.getElementById("historyBackdrop");
  var historyToggleButton = document.getElementById("historyToggleButton");
  var historyCloseButton = document.getElementById("historyCloseButton");
  var newChatButton = document.getElementById("newChatButton");
  var deleteAllChatsButton = document.getElementById("deleteAllChatsButton");
  var historySearchInput = document.getElementById("historySearchInput");
  var historyList = document.getElementById("historyList");
  var themeToggleButton = document.getElementById("themeToggleButton");
  var themeToggleIcon = document.getElementById("themeToggleIcon");
  var languageSelect = document.getElementById("languageSelect");
  var highlightNavButtons = document.querySelectorAll(".highlight-nav");
  var highlightTracks = {
    announcements: document.getElementById("announcementsTrack"),
    news: document.getElementById("newsTrack"),
    events: document.getElementById("eventsTrack"),
  };
  var SpeechRecognitionClass = window.SpeechRecognition || window.webkitSpeechRecognition || null;

  var audioState = {
    context: null,
    primed: false,
  };
  var runtimeBranding = {
    chatLogoUrl: initialChatLogo ? initialChatLogo.getAttribute("src") : null,
  };
  var state = {
    conversations: [],
    activeConversationId: null,
    pendingConversationId: null,
    theme: "light",
    highlights: {
      announcements: [],
      news: [],
      events: [],
    },
    carouselIndex: {
      announcements: 0,
      news: 0,
      events: 0,
    },
    voice: {
      supported: !!SpeechRecognitionClass,
      listening: false,
      recognition: null,
      baseText: "",
      denied: false,
    },
    clientId: "",
    preferredLanguage: "tr",
    location: {
      latitude: null,
      longitude: null,
      updatedAt: 0,
      permission: "prompt",
    },
  };
  var ambientState = {
    canvas: ambientCanvas,
    context: null,
    width: 0,
    height: 0,
    dpr: 1,
    particles: [],
    animationFrame: 0,
    pointer: {
      x: 0,
      y: 0,
      active: false,
      down: false,
      vx: 0,
      vy: 0,
    },
  };
  var toastElement = null;
  var toastTimer = 0;

  function getUiLanguage() {
    return state.preferredLanguage || "tr";
  }

  function getWelcomeMessage(language) {
    return WELCOME_MESSAGES[language] || WELCOME_MESSAGES.tr;
  }

  function getFallbackMessage(language) {
    return FALLBACK_MESSAGES[language] || FALLBACK_MESSAGES.tr;
  }

  function updateComposerCopy() {
    input.placeholder = INPUT_PLACEHOLDERS[getUiLanguage()] || INPUT_PLACEHOLDERS.tr;
  }

  function getUiText() {
    return UI_TEXTS[getUiLanguage()] || UI_TEXTS.tr;
  }

  function getDefaultConversationTitle() {
    return getUiText().defaultTitle || UI_TEXTS.tr.defaultTitle;
  }

  function isDefaultConversationTitle(value) {
    var titles = [UI_TEXTS.tr.defaultTitle, UI_TEXTS.en.defaultTitle, UI_TEXTS.ar.defaultTitle];
    return titles.indexOf(String(value || "").trim()) !== -1;
  }

  function translateStatusText(text) {
    var ui = getUiText();
    var input = String(text || "");
    var languageKeys = Object.keys(UI_TEXTS);
    var index;

    for (index = 0; index < languageKeys.length; index += 1) {
      var statusMap = UI_TEXTS[languageKeys[index]].status || {};
      var statusKeys = Object.keys(statusMap);
      var innerIndex;
      for (innerIndex = 0; innerIndex < statusKeys.length; innerIndex += 1) {
        var key = statusKeys[innerIndex];
        if (statusMap[key] === input && ui.status[key]) {
          return ui.status[key];
        }
      }
    }
    return input;
  }

  function applyInterfaceLanguage() {
    var ui = getUiText();

    document.documentElement.lang = getUiLanguage() === "ar" ? "ar" : getUiLanguage();
    document.documentElement.dir = getUiLanguage() === "ar" ? "rtl" : "ltr";
    document.title = ui.documentTitle;

    if (document.getElementById("historyEyebrow")) {
      document.getElementById("historyEyebrow").textContent = ui.historyEyebrow;
    }
    if (document.getElementById("historyTitle")) {
      document.getElementById("historyTitle").textContent = ui.historyTitle;
    }
    if (document.getElementById("historySearchLabel")) {
      document.getElementById("historySearchLabel").textContent = ui.historySearchLabel;
    }
    if (historySearchInput) {
      historySearchInput.placeholder = ui.historySearchPlaceholder;
    }
    if (historyToggleButton) {
      historyToggleButton.title = ui.historyOpen;
      historyToggleButton.setAttribute("aria-label", ui.historyOpen);
    }
    if (historyCloseButton) {
      historyCloseButton.title = ui.historyClose;
      historyCloseButton.setAttribute("aria-label", ui.historyClose);
    }
    if (newChatButton) {
      newChatButton.textContent = ui.newChat;
    }
    if (deleteAllChatsButton) {
      deleteAllChatsButton.textContent = ui.deleteAll;
      deleteAllChatsButton.title = ui.deleteAll;
      deleteAllChatsButton.setAttribute("aria-label", ui.deleteAll);
    }
    if (document.getElementById("brandHeading")) {
      document.getElementById("brandHeading").textContent = ui.brandHeading;
    }
    if (document.getElementById("chatEyebrow")) {
      document.getElementById("chatEyebrow").textContent = ui.chatEyebrow;
    }
    if (document.getElementById("chatTitle")) {
      document.getElementById("chatTitle").textContent = ui.chatTitle;
    }
    if (clearButton) {
      clearButton.textContent = ui.clear;
    }
    if (document.getElementById("quickPromptsTitle")) {
      document.getElementById("quickPromptsTitle").textContent = ui.quickPromptsTitle;
    }
    if (document.getElementById("chipAnnouncements")) {
      document.getElementById("chipAnnouncements").textContent = ui.chips.announcements;
    }
    if (document.getElementById("chipExams")) {
      document.getElementById("chipExams").textContent = ui.chips.exams;
    }
    if (document.getElementById("chipStaff")) {
      document.getElementById("chipStaff").textContent = ui.chips.staff;
    }
    if (document.getElementById("chipContact")) {
      document.getElementById("chipContact").textContent = ui.chips.contact;
    }
    if (document.getElementById("quickLinkMenu")) {
      document.getElementById("quickLinkMenu").textContent = ui.quickLinks.menu;
    }
    if (document.getElementById("quickLinkCalendar")) {
      document.getElementById("quickLinkCalendar").textContent = ui.quickLinks.calendar;
    }
    if (document.getElementById("quickLinkObs")) {
      document.getElementById("quickLinkObs").textContent = ui.quickLinks.obs;
    }
    if (document.getElementById("quickLinkWifi")) {
      document.getElementById("quickLinkWifi").textContent = ui.quickLinks.wifi;
    }
    if (document.getElementById("quickLinkLibrary")) {
      document.getElementById("quickLinkLibrary").textContent = ui.quickLinks.library;
    }
    if (document.getElementById("quickLinkEbys")) {
      document.getElementById("quickLinkEbys").textContent = ui.quickLinks.ebys;
    }
    if (document.getElementById("quickLinkDirectory")) {
      document.getElementById("quickLinkDirectory").textContent = ui.quickLinks.directory;
    }
    if (document.getElementById("announcementsTitle")) {
      document.getElementById("announcementsTitle").textContent = ui.highlights.announcements;
    }
    if (document.getElementById("newsTitle")) {
      document.getElementById("newsTitle").textContent = ui.highlights.news;
    }
    if (document.getElementById("eventsTitle")) {
      document.getElementById("eventsTitle").textContent = ui.highlights.events;
    }
    if (themeToggleButton) {
      themeToggleButton.title = ui.theme.label;
      themeToggleButton.setAttribute("aria-label", ui.theme.label);
    }
    if (languageSelect) {
      languageSelect.title = ui.languageLabel;
      languageSelect.setAttribute("aria-label", ui.languageLabel);
      Array.prototype.forEach.call(languageSelect.options, function (option) {
        if (ui.languageNames[option.value]) {
          option.textContent = ui.languageNames[option.value];
        }
      });
    }
    if (voiceButton) {
      voiceButton.title = state.voice.listening ? ui.voice.stop : ui.voice.start;
      voiceButton.setAttribute("aria-label", state.voice.listening ? ui.voice.stop : ui.voice.start);
    }
    if (submitButton) {
      submitButton.title = ui.send.label;
      submitButton.setAttribute("aria-label", ui.send.label);
    }
    if (typingRow) {
      typingRow.setAttribute("aria-label", ui.typingLabel);
    }
    updateComposerCopy();
    if (statusBadge) {
      var currentStatusText = String(statusBadge.textContent || "").replace(/\s+/g, " ").trim();
      var currentStateName = statusBadge.classList.contains("error")
        ? "error"
        : statusBadge.classList.contains("busy")
          ? "busy"
          : "ready";
      if (currentStatusText) {
        setStatus(currentStatusText, currentStateName);
      }
    }
  }

  function refreshLanguageSensitiveConversations() {
    state.conversations.forEach(function (conversation) {
      if (isDefaultConversationTitle(conversation.title)) {
        conversation.title = getDefaultConversationTitle();
      }
      if (
        conversation.messages.length === 1 &&
        conversation.messages[0] &&
        conversation.messages[0].role === "assistant" &&
        conversation.messages[0].status === "greeting"
      ) {
        conversation.messages[0].text = getWelcomeMessage(getUiLanguage());
      }
    });
  }

  function setStatus(text, stateName) {
    stateName = stateName || "ready";
    text = translateStatusText(text);
    statusBadge.innerHTML = "";

    var dot = document.createElement("span");
    dot.className = "status-dot";
    statusBadge.appendChild(dot);
    statusBadge.appendChild(document.createTextNode(text));
    statusBadge.className = stateName === "ready" ? "status" : "status " + stateName;
  }

  function createUserAvatarIcon() {
    var wrapper = document.createElement("span");
    wrapper.className = "avatar-icon";
    wrapper.innerHTML =
      '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">' +
      '<path d="M15.75 6.75a3.75 3.75 0 1 1-7.5 0a3.75 3.75 0 0 1 7.5 0Z" />' +
      '<path d="M4.5 20.118a7.5 7.5 0 0 1 15 0A17.933 17.933 0 0 1 12 21.75a17.933 17.933 0 0 1-7.5-1.632Z" />' +
      "</svg>";
    return wrapper;
  }

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function linkify(value) {
    return String(value || "").replace(
      /(https?:\/\/[^\s<]+)/g,
      '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>'
    );
  }

  function dedupeSources(sources) {
    var unique = [];
    var seen = {};
    var index;

    sources = sources || [];
    for (index = 0; index < sources.length; index += 1) {
      if (!sources[index] || !sources[index].url || seen[sources[index].url]) {
        continue;
      }
      seen[sources[index].url] = true;
      unique.push(sources[index]);
    }

    return unique;
  }

  function normalizeAssistantLine(line) {
    var cleaned = String(line || "").replace(/\*\*/g, "").replace(/__/g, "").trim();
    if (!cleaned) {
      return "";
    }

    cleaned = cleaned.replace(/^(?:📖|📎)?\s*(açıklama|description|detaylar?)\s*:\s*/i, "");
    cleaned = cleaned.replace(/^(?:✅)?\s*(sonuç|sonuc|result)\s*:\s*/i, "");

    if (/^(?:🔗)?\s*(kaynak|source|sources)\s*:?.*$/i.test(cleaned)) {
      return "";
    }

    if (/^(metadata|chunk açıklaması|chunk aciklamasi)\s*:?.*$/i.test(cleaned)) {
      return "";
    }

    if (/^\d+[.)]?$/.test(cleaned)) {
      return "";
    }

    return cleaned;
  }

  function sanitizeAssistantText(text) {
    var lines = String(text || "").split("\n");
    var cleaned = [];
    var index;

    for (index = 0; index < lines.length; index += 1) {
      var normalized = normalizeAssistantLine(lines[index]);
      if (!normalized && (!cleaned.length || cleaned[cleaned.length - 1] === "")) {
        continue;
      }
      cleaned.push(normalized);
    }

    return cleaned.join("\n").replace(/\n{3,}/g, "\n\n").trim();
  }

  function renderBlock(block) {
    var lines = String(block || "")
      .split("\n")
      .map(function (line) {
        return line.trim();
      })
      .filter(function (line) {
        return !!line;
      });

    if (!lines.length) {
      return "";
    }

    var allBullets = lines.every(function (line) {
      return /^[•-]\s+/.test(line);
    });

    if (allBullets) {
      return (
        "<ul>" +
        lines
          .map(function (line) {
            return "<li>" + linkify(escapeHtml(line.replace(/^[•-]\s+/, ""))) + "</li>";
          })
          .join("") +
        "</ul>"
      );
    }

    if (
      lines.length > 1 &&
      !/^[•-]\s+/.test(lines[0]) &&
      lines.slice(1).every(function (line) {
        return /^[•-]\s+/.test(line);
      })
    ) {
      return (
        "<p>" +
        linkify(escapeHtml(lines[0])) +
        "</p><ul>" +
        lines
          .slice(1)
          .map(function (line) {
            return "<li>" + linkify(escapeHtml(line.replace(/^[•-]\s+/, ""))) + "</li>";
          })
          .join("") +
        "</ul>"
      );
    }

    return "<p>" + linkify(escapeHtml(lines.join("\n"))).replace(/\n/g, "<br />") + "</p>";
  }

  function renderRichText(text) {
    return sanitizeAssistantText(text)
      .split(/\n{2,}/)
      .map(function (block) {
        return renderBlock(block);
      })
      .join("");
  }

  function renderAssistantText(text) {
    var sourceText = String(text || "");
    if (!sourceText.trim()) {
      return "<p>" + escapeHtml(getFallbackMessage(getUiLanguage())) + "</p>";
    }

    var parts = sourceText.split("```");
    var html = [];
    var index;

    for (index = 0; index < parts.length; index += 1) {
      if (index % 2 === 1) {
        var code = parts[index].replace(/^\s*[a-z0-9_+-]+\n/i, "").replace(/^\n+|\n+$/g, "");
        if (code) {
          html.push('<pre class="code-block"><code>' + escapeHtml(code) + "</code></pre>");
        }
      } else {
        var rich = renderRichText(parts[index]);
        if (rich) {
          html.push(rich);
        }
      }
    }

    return html.length ? html.join("") : "<p>" + escapeHtml(getFallbackMessage(getUiLanguage())) + "</p>";
  }

  function renderUserText(text) {
    return "<p>" + escapeHtml(text) + "</p>";
  }

  function renderSources(sources) {
    var uniqueSources = dedupeSources(sources);
    var wrapper;
    var index;

    if (!uniqueSources.length) {
      return null;
    }

    wrapper = document.createElement("div");
    wrapper.className = "source-links";

    for (index = 0; index < uniqueSources.length; index += 1) {
      var link = document.createElement("a");
      var href = uniqueSources[index].url || "";
      link.className = "source-link";
      link.href = href;
      if (!/^tel:|^mailto:/i.test(href)) {
        link.target = "_blank";
        link.rel = "noopener noreferrer";
      }
      link.textContent = uniqueSources[index].title || "🔗 " + (index + 1);
      wrapper.appendChild(link);
    }

    return wrapper;
  }

  function ensureToast() {
    if (toastElement) {
      return toastElement;
    }

    toastElement = document.createElement("div");
    toastElement.className = "copy-toast";
    toastElement.setAttribute("role", "status");
    toastElement.setAttribute("aria-live", "polite");
    document.body.appendChild(toastElement);
    return toastElement;
  }

  function showToast(message) {
    var toast = ensureToast();
    window.clearTimeout(toastTimer);
    toast.textContent = String(message || "").trim();
    toast.classList.add("visible");
    toastTimer = window.setTimeout(function () {
      toast.classList.remove("visible");
    }, 1800);
  }

  function truncateText(text, limit) {
    var value = String(text || "").replace(/\s+/g, " ").trim();
    if (!value || value.length <= limit) {
      return value;
    }
    return value.slice(0, Math.max(0, limit - 1)).trim() + "…";
  }

  function supportsAmbientScene() {
    return !!(ambientState.canvas && ambientState.canvas.getContext);
  }

  function resizeAmbientScene() {
    var canvas = ambientState.canvas;
    var context;
    var density;
    var symbols;
    var targetCount;
    var index;

    if (!supportsAmbientScene()) {
      return;
    }

    context = ambientState.context || ambientState.canvas.getContext("2d");
    if (!context) {
      return;
    }

    ambientState.context = context;
    ambientState.dpr = Math.max(1, Math.min(window.devicePixelRatio || 1, 2));
    ambientState.width = window.innerWidth;
    ambientState.height = window.innerHeight;
    canvas.width = Math.floor(ambientState.width * ambientState.dpr);
    canvas.height = Math.floor(ambientState.height * ambientState.dpr);
    context.setTransform(ambientState.dpr, 0, 0, ambientState.dpr, 0, 0);

    density = Math.max(36, Math.min(ambientState.width / 24, 96));
    symbols = ["0", "1", "A", "T", "G", "C", "U", "</>", "{}", "RNA", "DNA", "[]"];
    targetCount = Math.round(density);

    if (ambientState.particles.length > targetCount) {
      ambientState.particles.length = targetCount;
    }

    for (index = ambientState.particles.length; index < targetCount; index += 1) {
      ambientState.particles.push({
        x: Math.random() * ambientState.width,
        y: Math.random() * ambientState.height,
        vx: (Math.random() - 0.5) * 0.8,
        vy: (Math.random() - 0.5) * 0.8,
        size: 12 + Math.random() * 12,
        alpha: 0.22 + Math.random() * 0.4,
        symbol: symbols[index % symbols.length],
        spin: (Math.random() - 0.5) * 0.01,
        angle: Math.random() * Math.PI * 2,
      });
    }
  }

  function updateAmbientPointer(event) {
    var nextX = event.clientX;
    var nextY = event.clientY;
    ambientState.pointer.vx = nextX - ambientState.pointer.x;
    ambientState.pointer.vy = nextY - ambientState.pointer.y;
    ambientState.pointer.x = nextX;
    ambientState.pointer.y = nextY;
    ambientState.pointer.active = true;
  }

  function drawAmbientScene() {
    var context = ambientState.context;
    var pointer = ambientState.pointer;
    var width = ambientState.width;
    var height = ambientState.height;
    var particles = ambientState.particles;
    var index;
    var otherIndex;

    if (!context || !width || !height) {
      return;
    }

    context.clearRect(0, 0, width, height);

    for (index = 0; index < particles.length; index += 1) {
      var particle = particles[index];
      var dx;
      var dy;
      var distance;
      var influence;

      if (pointer.active) {
        dx = pointer.x - particle.x;
        dy = pointer.y - particle.y;
        distance = Math.sqrt(dx * dx + dy * dy) || 1;
        if (distance < 180) {
          influence = (1 - distance / 180) * (pointer.down ? 0.32 : 0.12);
          particle.vx += (dx / distance) * influence + pointer.vx * 0.0035 * influence;
          particle.vy += (dy / distance) * influence + pointer.vy * 0.0035 * influence;
        }
        if (distance < 42) {
          particle.vx -= (dx / distance) * 0.24;
          particle.vy -= (dy / distance) * 0.24;
        }
      }

      particle.x += particle.vx;
      particle.y += particle.vy;
      particle.vx *= 0.985;
      particle.vy *= 0.985;
      particle.angle += particle.spin;

      if (particle.x < -20 || particle.x > width + 20) {
        particle.vx *= -1;
        particle.x = Math.max(0, Math.min(width, particle.x));
      }
      if (particle.y < -20 || particle.y > height + 20) {
        particle.vy *= -1;
        particle.y = Math.max(0, Math.min(height, particle.y));
      }

      context.save();
      context.translate(particle.x, particle.y);
      context.rotate(particle.angle);
      context.font = "600 " + particle.size + "px Aptos, Segoe UI, sans-serif";
      context.textAlign = "center";
      context.textBaseline = "middle";
      context.fillStyle = document.body.getAttribute("data-theme") === "dark"
        ? "rgba(146, 199, 255, " + particle.alpha + ")"
        : "rgba(0, 91, 170, " + particle.alpha + ")";
      context.fillText(particle.symbol, 0, 0);
      context.restore();
    }

    context.lineWidth = 1;
    for (index = 0; index < particles.length; index += 1) {
      var from = particles[index];
      for (otherIndex = index + 1; otherIndex < particles.length; otherIndex += 1) {
        var to = particles[otherIndex];
        var lineDx = from.x - to.x;
        var lineDy = from.y - to.y;
        var lineDistance = Math.sqrt(lineDx * lineDx + lineDy * lineDy);
        if (lineDistance > 110) {
          continue;
        }
        context.strokeStyle = document.body.getAttribute("data-theme") === "dark"
          ? "rgba(142, 199, 255, " + (0.12 * (1 - lineDistance / 110)) + ")"
          : "rgba(0, 91, 170, " + (0.09 * (1 - lineDistance / 110)) + ")";
        context.beginPath();
        context.moveTo(from.x, from.y);
        context.lineTo(to.x, to.y);
        context.stroke();
      }
    }

    ambientState.animationFrame = window.requestAnimationFrame(drawAmbientScene);
  }

  function bindAmbientScene() {
    if (!supportsAmbientScene()) {
      return;
    }

    resizeAmbientScene();
    window.addEventListener("resize", resizeAmbientScene);
    document.addEventListener(
      "pointermove",
      function (event) {
        updateAmbientPointer(event);
      },
      { passive: true }
    );
    document.addEventListener("pointerdown", function (event) {
      ambientState.pointer.down = true;
      updateAmbientPointer(event);
    });
    document.addEventListener("pointerup", function () {
      ambientState.pointer.down = false;
    });
    document.addEventListener("pointerleave", function () {
      ambientState.pointer.active = false;
      ambientState.pointer.down = false;
    });
    drawAmbientScene();
  }

  function copyText(text) {
    var value = String(text || "");
    if (!value) {
      showToast(getUiText().copy.failure);
      return;
    }

    function fallbackCopy() {
      try {
        var helper = document.createElement("textarea");
        helper.value = value;
        helper.setAttribute("readonly", "readonly");
        helper.style.position = "fixed";
        helper.style.opacity = "0";
        document.body.appendChild(helper);
        helper.select();
        document.execCommand("copy");
        document.body.removeChild(helper);
        playTone("share");
        showToast(getUiText().copy.success);
      } catch (error) {
        showToast(getUiText().copy.failure);
      }
    }

    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard
        .writeText(value)
        .then(function () {
          playTone("share");
          showToast(getUiText().copy.success);
        })
        .catch(function () {
          fallbackCopy();
        });
      return;
    }

    fallbackCopy();
  }

  function enhanceCodeBlocks(container) {
    var blocks = container.querySelectorAll(".code-block");
    Array.prototype.forEach.call(blocks, function (block) {
      if (!block || (block.parentNode && block.parentNode.classList.contains("code-block-shell"))) {
        return;
      }

      var shell = document.createElement("div");
      var actions = document.createElement("div");
      var copyButton = document.createElement("button");
      var code = block.textContent || "";

      shell.className = "code-block-shell";
      actions.className = "code-block-actions";
      copyButton.type = "button";
      copyButton.className = "code-copy-button";
      copyButton.title = getUiText().copy.label;
      copyButton.setAttribute("aria-label", getUiText().copy.label);
      copyButton.innerHTML = '<span aria-hidden="true">⧉</span>';
      copyButton.addEventListener("click", function () {
        copyText(code);
      });

      if (block.parentNode) {
        block.parentNode.insertBefore(shell, block);
      }
      actions.appendChild(copyButton);
      shell.appendChild(actions);
      shell.appendChild(block);
    });
  }

  function sendFeedback(interactionId, rating, buttons) {
    buttons.forEach(function (button) {
      button.disabled = true;
    });

    fetch("/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ interaction_id: interactionId, rating: rating }),
    })
      .then(function () {
        buttons.forEach(function (button) {
          button.classList.toggle("selected", button.dataset.rating === rating);
        });
      })
      .catch(function () {
        buttons.forEach(function (button) {
          button.disabled = false;
        });
      });
  }

  function buildMessageElement(role, text, meta) {
    meta = meta || {};

    var article = document.createElement("article");
    article.className = "message " + role + " message-enter";

    var avatar = document.createElement("div");
    avatar.className = role === "user" ? "avatar user-avatar" : "avatar assistant-avatar";
    if (role === "user") {
      avatar.appendChild(createUserAvatarIcon());
    } else if (runtimeBranding.chatLogoUrl) {
      var avatarLogo = document.createElement("img");
      avatarLogo.className = "avatar-logo";
      avatarLogo.alt = "İİBF logosu";
      avatarLogo.src = runtimeBranding.chatLogoUrl;
      avatarLogo.addEventListener("error", function () {
        avatar.textContent = "KAÜ";
      });
      avatar.appendChild(avatarLogo);
    } else {
      avatar.textContent = "KAÜ";
    }

    var bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.innerHTML = role === "assistant" ? renderAssistantText(text) : renderUserText(text);

    if (role === "assistant") {
      enhanceCodeBlocks(bubble);

      var sourceLinks = renderSources(meta.sources || []);
      if (sourceLinks) {
        bubble.appendChild(sourceLinks);
      }

      if (meta.interactionId) {
        var feedback = document.createElement("div");
        var positive = document.createElement("button");
        var negative = document.createElement("button");
        var buttons;

        feedback.className = "feedback-actions";
        positive.type = "button";
        negative.type = "button";
        positive.textContent = getUiText().feedback.up;
        negative.textContent = getUiText().feedback.down;
        positive.dataset.rating = "up";
        negative.dataset.rating = "down";
        buttons = [positive, negative];

        buttons.forEach(function (button) {
          button.addEventListener("click", function () {
            sendFeedback(meta.interactionId, button.dataset.rating, buttons);
          });
          feedback.appendChild(button);
        });

        bubble.appendChild(feedback);
      }
    }

    article.appendChild(avatar);
    article.appendChild(bubble);
    return article;
  }

  function appendMessage(role, text, meta) {
    var article = buildMessageElement(role, text, meta);
    messages.appendChild(article);
    scrollMessagesToBottom();
    window.setTimeout(function () {
      article.classList.remove("message-enter");
    }, 450);
  }

  function scrollMessagesToBottom() {
    messages.scrollTop = messages.scrollHeight;
  }

  function scrollMessagesBy(offset) {
    messages.scrollTop += offset;
  }

  function syncTyping() {
    typingRow.hidden = state.pendingConversationId !== state.activeConversationId;
    if (!typingRow.hidden) {
      scrollMessagesToBottom();
    }
  }

  function autoResize() {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 180) + "px";
  }

  function buildClientId() {
    if (window.crypto && typeof window.crypto.randomUUID === "function") {
      return window.crypto.randomUUID();
    }
    return "kaucan-" + Date.now().toString(36) + Math.random().toString(36).slice(2, 10);
  }

  function ensureClientId() {
    var storedClientId;

    try {
      storedClientId = window.localStorage.getItem(CLIENT_ID_KEY);
    } catch (error) {
      storedClientId = "";
    }

    if (!storedClientId) {
      storedClientId = buildClientId();
      try {
        window.localStorage.setItem(CLIENT_ID_KEY, storedClientId);
      } catch (error) {
        return storedClientId;
      }
    }

    return storedClientId;
  }

  function setVoiceButtonState(listening) {
    if (!voiceButton) {
      return;
    }

    voiceButton.classList.toggle("listening", !!listening);
    voiceButton.setAttribute("aria-pressed", listening ? "true" : "false");
    voiceButton.title = listening ? getUiText().voice.stop : getUiText().voice.start;
    voiceButton.setAttribute("aria-label", voiceButton.title);
  }

  function getAudioContext() {
    var AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) {
      return null;
    }

    if (!audioState.context) {
      audioState.context = new AudioContextClass();
    }

    if (audioState.context.state === "suspended") {
      audioState.context.resume();
    }

    return audioState.context;
  }

  function withReadyAudio(callback) {
    var context = getAudioContext();
    if (!context || typeof callback !== "function") {
      return;
    }

    function run() {
      audioState.primed = true;
      callback(context);
    }

    if (context.state === "suspended") {
      context
        .resume()
        .then(run)
        .catch(function () {
          return;
        });
      return;
    }

    run();
  }

  function primeAudio() {
    if (audioState.primed) {
      return;
    }

    withReadyAudio(function (context) {
      var oscillator = context.createOscillator();
      var gain = context.createGain();
      var now = context.currentTime + 0.001;

      gain.gain.setValueAtTime(0.00001, now);
      oscillator.type = "sine";
      oscillator.frequency.setValueAtTime(180, now);
      oscillator.connect(gain);
      gain.connect(context.destination);
      oscillator.start(now);
      oscillator.stop(now + 0.012);
    });
  }

  function scheduleTone(context, frequency, startTime, duration, type, peakGain) {
    var oscillator = context.createOscillator();
    var gain = context.createGain();

    oscillator.type = type || "sine";
    oscillator.frequency.setValueAtTime(frequency, startTime);
    gain.gain.setValueAtTime(0.0001, startTime);
    gain.gain.exponentialRampToValueAtTime(peakGain || 0.025, startTime + 0.014);
    gain.gain.exponentialRampToValueAtTime(0.0001, startTime + duration);

    oscillator.connect(gain);
    gain.connect(context.destination);
    oscillator.start(startTime);
    oscillator.stop(startTime + duration);
  }

  function playTone(kind) {
    var now;

    try {
      withReadyAudio(function (context) {
        now = context.currentTime + 0.01;

        if (kind === "send") {
          scheduleTone(context, 620, now, 0.08, "triangle", 0.022);
          scheduleTone(context, 840, now + 0.07, 0.11, "triangle", 0.021);
          scheduleTone(context, 980, now + 0.14, 0.08, "sine", 0.018);
          return;
        }

        if (kind === "receive") {
          scheduleTone(context, 500, now, 0.08, "sine", 0.018);
          scheduleTone(context, 660, now + 0.08, 0.1, "sine", 0.02);
          scheduleTone(context, 780, now + 0.18, 0.12, "triangle", 0.02);
          return;
        }

        if (kind === "new-chat") {
          scheduleTone(context, 460, now, 0.07, "triangle", 0.018);
          scheduleTone(context, 620, now + 0.06, 0.09, "triangle", 0.018);
          scheduleTone(context, 860, now + 0.13, 0.12, "sine", 0.016);
          return;
        }

        if (kind === "history") {
          scheduleTone(context, 560, now, 0.07, "sine", 0.012);
          scheduleTone(context, 480, now + 0.05, 0.06, "sine", 0.01);
          return;
        }

        if (kind === "theme") {
          scheduleTone(context, 720, now, 0.07, "sine", 0.013);
          scheduleTone(context, 940, now + 0.05, 0.1, "triangle", 0.013);
          return;
        }

        if (kind === "share") {
          scheduleTone(context, 680, now, 0.05, "triangle", 0.012);
          scheduleTone(context, 860, now + 0.04, 0.08, "triangle", 0.012);
          return;
        }

        if (kind === "voice-start") {
          scheduleTone(context, 520, now, 0.06, "sine", 0.014);
          scheduleTone(context, 720, now + 0.05, 0.08, "triangle", 0.014);
          return;
        }

        if (kind === "voice-stop") {
          scheduleTone(context, 640, now, 0.05, "triangle", 0.012);
          scheduleTone(context, 420, now + 0.05, 0.08, "sine", 0.012);
          return;
        }

        if (kind === "clear") {
          scheduleTone(context, 540, now, 0.06, "triangle", 0.013);
          scheduleTone(context, 680, now + 0.05, 0.08, "triangle", 0.013);
          return;
        }

        if (kind === "delete") {
          scheduleTone(context, 360, now, 0.08, "sawtooth", 0.013);
          scheduleTone(context, 240, now + 0.08, 0.1, "sawtooth", 0.012);
          return;
        }

        if (kind === "error") {
          scheduleTone(context, 320, now, 0.12, "sawtooth", 0.014);
          scheduleTone(context, 220, now + 0.1, 0.12, "sawtooth", 0.012);
        }
      });
    } catch (error) {
      return;
    }
  }

  function newConversationId() {
    return "conv-" + Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
  }

  function createWelcomeMessage() {
    return {
      role: "assistant",
      text: getWelcomeMessage(getUiLanguage()),
      sources: [],
      interactionId: null,
      status: "greeting",
    };
  }

  function createConversation() {
    var timestamp = Date.now();
    return {
      id: newConversationId(),
      title: getDefaultConversationTitle(),
      createdAt: timestamp,
      updatedAt: timestamp,
      messages: [createWelcomeMessage()],
    };
  }

  function normalizeStoredMessage(message) {
    return {
      role: message && message.role === "user" ? "user" : "assistant",
      text: String((message && message.text) || ""),
      sources: dedupeSources((message && message.sources) || []),
      interactionId: message && message.interactionId ? String(message.interactionId) : null,
      status: message && message.status ? String(message.status) : "",
    };
  }

  function normalizeConversation(conversation) {
    var normalizedMessages = Array.isArray(conversation && conversation.messages)
      ? conversation.messages.map(normalizeStoredMessage).filter(function (message) {
          return !!message.text;
        })
      : [];

    if (!normalizedMessages.length) {
      normalizedMessages = [createWelcomeMessage()];
    }

    return {
      id: conversation && conversation.id ? String(conversation.id) : newConversationId(),
      title: conversation && conversation.title ? String(conversation.title) : getDefaultConversationTitle(),
      createdAt: conversation && conversation.createdAt ? Number(conversation.createdAt) : Date.now(),
      updatedAt: conversation && conversation.updatedAt ? Number(conversation.updatedAt) : Date.now(),
      messages: normalizedMessages,
    };
  }

  function persistState() {
    try {
      window.localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          activeConversationId: state.activeConversationId,
          conversations: state.conversations,
        })
      );
    } catch (error) {
      return;
    }
  }

  function ensureConversationState() {
    var payload;
    var parsed;

    try {
      payload = window.localStorage.getItem(STORAGE_KEY);
      parsed = payload ? JSON.parse(payload) : null;
    } catch (error) {
      parsed = null;
    }

    if (parsed && Array.isArray(parsed.conversations) && parsed.conversations.length) {
      state.conversations = parsed.conversations.map(normalizeConversation);
      state.activeConversationId = parsed.activeConversationId || state.conversations[0].id;
    } else {
      state.conversations = [createConversation()];
      state.activeConversationId = state.conversations[0].id;
      persistState();
    }

    if (!findConversation(state.activeConversationId)) {
      state.activeConversationId = state.conversations[0].id;
    }
  }

  function findConversation(conversationId) {
    var index;
    for (index = 0; index < state.conversations.length; index += 1) {
      if (state.conversations[index].id === conversationId) {
        return state.conversations[index];
      }
    }
    return null;
  }

  function getActiveConversation() {
    var conversation = findConversation(state.activeConversationId);
    if (conversation) {
      return conversation;
    }

    if (!state.conversations.length) {
      state.conversations.push(createConversation());
    }

    state.activeConversationId = state.conversations[0].id;
    persistState();
    return state.conversations[0];
  }

  function updateQuickPromptsVisibility(conversation) {
    var activeConversation = conversation || getActiveConversation();
    var hasUserMessages = activeConversation.messages.some(function (message) {
      return message.role === "user" && String(message.text || "").trim();
    });
    if (quickPromptsShell) {
      quickPromptsShell.hidden = hasUserMessages;
    }
  }

  function supportsEnhancedCursor() {
    return !!(window.matchMedia && window.matchMedia("(pointer:fine)").matches && cursorLayer && cursorRing && cursorDot);
  }

  function bindCustomCursor() {
    if (!supportsEnhancedCursor()) {
      return;
    }

    document.documentElement.classList.add("cursor-enhanced");

    function setCursorPosition(x, y) {
      cursorRing.style.left = x + "px";
      cursorRing.style.top = y + "px";
      cursorDot.style.left = x + "px";
      cursorDot.style.top = y + "px";
    }

    document.addEventListener(
      "pointermove",
      function (event) {
        var target = event.target && typeof event.target.closest === "function"
          ? event.target.closest("a, button, textarea, input, select, .query-chip, .quick-link, .highlight-link, .history-action, .history-main")
          : null;
        setCursorPosition(event.clientX, event.clientY);
        document.documentElement.classList.toggle("cursor-hover", !!target);
      },
      { passive: true }
    );

    document.addEventListener("pointerdown", function () {
      document.documentElement.classList.add("cursor-pressed");
    });
    document.addEventListener("pointerup", function () {
      document.documentElement.classList.remove("cursor-pressed");
    });
    document.addEventListener("pointerleave", function () {
      document.documentElement.classList.remove("cursor-hover");
      document.documentElement.classList.remove("cursor-pressed");
    });
  }

  function toTitle(text) {
    var cleaned = String(text || "")
      .replace(/\s+/g, " ")
      .replace(/```[\s\S]*?```/g, "")
      .trim();

    if (!cleaned) {
      return getDefaultConversationTitle();
    }

    if (cleaned.length <= 48) {
      return cleaned;
    }

    return cleaned.slice(0, 45).trim() + "...";
  }

  function matchesHistoryFilter(conversation, filterText) {
    var normalizedFilter = String(filterText || "").toLowerCase().trim();
    if (!normalizedFilter) {
      return true;
    }
    return String(conversation.title || "").toLowerCase().indexOf(normalizedFilter) !== -1;
  }

  function openHistory() {
    document.body.classList.add("history-open");
    historyBackdrop.hidden = false;
    playTone("history");
  }

  function closeHistory() {
    document.body.classList.remove("history-open");
    historyBackdrop.hidden = true;
  }

  function selectConversation(conversationId) {
    if (state.activeConversationId === conversationId) {
      closeHistory();
      return;
    }
    state.activeConversationId = conversationId;
    persistState();
    renderHistoryList();
    renderConversation();
    closeHistory();
    playTone("history");
  }

  function conversationToShareText(conversation) {
    var ui = getUiText();
    var lines = [conversation.title || ui.share.title, ""];
    conversation.messages.forEach(function (message) {
      var label = message.role === "user" ? ui.share.userLabel : ui.share.botLabel;
      lines.push(label + ": " + String(message.text || "").trim());
    });
    return lines.join("\n");
  }

  function shareConversation(conversation) {
    var text = conversationToShareText(conversation);
    if (navigator.share) {
      navigator
        .share({
          title: conversation.title || getUiText().share.title,
          text: text,
        })
        .then(function () {
          playTone("share");
        })
        .catch(function () {
          return;
        });
      return;
    }

    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard
        .writeText(text)
        .then(function () {
          playTone("share");
        })
        .catch(function () {
          return;
        });
    }
  }

  function editConversationTitle(conversation) {
    var nextTitle = window.prompt(getUiText().history.editPrompt, conversation.title || getDefaultConversationTitle());
    if (nextTitle === null) {
      return;
    }

    nextTitle = toTitle(nextTitle);
    conversation.title = nextTitle || getDefaultConversationTitle();
    conversation.updatedAt = Date.now();
    persistState();
    renderHistoryList();
    playTone("history");
  }

  function deleteConversation(conversationId) {
    var nextConversations = state.conversations.filter(function (conversation) {
      return conversation.id !== conversationId;
    });

    if (!nextConversations.length) {
      nextConversations = [createConversation()];
    }

    state.conversations = nextConversations;
    if (!findConversation(state.activeConversationId)) {
      state.activeConversationId = state.conversations[0].id;
    }
    persistState();
    renderHistoryList();
    renderConversation();
    playTone("delete");
  }

  function deleteAllConversations() {
    stopVoiceInput(false);
    state.conversations = [createConversation()];
    state.activeConversationId = state.conversations[0].id;
    state.pendingConversationId = null;
    if (historySearchInput) {
      historySearchInput.value = "";
    }
    persistState();
    renderHistoryList();
    renderConversation();
    closeHistory();
    playTone("delete");
  }

  function resolveRecognitionLanguage() {
    if (state.preferredLanguage === "ar") {
      return "ar-SA";
    }
    if (state.preferredLanguage === "en") {
      return "en-US";
    }
    var text = String(input.value || "").toLowerCase();
    if (/\b(hello|who|what|where|when|why|how|dean|department|news|events)\b/.test(text)) {
      return "en-US";
    }
    return "tr-TR";
  }

  function joinVoiceText(baseText, transcript) {
    var prefix = String(baseText || "").trim();
    var suffix = String(transcript || "").trim();
    if (!prefix) {
      return suffix;
    }
    if (!suffix) {
      return prefix;
    }
    return prefix + " " + suffix;
  }

  function stopVoiceInput(updateStatus) {
    if (state.voice.recognition && state.voice.listening) {
      state.voice.listening = false;
      try {
        state.voice.recognition.stop();
      } catch (error) {
        return;
      }
    }
    setVoiceButtonState(false);
    playTone("voice-stop");
    if (updateStatus && !state.pendingConversationId) {
      setStatus("Hazır", "ready");
    }
  }

  function ensureVoiceRecognition() {
    if (!state.voice.supported || state.voice.recognition) {
      return state.voice.recognition;
    }

    state.voice.recognition = new SpeechRecognitionClass();
    state.voice.recognition.continuous = true;
    state.voice.recognition.interimResults = true;
    state.voice.recognition.maxAlternatives = 1;

    state.voice.recognition.onstart = function () {
      state.voice.listening = true;
      setVoiceButtonState(true);
      setStatus("Dinleniyor", "busy");
      playTone("voice-start");
    };

    state.voice.recognition.onresult = function (event) {
      var finalTranscript = "";
      var interimTranscript = "";
      var index;

      for (index = 0; index < event.results.length; index += 1) {
        if (event.results[index].isFinal) {
          finalTranscript += event.results[index][0].transcript + " ";
        } else {
          interimTranscript += event.results[index][0].transcript + " ";
        }
      }

      input.value = joinVoiceText(state.voice.baseText, (finalTranscript + interimTranscript).trim());
      autoResize();
    };

    state.voice.recognition.onerror = function (event) {
      state.voice.listening = false;
      setVoiceButtonState(false);
      if (event && (event.error === "not-allowed" || event.error === "service-not-allowed")) {
        state.voice.denied = true;
        setStatus("Mikrofon izni gerekli", "error");
        return;
      }
      if (!state.pendingConversationId) {
        setStatus("Sesli yazma durdu", "ready");
      }
    };

    state.voice.recognition.onend = function () {
      state.voice.listening = false;
      setVoiceButtonState(false);
      autoResize();
      if (!state.pendingConversationId && !state.voice.denied) {
        setStatus("Hazır", "ready");
      }
    };

    return state.voice.recognition;
  }

  function toggleVoiceInput() {
    var recognition;

    if (!state.voice.supported) {
      return;
    }

    if (state.voice.listening) {
      stopVoiceInput(true);
      return;
    }

    recognition = ensureVoiceRecognition();
    if (!recognition) {
      return;
    }

    state.voice.denied = false;
    state.voice.baseText = String(input.value || "").trim();
    recognition.lang = resolveRecognitionLanguage();

    try {
      recognition.start();
    } catch (error) {
      setStatus("Mikrofon başlatılamadı", "error");
    }
  }

  function initializeVoiceButton() {
    if (!voiceButton) {
      return;
    }

    if (!state.voice.supported) {
      voiceButton.disabled = true;
      voiceButton.title = getUiText().voice.unsupported;
      return;
    }

    setVoiceButtonState(false);
  }

  function renderHistoryList() {
    var filterText = historySearchInput ? historySearchInput.value : "";
    var hasItem = false;

    historyList.innerHTML = "";
    state.conversations
      .slice()
      .sort(function (left, right) {
        return right.updatedAt - left.updatedAt;
      })
      .forEach(function (conversation) {
        var row;
        var mainButton;
        var title;
        var actions;
        var shareButton;
        var editButton;
        var deleteButton;

        if (!matchesHistoryFilter(conversation, filterText)) {
          return;
        }

        hasItem = true;
        row = document.createElement("div");
        row.className = "history-item" + (conversation.id === state.activeConversationId ? " active" : "");

        mainButton = document.createElement("button");
        mainButton.type = "button";
        mainButton.className = "history-main";
        mainButton.addEventListener("click", function () {
          selectConversation(conversation.id);
        });

        title = document.createElement("div");
        title.className = "history-title";
        title.textContent = conversation.title || getDefaultConversationTitle();
        mainButton.appendChild(title);

        actions = document.createElement("div");
        actions.className = "history-actions";

        shareButton = document.createElement("button");
        shareButton.type = "button";
        shareButton.className = "history-action";
        shareButton.title = getUiText().history.share;
        shareButton.setAttribute("aria-label", getUiText().history.share);
        shareButton.innerHTML = '<span aria-hidden="true">⤴</span>';
        shareButton.addEventListener("click", function (event) {
          event.stopPropagation();
          shareConversation(conversation);
        });

        editButton = document.createElement("button");
        editButton.type = "button";
        editButton.className = "history-action";
        editButton.title = getUiText().history.edit;
        editButton.setAttribute("aria-label", getUiText().history.edit);
        editButton.innerHTML = '<span aria-hidden="true">✎</span>';
        editButton.addEventListener("click", function (event) {
          event.stopPropagation();
          editConversationTitle(conversation);
        });

        deleteButton = document.createElement("button");
        deleteButton.type = "button";
        deleteButton.className = "history-action";
        deleteButton.title = getUiText().history.delete;
        deleteButton.setAttribute("aria-label", getUiText().history.delete);
        deleteButton.innerHTML = '<span aria-hidden="true">🗑</span>';
        deleteButton.addEventListener("click", function (event) {
          event.stopPropagation();
          deleteConversation(conversation.id);
        });

        actions.appendChild(shareButton);
        actions.appendChild(editButton);
        actions.appendChild(deleteButton);
        row.appendChild(mainButton);
        row.appendChild(actions);
        historyList.appendChild(row);
      });

    if (!hasItem) {
      var empty = document.createElement("div");
      empty.className = "history-empty";
      empty.textContent = getUiText().history.empty;
      historyList.appendChild(empty);
    }
  }

  function renderConversation() {
    var conversation = getActiveConversation();
    var index;

    messages.innerHTML = "";
    for (index = 0; index < conversation.messages.length; index += 1) {
      var message = conversation.messages[index];
      var element = buildMessageElement(message.role, message.text, message);
      element.classList.remove("message-enter");
      messages.appendChild(element);
    }
    updateQuickPromptsVisibility(conversation);
    syncTyping();
    scrollMessagesToBottom();
  }

  function rememberMessage(conversationId, role, text, meta, renderNow) {
    var conversation = findConversation(conversationId);
    var message;

    if (!conversation) {
      conversation = getActiveConversation();
    }

    message = {
      role: role,
      text: String(text || ""),
      sources: dedupeSources((meta && meta.sources) || []),
      interactionId: meta && meta.interactionId ? String(meta.interactionId) : null,
      status: meta && meta.status ? String(meta.status) : "",
    };

    if (!message.text) {
      return;
    }

    conversation.messages.push(message);
    conversation.updatedAt = Date.now();
    if (role === "user" && (isDefaultConversationTitle(conversation.title) || conversation.messages.length <= 2)) {
      conversation.title = toTitle(text);
    }

    persistState();
    renderHistoryList();
    updateQuickPromptsVisibility(conversation);

    if (renderNow && state.activeConversationId === conversation.id) {
      appendMessage(role, text, message);
    }
  }

  function createNewConversation() {
    stopVoiceInput(false);
    var conversation = createConversation();
    state.conversations.unshift(conversation);
    state.activeConversationId = conversation.id;
    state.pendingConversationId = null;
    persistState();
    renderHistoryList();
    renderConversation();
    setStatus("Hazır");
    input.value = "";
    autoResize();
    input.focus();
    closeHistory();
    playTone("new-chat");
  }

  function resetActiveConversation() {
    stopVoiceInput(false);
    var conversation = getActiveConversation();
    conversation.title = getDefaultConversationTitle();
    conversation.updatedAt = Date.now();
    conversation.messages = [createWelcomeMessage()];
    persistState();
    renderHistoryList();
    renderConversation();
    input.value = "";
    autoResize();
    input.focus();
    playTone("clear");
  }

  function questionNeedsLocation(question) {
    return /(hava durumu|weather|forecast|temperature|sıcaklık|sicaklik|الطقس|طقس)/i.test(String(question || ""));
  }

  function hasFreshLocation() {
    return (
      typeof state.location.latitude === "number" &&
      typeof state.location.longitude === "number" &&
      Date.now() - Number(state.location.updatedAt || 0) < 15 * 60 * 1000
    );
  }

  function requestGeolocationIfNeeded(question) {
    return new Promise(function (resolve) {
      if (!questionNeedsLocation(question) || !navigator.geolocation) {
        resolve(null);
        return;
      }

      if (hasFreshLocation()) {
        resolve({
          latitude: state.location.latitude,
          longitude: state.location.longitude,
        });
        return;
      }

      setStatus(getUiText().status.requestingLocation, "busy");
      navigator.geolocation.getCurrentPosition(
        function (position) {
          state.location.latitude = Number(position.coords.latitude);
          state.location.longitude = Number(position.coords.longitude);
          state.location.updatedAt = Date.now();
          state.location.permission = "granted";
          resolve({
            latitude: state.location.latitude,
            longitude: state.location.longitude,
          });
        },
        function () {
          state.location.permission = "denied";
          setStatus(getUiText().status.locationDenied, "error");
          resolve(null);
        },
        {
          enableHighAccuracy: false,
          timeout: 5000,
          maximumAge: 10 * 60 * 1000,
        }
      );
    });
  }

  function askQuestion(question, conversationId, locationData) {
    setStatus("Yanıt hazırlanıyor", "busy");
    submitButton.disabled = true;
    state.pendingConversationId = conversationId;
    syncTyping();

    function finishRequest() {
      submitButton.disabled = false;
      state.pendingConversationId = null;
      syncTyping();
      input.focus();
    }

    fetch("/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question: question,
        client_id: state.clientId || "",
        preferred_language: state.preferredLanguage || "tr",
        latitude: locationData && typeof locationData.latitude === "number" ? locationData.latitude : null,
        longitude: locationData && typeof locationData.longitude === "number" ? locationData.longitude : null,
      }),
    })
      .then(function (response) {
        if (!response.ok) {
          throw new Error("request-failed");
        }
        return response.json();
      })
      .then(function (data) {
        rememberMessage(
          conversationId,
          "assistant",
          data.answer || getFallbackMessage(getUiLanguage()),
          {
            interactionId: data.interaction_id,
            sources: data.sources || [],
            status: data.status || "",
          },
          state.activeConversationId === conversationId
        );
        setStatus("Hazır");
        playTone("receive");
        finishRequest();
      })
      .catch(function () {
        rememberMessage(
          conversationId,
          "assistant",
          getFallbackMessage(getUiLanguage()),
          {},
          state.activeConversationId === conversationId
        );
        setStatus("Hata", "error");
        playTone("error");
        finishRequest();
      });
  }

  function submitQuestion(questionText) {
    var question = String(questionText || input.value).replace(/^\s+|\s+$/g, "");
    var conversation;

    if (!question || submitButton.disabled) {
      return;
    }

    stopVoiceInput(false);
    conversation = getActiveConversation();
    rememberMessage(conversation.id, "user", question, {}, state.activeConversationId === conversation.id);
    input.value = "";
    autoResize();
    playTone("send");
    requestGeolocationIfNeeded(question).then(function (locationData) {
      askQuestion(question, conversation.id, locationData);
    });
  }

  function applyLogo(url) {
    if (!brandLogo) {
      return;
    }

    if (!url) {
      brandLogo.hidden = true;
      if (brandFallback) {
        brandFallback.hidden = false;
      }
      return;
    }

    brandLogo.src = url;
    brandLogo.hidden = false;
    if (brandFallback) {
      brandFallback.hidden = true;
    }
  }

  function applyChatLogo(url) {
    runtimeBranding.chatLogoUrl = url || runtimeBranding.chatLogoUrl;

    function updateImage(target) {
      if (!target || !runtimeBranding.chatLogoUrl) {
        return;
      }
      target.hidden = false;
      target.src = runtimeBranding.chatLogoUrl;
    }

    updateImage(initialChatLogo);
    updateImage(typingChatLogo);
    updateImage(brandFacultyLogo);
  }

  function applyTheme(theme) {
    state.theme = theme === "dark" ? "dark" : "light";
    document.body.setAttribute("data-theme", state.theme);
    if (themeToggleIcon) {
      themeToggleIcon.textContent = state.theme === "dark" ? "☀" : "☾";
    }
    try {
      window.localStorage.setItem(THEME_KEY, state.theme);
    } catch (error) {
      return;
    }
  }

  function loadTheme() {
    var storedTheme;
    try {
      storedTheme = window.localStorage.getItem(THEME_KEY);
    } catch (error) {
      storedTheme = null;
    }
    applyTheme(storedTheme || "light");
  }

  function applyPreferredLanguage(language) {
    state.preferredLanguage = language === "en" || language === "ar" ? language : "tr";
    if (languageSelect) {
      languageSelect.value = state.preferredLanguage;
    }
    try {
      window.localStorage.setItem(LANGUAGE_KEY, state.preferredLanguage);
    } catch (error) {
      // Keep the UI responsive even if storage is unavailable.
    }
    applyInterfaceLanguage();
    refreshLanguageSensitiveConversations();
    persistState();
    renderHistoryList();
    renderConversation();
  }

  function loadPreferredLanguage() {
    var storedLanguage;
    try {
      storedLanguage = window.localStorage.getItem(LANGUAGE_KEY);
    } catch (error) {
      storedLanguage = null;
    }
    applyPreferredLanguage(storedLanguage || "tr");
  }

  function toggleTheme() {
    applyTheme(state.theme === "dark" ? "light" : "dark");
    playTone("theme");
  }

  function renderHighlightCard(topic, item) {
    var fallback = HIGHLIGHT_FALLBACKS[topic];
    var data = item || fallback;
    var imageUrl = data.image_url || runtimeBranding.chatLogoUrl || "/static/assets/iibf_logo.png?v=20260426a";
    var title = escapeHtml(truncateText(data.title || fallback.title, 92));
    var meta = [data.date || "", data.category || ""]
      .filter(function (value) {
        return !!value;
      })
      .join(" • ");
    var summary = escapeHtml(truncateText(data.summary || fallback.summary || "", 132));

    return (
      '<a class="highlight-link" href="' +
      escapeHtml(data.url || fallback.url) +
      '" target="_blank" rel="noopener noreferrer">' +
      '<div class="highlight-image"><img src="' +
      escapeHtml(imageUrl) +
      '" alt="' +
      title +
      '" /></div>' +
      '<div class="highlight-body">' +
      (meta ? '<p class="highlight-meta">' + escapeHtml(meta) + "</p>" : "") +
      "<h3>" +
      title +
      "</h3>" +
      (summary ? '<p class="highlight-summary">' + summary + "</p>" : "") +
      "</div>" +
      "</a>"
    );
  }

  function renderHighlights() {
    Object.keys(highlightTracks).forEach(function (topic) {
      var track = highlightTracks[topic];
      var items = state.highlights[topic] || [];
      var index = state.carouselIndex[topic] || 0;

      if (!track) {
        return;
      }

      if (!items.length) {
        track.innerHTML = renderHighlightCard(topic, null);
        return;
      }

      if (index >= items.length) {
        index = 0;
        state.carouselIndex[topic] = 0;
      }

      track.innerHTML = renderHighlightCard(topic, items[index]);
    });
  }

  function changeHighlight(topic, direction) {
    var items = state.highlights[topic] || [];
    if (!items.length) {
      window.open(HIGHLIGHT_FALLBACKS[topic].url, "_blank", "noopener");
      return;
    }

    if (direction === "prev") {
      state.carouselIndex[topic] = (state.carouselIndex[topic] - 1 + items.length) % items.length;
    } else {
      state.carouselIndex[topic] = (state.carouselIndex[topic] + 1) % items.length;
    }
    renderHighlights();
    playTone("history");
  }

  function loadHighlights() {
    fetch("/highlights")
      .then(function (response) {
        if (!response.ok) {
          throw new Error("highlights-failed");
        }
        return response.json();
      })
      .then(function (data) {
        state.highlights.announcements = Array.isArray(data.announcements) ? data.announcements : [];
        state.highlights.news = Array.isArray(data.news) ? data.news : [];
        state.highlights.events = Array.isArray(data.events) ? data.events : [];
        renderHighlights();
      })
      .catch(function () {
        renderHighlights();
      });
  }

  function loadHealth() {
    fetch("/health")
      .then(function (response) {
        return response.json();
      })
      .then(function (health) {
        applyLogo(health.logo_url);
        applyChatLogo(health.chat_logo_url);

        if (!health.index_ready) {
          setStatus("İndeks bekleniyor", "busy");
          return;
        }

        if (health.llm_provider === "ollama" && !health.ollama_running) {
          setStatus("Servis hazır", "ready");
          return;
        }

        setStatus("Hazır", "ready");
      })
      .catch(function () {
        setStatus("Bağlantı hatası", "error");
      });
  }

  function bindEvents() {
    document.addEventListener(
      "pointerdown",
      function () {
        primeAudio();
      },
      { passive: true }
    );
    document.addEventListener("keydown", function () {
      primeAudio();
    });

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      submitQuestion();
    });

    clearButton.addEventListener("click", function () {
      resetActiveConversation();
    });

    if (voiceButton) {
      voiceButton.addEventListener("click", function () {
        toggleVoiceInput();
      });
    }

    historyToggleButton.addEventListener("click", openHistory);
    historyCloseButton.addEventListener("click", closeHistory);
    historyBackdrop.addEventListener("click", closeHistory);

    if (newChatButton) {
      newChatButton.addEventListener("click", createNewConversation);
    }

    if (deleteAllChatsButton) {
      deleteAllChatsButton.addEventListener("click", function () {
        deleteAllConversations();
      });
    }

    if (historySearchInput) {
      historySearchInput.addEventListener("input", renderHistoryList);
    }

    if (themeToggleButton) {
      themeToggleButton.addEventListener("click", toggleTheme);
    }

    if (languageSelect) {
      languageSelect.addEventListener("change", function () {
        applyPreferredLanguage(languageSelect.value);
      });
    }

    Array.prototype.forEach.call(chips, function (chip) {
      chip.addEventListener("click", function () {
        playTone("history");
        submitQuestion(chip.textContent.replace(/^\s+|\s+$/g, ""));
      });
    });

    Array.prototype.forEach.call(highlightNavButtons, function (button) {
      button.addEventListener("click", function () {
        changeHighlight(button.dataset.topic, button.dataset.direction);
      });
    });

    input.addEventListener("input", autoResize);

    input.addEventListener("keydown", function (event) {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        submitQuestion();
      }
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        closeHistory();
      }
    });
  }

  function init() {
    document.body.classList.add("js-ready");
    loadTheme();
    bindAmbientScene();
    bindCustomCursor();
    state.clientId = ensureClientId();
    ensureConversationState();
    loadPreferredLanguage();
    initializeVoiceButton();
    bindEvents();
    autoResize();
    renderHistoryList();
    renderConversation();
    renderHighlights();
    loadHealth();
    loadHighlights();
    scrollMessagesToBottom();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
