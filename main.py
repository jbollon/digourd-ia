from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from app.models import ChatRequest, ChatResponse, RetrievedDoc
from app.rag import ProverbsRAG

from app.translator import PatoisTranslator

import logging
logger = logging.getLogger("uvicorn.error")
logger.setLevel(logging.INFO)

translator = PatoisTranslator()

app = FastAPI(title="RAG Proverbi Dialettali")
rag = ProverbsRAG()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return """
<!doctype html>
<html lang="it">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Chat proverbi dialettali</title>
  <style>
    body {
      font-family: Arial, sans-serif;
      max-width: 980px;
      margin: 0 auto;
      padding: 24px;
      background: #f6f7fb;
    }
    h1 { margin-bottom: 8px; }
    .muted { color: #666; margin-bottom: 20px; }
    #chat {
      background: white;
      border-radius: 14px;
      padding: 16px;
      min-height: 360px;
      box-shadow: 0 2px 10px rgba(0,0,0,0.08);
      overflow-y: auto;
    }
    .msg {
      padding: 12px 14px;
      border-radius: 12px;
      margin: 10px 0;
      white-space: pre-wrap;
      line-height: 1.5;
    }
    .user { background: #dff0ff; }
    .bot { background: #eef1f7; }
    .meta {
      background: #fff;
      border-radius: 12px;
      padding: 12px;
      margin-top: 14px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    }
    textarea {
      width: 100%;
      min-height: 90px;
      margin-top: 16px;
      padding: 12px;
      border-radius: 12px;
      border: 1px solid #ccc;
      resize: vertical;
      box-sizing: border-box;
    }
    button {
      margin-top: 12px;
      padding: 10px 18px;
      border: 0;
      border-radius: 10px;
      background: #111827;
      color: white;
      cursor: pointer;
    }
    button:hover { opacity: 0.92; }
    .doc {
      border-top: 1px solid #ececec;
      padding-top: 8px;
      margin-top: 8px;
    }
  </style>
</head>
<body>
  <h1>RAG proverbi in dialetto</h1>
  <div class="muted">FastAPI locale su Ubuntu + Claude per la risposta + retrieval semantico.</div>

  <div id="chat"></div>

  <textarea id="message" placeholder="Scrivi una domanda, ad esempio: 'Cerco un proverbio sul valore delle cose certe rispetto alle promesse'"></textarea>
  <button onclick="sendMessage()">Invia</button>

  <script>
    async function sendMessage() {
      const textarea = document.getElementById('message');
      const chat = document.getElementById('chat');
      const message = textarea.value.trim();
      if (!message) return;

      chat.innerHTML += `<div class="msg user"><strong>Tu:</strong> ${escapeHtml(message)}</div>`;
      textarea.value = '';

      const response = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message })
      });

      const data = await response.json();
      chat.innerHTML += `<div class="msg bot"><strong>Assistente:</strong> ${escapeHtml(data.answer)}</div>`;

      const docsHtml = data.retrieved.map(doc => `
        <div class="doc">
          <strong>${escapeHtml(doc.patois)}</strong><br>
          <em>${escapeHtml(doc.it)}</em><br>
          <em>${escapeHtml(doc.fr)}</em><br>
          <small>ID: ${escapeHtml(doc.id)} | score: ${doc.score.toFixed(4)}</small>
        </div>
      `).join('');

 <!--     chat.innerHTML += `<div class="meta"><strong>Contesto recuperato</strong>${docsHtml}</div>`;-->
      chat.scrollTop = chat.scrollHeight;
    }

    function escapeHtml(text) {
      return text
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#039;');
    }
  </script>
</body>
</html>
    """


@app.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    retrieved = rag.retrieve(payload.message)
    #answer = rag.generate_answer(payload.message, retrieved)

    answer_fr = rag.generate_answer(payload.message, retrieved)
    logger.info(answer_fr)
    #answer_pt = translator.translate_text(answer_fr)
    
    #answer_pt = "ciao" #answer_pt + "\n" + answer_fr

    docs = [RetrievedDoc(**item) for item in retrieved]
    return ChatResponse(answer=answer_fr, retrieved=docs)

