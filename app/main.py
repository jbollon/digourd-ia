from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.models import ChatRequest, ChatResponse, RetrievedDoc
from app.rag import ProverbsRAG


app = FastAPI(title="Digourd-IA")
rag = ProverbsRAG()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    retrieved = rag.retrieve(payload.message)
    answer = rag.generate_answer(payload.message, retrieved, payload.history or [])
    docs = [RetrievedDoc(**item) for item in retrieved]
    return ChatResponse(answer=answer, retrieved=docs)
