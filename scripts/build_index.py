import json
from pathlib import Path
from typing import List, Dict

import faiss
import numpy as np
from dotenv import load_dotenv
from fastembed import TextEmbedding

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "data" / "proverbi.jsonl"
STORAGE_DIR = BASE_DIR / "storage"
CACHE_DIR = BASE_DIR / "storage"
INDEX_PATH = STORAGE_DIR / "faiss.index"
METADATA_PATH = STORAGE_DIR / "metadata.json"

# Modello locale multilingua, buono per FR/IT e testi brevi
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
model = TextEmbedding(model_name=MODEL_NAME,
                    cache_dir = CACHE_DIR)


def load_jsonl(path: Path) -> List[Dict]:
    rows: List[Dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Errore JSON alla riga {line_number}: {exc}") from exc

            rows.append(
                {
                    "id": str(obj.get("id", line_number)),
                    "patois": obj.get("patois", "").strip(),
                    "fr": obj.get("fr", "").strip(),
                    "it": obj.get("it", "").strip(),
                    "comune": obj.get("comune", "").strip(),
                }
            )
    return rows


def normalize(text: str) -> str:
    return " ".join(text.lower().split())


def build_text_for_embedding(item: Dict) -> str:
    # minimo rumore, massimo segnale
    return normalize(f"{item['fr']}\n{item['it']}\n{item['patois']}")


def main() -> None:
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"File non trovato: {DATA_PATH}")

    STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    rows = load_jsonl(DATA_PATH)
    if not rows:
        raise ValueError("Il file JSONL è vuoto")

    texts = [build_text_for_embedding(row) for row in rows]

    print("Generazione embeddings locali con FastEmbed...")
    vectors = np.array(list(model.embed(texts)), dtype="float32")

    faiss.normalize_L2(vectors)
    dimension = vectors.shape[1]
    index = faiss.IndexFlatIP(dimension)
    index.add(vectors)

    faiss.write_index(index, str(INDEX_PATH))
    METADATA_PATH.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Indicizzazione completata: {len(rows)} proverbi")
    print(f"Indice salvato in: {INDEX_PATH}")
    print(f"Metadata salvati in: {METADATA_PATH}")


if __name__ == "__main__":
    main()
