import json
import os
from pathlib import Path
from typing import List, Dict, Any

import faiss
import numpy as np
import voyageai
from anthropic import Anthropic
from dotenv import load_dotenv

from app.prompts import SYSTEM_PROMPT, build_user_prompt


load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
STORAGE_DIR = BASE_DIR / "storage"
INDEX_PATH = STORAGE_DIR / "faiss.index"
METADATA_PATH = STORAGE_DIR / "metadata.json"

VOYAGE_MODEL = os.getenv("VOYAGE_MODEL", "voyage-3.5")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5")
TOP_K = int(os.getenv("TOP_K", "3"))

voyage_client = voyageai.Client(api_key=os.getenv("VOYAGE_API_KEY"))
anthropic_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


class ProverbsRAG:
    def __init__(self) -> None:
        if not INDEX_PATH.exists() or not METADATA_PATH.exists():
            raise FileNotFoundError(
                "Indice non trovato. Esegui prima: python scripts/build_index.py"
            )

        self.index = faiss.read_index(str(INDEX_PATH))
        self.metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))

    def embed_query(self, query: str) -> np.ndarray:
        result = voyage_client.embed(
            [query],
            model=VOYAGE_MODEL,
            input_type="query",
        )
        vector = np.array(result.embeddings[0], dtype="float32")
        return vector.reshape(1, -1)

    def retrieve(self, query: str, top_k: int = TOP_K) -> List[Dict[str, Any]]:
        query_vector = self.embed_query(query)
        scores, indices = self.index.search(query_vector, top_k)
        print(f"{top_k} -> top_l")

        results: List[Dict[str, Any]] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:
                continue
            item = self.metadata[idx].copy()
            item["score"] = float(score)
            results.append(item)
        return results

    @staticmethod
    def format_context(items: List[Dict[str, Any]]) -> str:
        chunks = []
        for i, item in enumerate(items, start=1):
            chunks.append(
                f"""
Documento {i}
ID: {item['id']}
Proverbio (dialetto): {item['patois']}
Traduzione francese: {item['francese']}
Traduzione italiana: {item['italiano']}
Significato: {item['significato']}
""".strip()
            )
        return "\n\n".join(chunks)

    def generate_answer(self, user_query: str, retrieved_items: List[Dict[str, Any]]) -> str:
        context = self.format_context(retrieved_items)
        user_prompt = build_user_prompt(user_query, context)

        response = anthropic_client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=700,
            temperature=0.2,
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": user_prompt}
            ],
        )

        print(context)
        print(response)

        parts = []
        for block in response.content:
            if getattr(block, "type", None) == "text":
                parts.append(block.text)
        return "\n".join(parts).strip()
