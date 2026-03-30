from pydantic import BaseModel
from typing import List, Optional


class ChatRequest(BaseModel):
    message: str
    history: Optional[List[dict]] = None


class RetrievedDoc(BaseModel):
    id: str
    patois: str
    fr: str
    it: str
    comune: str
    score: float


class ChatResponse(BaseModel):
    answer: str
    retrieved: List[RetrievedDoc]
