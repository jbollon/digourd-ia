// ═══════════════════════════════════════════════
// i18n
// ═══════════════════════════════════════════════
const i18n = {
  it: {
    greeting_title:  "Bondzor!",
    greeting_sub:    "Cosa vuoi scoprire oggi?",
    chip1:           "Un proverbio sull'inverno",
    chip2:           "Un proverbio sulla pazienza",
    chip3:           "Un proverbio sulla ricchezza",
    placeholder:     "Scrivi un messaggio…",
    send:            "Invia",
    you:             "Tu",
    error:           "Si è verificato un errore. Riprova.",
    save:            "Salva il proverbio",
    saved_done:      "Salvato!",
    unsave:          "Rimuovi dai salvati",
    share:           "Condividi",
  },
  fr: {
    greeting_title:  "Bondzor!",
    greeting_sub:    "Qu'est-ce que vous voulez découvrir aujourd'hui?",
    chip1:           "Un proverbe sur l'hiver",
    chip2:           "Un proverbe sur la patience",
    chip3:           "Un proverbe sur la richesse",
    placeholder:     "Écrivez un message…",
    send:            "Envoyer",
    you:             "Vous",
    error:           "Une erreur s'est produite. Réessayez.",
    save:            "Enregistrer",
    saved_done:      "Enregistré!",
    unsave:          "Supprimer",
    share:           "Partager",
  },
};

let currentLang = "it";
let previousScreen = "chat";

// ═══════════════════════════════════════════════
// Conversation history
// ═══════════════════════════════════════════════
const MAX_HISTORY = 10;
let conversationHistory = [];

function pushHistory(role, content) {
  conversationHistory.push({ role, content });
  if (conversationHistory.length > MAX_HISTORY) {
    conversationHistory = conversationHistory.slice(-MAX_HISTORY);
  }
}

// ═══════════════════════════════════════════════
// Saved proverbs (localStorage)
// ═══════════════════════════════════════════════
function getSaved() {
  try { return JSON.parse(localStorage.getItem("saved_proverbs") || "[]"); }
  catch { return []; }
}
function setSaved(arr) {
  localStorage.setItem("saved_proverbs", JSON.stringify(arr));
}
function isSaved(id) {
  return getSaved().some(p => p.id === id);
}
function toggleSave(proverb) {
  let saved = getSaved();
  const idx = saved.findIndex(p => p.id === proverb.id);
  if (idx === -1) saved.push(proverb);
  else saved.splice(idx, 1);
  setSaved(saved);
  return idx === -1; // true = now saved
}

// ═══════════════════════════════════════════════
// Screen navigation
// ═══════════════════════════════════════════════
function showScreen(name) {
  document.querySelectorAll(".screen").forEach(s => s.classList.remove("active"));
  document.getElementById("screen-" + name).classList.add("active");
  if (name === "saved") renderSavedScreen();
}

// ═══════════════════════════════════════════════
// Language toggle
// ═══════════════════════════════════════════════
function toggleLang() {
  currentLang = currentLang === "it" ? "fr" : "it";
  applyLang();
}

function applyLang() {
  const t = i18n[currentLang];
  document.querySelectorAll("#lang-btn").forEach(b => b.textContent = currentLang === "it" ? "FR" : "IT");
  document.getElementById("greeting-title").textContent  = t.greeting_title;
  document.getElementById("greeting-sub").textContent    = t.greeting_sub;
  document.getElementById("message-input").placeholder   = t.placeholder;

  const chips = document.querySelectorAll(".chip");
  if (chips[0]) { chips[0].textContent = t.chip1; chips[0].dataset.text = t.chip1; }
  if (chips[1]) { chips[1].textContent = t.chip2; chips[1].dataset.text = t.chip2; }
  if (chips[2]) { chips[2].textContent = t.chip3; chips[2].dataset.text = t.chip3; }
}

