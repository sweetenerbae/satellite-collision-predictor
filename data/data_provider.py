import requests
import json
import os
import time
from pathlib import Path

CELESTRAK_URL = (
    "https://celestrak.org/NORAD/elements/gp.php"
    "?GROUP=STATIONS&FORMAT=JSON"
)

CACHE_FILE = "data/active_satellites.json"
CACHE_TTL_SECONDS = 2 * 60 * 60

def fetch_satellites():
    cache_path = Path(__file__).resolve().parent / "satellites.json"

    if is_cache_fresh(cache_path):
        with cache_path.open("r", encoding="utf-8") as file:
            return json.load(file)

    response = requests.get(
        "https://celestrak.org/NORAD/elements/gp.php?GROUP=STATIONS&FORMAT=JSON",
        timeout=30
    )

    response.raise_for_status()

    data = response.json()

    if not isinstance(data, list) or not data:
        raise ValueError("CelesTrak returned an empty or invalid catalog")

    temporary = cache_path.with_suffix(".json.tmp")
    with temporary.open("w", encoding="utf-8") as file:
        json.dump(data, file)
    temporary.replace(cache_path)

    return data
def is_cache_fresh(cache_path: Path) -> bool:
    if not cache_path.exists():
        return False

    cache_age_seconds = time.time() - cache_path.stat().st_mtime

    return cache_age_seconds < CACHE_TTL_SECONDS