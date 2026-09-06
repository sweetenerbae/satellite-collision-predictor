import requests

CELESTRAK_URL = (
    "https://celestrak.org/NORAD/elements/gp.php"
    "?GROUP=ACTIVE&FORMAT=JSON"
)

def fetch_satellites():
    response = requests.get(CELESTRAK_URL)
    response.raise_for_status()

    return response.json()