// ═══════════════════════════════════════════════
// Helpers
// ═══════════════════════════════════════════════
function escapeHtml(text) {
  return String(text ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function fillMessage(text) {
  document.getElementById("message-input").value = text;
  document.getElementById("message-input").focus();
}

/**
 * Parsa la risposta grezza di Claude e restituisce:
 * { patois, fr, it, comment, html }
 * html = versione già renderizzata per il bubble chat
 */
function parseAnswer(rawText) {
  const patoisMatch = rawText.match(/\(\(patois:\s*(.*?)\)\)/s);
  const frMatch     = rawText.match(/\(\(fr:\s*(.*?)\)\)/s);
  const itMatch     = rawText.match(/\(\(it:\s*(.*?)\)\)/s);

  const patois  = patoisMatch ? patoisMatch[1].trim() : null;
  const fr      = frMatch     ? frMatch[1].trim()     : null;
  const it      = itMatch     ? itMatch[1].trim()     : null;

  // Testo senza i marker → commento
  const comment = rawText
    .replace(/\(\(patois:.*?\)\)/s, "")
    .replace(/\(\(fr:.*?\)\)/s, "")
    .replace(/\(\(it:.*?\)\)/s, "")
    .replace(/\n{2,}/g, "\n")
    .trim();

  // HTML per il bubble
  const parts = rawText.split(/(\(\((?:patois|fr|it):[^)]*\)\))/g);
  const PREFIX = { patois: "⚫🔴", fr: "🇫🇷", it: "🇮🇹" };
  let html = "";
  let inBlock = false;
  for (const part of parts) {
    const m = part.match(/^\(\((patois|fr|it):\s*(.*?)\)\)$/s);
    if (m) {
      if (!inBlock) { html += '<div class="proverb-block">'; inBlock = true; }
      html += `<div class="proverb-line">${PREFIX[m[1]]} <em>"${escapeHtml(m[2].trim())}"</em></div>`;
    } else {
      if (inBlock) { html += "</div>"; inBlock = false; }
      html += escapeHtml(part).replace(/\n+/g, "<br>");
    }
  }
  if (inBlock) html += "</div>";

  return { patois, fr, it, comment, html };
}

// ═══════════════════════════════════════════════
// Chat: add message bubble
// ═══════════════════════════════════════════════
let lastParsed = null; // last parsed proverb from AI response

function addBubble(role, htmlContent, proverbData = null) {
  const container = document.getElementById("chat-messages");

  // hide chips after first user message
  if (role === "user") {
    const chips = document.getElementById("quick-chips");
    if (chips) chips.style.display = "none";
  }

  const wrap = document.createElement("div");
  wrap.className = role === "user"
    ? "flex justify-end"
    : "flex justify-start";

  if (role === "user") {
    wrap.innerHTML = `
      <div class="max-w-[80%] bg-primary/10 text-on-surface px-5 py-3 rounded-2xl rounded-br-sm text-base leading-relaxed">
        ${htmlContent}
      </div>`;
  } else {
    // Bot bubble with optional save button
    const saveBtn = proverbData ? `
      <button onclick='handleSaveFromChat(${JSON.stringify(proverbData).replace(/'/g, "&#039;")})'
              class="save-btn mt-3 flex items-center gap-1.5 text-xs font-bold text-primary hover:text-primary/70 transition-colors"
              data-id="${escapeHtml(proverbData.id)}">
        <span class="material-symbols-outlined text-base">bookmark</span>
        <span class="save-label">${i18n[currentLang].save}</span>
      </button>` : "";

    wrap.innerHTML = `
      <div class="max-w-[88%] bg-surface-container-low border border-outline-variant/20 px-5 py-4 rounded-2xl rounded-bl-sm shadow-sm">
        <p class="text-[10px] font-bold uppercase tracking-widest text-primary mb-2 opacity-80">Digourd-IA</p>
        <div class="text-base leading-relaxed font-serif text-on-surface">${htmlContent}</div>
        ${saveBtn}
      </div>`;
  }

  container.appendChild(wrap);
  container.scrollTop = container.scrollHeight;
  return wrap;
}

function addTyping() {
  const container = document.getElementById("chat-messages");
  const wrap = document.createElement("div");
  wrap.className = "flex justify-start";
  wrap.id = "typing-indicator";
  wrap.innerHTML = `
    <div class="bg-surface-container-low border border-outline-variant/20 px-5 py-4 rounded-2xl rounded-bl-sm shadow-sm">
      <p class="text-[10px] font-bold uppercase tracking-widest text-primary mb-2 opacity-80">Digourd-IA</p>
      <div class="flex gap-1.5 items-center">
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
      </div>
    </div>`;
  container.appendChild(wrap);
  container.scrollTop = container.scrollHeight;
  return wrap;
}

// ═══════════════════════════════════════════════
// Chat: save button inside bubble
// ═══════════════════════════════════════════════
function handleSaveFromChat(proverbData) {
  const nowSaved = toggleSave(proverbData);
  // update all save buttons for this id
  document.querySelectorAll(`.save-btn[data-id="${proverbData.id}"]`).forEach(btn => {
    const label = btn.querySelector(".save-label");
    const icon  = btn.querySelector(".material-symbols-outlined");
    label.textContent = nowSaved ? i18n[currentLang].saved_done : i18n[currentLang].save;
    icon.style.fontVariationSettings = nowSaved ? "'FILL' 1" : "'FILL' 0";
  });
}

// ═══════════════════════════════════════════════
// Chat: send message
// ═══════════════════════════════════════════════
async function sendMessage() {
  const input = document.getElementById("message-input");
  const message = input.value.trim();
  if (!message) return;

  const sendBtn = document.getElementById("send-btn");
  sendBtn.disabled = true;
  input.value = "";

  addBubble("user", escapeHtml(message));
  const typingEl = addTyping();

  try {
    const res = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, history: conversationHistory }),
    });
    const data = await res.json();

    pushHistory("user", message);
    pushHistory("assistant", data.answer);

    typingEl.remove();

    const parsed = parseAnswer(data.answer);
    lastParsed = parsed;

    // Build proverbData for save button if we have a proverb
    let proverbData = null;
    if (parsed.patois && data.retrieved && data.retrieved.length > 0) {
      const top = data.retrieved[0];
      proverbData = {
        id:      top.id,
        patois:  parsed.patois,
        fr:      parsed.fr || top.fr,
        it:      parsed.it || top.it,
        comune:  top.comune,
        comment: parsed.comment,
      };
    }

    addBubble("bot", parsed.html, proverbData);

  } catch (e) {
    typingEl.remove();
    addBubble("bot", escapeHtml(i18n[currentLang].error));
  } finally {
    sendBtn.disabled = false;
  }
}

