const form = document.querySelector("#askForm");
const input = document.querySelector("#questionInput");
const messages = document.querySelector("#messages");
const submitButton = document.querySelector("#submitButton");
const clearButton = document.querySelector("#clearButton");
const statusBadge = document.querySelector("#statusBadge");
const providerBox = document.querySelector("#providerBox");
const chips = document.querySelectorAll(".query-chip");
const typingRow = document.querySelector("#typingRow");
const brandLogo = document.querySelector("#brandLogo");
const brandFallback = document.querySelector("#brandFallback");

const WELCOME_MESSAGE =
  "👋 Merhaba, ben KAÜCAN - Kafkas Üniversitesi Dijital Asistanı. İİBF hakkında duyurular, akademik bilgiler, personel, iletişim, sınavlar, yemek menüsü ve diğer konularda yardımcı olabilirim.";
const FALLBACK_MESSAGE =
  "⚠️ Bu konuda güvenilir bir bilgiye ulaşamadım. En doğru bilgi için fakülte ile iletişime geçmenizi öneririm.";

const audioState = {
  context: null,
};

const setStatus = (text, state = "ready") => {
  statusBadge.textContent = "";
  const dot = document.createElement("span");
  dot.className = "status-dot";
  statusBadge.append(dot, document.createTextNode(text));
  statusBadge.className = `status ${state === "ready" ? "" : state}`.trim();
};

const escapeHtml = (value) =>
  value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

const linkify = (value) =>
  value.replace(
    /(https?:\/\/[^\s<]+)/g,
    '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>'
  );

const dedupeSources = (sources = []) => {
  const unique = [];
  const seen = new Set();
  for (const source of sources) {
    if (!source?.url || seen.has(source.url)) {
      continue;
    }
    unique.push(source);
    seen.add(source.url);
  }
  return unique;
};

const normalizeAssistantLine = (line) => {
  let cleaned = line.replace(/\*\*/g, "").replace(/__/g, "").trim();
  if (!cleaned) {
    return "";
  }

  const labelPatterns = [
    /^(?:📖|📎)?\s*(açıklama|description|detaylar?)\s*:\s*/i,
    /^(?:✅)?\s*(sonuç|sonuc)\s*:\s*/i,
  ];

  labelPatterns.forEach((pattern) => {
    cleaned = cleaned.replace(pattern, "");
  });

  if (/^(?:🔗)?\s*(kaynak|source|sources)\s*:?.*$/i.test(cleaned)) {
    return "";
  }

  if (/^(metadata|chunk açıklaması|chunk aciklamasi)\s*:?.*$/i.test(cleaned)) {
    return "";
  }

  cleaned = cleaned.replace(/https?:\/\/[^\s]+/g, "").trim();
  return cleaned;
};

const sanitizeAssistantText = (text) => {
  const lines = (text || "")
    .split("\n")
    .map(normalizeAssistantLine)
    .filter((line, index, array) => line || array[index - 1]);

  return lines.join("\n").replace(/\n{3,}/g, "\n\n").trim();
};

const renderBlock = (block) => {
  const lines = block
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

  if (!lines.length) {
    return "";
  }

  const bulletLines = lines.filter((line) => /^[•-]\s+/.test(line));
  if (bulletLines.length === lines.length) {
    const items = bulletLines
      .map((line) => `<li>${linkify(escapeHtml(line.replace(/^[•-]\s+/, "")))}</li>`)
      .join("");
    return `<ul>${items}</ul>`;
  }

  if (
    lines.length > 1 &&
    !/^[•-]\s+/.test(lines[0]) &&
    lines.slice(1).every((line) => /^[•-]\s+/.test(line))
  ) {
    const intro = `<p>${linkify(escapeHtml(lines[0]))}</p>`;
    const items = lines
      .slice(1)
      .map((line) => `<li>${linkify(escapeHtml(line.replace(/^[•-]\s+/, "")))}</li>`)
      .join("");
    return `${intro}<ul>${items}</ul>`;
  }

  return `<p>${linkify(escapeHtml(lines.join("\n"))).replace(/\n/g, "<br />")}</p>`;
};

