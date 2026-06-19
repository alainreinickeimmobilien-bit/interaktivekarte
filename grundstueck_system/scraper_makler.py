# ============================================================
# scraper_makler.py – Lokale Makler-Websites
# ============================================================

import requests
import re
import time
from bs4 import BeautifulSoup
from config import KEYWORDS_NEGATIV


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "de-DE,de;q=0.9",
}


def _parse_standard(soup, url_base, plz_set, plattform):
    """Generischer Parser für einfache Makler-Seiten."""
    ergebnisse = []
    # Suche nach Links die 'grundstueck' oder 'expose' enthalten
    links = soup.find_all("a", href=re.compile(r"grundst|expose|plot|land|bauland", re.I))
    for link in links:
        href = link.get("href", "")
        full = href if href.startswith("http") else url_base + href
        text = link.text.strip()
        # PLZ im Text prüfen
        plz_m = re.search(r"\b(0[4-9]\d{3})\b", text)
        if plz_m and plz_m.group(1) in plz_set:
            ergebnisse.append({
                "plattform": plattform,
                "titel":     text[:100],
                "plz":       plz_m.group(1),
                "ort":       "",
                "adresse":   "",
                "groesse":   "",
                "preis":     "",
                "bplan":     "unbekannt",
                "anbieter":  plattform,
                "link":      full,
                "notizen":   "",
            })
    return ergebnisse


def _scrape_estaya(plz_set: set) -> list:
    ergebnisse = []
    urls = [
        "https://www.estaya.de/grundstuecke/",
        "https://www.estaya.de/immobilien/?typ=grundstueck",
    ]
    s = requests.Session()
    s.headers.update(HEADERS)
    for url in urls:
        try:
            r = s.get(url, timeout=15)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, "lxml")
            # Estaya listet Objekte als Kacheln
            cards = soup.select(".property-item, .listing-item, article, .immobilie")
            for card in cards:
                text = card.text
                plz_m = re.search(r"\b(0[4-9]\d{3})\b", text)
                if not plz_m or plz_m.group(1) not in plz_set:
                    continue
                link_el = card.select_one("a[href]")
                href = link_el["href"] if link_el else ""
                full = href if href.startswith("http") else "https://www.estaya.de" + href
                preis_m = re.search(r"([\d\.,]+)\s*€", text)
                gr_m    = re.search(r"([\d\.,]+)\s*m[²2]", text)
                ergebnisse.append({
                    "plattform": "Estaya Immobilien",
                    "titel":     card.select_one("h2,h3,h4") and card.select_one("h2,h3,h4").text.strip()[:100] or "",
                    "plz":       plz_m.group(1),
                    "ort":       "",
                    "adresse":   "",
                    "groesse":   gr_m.group(1) + " m²" if gr_m else "",
                    "preis":     preis_m.group(1) + " €" if preis_m else "",
                    "bplan":     "unbekannt",
                    "anbieter":  "Estaya Immobilien",
                    "link":      full,
                    "notizen":   "",
                })
        except Exception as e:
            print(f"  Estaya Fehler: {e}")
        time.sleep(1)
    return ergebnisse


def _scrape_volksbank_mittweida(plz_set: set) -> list:
    """Volksbank Mittweida / Kay Pöschmann – Grundstücksangebote."""
    ergebnisse = []
    s = requests.Session()
    s.headers.update(HEADERS)
    urls = [
        "https://www.voba-mittweida.de/immobilien/grundstuecke",
        "https://www.voba-mittweida.de/immobilien",
        "https://www.vr-immo.de/immobiliensuche?typ=grundstueck&ort=mittelsachsen",
    ]
    for url in urls:
        try:
            r = s.get(url, timeout=15)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, "lxml")
            cards = soup.select("article, .listing, .property, .immobilie, .expose")
            for card in cards:
                text = card.text
                plz_m = re.search(r"\b(0[4-9]\d{3})\b", text)
                if not plz_m or plz_m.group(1) not in plz_set:
                    continue
                link_el = card.select_one("a")
                href = link_el["href"] if link_el else ""
                full = href if href.startswith("http") else "https://www.voba-mittweida.de" + href
                preis_m = re.search(r"([\d\.,]+)\s*€", text)
                gr_m    = re.search(r"([\d\.,]+)\s*m[²2]", text)
                ergebnisse.append({
                    "plattform": "Volksbank Mittweida",
                    "titel":     card.select_one("h2,h3") and card.select_one("h2,h3").text.strip()[:100] or text.strip()[:80],
                    "plz":       plz_m.group(1),
                    "ort":       "",
                    "adresse":   "",
                    "groesse":   gr_m.group(1) + " m²" if gr_m else "",
                    "preis":     preis_m.group(1) + " €" if preis_m else "",
                    "bplan":     "unbekannt",
                    "anbieter":  "Volksbank Mittweida / Kay Pöschmann",
                    "link":      full,
                    "notizen":   "",
                })
        except Exception as e:
            print(f"  Volksbank MW Fehler: {e}")
        time.sleep(1)
    return ergebnisse


