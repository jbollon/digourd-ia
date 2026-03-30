import json
import os
from pathlib import Path
from typing import List, Dict

import faiss
import numpy as np
import voyageai
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "data" / "proverbi.jsonl"
STORAGE_DIR = BASE_DIR / "storage"
INDEX_PATH = STORAGE_DIR / "faiss.index"
METADATA_PATH = STORAGE_DIR / "metadata.json"

VOYAGE_MODEL = os.getenv("VOYAGE_MODEL", "voyage-3.5")
client = voyageai.Client(api_key=os.getenv("VOYAGE_API_KEY"))


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
                    "francese": obj.get("francese", "").strip(),
                    "italiano": obj.get("italiano", "").strip(),
                    "significato": obj.get("significato", "").strip(),
                }
            )
    return rows


def build_text_for_embedding(item: Dict) -> str:
    return (
        f"Proverbio in dialetto: {item['patois']}\n"
        f"Traduzione italiana: {item['francese']}\n"
        f"Traduzione italiana: {item['italiano']}\n"
        f"Significato: {item['significato']}"
    )


def main() -> None:
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"File non trovato: {DATA_PATH}")

    STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    rows = load_jsonl(DATA_PATH)
    if not rows:
        raise ValueError("Il file JSONL è vuoto")

    texts = [build_text_for_embedding(row) for row in rows]

    result = client.embed(
        texts,
        model=VOYAGE_MODEL,
        input_type="document",
    )

    vectors = np.array(result.embeddings, dtype="float32")

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