const renderAssistantText = (text) => {
  const sanitized = sanitizeAssistantText(text);
  if (!sanitized) {
    return `<p>${escapeHtml(FALLBACK_MESSAGE)}</p>`;
  }

  return sanitized
    .split(/\n{2,}/)
    .map((block) => renderBlock(block))
    .join("");
};

const renderUserText = (text) => `<p>${escapeHtml(text)}</p>`;

const renderSources = (sources = []) => {
  const uniqueSources = dedupeSources(sources);
  if (!uniqueSources.length) {
    return null;
  }

  const wrapper = document.createElement("div");
  wrapper.className = "source-links";

  uniqueSources.forEach((source, index) => {
    const link = document.createElement("a");
    link.className = "source-link";
    link.href = source.url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = uniqueSources.length === 1 ? "🔗 Kaynağı Aç" : `🔗 Kaynağı Aç ${index + 1}`;
    wrapper.append(link);
  });

  return wrapper;
};

const sendFeedback = async (interactionId, rating, buttons) => {
  buttons.forEach((button) => {
    button.disabled = true;
  });

  try {
    await fetch("/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ interaction_id: interactionId, rating }),
    });

    buttons.forEach((button) => {
      button.classList.toggle("selected", button.dataset.rating === rating);
    });
  } catch (error) {
    buttons.forEach((button) => {
      button.disabled = false;
    });
  }
};

const addMessage = (role, text, meta = {}) => {
  const article = document.createElement("article");
  article.className = `message ${role}`;

  const avatar = document.createElement("div");
  avatar.className = "avatar";
  avatar.textContent = role === "user" ? "SİZ" : "KAÜ";

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.innerHTML = role === "assistant" ? renderAssistantText(text) : renderUserText(text);

  if (role === "assistant") {
    const sourceLinks = renderSources(meta.sources);
    if (sourceLinks) {
      bubble.append(sourceLinks);
    }

    if (meta.interactionId) {
      const feedback = document.createElement("div");
      feedback.className = "feedback-actions";
      feedback.setAttribute("aria-label", "Yanıt geri bildirimi");

      const positive = document.createElement("button");
      positive.type = "button";
      positive.textContent = "Yararlı";
      positive.dataset.rating = "up";

      const negative = document.createElement("button");
      negative.type = "button";
      negative.textContent = "Geliştirilmeli";
      negative.dataset.rating = "down";

      const buttons = [positive, negative];
      buttons.forEach((button) => {
        button.addEventListener("click", () => {
          sendFeedback(meta.interactionId, button.dataset.rating, buttons);
        });
      });

      feedback.append(positive, negative);
      bubble.append(feedback);
    }
  }

  article.append(avatar, bubble);
  messages.append(article);

  requestAnimationFrame(() => {
    article.classList.add("is-visible");
  });

  scrollMessages();
};

const scrollMessages = () => {
  messages.scrollTop = messages.scrollHeight;
};

const showTyping = () => {
  typingRow.hidden = false;
  scrollMessages();
};

const hideTyping = () => {
  typingRow.hidden = true;
};

