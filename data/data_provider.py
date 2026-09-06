import requests
import json
import os

CELESTRAK_URL = (
    "https://celestrak.org/NORAD/elements/gp.php"
    "?GROUP=STATIONS&FORMAT=JSON"
)

CACHE_FILE = "data/active_satellites.json"

def fetch_satellites():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r")as file:
            return json.load(file)

    response = requests.get(CELESTRAK_URL, timeout=20)

    if response.status_code != 200:
        print("CelesTrak error:", response.status_code)
        print(response.text)
        return []

    satellites = response.json()

    os.makedirs("data", exist_ok=True)

    with open(CACHE_FILE, "w") as file:
        json.dump(satellites, file)

    return response.json()

