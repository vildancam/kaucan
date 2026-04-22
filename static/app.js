const form = document.querySelector("#askForm");
const input = document.querySelector("#questionInput");
const messages = document.querySelector("#messages");
const submitButton = document.querySelector("#submitButton");
const clearButton = document.querySelector("#clearButton");
const statusBadge = document.querySelector("#statusBadge");
const providerBox = document.querySelector("#providerBox");
const chips = document.querySelectorAll(".query-chip");

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

const renderAnswer = (text) => {
  const escaped = escapeHtml(text);
  return escaped
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(
      /(https?:\/\/[^\s<]+)/g,
      '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>'
    )
    .split(/\n{2,}/)
    .map((block) => `<p>${block.replace(/\n/g, "<br />")}</p>`)
    .join("");
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
  avatar.textContent = role === "user" ? "Siz" : "KAÜ";

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.innerHTML = role === "assistant" ? renderAnswer(text) : `<p>${escapeHtml(text)}</p>`;

  if (role === "assistant" && meta.interactionId) {
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

  article.append(avatar, bubble);
  messages.append(article);
  messages.scrollTop = messages.scrollHeight;
};

const askQuestion = async (question) => {
  setStatus("Yanıtlanıyor", "busy");
  submitButton.disabled = true;

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
    addMessage("assistant", data.answer, { interactionId: data.interaction_id });
    setStatus("Hazır");
  } catch (error) {
    addMessage(
      "assistant",
      "Bu konuda kesin bir bilgiye ulaşılamadı. Detaylı bilgi için ilgili fakülte ile iletişime geçmeniz önerilir."
    );
    setStatus("Hata", "error");
  } finally {
    submitButton.disabled = false;
    input.focus();
  }
};

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const question = input.value.trim();
  if (!question) {
    return;
  }

  addMessage("user", question);
  input.value = "";
  askQuestion(question);
});

clearButton.addEventListener("click", () => {
  input.value = "";
  input.focus();
});

chips.forEach((chip) => {
  chip.addEventListener("click", () => {
    input.value = chip.textContent.trim();
    input.focus();
  });
});

input.addEventListener("keydown", (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
    form.requestSubmit();
  }
});

const loadHealth = async () => {
  try {
    const response = await fetch("/health");
    const health = await response.json();
    if (health.llm_provider === "ollama") {
      if (health.ollama_running && health.ollama_model_available) {
        setStatus("Ollama Aktif");
        providerBox.textContent = `Yerel model aktif: ${health.ollama_model}`;
      } else {
        setStatus("Ollama Bekliyor", "busy");
        providerBox.textContent = `Ollama ayarlı, model bekleniyor: ${health.ollama_model}`;
      }
    } else if (health.llm_provider === "openai" && health.openai_configured) {
      setStatus("OpenAI Ayarlı");
      providerBox.textContent = `OpenAI API yapılandırıldı: ${health.openai_model}`;
    } else {
      setStatus("Yerel RAG");
      providerBox.textContent = "OpenAI API anahtarı tanımlı değil; yerel RAG yanıtı kullanılacak.";
    }
  } catch (error) {
    setStatus("Kontrol Hatası", "error");
    providerBox.textContent = "Servis durumu okunamadı.";
  }
};

loadHealth();
