// ── i18n ────────────────────────────────────────────────────────────────────
const i18n = {
  it: {
    subtitle:       "L'esperta dei proverbi",
    about_title:    "Chi sono",
    about_text:     "Digourd-IA recupera proverbi in patois, le loro traduzioni e il loro significato a partire dalla tua domanda.",
    examples_title: "Esempi",
    ex1_label:      "Pazienza",
    ex1_text:       "Cerco un proverbio sulla pazienza",
    ex2_label:      "Ricchezza",
    ex2_text:       "Voglio un proverbio sulla ricchezza e il destino",
    ex3_label:      "Certezza",
    ex3_text:       "Trova un proverbio sulle cose certe contro le promesse",
    chat_title:     "Parla con Digourd-IA",
    chat_sub:       "Fai una domanda in linguaggio naturale.",
    online:         "● Online",
    placeholder:    "Es.: Cerco un proverbio sul fatto che dopo la pioggia viene il sole",
    send:           "Invia",
    you:            "Tu",
    error:          "Si è verificato un errore durante la richiesta.",
  },
  fr: {
    subtitle:       "L'experte des proverbes",
    about_title:    "À propos",
    about_text:     "Digourd-IA retrouve des proverbes en patois, leurs traductions et leur sens à partir de votre question.",
    examples_title: "Exemples",
    ex1_label:      "Patience",
    ex1_text:       "Je cherche un proverbe sur la patience",
    ex2_label:      "Richesse",
    ex2_text:       "Je veux un proverbe sur la richesse et la destinée",
    ex3_label:      "Certitude",
    ex3_text:       "Trouve un proverbe sur les choses certaines contre les promesses",
    chat_title:     "Parlez avec Digourd-IA",
    chat_sub:       "Posez une question en langage naturel.",
    online:         "● En ligne",
    placeholder:    "Ex. : Je cherche un proverbe sur le fait qu'après la pluie vient le beau temps",
    send:           "Envoyer",
    you:            "Vous",
    error:          "Une erreur s'est produite pendant la requête.",
  }
};

let currentLang = "it";

function setLang(lang) {
  currentLang = lang;
  const t = i18n[lang];

  document.querySelectorAll(".lang-btn").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.lang === lang);
  });

  document.querySelector(".brand-card p").textContent          = t.subtitle;
  document.querySelector(".info-card.about h2").textContent    = t.about_title;
  document.querySelector(".info-card.about p").textContent     = t.about_text;
  document.querySelector(".info-card.examples h2").textContent = t.examples_title;

  const exBtns = document.querySelectorAll(".example-btn");
  exBtns[0].textContent = t.ex1_label;
  exBtns[0].onclick = () => fillExample(t.ex1_text);
  exBtns[1].textContent = t.ex2_label;
  exBtns[1].onclick = () => fillExample(t.ex2_text);
  exBtns[2].textContent = t.ex3_label;
  exBtns[2].onclick = () => fillExample(t.ex3_text);

  document.querySelector(".chat-header h2").textContent = t.chat_title;
  document.querySelector(".chat-header p").textContent  = t.chat_sub;
  document.querySelector(".status-pill").textContent    = t.online;
  document.getElementById("message").placeholder        = t.placeholder;
  document.getElementById("sendBtn").textContent        = t.send;
}

// ── Helpers ──────────────────────────────────────────────────────────────────
function escapeHtml(text) {
  return String(text ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function fillExample(text) {
  document.getElementById("message").value = text;
}

function addMessage(role, html) {
  const chat = document.getElementById("chat");
  const div = document.createElement("div");
  div.className = `message ${role}`;
  div.innerHTML = html;
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
  return div;
}

/**
 * Converte il testo grezzo di Claude in HTML sicuro.
 * DEVE essere chiamata sul testo grezzo, PRIMA di escapeHtml.
 *
 *  - parti normali → escapeHtml + newline → <br>
 *  - ((patois))    → ⚫🔴 "patois" in corsivo
 */
function formatAnswer(rawText) {
  const parts = rawText.split(/\*\*(.+?)\*\*/g);
  return parts.map(part => {
    const match = part.match(/^(.+?)$/);
    if (match) {
      return `⚫🔴 <em>${escapeHtml(match[1])}</em>`;
    }
    return escapeHtml(part).replace(/\n/g, "<br>");
  }).join("");
}

// ── Send ─────────────────────────────────────────────────────────────────────
async function sendMessage() {
  const textarea = document.getElementById("message");
  const message = textarea.value.trim();
  if (!message) return;

  const sendBtn = document.getElementById("sendBtn");
  sendBtn.disabled = true;

  const t = i18n[currentLang];
  addMessage("user", `<strong>${escapeHtml(t.you)}</strong>${escapeHtml(message)}`);
  textarea.value = "";

  const typingEl = addMessage(
    "bot",
    `<strong>Digourd-IA</strong><div class="typing"><span></span><span></span><span></span></div>`
  );

  try {
    const response = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message })
    });

    const data = await response.json();

    // formatAnswer lavora sul testo grezzo — niente escapeHtml prima!
    typingEl.innerHTML = `<strong>Digourd-IA</strong><br>${formatAnswer(data.answer)}`;

  } catch (error) {
    typingEl.innerHTML = `<strong>Digourd-IA</strong><br>${escapeHtml(t.error)}`;
  } finally {
    sendBtn.disabled = false;
  }
}

document.getElementById("message")?.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

// ── Init ─────────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => setLang("it"));
