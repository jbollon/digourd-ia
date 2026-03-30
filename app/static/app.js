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

function renderSources(retrieved) {
  if (!retrieved?.length) return "";

  const cards = retrieved.map(doc => `
    <div class="source-card">
      <div class="patois">${escapeHtml(doc.patois)}</div>
      <div>${escapeHtml(doc.fr)}</div>
      <div>${escapeHtml(doc.it)}</div>
      <div class="meta">
        ${escapeHtml(doc.comune || "")} · score ${Number(doc.score).toFixed(4)}
      </div>
    </div>
  `).join("");

  return `<div class="sources">${cards}</div>`;
}

async function sendMessage() {
  const textarea = document.getElementById("message");
  const message = textarea.value.trim();
  if (!message) return;

  const sendBtn = document.getElementById("sendBtn");
  sendBtn.disabled = true;

  addMessage("user", `<strong>Vous</strong>${escapeHtml(message)}`);
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

    typingEl.innerHTML = `
      <strong>Digourd-IA</strong>
      ${escapeHtml(data.answer)}
      ${renderSources(data.retrieved)}
    `;
  } catch (error) {
    typingEl.innerHTML = `
      <strong>Digourd-IA</strong>
      Une erreur s'est produite pendant la requête.
    `;
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
