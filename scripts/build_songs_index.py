import json
from pathlib import Path

import faiss
import numpy as np
from fastembed import TextEmbedding

BASE_DIR    = Path(__file__).resolve().parent.parent
DATA_PATH   = BASE_DIR / "data" / "canzoni.jsonl"
STORAGE_DIR = BASE_DIR / "storage"
INDEX_PATH  = STORAGE_DIR / "canzoni.index"
META_PATH   = STORAGE_DIR / "canzoni_metadata.json"
MODEL_NAME  = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

model = TextEmbedding(model_name=MODEL_NAME, cache_dir=STORAGE_DIR)


def load_jsonl(path: Path):
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def build_search_text(item: dict) -> str:
    temi = " ".join(item.get("temi", []))
    strofe_it = " ".join(s.get("it", "") for s in item.get("strofe", []))
    return " ".join([
        item.get("titolo", ""),
        item.get("descrizione", ""),
        temi,
        strofe_it,
    ]).lower()


def main():
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    rows = load_jsonl(DATA_PATH)
    if not rows:
        raise ValueError("canzoni.jsonl è vuoto")

    texts   = [build_search_text(r) for r in rows]
    vectors = np.array(list(model.embed(texts)), dtype="float32")
    faiss.normalize_L2(vectors)

    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)
    faiss.write_index(index, str(INDEX_PATH))
    META_PATH.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Indicizzazione completata: {len(rows)} canzoni")


if __name__ == "__main__":
    main()
