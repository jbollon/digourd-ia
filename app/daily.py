"""
Proverbio del giorno — selezione intelligente e persistenza su Google Cloud Storage.

Il "giorno proverbio" cambia alle 08:00 CET.
Prima delle 08:00 viene mostrato il proverbio del giorno precedente.

Priorità di selezione (solo tra proverbi non ancora mostrati):
  1. Santo del giorno
  2. Mese corrente
  3. Stagione corrente
  4. Casuale
Quando tutti i proverbi sono stati mostrati si ricomincia da capo.
"""

import json
import random
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Any

from google.cloud import storage

BUCKET_NAME = "digourdia0000-app-data"
STATE_BLOB  = "proverb_of_day.json"
CET         = timezone(timedelta(hours=1))
CUTOFF_HOUR = 8

# ── Calendario dei santi (MM-DD → keywords da cercare nel testo del proverbio) ──
SAINTS_CALENDAR: dict[str, list[str]] = {
    "01-01": ["capodanno", "nouvel an"],
    "01-06": ["epifania", "befana", "épiphanie"],
    "01-07": ["raimondo"],
    "01-13": ["ilario"],
    "01-17": ["antonio"],
    "01-20": ["sebastiano"],
    "01-21": ["agnese"],
    "01-22": ["vincenzo", "vincent"],
    "01-24": ["timoteo"],
    "01-25": ["paolo", "paul"],
    "02-02": ["candelora", "chandeleur"],
    "02-03": ["biagio", "blaise"],
    "02-05": ["agata"],
    "02-14": ["valentino", "valentin"],
    "02-24": ["mattia", "mathias"],
    "03-12": ["gregorio", "grégoire"],
    "03-17": ["patrizio", "patrick"],
    "03-19": ["giuseppe", "joseph"],
    "03-25": ["annunciazione", "annonciation"],
    "04-23": ["giorgio", "georges"],
    "04-25": ["marco", "marc"],
    "05-01": ["giuseppe", "joseph"],
    "05-03": ["filippo", "philippe", "giacomo", "jacques"],
    "06-13": ["antonio", "antoine"],
    "06-24": ["giovanni", "jean"],
    "06-29": ["pietro", "pierre", "paolo", "paul"],
    "07-02": ["visitazione"],
    "07-22": ["maddalena", "madeleine"],
    "07-25": ["giacomo", "jacques"],
    "07-26": ["anna", "anne", "gioacchino"],
    "08-06": ["trasfigurazione"],
    "08-10": ["lorenzo", "laurent"],
    "08-15": ["assunta", "ferragosto", "assomption"],
    "08-24": ["bartolomeo", "barthélemy"],
    "09-08": ["maria", "marie", "natività"],
    "09-14": ["croce", "croix"],
    "09-21": ["matteo", "matthieu"],
    "09-29": ["michele", "michel", "gabriele", "raffaele"],
    "10-04": ["francesco", "françois"],
    "10-18": ["luca", "luc"],
    "10-28": ["simone", "giuda"],
    "11-01": ["ognissanti", "toussaint"],
    "11-02": ["morti", "défunts"],
    "11-11": ["martino", "martin"],
    "11-22": ["cecilia", "cécile"],
    "11-25": ["caterina", "catherine"],
    "11-30": ["andrea", "andré"],
    "12-04": ["barbara"],
    "12-06": ["nicola", "nicolas"],
    "12-08": ["immacolata", "immaculée"],
    "12-13": ["lucia"],
    "12-25": ["natale", "noël"],
    "12-26": ["stefano", "étienne"],
    "12-27": ["giovanni", "jean"],
}

# ── Keywords per mese ──────────────────────────────────────────────────────────
MONTH_KEYWORDS: dict[int, list[str]] = {
    1:  ["gennaio", "janvier", "zenouì", "zenvi"],
    2:  ["febbraio", "février", "frevouì"],
    3:  ["marzo", "mars"],
    4:  ["aprile", "avril"],
    5:  ["maggio", "mai"],
    6:  ["giugno", "juin"],
    7:  ["luglio", "juillet"],
    8:  ["agosto", "août", "ferragosto"],
    9:  ["settembre", "septembre"],
    10: ["ottobre", "octobre"],
    11: ["novembre"],
    12: ["dicembre", "décembre", "noël", "natale"],
}

