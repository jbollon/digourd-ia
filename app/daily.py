"""
Proverbio del giorno — selezione e persistenza su Google Cloud Storage.

Il "giorno proverbio" cambia alle 08:00 CET.
Prima delle 08:00 viene mostrato il proverbio del giorno precedente.
Quando tutti i proverbi sono stati mostrati si ricomincia da capo.
"""

import json
import random
from datetime import datetime, timedelta, timezone
from typing import Any

from google.cloud import storage

BUCKET_NAME = "digourdia0000-app-data"
STATE_BLOB  = "proverb_of_day.json"
CET         = timezone(timedelta(hours=1))   # UTC+1 (ora solare; +2 in estate ma accettabile)
CUTOFF_HOUR = 8


def _proverb_date(now: datetime) -> str:
    """Restituisce la data 'proverbio': ieri se prima delle 8:00, oggi altrimenti."""
    if now.hour < CUTOFF_HOUR:
        now = now - timedelta(days=1)
    return now.strftime("%Y-%m-%d")


def _load_state(bucket) -> dict:
    blob = bucket.blob(STATE_BLOB)
    if blob.exists():
        return json.loads(blob.download_as_text(encoding="utf-8"))
    return {"date": None, "proverb_id": None, "shown_ids": [], "history": []}


def _save_state(bucket, state: dict) -> None:
    bucket.blob(STATE_BLOB).upload_from_string(
        json.dumps(state, ensure_ascii=False, indent=2),
        content_type="application/json",
    )


def get_daily_proverb_id(all_ids: list[str]) -> str:
    """
    Restituisce l'ID del proverbio del giorno.
    Seleziona un nuovo proverbio se la data è cambiata (dopo le 08:00 CET).
    """
    now   = datetime.now(CET)
    today = _proverb_date(now)

    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)
    state  = _load_state(bucket)

    # Proverbio già selezionato per oggi
    if state["date"] == today and state["proverb_id"]:
        return state["proverb_id"]

    # Nuovo giorno — scegli un proverbio non ancora mostrato
    shown     = set(state.get("shown_ids", []))
    available = [pid for pid in all_ids if pid not in shown]

    if not available:
        # Tutti i proverbi esauriti: si ricomincia da capo
        shown     = set()
        available = all_ids

    new_id = random.choice(available)
    shown.add(new_id)

    history = state.get("history", [])
    history.append({"date": today, "proverb_id": new_id})

    _save_state(bucket, {
        "date":       today,
        "proverb_id": new_id,
        "shown_ids":  list(shown),
        "history":    history,
    })

    return new_id
