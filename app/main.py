import json

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.models import ChatRequest, ChatResponse, RetrievedDoc
from app.rag import ProverbsRAG
from app.auth import auth_middleware, add_auth_routes, REQUIRE_AUTH, SESSION_SECRET
from app.daily import get_daily_proverb_id, save_daily_comment


app = FastAPI(title="Digourd-IA")


class ServiceWorkerHeaderMiddleware(BaseHTTPMiddleware):
    """Allow sw.js (served under /static/) to control the full site scope."""
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if request.url.path == "/static/sw.js":
            response.headers["Service-Worker-Allowed"] = "/"
            response.headers["Content-Type"] = "application/javascript"
        return response


rag = ProverbsRAG()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth middleware (deve girare prima di ServiceWorker e dopo Session)
if REQUIRE_AUTH:
    app.middleware("http")(auth_middleware)
    add_auth_routes(app)

app.add_middleware(ServiceWorkerHeaderMiddleware)

# SessionMiddleware deve essere il più esterno (aggiunto per ultimo)
# così inizializza request.session prima di tutti gli altri middleware
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/daily")
def daily_proverb():
    all_ids = [item["id"] for item in rag.metadata]
    proverb_id, comment = get_daily_proverb_id(all_ids, rag.metadata)
    item = next((p for p in rag.metadata if p["id"] == proverb_id), None)
    if not item:
        return {"error": "Proverbio non trovato"}
    if not comment:
        comment = rag.generate_daily_comment(item)
        save_daily_comment(comment)
    return {
        "id":      item["id"],
        "patois":  item["patois"],
        "fr":      item["fr"],
        "it":      item["it"],
        "comune":  item["comune"],
        "comment": comment,
    }


@app.post("/chat/stream")
def chat_stream(payload: ChatRequest):
    retrieved = rag.retrieve(payload.message)
    songs     = rag.retrieve_songs(payload.message)

    retrieved_payload = [
        {"id": d["id"], "patois": d["patois"], "fr": d["fr"],
         "it": d["it"], "comune": d["comune"]}
        for d in retrieved
    ]
    songs_payload = [
        {"id": s["id"], "titolo": s["titolo"], "video_url": s["video_url"]}
        for s in songs
    ]

    def generate():
        for chunk in rag.stream_answer(
            payload.message, retrieved, payload.history or [], songs
        ):
            yield f"data: {json.dumps({'text': chunk})}\n\n"
        yield f"data: {json.dumps({'done': True, 'retrieved': retrieved_payload, 'songs': songs_payload})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    retrieved = rag.retrieve(payload.message)
    answer = rag.generate_answer(payload.message, retrieved, payload.history or [])
    docs = [RetrievedDoc(**item) for item in retrieved]
    return ChatResponse(answer=answer, retrieved=docs)
