import json
import os
from pathlib import Path
from typing import List, Dict, Any

import faiss
import numpy as np
from anthropic import Anthropic
from dotenv import load_dotenv
from fastembed import TextEmbedding

from app.prompts import SYSTEM_PROMPT, build_user_prompt

load_dotenv()

BASE_DIR    = Path(__file__).resolve().parent.parent
STORAGE_DIR = BASE_DIR / "storage"
CACHE_DIR   = STORAGE_DIR

INDEX_PATH       = STORAGE_DIR / "faiss.index"
METADATA_PATH    = STORAGE_DIR / "metadata.json"
VOCAB_INDEX_PATH = STORAGE_DIR / "vocab.index"
VOCAB_META_PATH  = STORAGE_DIR / "vocab_metadata.json"

CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5")
TOP_K        = int(os.getenv("TOP_K", "3"))
VOCAB_TOP_K  = int(os.getenv("VOCAB_TOP_K", "4"))
MODEL_NAME   = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
EMBED_MODEL  = os.getenv("EMBED_MODEL", MODEL_NAME)

anthropic_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
embedder = TextEmbedding(model_name=EMBED_MODEL, cache_dir=CACHE_DIR)


def normalize(text: str) -> str:
    return " ".join(text.lower().split())


class ProverbsRAG:
    def __init__(self) -> None:
        if not INDEX_PATH.exists() or not METADATA_PATH.exists():
            raise FileNotFoundError(
                "Indice proverbi non trovato. Esegui: python scripts/build_index.py"
            )
        self.index    = faiss.read_index(str(INDEX_PATH))
        self.metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))

        self._vocab_index: Any = None
        self._vocab_meta: List[Dict] = []
        if VOCAB_INDEX_PATH.exists() and VOCAB_META_PATH.exists():
            self._vocab_index = faiss.read_index(str(VOCAB_INDEX_PATH))
            self._vocab_meta  = json.loads(VOCAB_META_PATH.read_text(encoding="utf-8"))
        else:
            print("WARNING: indice vocabolario non trovato. "
                  "Esegui: python scripts/build_vocab_index.py")

    def _embed(self, text: str) -> np.ndarray:
        vec = np.array(
            list(embedder.embed([normalize(text)]))[0],
            dtype="float32",
        ).reshape(1, -1)
        faiss.normalize_L2(vec)
        return vec

    def retrieve(self, query: str, top_k: int = TOP_K) -> List[Dict[str, Any]]:
        scores, indices = self.index.search(self._embed(query), top_k)
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:
                continue
            item = self.metadata[idx].copy()
            item["score"] = float(score)
            results.append(item)
        return results

    def retrieve_vocab(self, query: str, top_k: int = VOCAB_TOP_K) -> List[Dict[str, Any]]:
        if self._vocab_index is None:
            return []
        scores, indices = self._vocab_index.search(self._embed(query), top_k)
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:
                continue
            item = self._vocab_meta[idx].copy()
            item["score"] = float(score)
            results.append(item)
        return results

    @staticmethod
    def format_context(items: List[Dict[str, Any]]) -> str:
        chunks = []
        for i, item in enumerate(items, start=1):
            chunks.append(
                f"Documento {i}\n"
                f"ID: {item['id']}\n"
                f"Proverbio (patois): {item['patois']}\n"
                f"Traduzione francese: {item['fr']}\n"
                f"Traduzione italiana: {item['it']}\n"
                f"Comune: {item['comune']}"
            )
        return "\n\n".join(chunks)

    @staticmethod
    def format_vocab(items: List[Dict[str, Any]]) -> str:
        if not items:
            return ""
        lines = []
        for item in items:
            tipo = item.get("_tipo", "")
            if tipo == "frase":
                lines.append(
                    f'- [{item["id"]}] "{item["patois"]}" '
                    f'= "{item.get("it","")}" '
                    f'(contesto: {item.get("contesto","")})'
                )
            else:
                lines.append(
                    f'- [{item["id"]}] "{item["patois"]}" '
                    f'= "{item.get("it","")}" '
                    f'(uso: {item.get("uso","")})'
                )
        return "\n".join(lines)

    def generate_answer(
        self,
        user_query: str,
        retrieved_items: List[Dict[str, Any]],
        history: List[dict] = [],
    ) -> str:
        context     = self.format_context(retrieved_items)
        user_prompt = build_user_prompt(user_query, context)

        # ── Step 1: risposta base ─────────────────────────────────────────────
        messages = history + [{"role": "user", "content": user_prompt}]

        base_response = anthropic_client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=700,
            temperature=0.2,
            system=SYSTEM_PROMPT,
            messages=messages,
        )
        base_answer = "\n".join(
            block.text
            for block in base_response.content
            if getattr(block, "type", None) == "text"
        ).strip()

        # ── Step 2: arricchimento con vocabolario ─────────────────────────────
        vocab_items = self.retrieve_vocab(base_answer)
        if not vocab_items:
            return base_answer

        vocab_context = self.format_vocab(vocab_items)

        enrichment_prompt = (
            f"Hai appena generato questa risposta:\n\n{base_answer}\n\n"
            f"Ora DEVI riscriverla integrando OBBLIGATORIAMENTE almeno 3 di queste "
            f"espressioni in patois valdostano, inserendole nel testo in modo che suonino "
            f"naturali (puoi adattare leggermente la frase che le circonda):\n\n"
            f"{vocab_context}\n\n"
            f"Regole ferree:\n"
            f"- Usa ALMENO 3 espressioni dalla lista, anche più se si adattano bene.\n"
            f"- Privilegia l'uso dell'espressione 'de no s-atre'.\n"
            f"- Inseriscile nel testo della risposta (introduzione o commento finale), "
            f"NON nei marker ((patois:...)), ((fr:...)), ((it:...)) che devono restare intatti.\n"
            f"- Mantieni esattamente il formato con i tre marker consecutivi senza righe vuote.\n"
            f"- Non spiegare cosa hai fatto, rispondi direttamente."
        )

        enriched_response = anthropic_client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=800,
            temperature=0.4,
            system=SYSTEM_PROMPT,
            messages=messages + [
                {"role": "assistant", "content": base_answer},
                {"role": "user",      "content": enrichment_prompt},
            ],
        )

        return "\n".join(
            block.text
            for block in enriched_response.content
            if getattr(block, "type", None) == "text"
        ).strip()