// ═══════════════════════════════════════════════
// Saved screen
// ═══════════════════════════════════════════════
function renderSavedScreen() {
  const grid  = document.getElementById("saved-grid");
  const empty = document.getElementById("saved-empty");
  const saved = getSaved();

  grid.innerHTML = "";
  if (saved.length === 0) {
    empty.classList.remove("hidden");
    return;
  }
  empty.classList.add("hidden");

  saved.forEach((p, i) => {
    const actNum = ["I","II","III","IV","V","VI","VII","VIII","IX","X"][i] || (i+1);
    const card = document.createElement("article");
    card.className = "group relative flex flex-col bg-surface-container-lowest rounded-xl p-7 ticket-cutout transition-all duration-300 hover:-translate-y-1 shadow-[0_10px_40px_-15px_rgba(28,28,25,0.08)] cursor-pointer";
    card.innerHTML = `
      <div class="flex justify-between items-start mb-5">
        <span class="text-[10px] font-bold uppercase tracking-[0.2em] text-outline px-2 py-1 border border-outline-variant rounded">
          Acte ${actNum}
        </span>
        <button onclick="removeSaved('${escapeHtml(p.id)}'); event.stopPropagation();"
                class="text-primary hover:text-primary/60 transition-colors">
          <span class="material-symbols-outlined" style="font-variation-settings:'FILL' 1">bookmark</span>
        </button>
      </div>
      <h3 class="font-serif text-xl mb-4 leading-snug italic text-on-surface flex-1">
        "${escapeHtml(p.patois)}"
      </h3>
      <div class="mt-auto space-y-3 pt-5 border-t border-dashed border-outline-variant">
        <div class="flex gap-3 items-start">
          <span class="text-[10px] font-bold text-secondary uppercase shrink-0 mt-0.5">IT</span>
          <p class="text-sm text-on-surface-variant">${escapeHtml(p.it || "")}</p>
        </div>
        <div class="flex gap-3 items-start">
          <span class="text-[10px] font-bold text-secondary uppercase shrink-0 mt-0.5">FR</span>
          <p class="text-sm text-on-surface-variant">${escapeHtml(p.fr || "")}</p>
        </div>
      </div>`;
    card.onclick = () => openResult(p);
    grid.appendChild(card);
  });
}