# ── Keywords per stagione ──────────────────────────────────────────────────────
SEASON_KEYWORDS: dict[str, list[str]] = {
    "inverno":   ["inverno", "hiver", "invernale", "iveue", "iveùe"],
    "primavera": ["primavera", "printemps", "ifouryi", "ifourì"],
    "estate":    ["estate", "été", "estivo", "itsaten", "itsatèn"],
    "autunno":   ["autunno", "automne", "autunnale", "aouton", "aoutón"],
}


def _get_season(month: int) -> str:
    if month in (12, 1, 2):
        return "inverno"
    if month in (3, 4, 5):
        return "primavera"
    if month in (6, 7, 8):
        return "estate"
    return "autunno"


def _strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )


def _find_match(available_ids: list[str], metadata: list[dict], keywords: list[str]) -> str | None:
    """Restituisce un ID casuale tra i disponibili che contengono almeno una keyword."""
    id_to_meta = {m["id"]: m for m in metadata}
    kw_norm = [_strip_accents(k.lower()) for k in keywords]
    matches = []
    for pid in available_ids:
        item = id_to_meta.get(pid, {})
        text = _strip_accents(
            " ".join([item.get("patois", ""), item.get("fr", ""), item.get("it", "")])
        ).lower()
        if any(kw in text for kw in kw_norm):
            matches.append(pid)
    return random.choice(matches) if matches else None


def _select_proverb(all_ids: list[str], shown: set, metadata: list[dict], now: datetime) -> tuple[str, set]:
    """
    Applica la catena di priorità. Restituisce (proverb_id, shown_aggiornato).
    Se available è vuoto (tutti mostrati) azzera shown e riprova.
    """
    available = [pid for pid in all_ids if pid not in shown]
    if not available:
        shown = set()
        available = all_ids

    date_key = now.strftime("%m-%d")

    # 1. Santo del giorno
    saint_kws = SAINTS_CALENDAR.get(date_key)
    if saint_kws:
        match = _find_match(available, metadata, saint_kws)
        if match:
            return match, shown

    # 2. Mese
    month_kws = MONTH_KEYWORDS.get(now.month, [])
    match = _find_match(available, metadata, month_kws)
    if match:
        return match, shown

    # 3. Stagione
    season_kws = SEASON_KEYWORDS[_get_season(now.month)]
    match = _find_match(available, metadata, season_kws)
    if match:
        return match, shown

    # 4. Casuale
    return random.choice(available), shown


# ── GCS helpers ───────────────────────────────────────────────────────────────

def _proverb_date(now: datetime) -> str:
    if now.hour < CUTOFF_HOUR:
        now = now - timedelta(days=1)
    return now.strftime("%Y-%m-%d")


def _load_state(bucket) -> dict:
    blob = bucket.blob(STATE_BLOB)
    if blob.exists():
        return json.loads(blob.download_as_text(encoding="utf-8"))
    return {"date": None, "proverb_id": None, "shown_ids": [], "history": [], "comment": None}


def _save_state(bucket, state: dict) -> None:
    bucket.blob(STATE_BLOB).upload_from_string(
        json.dumps(state, ensure_ascii=False, indent=2),
        content_type="application/json",
    )


# ── API pubblica ───────────────────────────────────────────────────────────────

def get_daily_proverb_id(all_ids: list[str], metadata: list[dict]) -> tuple[str, str | None]:
    """
    Restituisce (proverb_id, comment) del proverbio del giorno.
    comment è None se non ancora generato per oggi.
    """
    now   = datetime.now(CET)
    today = _proverb_date(now)

    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)
    state  = _load_state(bucket)

    if state["date"] == today and state["proverb_id"]:
        return state["proverb_id"], state.get("comment") or None

    shown    = set(state.get("shown_ids", []))
    new_id, shown = _select_proverb(all_ids, shown, metadata, now)
    shown.add(new_id)

    history = state.get("history", [])
    history.append({"date": today, "proverb_id": new_id})

    _save_state(bucket, {
        "date":       today,
        "proverb_id": new_id,
        "shown_ids":  list(shown),
        "history":    history,
        "comment":    None,
    })

    return new_id, None


def save_daily_comment(comment: str) -> None:
    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)
    state  = _load_state(bucket)
    state["comment"] = comment
    _save_state(bucket, state)