const autoResize = () => {
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 220)}px`;
};

const playTone = async (kind) => {
  const AudioContextClass = window.AudioContext || window.webkitAudioContext;
  if (!AudioContextClass) {
    return;
  }

  try {
    if (!audioState.context) {
      audioState.context = new AudioContextClass();
    }

    if (audioState.context.state === "suspended") {
      await audioState.context.resume();
    }

    const oscillator = audioState.context.createOscillator();
    const gain = audioState.context.createGain();
    const now = audioState.context.currentTime;

    oscillator.type = kind === "receive" ? "sine" : "triangle";
    oscillator.frequency.setValueAtTime(kind === "receive" ? 540 : 660, now);
    oscillator.frequency.exponentialRampToValueAtTime(
      kind === "receive" ? 760 : 880,
      now + 0.12
    );

    gain.gain.setValueAtTime(0.0001, now);
    gain.gain.exponentialRampToValueAtTime(0.025, now + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.18);

    oscillator.connect(gain);
    gain.connect(audioState.context.destination);
    oscillator.start(now);
    oscillator.stop(now + 0.18);
  } catch (error) {
    // Tarayıcı sesi engellerse akış sessizce devam etsin.
  }
};

const askQuestion = async (question) => {
  setStatus("Yanıt hazırlanıyor", "busy");
  submitButton.disabled = true;
  showTyping();

  try {
    const response = await fetch("/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });

    if (!response.ok) {
      throw new Error("İstek başarısız oldu.");
    }

    const data = await response.json();
    hideTyping();
    addMessage("assistant", data.answer || FALLBACK_MESSAGE, {
      interactionId: data.interaction_id,
      sources: data.sources || [],
    });
    setStatus("Hazır");
    void playTone("receive");
  } catch (error) {
    hideTyping();
    addMessage("assistant", FALLBACK_MESSAGE);
    setStatus("Hata", "error");
  } finally {
    submitButton.disabled = false;
    input.focus();
  }
};

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = input.value.trim();
  if (!question) {
    return;
  }

  addMessage("user", question);
  input.value = "";
  autoResize();
  void playTone("send");
  await askQuestion(question);
});

clearButton.addEventListener("click", () => {
  input.value = "";
  autoResize();
  input.focus();
});

chips.forEach((chip) => {
  chip.addEventListener("click", () => {
    input.value = chip.textContent.trim();
    autoResize();
    input.focus();
  });
});

input.addEventListener("input", autoResize);

input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    if (input.value.trim()) {
      form.requestSubmit();
    }
  }
});

const applyLogo = (logoUrl) => {
  if (!logoUrl) {
    brandLogo.hidden = true;
    brandFallback.hidden = false;
    return;
  }

  brandLogo.src = logoUrl;
  brandLogo.hidden = false;
  brandFallback.hidden = true;

  brandLogo.addEventListener(
    "error",
    () => {
      brandLogo.hidden = true;
      brandFallback.hidden = false;
    },
    { once: true }
  );
};

const loadHealth = async () => {
  try {
    const response = await fetch("/health");
    const health = await response.json();

    applyLogo(health.logo_url);

    if (!health.index_ready) {
      setStatus("İndeks Bekleniyor", "busy");
      providerBox.textContent = "Arama indeksi henüz hazır değil.";
      return;
    }

    if (health.llm_provider === "ollama") {
      if (health.ollama_running && health.ollama_model_available) {
        setStatus("Ollama Aktif");
        providerBox.textContent = `Yerel model aktif: ${health.ollama_model}`;
      } else {
        setStatus("Ollama Bekliyor", "busy");
        providerBox.textContent = `Ollama ayarlı, model bekleniyor: ${health.ollama_model}`;
      }
      return;
    }

    if (health.llm_provider === "openai" && health.openai_configured) {
      setStatus("OpenAI Aktif");
      providerBox.textContent = `OpenAI yapılandırıldı: ${health.openai_model}`;
      return;
    }

    setStatus("Yerel RAG");
    providerBox.textContent = "OpenAI veya Ollama etkin değil; yerel RAG yanıtı kullanılacak.";
  } catch (error) {
    setStatus("Kontrol Hatası", "error");
    providerBox.textContent = "Servis durumu okunamadı.";
    applyLogo(null);
  }
};

const bootstrapConversation = () => {
  addMessage("assistant", WELCOME_MESSAGE);
  autoResize();
  document.body.classList.add("is-ready");
  loadHealth();
};

bootstrapConversation();
