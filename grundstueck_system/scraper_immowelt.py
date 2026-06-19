# ============================================================
# scraper_immowelt.py – ImmoWelt Grundstücke (Playwright)
# ============================================================

import re
import time
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from config import PLAYWRIGHT_TIMEOUT, KEYWORDS_NEGATIV


# ImmoWelt Sachsen – Location-Codes für relevante Landkreise
LOCATION_CODES = {
    "Sachsen_gesamt":   "AD08DE14B",
    "Mittelsachsen":    "AD08DE14B60",
    "Erzgebirgskreis":  "AD08DE14B26",
    "Chemnitz":         "AD08DE14B61",
}

SEARCH_URL = ("https://www.immowelt.de/suche/grundstuecke/kaufen"
              "?locations={loc}&page={page}")

EXPOSE_BASE = "https://www.immowelt.de/expose/{expose_id}"


def _get_expose_ids_from_page(html: str) -> list:
    ids = re.findall(r"/expose/([a-f0-9\-]{36})", html)
    return list(dict.fromkeys(ids))  # dedupliziert, Reihenfolge erhalten


def _parse_expose(page, url: str) -> dict | None:
    try:
        page.goto(url, timeout=PLAYWRIGHT_TIMEOUT)
        page.wait_for_timeout(4000)
    except PWTimeout:
        return None

    text = page.inner_text("body")
    html = page.content()
    soup = BeautifulSoup(html, "lxml")

    # Negativfilter
    text_lower = text.lower()
    if any(k in text_lower for k in KEYWORDS_NEGATIV):
        return None

    # PLZ + Ort
    plz_m = re.search(r"\b(0[4-9]\d{3})\b", text)
    plz   = plz_m.group(1) if plz_m else ""

    # Adresse aus Breadcrumb oder Text
    adresse = ""
    bc = soup.select_one("[class*=breadcrumb], [class*=address]")
    if bc:
        adresse = bc.text.strip()[:100]

    # Ort
    ort = ""
    ort_m = re.search(r"\b0[4-9]\d{3}\s+([A-ZÄÖÜa-zäöüß\-]+)", text)
    if ort_m:
        ort = ort_m.group(1).strip()

    # Preis
    preis = ""
    preis_m = re.search(r"([\d\.,]+)\s*€", text)
    if preis_m:
        preis = preis_m.group(1).replace(".", "").replace(",", ".") + " €"

    # Größe
    groesse = ""
    gr_m = re.search(r"([\d\.,]+)\s*m[²2]", text)
    if gr_m:
        groesse = gr_m.group(1).replace(".", "").replace(",", ".") + " m²"

    # Anbieter
    anbieter = ""
    anb_el = soup.select_one("[class*=provider], [class*=broker], [class*=agent]")
    if anb_el:
        anbieter = anb_el.text.strip()[:100]

    # B-Plan – Heuristik
    bplan = "unbekannt"
    if "bebauungsplan" in text_lower or "b-plan" in text_lower:
        bplan = "ja"
    elif "kein bebauungsplan" in text_lower or "ohne b-plan" in text_lower:
        bplan = "nein"

    return {
        "plattform": "ImmoWelt",
        "titel":     page.title()[:100],
        "plz":       plz,
        "ort":       ort,
        "adresse":   adresse,
        "groesse":   groesse,
        "preis":     preis,
        "bplan":     bplan,
        "anbieter":  anbieter,
        "link":      url.split("?")[0],
        "notizen":   "",
    }


def suche_immowelt(plz_set: set) -> list:
    """Durchsucht ImmoWelt nach Grundstücken und filtert nach PLZ."""
    ergebnisse = []
    alle_expose_ids = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            locale="de-DE",
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )

        # Schritt 1: Expose-IDs aus Suchergebnissen sammeln
        search_page = ctx.new_page()
        for loc_name, loc_code in LOCATION_CODES.items():
            for page_nr in range(1, 4):  # max. 3 Seiten pro Region
                url = SEARCH_URL.format(loc=loc_code, page=page_nr)
                try:
                    search_page.goto(url, timeout=PLAYWRIGHT_TIMEOUT)
                    search_page.wait_for_timeout(4000)
                    html = search_page.content()
                    ids  = _get_expose_ids_from_page(html)
                    neue = [i for i in ids if i not in alle_expose_ids]
                    alle_expose_ids.update(neue)
                    print(f"  IW {loc_name} Seite {page_nr}: {len(neue)} neue Exposés")
                    if not neue:
                        break
                except PWTimeout:
                    break
                time.sleep(1)

        print(f"ImmoWelt: {len(alle_expose_ids)} Exposés total – lade Details...")

        # Schritt 2: Jedes Expose laden und PLZ prüfen
        expose_page = ctx.new_page()
        for expose_id in list(alle_expose_ids):
            url = EXPOSE_BASE.format(expose_id=expose_id)
            eintrag = _parse_expose(expose_page, url)
            if eintrag and eintrag["plz"] and eintrag["plz"] in plz_set:
                ergebnisse.append(eintrag)
                print(f"  ✓ {eintrag['plz']} {eintrag['ort']} – {eintrag['preis']}")
            time.sleep(0.5)

        browser.close()

    print(f"ImmoWelt: {len(ergebnisse)} Grundstücke im Gebiet gefunden")
    return ergebnisse