def _scrape_garant(plz_set: set) -> list:
    """Garant Immobilien – Grundstücke in Sachsen."""
    ergebnisse = []
    s = requests.Session()
    s.headers.update(HEADERS)
    try:
        r = s.get("https://www.garant-immo.de/immobiliensuche/?art=grundstueck&ort=sachsen", timeout=15)
        if r.status_code != 200:
            return []
        soup = BeautifulSoup(r.text, "lxml")
        cards = soup.select("article, .property, .listing, .expose-item")
        for card in cards:
            text = card.text
            plz_m = re.search(r"\b(0[4-9]\d{3})\b", text)
            if not plz_m or plz_m.group(1) not in plz_set:
                continue
            link_el = card.select_one("a")
            href = link_el["href"] if link_el else ""
            full = href if href.startswith("http") else "https://www.garant-immo.de" + href
            preis_m = re.search(r"([\d\.,]+)\s*€", text)
            gr_m    = re.search(r"([\d\.,]+)\s*m[²2]", text)
            ergebnisse.append({
                "plattform": "Garant Immobilien",
                "titel":     card.select_one("h2,h3") and card.select_one("h2,h3").text.strip()[:100] or "",
                "plz":       plz_m.group(1),
                "ort":       "",
                "adresse":   "",
                "groesse":   gr_m.group(1) + " m²" if gr_m else "",
                "preis":     preis_m.group(1) + " €" if preis_m else "",
                "bplan":     "unbekannt",
                "anbieter":  "Garant Immobilien",
                "link":      full,
                "notizen":   "",
            })
    except Exception as e:
        print(f"  Garant Fehler: {e}")
    return ergebnisse


def _scrape_weitere(plz_set: set) -> list:
    """Weitere bekannte Makler in der Region – generischer Scraper."""
    ergebnisse = []
    makler_sites = [
        ("Hypoconnect Sachsen",   "https://www.hypoconnect.de/immobilien?typ=grundstueck&region=sachsen"),
        ("Sparkasse Mittelsachsen","https://www.sparkasse-mittelsachsen.de/immobilien/grundstuecke"),
        ("VR ImmoService",         "https://www.vr-immo.de/immobiliensuche?typ=grundstueck&region=mittelsachsen"),
        ("Kreissparkasse Mittelsachsen", "https://www.ksk-ms.de/immobilien"),
    ]
    s = requests.Session()
    s.headers.update(HEADERS)
    for name, url in makler_sites:
        try:
            r = s.get(url, timeout=12)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, "lxml")
            res  = _parse_standard(soup, url.rsplit("/", 1)[0], plz_set, name)
            ergebnisse.extend(res)
            if res:
                print(f"  {name}: {len(res)} Treffer")
        except Exception as e:
            print(f"  {name} Fehler: {e}")
        time.sleep(1)
    return ergebnisse


def suche_makler(plz_set: set) -> list:
    """Durchsucht alle konfigurierten Makler-Websites."""
    alle = []
    print("  Suche Estaya...")
    alle.extend(_scrape_estaya(plz_set))
    print("  Suche Volksbank Mittweida...")
    alle.extend(_scrape_volksbank_mittweida(plz_set))
    print("  Suche Garant Immobilien...")
    alle.extend(_scrape_garant(plz_set))
    print("  Suche weitere Makler...")
    alle.extend(_scrape_weitere(plz_set))
    print(f"Makler gesamt: {len(alle)} Grundstücke gefunden")
    return alle
