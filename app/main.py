from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.models import ChatRequest, ChatResponse, RetrievedDoc
from app.rag import ProverbsRAG
from app.auth import auth_middleware, add_auth_routes, REQUIRE_AUTH, SESSION_SECRET
from app.daily import get_daily_proverb_id


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
    proverb_id = get_daily_proverb_id(all_ids)
    item = next((p for p in rag.metadata if p["id"] == proverb_id), None)
    if not item:
        return {"error": "Proverbio non trovato"}
    return {
        "id":      item["id"],
        "patois":  item["patois"],
        "fr":      item["fr"],
        "it":      item["it"],
        "comune":  item["comune"],
        "comment": "",
    }


@app.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    retrieved = rag.retrieve(payload.message)
    answer = rag.generate_answer(payload.message, retrieved, payload.history or [])
    docs = [RetrievedDoc(**item) for item in retrieved]
    return ChatResponse(answer=answer, retrieved=docs)
