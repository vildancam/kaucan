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
  var statusBadge = document.getElementById("statusBadge");
  var typingRow = document.getElementById("typingRow");
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
  };

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

  function setStatus(text, stateName) {
    stateName = stateName || "ready";
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
      link.textContent = uniqueSources[index].title || "🔗 Kaynağı Aç " + (index + 1);
      wrapper.appendChild(link);
    }

    return wrapper;
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
        positive.textContent = "Yararlı";
        negative.textContent = "Geliştirilmeli";
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
    voiceButton.title = listening ? "Dikteyi durdur" : "Sesli yazma";
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
    var context;
    var now;

    try {
      context = getAudioContext();
      if (!context) {
        return;
      }

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
      title: "Yeni Sohbet",
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
      title: conversation && conversation.title ? String(conversation.title) : "Yeni Sohbet",
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

  function toTitle(text) {
    var cleaned = String(text || "")
      .replace(/\s+/g, " ")
      .replace(/```[\s\S]*?```/g, "")
      .trim();

    if (!cleaned) {
      return "Yeni Sohbet";
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
    var lines = [conversation.title || "KAÜCAN Sohbeti", ""];
    conversation.messages.forEach(function (message) {
      var label = message.role === "user" ? "Kullanıcı" : "KAÜCAN";
      lines.push(label + ": " + String(message.text || "").trim());
    });
    return lines.join("\n");
  }

  function shareConversation(conversation) {
    var text = conversationToShareText(conversation);
    if (navigator.share) {
      navigator
        .share({
          title: conversation.title || "KAÜCAN Sohbeti",
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
    var nextTitle = window.prompt("Sohbet başlığını düzenleyin:", conversation.title || "Yeni Sohbet");
    if (nextTitle === null) {
      return;
    }

    nextTitle = toTitle(nextTitle);
    conversation.title = nextTitle || "Yeni Sohbet";
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
      voiceButton.title = "Tarayıcı sesli yazmayı desteklemiyor";
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
        title.textContent = conversation.title || "Yeni Sohbet";
        mainButton.appendChild(title);

        actions = document.createElement("div");
        actions.className = "history-actions";

        shareButton = document.createElement("button");
        shareButton.type = "button";
        shareButton.className = "history-action";
        shareButton.title = "Paylaş";
        shareButton.setAttribute("aria-label", "Paylaş");
        shareButton.innerHTML = '<span aria-hidden="true">⤴</span>';
        shareButton.addEventListener("click", function (event) {
          event.stopPropagation();
          shareConversation(conversation);
        });

        editButton = document.createElement("button");
        editButton.type = "button";
        editButton.className = "history-action";
        editButton.title = "Başlığı düzenle";
        editButton.setAttribute("aria-label", "Başlığı düzenle");
        editButton.innerHTML = '<span aria-hidden="true">✎</span>';
        editButton.addEventListener("click", function (event) {
          event.stopPropagation();
          editConversationTitle(conversation);
        });

        deleteButton = document.createElement("button");
        deleteButton.type = "button";
        deleteButton.className = "history-action";
        deleteButton.title = "Sil";
        deleteButton.setAttribute("aria-label", "Sil");
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
      empty.textContent = "Aranan başlıkla eşleşen sohbet bulunamadı.";
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
    if (role === "user" && (conversation.title === "Yeni Sohbet" || conversation.messages.length <= 2)) {
      conversation.title = toTitle(text);
    }

    persistState();
    renderHistoryList();

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
    conversation.title = "Yeni Sohbet";
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

  function askQuestion(question, conversationId) {
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
    askQuestion(question, conversation.id);
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
      return;
    }
    updateComposerCopy();
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
    var title = escapeHtml(data.title || fallback.title);
    var meta = [data.date || "", data.category || ""]
      .filter(function (value) {
        return !!value;
      })
      .join(" • ");
    var summary = escapeHtml(data.summary || fallback.summary || "");

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
    loadPreferredLanguage();
    state.clientId = ensureClientId();
    ensureConversationState();
    initializeVoiceButton();
    bindEvents();
    autoResize();
    updateComposerCopy();
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
