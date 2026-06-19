# ============================================================
# scraper_thinkimmo.py – ThinkImmo API (50 Portale in einem!)
# Deckt ab: IS24, ImmoWelt, Kleinanzeigen + 47 weitere
# Auth: Chrome-Session (kein separater API-Key nötig)
# ============================================================

import json
import time
import requests
from config import KEYWORDS_NEGATIV


API_BASE  = "https://api.thinkimmo.com"
AUTH_URL  = "https://thinkimmo.com/api/auth/session"

# Geo-Filter: Sachsen gesamt (wird danach per PLZ gefiltert)
GEO_SACHSEN = [{
    "geoSearchQuery": "Sachsen",
    "geoSearchType":  "state",
    "region":         "Sachsen",
}]

PAGE_SIZE = 100   # max. pro Anfrage
MAX_PAGES = 25    # max. Seiten (= 2.500 Ergebnisse)


def _get_session(cookies: dict = None) -> requests.Session:
    """
    Baut eine authentifizierte Session auf.
    Wenn `cookies` übergeben wird (z.B. aus der Webapp-DB), wird dieser
    Cookie-Satz verwendet. Sonst wird versucht, ihn aus dem lokalen
    Chrome-Browser auszulesen (nur auf dem Mac möglich).
    """
    if cookies is None:
        try:
            from pycookiecheat import chrome_cookies
        except ImportError:
            raise RuntimeError(
                "ThinkImmo: kein Cookie übergeben und pycookiecheat nicht verfügbar "
                "— bitte Cookie über die Webapp hinterlegen oder lokal mit Chrome-Login ausführen"
            )
        cookies = chrome_cookies("https://thinkimmo.com")
    s = requests.Session()
    s.cookies.update(cookies)
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept":     "application/json",
        "Referer":    "https://thinkimmo.com/search",
    })
    auth = s.get(AUTH_URL, timeout=10).json()
    token = auth.get("accessToken", "")
    if not token:
        raise RuntimeError("ThinkImmo: Kein Access-Token — bitte Chrome öffnen und bei ThinkImmo einloggen")
    s.headers["Authorization"] = f"Bearer {token}"
    return s


def _plattform_label(platforms: list) -> str:
    """Wandelt interne Kürzel in lesbare Namen um."""
    namen = {
        "is24":    "ImmoScout24",
        "iw":      "ImmoWelt",
        "ebk":     "Kleinanzeigen",
        "immonet": "ImmoNet",
        "ohne":    "OhneMakler",
        "kip":     "KIP",
    }
    kuerzel = [p.get("name", "") for p in platforms]
    return ", ".join(namen.get(k, k) for k in kuerzel[:2])


def _ist_relevant(titel: str) -> bool:
    titel_lower = titel.lower()
    return not any(k in titel_lower for k in KEYWORDS_NEGATIV)


def suche_thinkimmo(plz_set: set, cookies: dict = None) -> list:
    """
    Sucht Grundstücke auf ThinkImmo (50 Portale gleichzeitig),
    filtert nach PLZ-Gebiet und gibt strukturierte Einträge zurück.

    `cookies`: optionaler Cookie-Satz (z.B. aus der Webapp-DB), ersetzt
    die Chrome-Cookie-Extraktion, wenn übergeben.
    """
    print("  ThinkImmo: Authentifiziere...")
    try:
        s = _get_session(cookies)
    except RuntimeError as e:
        print(f"  ⚠ {e}")
        return []

    ergebnisse = []
    gesehen_ids = set()

    for page in range(MAX_PAGES):
        params = {
            "active":            "true",
            "type":              "LANDBUY",
            "sortBy":            "publishDate,desc",
            "from":              page * PAGE_SIZE,
            "size":              PAGE_SIZE,
            "grossReturnAnd":    "false",
            "allowUnknown":      "false",
            "favorite":          "false",
            "excludedFields":    "true",
            "geoSearches":       json.dumps(GEO_SACHSEN),
            "averageAggregation":"buyingPrice;pricePerSqm;plotArea;runningTime",
            "termsAggregation":  "platforms.name.keyword,60",
        }

        try:
            r = s.get(f"{API_BASE}/immo", params=params, timeout=20)
            r.raise_for_status()
        except Exception as e:
            print(f"  ThinkImmo Seite {page+1}: Fehler – {e}")
            break

        data    = r.json()
        total   = data.get("total", 0)
        results = data.get("results", [])

        if not results:
            break

        for item in results:
            item_id = item.get("id", "")
            if item_id in gesehen_ids:
                continue
            gesehen_ids.add(item_id)

            plz = str(item.get("zip", "") or "").zfill(5)
            if plz not in plz_set:
                continue

            titel = item.get("title", "")
            if not _ist_relevant(titel):
                continue

            preis     = item.get("buyingPrice")
            groesse   = item.get("squareMeter") or item.get("plotArea")
            plattform = _plattform_label(item.get("platforms", []))

            # Expose-Link aufbauen
            plattform_data = item.get("platforms", [])
            link = ""
            for p in plattform_data:
                name = p.get("name", "")
                pid  = p.get("id", "")
                if name == "is24" and pid:
                    link = f"https://www.immobilienscout24.de/expose/{pid}"
                    break
                elif name == "iw" and pid:
                    link = f"https://www.immowelt.de/expose/{pid}"
                    break
                elif name == "ebk" and pid:
                    link = f"https://www.kleinanzeigen.de/s-anzeige/x/{pid}"
                    break
            if not link:
                link = f"https://thinkimmo.com/search?id={item_id}"

            ergebnisse.append({
                "plattform": plattform or "ThinkImmo",
                "titel":     titel[:100],
                "plz":       plz,
                "ort":       item.get("city", ""),
                "adresse":   item.get("street", "") or "",
                "groesse":   f"{groesse} m²" if groesse else "",
                "preis":     f"{int(preis):,} €".replace(",", ".") if preis else "Preis auf Anfrage",
                "bplan":     "unbekannt",
                "anbieter":  item.get("broker", {}).get("name", "") if isinstance(item.get("broker"), dict) else "",
                "link":      link,
                "notizen":   "",
            })

        gefunden = len([e for e in ergebnisse])
        print(f"  ThinkImmo Seite {page+1}/{(total//PAGE_SIZE)+1}: "
              f"{len(results)} geladen, {gefunden} im Gebiet (gesamt {total})")

        if (page + 1) * PAGE_SIZE >= total:
            break

        time.sleep(0.5)

    print(f"ThinkImmo gesamt: {len(ergebnisse)} Grundstücke im PLZ-Gebiet")
    return ergebnisse
