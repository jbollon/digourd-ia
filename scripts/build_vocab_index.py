"""
Costruisce l'indice FAISS per vocabolario e frasi dialettali.

Uso:
    python scripts/build_vocab_index.py
"""
import json
from pathlib import Path
from typing import List, Dict

import faiss
import numpy as np
from dotenv import load_dotenv
from fastembed import TextEmbedding

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
STORAGE_DIR = BASE_DIR / "storage"
CACHE_DIR = STORAGE_DIR

VOCAB_PATH  = BASE_DIR / "data" / "vocabolario.jsonl"
FRASI_PATH  = BASE_DIR / "data" / "frasi.jsonl"
INDEX_PATH  = STORAGE_DIR / "vocab.index"
META_PATH   = STORAGE_DIR / "vocab_metadata.json"

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
model = TextEmbedding(model_name=MODEL_NAME, cache_dir=CACHE_DIR)


def load_jsonl(path: Path) -> List[Dict]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def normalize(text: str) -> str:
    return " ".join(text.lower().split())


def build_text(item: Dict) -> str:
    """Testo da embeddare: combina patois, traduzione e contesto/uso."""
    parts = [
        item.get("patois", ""),
        item.get("it", ""),
        item.get("fr", ""),
        item.get("contesto", item.get("uso", "")),
    ]
    return normalize(" ".join(p for p in parts if p))


def main() -> None:
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    rows: List[Dict] = []

    if VOCAB_PATH.exists():
        vocab = load_jsonl(VOCAB_PATH)
        for r in vocab:
            r["_tipo"] = "vocabolo"
        rows.extend(vocab)
        print(f"vocabolario.jsonl: {len(vocab)} voci")
    else:
        print(f"ATTENZIONE: {VOCAB_PATH} non trovato, saltato")

    if FRASI_PATH.exists():
        frasi = load_jsonl(FRASI_PATH)
        for r in frasi:
            r["_tipo"] = "frase"
        rows.extend(frasi)
        print(f"frasi.jsonl: {len(frasi)} frasi")
    else:
        print(f"ATTENZIONE: {FRASI_PATH} non trovato, saltato")

    if not rows:
        raise ValueError("Nessun dato trovato nei file jsonl")

    texts = [build_text(r) for r in rows]

    print("Generazione embeddings...")
    vectors = np.array(list(model.embed(texts)), dtype="float32")
    faiss.normalize_L2(vectors)

    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)

    faiss.write_index(index, str(INDEX_PATH))
    META_PATH.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Indicizzazione completata: {len(rows)} voci totali")
    print(f"Indice: {INDEX_PATH}")
    print(f"Metadata: {META_PATH}")


if __name__ == "__main__":
    main()
