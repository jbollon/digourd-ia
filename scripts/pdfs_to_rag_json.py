#!/usr/bin/env python3
import argparse
import json
import os
import re
import uuid
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from pypdf import PdfReader

try:
    from anthropic import Anthropic
except Exception:
    Anthropic = None


load_dotenv()

SECTION_RE = re.compile(
    r"^[A-ZÀ-ÖØ-Ý'`\- ,]+●[A-ZÀ-ÖØ-Ý'`\- ,]+●[A-ZÀ-ÖØ-Ý'`\- ,]+$"
)
PAREN_RE = re.compile(r"^\((.+?)\)$")


@dataclass
class ProverbRecord:
    id: str
    #source_file: str
    #source_page: int
    #section_fr: Optional[str]
    #section_it: Optional[str]
    patois: str
    fr: str
    it: str
    comune: str
    search_text: str
    #ai_keywords_fr: Optional[List[str]] = None
    #ai_explanation_fr: Optional[str] = None


def normalize_line(line: str) -> str:
    line = line.replace("●", " ● ")
    line = re.sub(r"\s+", " ", line)
    return line.strip()


def is_noise_line(line: str) -> bool:
    if not line:
        return True

    lowered = line.lower()
    noise_starts = (
        "proverbe é ditón",
        "proverbes et dictons",
        "proverbi e detti",
        "padze",
        "page",
        "pagina",
    )
    if any(lowered.startswith(x) for x in noise_starts):
        return True

    if re.match(r"^page\s+\d+$", lowered):
        return True

    return False


def parse_section_header(line: str) -> Optional[Dict[str, str]]:
    # Esempio:
    # BIÈN É RETSESSE ● BIENS ET RICHESSE ● BENI E RICCHEZZA
    if "●" not in line:
        return None

    parts = [p.strip() for p in line.split("●")]
    if len(parts) != 3:
        return None

    # teniamo FR e IT; il patois è utile ma non necessario come metadato di sezione
    return {
        "section_pt": parts[0],
        "section_fr": parts[1],
        "section_it": parts[2],
    }


def clean_page_text(text: str) -> List[str]:
    lines = [normalize_line(x) for x in text.splitlines()]
    return [x for x in lines if not is_noise_line(x)]


def parse_pdf(pdf_path: Path) -> List[ProverbRecord]:
    reader = PdfReader(str(pdf_path))
    records: List[ProverbRecord] = []

    current_section_fr: Optional[str] = None
    current_section_it: Optional[str] = None

    for page_idx, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        lines = clean_page_text(text)

        i = 0
        while i < len(lines):
            line = lines[i]

            maybe_section = parse_section_header(line)
            if maybe_section:
                current_section_fr = maybe_section["section_fr"]
                current_section_it = maybe_section["section_it"]
                i += 1
                continue

            # pattern atteso:
            # 1 patois
            # 2 francese
            # 3 italiano
            # 4 (comune)
            if i + 3 < len(lines):
                l1, l2, l3, l4 = lines[i], lines[i + 1], lines[i + 2], lines[i + 3]
                m = PAREN_RE.match(l4)

                if m:
                    comune = m.group(1).strip()

                    record = ProverbRecord(
                        id=str(uuid.uuid4()),
                        #source_file=pdf_path.name,
                        #source_page=page_idx,
                        #section_fr=current_section_fr,
                        #section_it=current_section_it,
                        patois=l1,
                        fr=l2,
                        it=l3,
                        comune=comune,
                        search_text=" ".join(
                            x for x in [
                                l1, l2, l3, comune#, current_section_fr, current_section_it
                            ] if x
                        ),
                    )
                    records.append(record)
                    i += 4
                    continue

            i += 1

    return records


def enrich_with_ai(records: List[ProverbRecord], model: str) -> None:
    if not records:
        return

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY mancante nel file .env")

    if Anthropic is None:
        raise RuntimeError("Pacchetto anthropic non installato")

    client = Anthropic(api_key=api_key)

    for rec in records:
        prompt = f"""
Tu reçois un proverbe en patois avec traduction française et italienne.
Retourne uniquement un JSON valide avec:
- ai_keywords_fr: liste de 3 à 6 mots-clés en français
- ai_explanation_fr: brève explication en français, max 25 mots

Données:
patois: {rec.patois}
français: {rec.fr}
italien: {rec.it}
commune: {rec.comune}
section: {rec.section_fr or ""}
""".strip()

        msg = client.messages.create(
            model=model,
            max_tokens=200,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )

        text_parts: List[str] = []
        for block in msg.content:
            if getattr(block, "type", None) == "text":
                text_parts.append(block.text)

        raw = "\n".join(text_parts).strip()

        try:
            data = json.loads(raw)
            rec.ai_keywords_fr = data.get("ai_keywords_fr")
            rec.ai_explanation_fr = data.get("ai_explanation_fr")
        except json.JSONDecodeError:
            rec.ai_keywords_fr = None
            rec.ai_explanation_fr = None


def save_json(records: List[ProverbRecord], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(asdict(r), ensure_ascii=False) + "\n")

#def save_json(records: List[ProverbRecord], out_path: Path) -> None:
 #   payload = ora[asdict(r) for r in records]
  #  out_path.parent.mkdir(parents=True, exist_ok=True)
   # out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_dir", required=True, help="Cartella con i PDF")
    parser.add_argument("--output", required=True, help="File JSON finale")
    #parser.add_argument(
     #   "--ai-enrich",
      #  action="store_true",
       # help="Aggiunge keywords e explanation con Anthropic",
    #)
    #parser.add_argument(
     #   "--anthropic-model",
      #  default=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5"),
       # help="Modello Anthropic da usare",
    #)
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_path = Path(args.output)

    if not input_dir.exists() or not input_dir.is_dir():
        raise FileNotFoundError(f"Cartella non trovata: {input_dir}")

    pdf_files = sorted(input_dir.glob("*.pdf"))
    if not pdf_files:
        raise FileNotFoundError(f"Nessun PDF trovato in {input_dir}")

    all_records: List[ProverbRecord] = []
    for pdf_path in pdf_files:
        parsed = parse_pdf(pdf_path)
        all_records.extend(parsed)
        print(f"{pdf_path.name}: estratti {len(parsed)} proverbi")

    #if args.ai_enrich:
     #   enrich_with_ai(all_records, args.anthropic_model)

    save_json(all_records, output_path)
    print(f"Totale proverbi: {len(all_records)}")
    print(f"JSON salvato in: {output_path}")


if __name__ == "__main__":
    main()
