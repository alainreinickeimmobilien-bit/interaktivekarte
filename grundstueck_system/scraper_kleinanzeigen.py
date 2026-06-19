# ============================================================
# scraper_kleinanzeigen.py – Kleinanzeigen.de Grundstücke
# ============================================================

import requests
import re
import time
from bs4 import BeautifulSoup
from config import KEYWORDS_POSITIV, KEYWORDS_NEGATIV


BASE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "de-DE,de;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Regionsbasierte Suche statt 588 einzelner PLZ
# Format: (Anzeigename, URL-Region)
REGIONEN = [
    ("Mittelsachsen",   "https://www.kleinanzeigen.de/s-grundstueck/mittelsachsen/k0l8258"),
    ("Erzgebirgskreis", "https://www.kleinanzeigen.de/s-grundstueck/erzgebirgskreis/k0"),
    ("Chemnitz",        "https://www.kleinanzeigen.de/s-grundstueck/chemnitz/k0"),
]
MAX_SEITEN = 10  # max. Seiten pro Region


def _ist_relevant(titel: str, beschreibung: str) -> bool:
    text = (titel + " " + beschreibung).lower()
    hat_positiv = any(k in text for k in KEYWORDS_POSITIV)
    hat_negativ = any(k in text for k in KEYWORDS_NEGATIV)
    return hat_positiv and not hat_negativ


def _parse_preis(text: str) -> str:
    text = text.strip()
    if not text or "anfrage" in text.lower():
        return "Preis auf Anfrage"
    m = re.search(r"[\d\.,]+", text)
    if m:
        return m.group().replace(".", "").replace(",", ".") + " €"
    return text


def _parse_groesse(text: str) -> str:
    m = re.search(r"([\d\.,]+)\s*m[²2]", text, re.IGNORECASE)
    if m:
        return m.group(1).replace(".", "").replace(",", ".") + " m²"
    return ""


def _parse_seite(soup, gesehen: set) -> list:
    treffer = []
    for ad in soup.select("article.aditem"):
        try:
            title_el = ad.select_one(".text-module-begin, h2, .ellipsis")
            price_el = ad.select_one(".aditem-main--middle--price-shipping, [class*=price]")
            link_el  = ad.select_one("a[href]")
            desc_el  = ad.select_one(".aditem-main--middle--description, [class*=description]")
            size_el  = ad.select_one(".aditem-main--bottom, .simpletag")

            titel  = title_el.text.strip() if title_el else ""
            beschr = desc_el.text.strip()   if desc_el  else ""

            if not _ist_relevant(titel, beschr):
                continue

            link = ""
            if link_el and link_el.get("href"):
                href = link_el["href"]
                link = href if href.startswith("http") else "https://www.kleinanzeigen.de" + href
            if not link or link in gesehen:
                continue
            gesehen.add(link)

            # Ort aus Titel extrahieren (z.B. "Grundstück in Penig / Mittelsachsen")
            ort_m = re.search(r"\bin\s+([A-ZÄÖÜa-zäöüß\-]+(?:\s+/\s+[A-ZÄÖÜa-zäöüß\-]+)?)", titel)
            ort   = ort_m.group(1) if ort_m else ""

            # Größe aus size-Element oder Titel/Beschreibung
            size_text = size_el.text.strip() if size_el else ""
            groesse   = _parse_groesse(size_text) or _parse_groesse(titel + " " + beschr)

            treffer.append({
                "plattform": "Kleinanzeigen",
                "titel":     titel,
                "plz":       "",   # kein PLZ in Listenansicht → wird beim Import nachgepflegt
                "ort":       ort,
                "adresse":   "",
                "groesse":   groesse,
                "preis":     _parse_preis(price_el.text if price_el else ""),
                "bplan":     "unbekannt",
                "anbieter":  "",
                "link":      link,
                "notizen":   beschr[:200],
            })
        except Exception:
            continue
    return treffer


def suche_kleinanzeigen(plz_set: set = None) -> list:
    """Durchsucht Kleinanzeigen regionenbasiert (Mittelsachsen, Erzgebirge, Chemnitz)."""
    session = requests.Session()
    session.headers.update(BASE_HEADERS)
    ergebnisse = []
    gesehen_urls = set()

    for region_name, basis_url in REGIONEN:
        for seite in range(1, MAX_SEITEN + 1):
            url = basis_url if seite == 1 else f"{basis_url}?pageNum={seite}"
            try:
                r = session.get(url, timeout=15)
                if r.status_code != 200:
                    break
            except Exception as e:
                print(f"  KA {region_name} S.{seite}: Fehler – {e}")
                break

            soup = BeautifulSoup(r.text, "lxml")
            neu  = _parse_seite(soup, gesehen_urls)
            ergebnisse.extend(neu)

            # Prüfe ob weitere Seiten existieren
            naechste = soup.select_one("a.pagination-next, [data-testid=pagination-next]")
            if not naechste:
                break

            time.sleep(0.8)

        print(f"  KA {region_name}: bisher {len(ergebnisse)} Treffer")
        time.sleep(1)

    print(f"Kleinanzeigen gesamt: {len(ergebnisse)} Grundstücke im Gebiet")
    return ergebnisse
