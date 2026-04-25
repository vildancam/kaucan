(function () {
  var form = document.getElementById("askForm");
  var input = document.getElementById("questionInput");
  var messages = document.getElementById("messages");
  var submitButton = document.getElementById("submitButton");
  var clearButton = document.getElementById("clearButton");
  var statusBadge = document.getElementById("statusBadge");
  var providerBox = document.getElementById("providerBox");
  var typingRow = document.getElementById("typingRow");
  var chips = document.querySelectorAll(".query-chip");
  var brandLogo = document.getElementById("brandLogo");
  var brandFallback = document.getElementById("brandFallback");

  var FALLBACK_MESSAGE =
    "⚠️ Bu konuda güvenilir bir bilgiye ulaşamadım. En doğru bilgi için fakülte ile iletişime geçmenizi öneririm.";

  var audioState = {
    context: null,
  };

  function setStatus(text, state) {
    state = state || "ready";
    statusBadge.innerHTML = "";

    var dot = document.createElement("span");
    dot.className = "status-dot";
    statusBadge.appendChild(dot);
    statusBadge.appendChild(document.createTextNode(text));
    statusBadge.className = state === "ready" ? "status" : "status " + state;
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
    cleaned = cleaned.replace(/^(?:✅)?\s*(sonuç|sonuc)\s*:\s*/i, "");

    if (/^(?:🔗)?\s*(kaynak|source|sources)\s*:?.*$/i.test(cleaned)) {
      return "";
    }

    if (/^(metadata|chunk açıklaması|chunk aciklamasi)\s*:?.*$/i.test(cleaned)) {
      return "";
    }

    cleaned = cleaned.replace(/https?:\/\/[^\s]+/g, "").trim();
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

  function renderAssistantText(text) {
    var sanitized = sanitizeAssistantText(text);
    if (!sanitized) {
      return "<p>" + escapeHtml(FALLBACK_MESSAGE) + "</p>";
    }

    return sanitized
      .split(/\n{2,}/)
      .map(function (block) {
        return renderBlock(block);
      })
      .join("");
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
      link.className = "source-link";
      link.href = uniqueSources[index].url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = uniqueSources.length === 1 ? "🔗 Kaynağı Aç" : "🔗 Kaynağı Aç " + (index + 1);
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

  function addMessage(role, text, meta) {
    meta = meta || {};

    var article = document.createElement("article");
    article.className = "message " + role + " message-enter";

    var avatar = document.createElement("div");
    avatar.className = "avatar";
    avatar.textContent = role === "user" ? "SİZ" : "KAÜ";

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
    messages.appendChild(article);
    scrollMessages();

    window.setTimeout(function () {
      article.classList.remove("message-enter");
    }, 500);
  }

  function scrollMessages() {
    messages.scrollTop = messages.scrollHeight;
  }

  function showTyping() {
    typingRow.hidden = false;
    scrollMessages();
  }

  function hideTyping() {
    typingRow.hidden = true;
  }

  function autoResize() {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 200) + "px";
  }

  function playTone(kind) {
    var AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) {
      return;
    }

    try {
      if (!audioState.context) {
        audioState.context = new AudioContextClass();
      }

      if (audioState.context.state === "suspended") {
        audioState.context.resume();
      }

      var oscillator = audioState.context.createOscillator();
      var gain = audioState.context.createGain();
      var now = audioState.context.currentTime;

      oscillator.type = kind === "receive" ? "sine" : "triangle";
      oscillator.frequency.setValueAtTime(kind === "receive" ? 540 : 660, now);
      oscillator.frequency.exponentialRampToValueAtTime(kind === "receive" ? 760 : 880, now + 0.12);
      gain.gain.setValueAtTime(0.0001, now);
      gain.gain.exponentialRampToValueAtTime(0.025, now + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.18);

      oscillator.connect(gain);
      gain.connect(audioState.context.destination);
      oscillator.start(now);
      oscillator.stop(now + 0.18);
    } catch (error) {
      return;
    }
  }

  function askQuestion(question) {
    setStatus("Yanıt hazırlanıyor", "busy");
    submitButton.disabled = true;
    showTyping();

    function finishRequest() {
      submitButton.disabled = false;
      input.focus();
    }

    fetch("/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: question }),
    })
      .then(function (response) {
        if (!response.ok) {
          throw new Error("request-failed");
        }
        return response.json();
      })
      .then(function (data) {
        hideTyping();
        addMessage("assistant", data.answer || FALLBACK_MESSAGE, {
          interactionId: data.interaction_id,
          sources: data.sources || [],
        });
        setStatus("Hazır");
        playTone("receive");
        finishRequest();
      })
      .catch(function () {
        hideTyping();
        addMessage("assistant", FALLBACK_MESSAGE, {});
        setStatus("Hata", "error");
        finishRequest();
      });
  }

  function submitCurrentQuestion() {
    var question = input.value.replace(/^\s+|\s+$/g, "");
    if (!question) {
      return;
    }

    addMessage("user", question, {});
    input.value = "";
    autoResize();
    playTone("send");
    askQuestion(question);
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

  function loadHealth() {
    fetch("/health")
      .then(function (response) {
        return response.json();
      })
      .then(function (health) {
        applyLogo(health.logo_url);

        if (!health.index_ready) {
          setStatus("İndeks Bekleniyor", "busy");
          providerBox.textContent = "Arama indeksi henüz hazır değil.";
          return;
        }

        if (health.llm_provider === "ollama") {
          if (health.ollama_running && health.ollama_model_available) {
            setStatus("Ollama Aktif");
            providerBox.textContent = "Yerel model aktif: " + health.ollama_model;
          } else {
            setStatus("Ollama Bekliyor", "busy");
            providerBox.textContent = "Ollama ayarlı, model bekleniyor: " + health.ollama_model;
          }
          return;
        }

        if (health.llm_provider === "openai" && health.openai_configured) {
          setStatus("OpenAI Aktif");
          providerBox.textContent = "OpenAI yapılandırıldı: " + health.openai_model;
          return;
        }

        setStatus("Yerel RAG");
        providerBox.textContent = "Yerel RAG yanıtı kullanılıyor.";
      })
      .catch(function () {
        setStatus("Kontrol Hatası", "error");
        providerBox.textContent = "Servis durumu okunamadı.";
      });
  }

  function bindEvents() {
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      submitCurrentQuestion();
    });

    clearButton.addEventListener("click", function () {
      input.value = "";
      autoResize();
      input.focus();
    });

    Array.prototype.forEach.call(chips, function (chip) {
      chip.addEventListener("click", function () {
        input.value = chip.textContent.replace(/^\s+|\s+$/g, "");
        autoResize();
        input.focus();
      });
    });

    input.addEventListener("input", autoResize);

    input.addEventListener("keydown", function (event) {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        submitCurrentQuestion();
      }
    });
  }

  function init() {
    document.body.classList.add("js-ready");
    bindEvents();
    autoResize();
    loadHealth();
    scrollMessages();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
