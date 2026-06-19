# ============================================================
# config.py – Zentrale Konfiguration
# ============================================================

import os

# Pfade
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
_PLZ_FILE_LOKAL = os.path.join(BASE_DIR, "..", "PLZ-Gebiet_29.08.24.xlsx")
PLZ_FILE   = os.environ.get(
    "PLZ_FILE",
    _PLZ_FILE_LOKAL if os.path.exists(_PLZ_FILE_LOKAL)
    else "/Users/sophiakroehner/Desktop/Massa/7_Sophia/PLZ-Gebiet_29.08.24.xlsx",
)
EXCEL_OUT  = os.environ.get("EXCEL_OUT", "/Users/sophiakroehner/Desktop/Grundstuecke_Uebersicht.xlsx")
SEEN_FILE  = os.path.join(BASE_DIR, "bereits_gefunden.json")

# Propstack
PROPSTACK_API_KEY = "AuvE4OoSOHIxYMu2zIvNfN8jWAymlttW4Csj4lD8"
PROPSTACK_BASE    = "https://api.propstack.de/v1"

# Suchfilter
KEYWORDS_POSITIV  = ["grundstück", "bauland", "baugrundstück", "baufläche",
                     "wohnbauland", "bauplatz", "bebaubar"]
KEYWORDS_NEGATIV  = ["garage", "stellplatz", "pacht", "gewerbe",
                     "landwirtschaft", "acker", "wald", "forst",
                     "wohnung", "zimmer", "wir suchen", "suche grundstück",
                     "gesucht", "werkschutz", "fahrer", "nebenerwerb",
                     "miete", "vermiete", "zu vermieten", "zu verpachten"]

# Playwright Timeout (ms)
PLAYWRIGHT_TIMEOUT = 30_000