function removeSaved(id) {
  let saved = getSaved();
  setSaved(saved.filter(p => p.id !== id));
  renderSavedScreen();
}

// ═══════════════════════════════════════════════
// Result screen
// ═══════════════════════════════════════════════
let currentResultProverb = null;
let resultCameFrom = "chat";

function openResult(proverb) {
  resultCameFrom = document.querySelector(".screen.active").id.replace("screen-", "");
  currentResultProverb = proverb;

  document.getElementById("result-patois").textContent  = `"${proverb.patois}"`;
  document.getElementById("result-fr").textContent      = proverb.fr || "";
  document.getElementById("result-it").textContent      = proverb.it || "";
  document.getElementById("result-comment").textContent = proverb.comment || "";

  const comuneEl = document.getElementById("result-comune");
  if (proverb.comune) {
    comuneEl.textContent = "📍 " + proverb.comune;
    comuneEl.classList.remove("hidden");
  } else {
    comuneEl.classList.add("hidden");
  }

  updateResultSaveBtn();
  showScreen("result");
}

function updateResultSaveBtn() {
  if (!currentResultProverb) return;
  const saved = isSaved(currentResultProverb.id);
  const label = document.getElementById("result-save-label");
  const btn   = document.getElementById("result-save-btn");
  const icon  = btn.querySelector(".material-symbols-outlined");
  label.textContent = saved ? i18n[currentLang].saved_done : i18n[currentLang].save;
  icon.style.fontVariationSettings = saved ? "'FILL' 1" : "'FILL' 0";
}

function toggleSaveFromResult() {
  if (!currentResultProverb) return;
  toggleSave(currentResultProverb);
  updateResultSaveBtn();
}

function goBackFromResult() {
  showScreen(resultCameFrom);
}

function shareProverb() {
  if (!currentResultProverb) return;
  const text = `"${currentResultProverb.patois}"\n🇫🇷 ${currentResultProverb.fr}\n🇮🇹 ${currentResultProverb.it}\n\n— Digourd-IA`;
  if (navigator.share) {
    navigator.share({ text });
  } else {
    navigator.clipboard.writeText(text).then(() => alert("Copiato!"));
  }
}

// ═══════════════════════════════════════════════
// Proverbio del giorno
// ═══════════════════════════════════════════════
async function loadDailyProverb() {
  const btn = document.getElementById("daily-btn");
  const label = document.getElementById("daily-label");
  const originalLabel = label.textContent;
  btn.disabled = true;
  label.textContent = "…";

  try {
    const res = await fetch("/api/daily");
    const proverb = await res.json();
    if (proverb.error) throw new Error(proverb.error);
    openResult(proverb);
  } catch {
    label.textContent = i18n[currentLang].error;
    setTimeout(() => { label.textContent = originalLabel; }, 2000);
  } finally {
    btn.disabled = false;
    if (label.textContent === "…") label.textContent = originalLabel;
  }
}

// ═══════════════════════════════════════════════
// Enter key
// ═══════════════════════════════════════════════
document.addEventListener("DOMContentLoaded", () => {
  applyLang();

  document.getElementById("message-input")?.addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });
});
