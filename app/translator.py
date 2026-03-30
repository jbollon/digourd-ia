import json
from pathlib import Path
from typing import Dict, List
import spacy
import re

BASE_DIR = Path(__file__).resolve().parent.parent
DICT_PATH = BASE_DIR / "data" / "fr_pt_dictionary.json"
PREF_PATH = BASE_DIR / "config" / "dialect_preferences.json"

nlp = spacy.load("fr_core_news_sm")


class PatoisTranslator:
    def __init__(self):
        self.dictionary = self._load_dictionary()
        self.preferences = self._load_preferences()
        self.index = self._build_index()

    def _load_dictionary(self) -> List[Dict]:
        with open(DICT_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    def _load_preferences(self) -> List[str]:
        with open(PREF_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("default", [])

    def _build_index(self) -> Dict[str, List[Dict]]:
        idx = {}
        for row in self.dictionary:
            key = row["fr"].strip().lower()
            idx.setdefault(key, []).append(row)
        return idx

    def _pick_variant(self, candidates: List[Dict]) -> str:
        rank = {name: i for i, name in enumerate(self.preferences)}
        candidates = sorted(candidates, key=lambda x: rank.get(x["dialect"], 999))
        return candidates[0]["fp"]

    def _translate_token(self, token) -> str:
        if not token.is_alpha:
            return token.text + token.whitespace_

        lemma = token.lemma_.lower().strip()
        surface = token.text.lower().strip()

        candidates = self.index.get(lemma) or self.index.get(surface)
        if not candidates:
            return token.text + token.whitespace_

        return self._pick_variant(candidates) + token.whitespace_



    def translate_text(self, text: str) -> str:
        # Trova tutte le parti ((...))
        pattern = r"\(\((.*?)\)\)"
        
        parts = []
        last_end = 0
    
        for match in re.finditer(pattern, text):
            start, end = match.span()
    
            # Parte da tradurre (prima del match)
            if start > last_end:
                segment = text[last_end:start]
                doc = nlp(segment)
                translated = "".join(self._translate_token(token) for token in doc)
                parts.append(translated)
    
            # Parte NON tradotta (dentro ((...))) → solo testo interno
            protected_text = match.group(1)
            parts.append(protected_text)
    
            last_end = end
    
        # Ultima parte dopo l'ultimo match
        if last_end < len(text):
            segment = text[last_end:]
            doc = nlp(segment)
            translated = "".join(self._translate_token(token) for token in doc)
            parts.append(translated)
    
        return "".join(parts).strip()
