# ============================================================
# scraper_is24.py – ImmoScout24 Grundstücke (Playwright)
# ============================================================

import re
import time
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from config import PLAYWRIGHT_TIMEOUT, KEYWORDS_NEGATIV


# ImmoScout24 Suchseite für Grundstücke in Sachsen
SEARCH_URL = ("https://www.immobilienscout24.de/Suche/de/sachsen/grundstueck-kaufen"
              "?pagenumber={page}")


def _accept_cookies(page):
    """Versucht Cookie-Banner zu schließen."""
    try:
        # IS24 nutzt Usercentrics im Shadow DOM
        page.evaluate("""
            () => {
                const host = document.querySelector('#usercentrics-root');
                if (host && host.shadowRoot) {
                    const btn = host.shadowRoot.querySelector('button[data-testid="uc-accept-all-button"]');
                    if (btn) btn.click();
                }
            }
        """)
        page.wait_for_timeout(1000)
    except:
        pass


def _get_expose_links(html: str) -> list:
    """Extrahiert IS24-Expose-Links aus der Suchergebnisseite."""
    links = re.findall(r'href="(/expose/\d+)"', html)
    links += re.findall(r'"url"\s*:\s*"(https://www\.immobilienscout24\.de/expose/\d+)"', html)
    return list(dict.fromkeys(links))


def _parse_is24_expose(page, url: str, plz_set: set) -> dict | None:
    full_url = url if url.startswith("http") else f"https://www.immobilienscout24.de{url}"
    try:
        page.goto(full_url, timeout=PLAYWRIGHT_TIMEOUT)
        _accept_cookies(page)
        page.wait_for_timeout(3000)
    except PWTimeout:
        return None

    text  = page.inner_text("body")
    html  = page.content()
    soup  = BeautifulSoup(html, "lxml")
    lower = text.lower()

    if any(k in lower for k in KEYWORDS_NEGATIV):
        return None

    # PLZ
    plz_m = re.search(r"\b(0[4-9]\d{3})\b", text)
    if not plz_m:
        return None
    plz = plz_m.group(1)
    if plz not in plz_set:
        return None

    ort = ""
    ort_m = re.search(r"\b0[4-9]\d{3}\s+([A-ZÄÖÜa-zäöüß\-]+)", text)
    if ort_m:
        ort = ort_m.group(1)

    preis = ""
    preis_m = re.search(r"([\d\.,]+)\s*€", text)
    if preis_m:
        preis = preis_m.group(1).replace(".", "").replace(",", ".") + " €"

    groesse = ""
    gr_m = re.search(r"([\d\.,]+)\s*m[²2]", text)
    if gr_m:
        groesse = gr_m.group(1).replace(".", "").replace(",", ".") + " m²"

    anbieter = ""
    anb = soup.select_one("[class*=provider], [class*=contact], [data-qa=agent-name]")
    if anb:
        anbieter = anb.text.strip()[:100]

    bplan = "unbekannt"
    if "bebauungsplan" in lower or "b-plan" in lower:
        bplan = "ja" if "kein" not in lower[:lower.find("bebauungsplan")+20] else "nein"

    return {
        "plattform": "ImmoScout24",
        "titel":     page.title()[:100],
        "plz":       plz,
        "ort":       ort,
        "adresse":   "",
        "groesse":   groesse,
        "preis":     preis,
        "bplan":     bplan,
        "anbieter":  anbieter,
        "link":      full_url,
        "notizen":   "",
    }


def suche_is24(plz_set: set) -> list:
    """Durchsucht ImmoScout24 nach Grundstücken (mit Playwright-Stealth)."""
    ergebnisse = []
    alle_links = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
        ctx = browser.new_context(
            locale="de-DE",
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900},
        )
        # Verstecke webdriver-Fingerprint
        ctx.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)

        search_page = ctx.new_page()

        # Startseite besuchen (Cookie-Session aufbauen)
        try:
            search_page.goto("https://www.immobilienscout24.de/", timeout=15000)
            _accept_cookies(search_page)
            search_page.wait_for_timeout(2000)
        except:
            pass

        # Suchergebnisse abrufen
        for page_nr in range(1, 6):
            url = SEARCH_URL.format(page=page_nr)
            try:
                r = search_page.goto(url, timeout=PLAYWRIGHT_TIMEOUT)
                status = r.status if r else 0
                if status == 401:
                    print(f"  IS24 Seite {page_nr}: Zugriff verweigert (401) – Anti-Bot aktiv")
                    break
                search_page.wait_for_timeout(3000)
                html  = search_page.content()
                links = _get_expose_links(html)
                neue  = [l for l in links if l not in alle_links]
                alle_links.update(neue)
                print(f"  IS24 Seite {page_nr}: {len(neue)} neue Exposés ({status})")
                if not neue:
                    break
            except PWTimeout:
                break
            time.sleep(1.5)

        print(f"IS24: {len(alle_links)} Exposés – lade Details...")

        expose_page = ctx.new_page()
        for link in list(alle_links):
            eintrag = _parse_is24_expose(expose_page, link, plz_set)
            if eintrag:
                ergebnisse.append(eintrag)
                print(f"  ✓ IS24 {eintrag['plz']} {eintrag['ort']} – {eintrag['preis']}")
            time.sleep(0.8)

        browser.close()

    print(f"IS24: {len(ergebnisse)} Grundstücke im Gebiet gefunden")
    return ergebnisse
