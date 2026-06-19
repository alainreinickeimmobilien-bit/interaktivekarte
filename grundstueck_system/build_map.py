"""Baut eine Leaflet/OpenStreetMap-Karte aller Grundstücke
(aus Grundstuecke_Uebersicht.xlsx + alainreinickeimmobilien.de) als HTML-Datei.
"""
import json
import re
import time
from pathlib import Path

import openpyxl
import requests

BASE = Path(__file__).resolve().parent.parent
EXCEL = BASE / "Grundstuecke_Uebersicht.xlsx"
OUT_HTML = BASE / "grundstuecke_karte.html"
GEOCACHE = BASE / "grundstueck_system" / "geocode_cache.json"

JUNK_KEYWORDS = [
    "fachkraft", "gehalt", "vollzeit", "teilzeit", "bewerbung", "ihk",
    "quereinsteiger", "werkschutz", "sicherheitsdienst", "objektschutz",
    "arbeitsplatz",
    # Gesuche / Nicht-Grundstücks-Inserate (kein Grundstück zum Verkauf)
    "suche efh", "suche haus", "suche immobilie", "suche wohnung",
    "gesucht", "wohnung in ruhiger", "raum-wohnung", "miete gesucht",
    "biete meine wohnung", "tausche",
]

# Nur Zeilen behalten, deren Link/Notizen erkennbar ein Grundstücks-Angebot
# (zum Verkauf) ist – nicht jede Erwähnung von "Grundstück" reicht (z.B.
# Haus-mit-Grundstück-Inserate ohne reines Grundstück, oder Gesuche).
REQUIRE_KEYWORDS = ["grundstück", "grundstuck", "baugrundstück", "baugrundstuck", "bauland", "parzelle"]
EXCLUDE_IF_CONTAINS = ["suche ", "gesucht", "miete", "vermiet"]

# Wörter, die als "Ort" in der Excel-Liste auftauchen, aber keine echten
# Ortsnamen sind (Reste aus automatisch zugeschnittenen Anzeigentiteln).
BAD_ORT_WORDS = {"ruhiger", "der", "die", "das", "ein", "eine"}


def load_geocache():
    if GEOCACHE.exists():
        return json.loads(GEOCACHE.read_text())
    return {}


def save_geocache(cache):
    GEOCACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=2))


def geocode(query, cache):
    if not query:
        return None
    key = query.strip().lower()
    if key in cache:
        return cache[key]
    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "json", "limit": 1, "countrycodes": "de"},
            headers={"User-Agent": "massa-grundstueck-karte/1.0 (sophia)"},
            timeout=10,
        )
        data = resp.json()
        if data:
            result = {"lat": float(data[0]["lat"]), "lon": float(data[0]["lon"])}
        else:
            result = None
    except Exception:
        result = None
    cache[key] = result
    save_geocache(cache)
    time.sleep(1)  # Nominatim Nutzungsrichtlinie: max. 1 req/sec
    return result


def clean_price(preis):
    if preis is None:
        return ""
    return str(preis)


def parse_number(value):
    """Extrahiert eine Zahl aus Strings wie '650', '660 m²', '45.000 €', '1.000–1.254 m²' (nimmt den ersten Wert)."""
    if value is None:
        return None
    s = str(value)
    m = re.search(r"[\d][\d.,]*", s)
    if not m:
        return None
    num = m.group(0).replace(".", "").replace(",", ".")
    try:
        return float(num)
    except ValueError:
        return None


def compute_preis_pro_qm(preis_gesamt, groesse):
    g = parse_number(groesse)
    p = parse_number(preis_gesamt)
    if not g or not p:
        return None
    return round(p / g, 2)


def expand_parzellen(kategorie, quelle, titel_basis, ort, link, anzahl,
                      groesse_min=None, groesse_max=None, preis_pro_qm=None,
                      preis_pro_qm_max=None, erschliessung=0, parzellen=None, hinweis=""):
    """Erzeugt für ein Baugebiet/Mehrfach-Grundstück die passenden Zeilen.

    `parzellen` (optional): Liste von (groesse_m2, preis_gesamt) mit exakt
    bekannten Werten je Parzelle -> eine Zeile pro Parzelle.

    Sind die Einzelmaße NICHT bekannt (nur Anzahl + Größen-/Preis-Spanne aus
    dem Exposé/B-Plan), wird KEINE erfundene Einzelaufteilung erzeugt –
    stattdessen eine Zeile mit der Spanne als "von–bis"-Angabe.
    """
    rows = []
    if parzellen:
        n = len(parzellen)
        for i, (g, p) in enumerate(parzellen, 1):
            ppqm = round(p / g, 2) if (g and p) else preis_pro_qm
            rows.append({
                "kategorie": kategorie, "quelle": quelle,
                "titel": f"{titel_basis} – Parzelle {i}/{n}{hinweis}",
                "groesse": f"{g} m²" if g else "",
                "preis": f"{p:,.0f} €".replace(",", ".") if p else "",
                "preis_pro_qm": ppqm,
                "link": link, "status": "", "geo_query": f"{ort}, Deutschland",
            })
        return rows

    # Keine Einzelmaße bekannt -> eine Zeile mit der Spanne, nichts erfinden.
    if groesse_min and groesse_max and groesse_min != groesse_max:
        groesse_text = f"{groesse_min:g}–{groesse_max:g} m² (Spanne, Einzelmaße laut Anbieter nicht aufgeschlüsselt)"
    elif groesse_min or groesse_max:
        groesse_text = f"{groesse_min or groesse_max:g} m² je Parzelle"
    else:
        groesse_text = "k.A."

    if preis_pro_qm and preis_pro_qm_max and preis_pro_qm != preis_pro_qm_max:
        preis_text = f"{preis_pro_qm:g}–{preis_pro_qm_max:g} €/m²"
    elif preis_pro_qm:
        preis_text = f"ab {preis_pro_qm:g} €/m²"
    else:
        preis_text = "k.A."
    if erschliessung:
        preis_text += f" + {erschliessung:g} € Erschließungspauschale"

    rows.append({
        "kategorie": kategorie, "quelle": quelle,
        "titel": f"{titel_basis} ({anzahl} Parzellen){hinweis}",
        "groesse": groesse_text,
        "preis": preis_text,
        "preis_pro_qm": preis_pro_qm,
        "link": link, "status": "", "geo_query": f"{ort}, Deutschland",
    })
    return rows


def location_query(plz, ort, adresse):
    plz = (str(plz).strip() if plz else "")
    ort = (str(ort).strip() if ort else "")
    adresse = (str(adresse).strip() if adresse else "")
    if ort.lower() in BAD_ORT_WORDS or len(ort) <= 2:
        ort = ""
    parts = []
    if adresse:
        parts.append(adresse)
    if plz or ort:
        parts.append(f"{plz} {ort}".strip())
    parts.append("Deutschland")
    if not plz and not ort and not adresse:
        return None
    return ", ".join(p for p in parts if p)


def load_excel_entries():
    wb = openpyxl.load_workbook(EXCEL, data_only=True)
    ws = wb["Grundstücke"]
    rows = list(ws.iter_rows(min_row=2, values_only=True))
    entries = []
    for r in rows:
        datum, plattform, plz, ort, adresse, groesse, preis, bplan, anbieter, link, status, propstack, notizen = r
        if link and "..." in str(link):
            continue  # Platzhalter/Beispiel-Zeile, keine echten Daten
        text = " ".join(str(x).lower() for x in [link, notizen, adresse] if x)
        if any(k in text for k in JUNK_KEYWORDS):
            continue
        if any(k in text for k in EXCLUDE_IF_CONTAINS):
            continue
        if not (plz or ort or adresse):
            continue
        query = location_query(plz, ort, adresse)
        if not query:
            continue
        groesse_str = str(groesse) if groesse else ""
        preis_str = clean_price(preis)
        entries.append({
            "kategorie": "eigene_suche",
            "quelle": plattform or "Excel-Liste",
            "titel": f"{ort or ''} {adresse or ''}".strip() or (plz or "Grundstück"),
            "groesse": groesse_str,
            "preis": preis_str,
            "preis_pro_qm": compute_preis_pro_qm(preis_str, groesse_str),
            "link": link or "",
            "status": status or "",
            "geo_query": query,
        })
    return entries


# Einzelgrundstücke (1 Parzelle pro Anzeige)
ALAIN_REINICKE_EINZEL = [
    {"titel": "Grundstück in Hohenstein-Ernstthal", "ort": "Hohenstein-Ernstthal", "groesse": "1.200 m²", "preis": "",
     "link": "https://alainreinicke.landingpage.immobilien/public/exposee/wohnen-auf-dem-logenberg-eyJzaG9wX3Rva2VuIjoiRHFGU1ZDY0M3V29XbmRWZ2dRODNlTHRKIiwicHJvcGVydHlfdG9rZW4iOiJ6U3ZjSGFkVmdOemFtblU1aWs3Ymo3V3oifQ=="},
    {"titel": "Grundstück in Chemnitz Kaßberg", "ort": "Chemnitz Kaßberg", "groesse": "490 m²", "preis": "",
     "link": "https://alainreinicke.landingpage.immobilien/public/exposee/baugrundstuck-aufm-kassberg-eyJzaG9wX3Rva2VuIjoiRHFGU1ZDY0M3V29XbmRWZ2dRODNlTHRKIiwicHJvcGVydHlfdG9rZW4iOiJhWUtIaUN5OUw1b2ZIUmdSbk1uWEJSSHkifQ=="},
    {"titel": "Baugebiet Neukirchen (Försterstr.) – aktuell vermarktete Parzelle, ges. 688–1.099 m² möglich",
     "ort": "Neukirchen, Erzgebirgskreis", "groesse": "688 m²", "preis": "110080",
     "link": "https://alainreinicke.landingpage.immobilien/public/exposee/baugebiet-an-der-forststrasse-eyJzaG9wX3Rva2VuIjoiRHFGU1ZDY0M3V29XbmRWZ2dRODNlTHRKIiwicHJvcGVydHlfdG9rZW4iOiJMTHZUWlFOb1ZWdVd4WVFFV0Q5RUxhRFAifQ=="},
    {"titel": "Grundstück Kemtau", "ort": "Kemtau", "groesse": "798 m²", "preis": "",
     "link": "https://alainreinicke.landingpage.immobilien/public/exposee/bauen-in-kemtau-mit-ausblick-eyJzaG9wX3Rva2VuIjoiRHFGU1ZDY0M3V29XbmRWZ2dRODNlTHRKIiwicHJvcGVydHlfdG9rZW4iOiJKaEQzSzJZMkV1NkdzNFN5bWZkQkU0NW8ifQ=="},
    {"titel": "Grundstück Gornau", "ort": "Gornau", "groesse": "687 m²", "preis": "",
     "link": "https://alainreinicke.landingpage.immobilien/public/exposee/ihr-traum-vom-eigenheim-neubaugebiet-in-gornau-eyJzaG9wX3Rva2VuIjoiRHFGU1ZDY0M3V29XbmRWZ2dRODNlTHRKIiwicHJvcGVydHlfdG9rZW4iOiJUaWdpODVtRkpiRWF2N1BFMWhDdnU4UUYifQ=="},
    {"titel": "Grundstück Königshain-Wiederau", "ort": "Königshain-Wiederau", "groesse": "2.250 m²", "preis": "",
     "link": "https://alainreinicke.landingpage.immobilien/public/exposee/grosses-grundstuck-in-konigshein-wiederau-eyJzaG9wX3Rva2VuIjoiRHFGU1ZDY0M3V29XbmRWZ2dRODNlTHRKIiwicHJvcGVydHlfdG9rZW4iOiJqYnN1b3MyZXpuaVR1TGtCRW9lQjRQN2kifQ=="},
    {"titel": "Grundstück Schönerstädt", "ort": "Schönerstädt", "groesse": "700 m²", "preis": "",
     "link": "https://alainreinicke.landingpage.immobilien/public/exposee/schoner-wohnen-in-schonerstadt-eyJzaG9wX3Rva2VuIjoiRHFGU1ZDY0M3V29XbmRWZ2dRODNlTHRKIiwicHJvcGVydHlfdG9rZW4iOiJXa2hMakZxOG83REtacjRlcGJBdXdxR0IifQ=="},
    {"titel": "Baugebiet Chemnitz-Wittgensdorf (Bräuteichweg) – 1 von insgesamt 18 Parzellen aktuell vermarktet",
     "ort": "Chemnitz-Wittgensdorf", "groesse": "655 m²", "preis": "73150",
     "link": "https://alainreinicke.landingpage.immobilien/public/exposee/grosses-baugebiet-im-brauteichweg-wittgensdorf-ihr-traumhaus-wartet-eyJzaG9wX3Rva2VuIjoiRHFGU1ZDY0M3V29XbmRWZ2dRODNlTHRKIiwicHJvcGVydHlfdG9rZW4iOiJjNkcxNEpYaU5yZXdrOWJVa294c2pIdksifQ=="},
    {"titel": "Grundstück Kleinolbersdorf-Altenhain", "ort": "Kleinolbersdorf-Altenhain", "groesse": "1.132 m²", "preis": "",
     "link": "https://alainreinicke.landingpage.immobilien/public/exposee/schnapp-dir-dein-traumgrundstuck-in-kleinobersdorf-altenhain-eyJzaG9wX3Rva2VuIjoiRHFGU1ZDY0M3V29XbmRWZ2dRODNlTHRKIiwicHJvcGVydHlfdG9rZW4iOiI1UWRXN1cxUFBtNEV6VzNYOUdFY1RXWTkifQ=="},
    {"titel": "Grundstück Lichtenau", "ort": "Lichtenau, Mittelsachsen", "groesse": "2.570 m²", "preis": "",
     "link": "https://alainreinicke.landingpage.immobilien/public/exposee/bau-doch-in-lichtenau-eyJzaG9wX3Rva2VuIjoiRHFGU1ZDY0M3V29XbmRWZ2dRODNlTHRKIiwicHJvcGVydHlfdG9rZW4iOiJjRmpoWWluMmd4enprRUJBVTMzdEtVM3AifQ=="},
]

# Baugebiete mit mehreren Parzellen – werden je in Einzelzeilen aufgesplittet.
# Wo exakte Einzelangaben aus dem Exposé bekannt sind, stehen sie unter
# "parzellen"; sonst werden anzahl/groesse_min/-max + Preis/m² zur Schätzung
# gleichmäßig verteilt ("ca."-Werte, klar gekennzeichnet).
ALAIN_REINICKE_BAUFELDER = [
    {"titel_basis": "Baugebiet Neukirchen (Krehergrund)", "ort": "Neukirchen, Erzgebirgskreis", "anzahl": 3,
     "groesse_min": 1000, "groesse_max": 1254, "preis_pro_qm": 185,
     "link": "https://alainreinicke.landingpage.immobilien/public/exposee/grundstuck-am-krehergrund-eyJzaG9wX3Rva2VuIjoiRHFGU1ZDY0M3V29XbmRWZ2dRODNlTHRKIiwicHJvcGVydHlfdG9rZW4iOiJHcjRjUzY4Q1JDekpZbzhYbUY4Nm1tV0oifQ=="},
    {"titel_basis": "Baugebiet Lichtenwalde", "ort": "Lichtenwalde", "anzahl": 10,
     "groesse_min": 592, "groesse_max": 1047, "preis_pro_qm": 150, "erschliessung": 6500,
     "link": "https://alainreinicke.landingpage.immobilien/public/exposee/10-grundstucke-in-lichtenwalde-eyJzaG9wX3Rva2VuIjoiRHFGU1ZDY0M3V29XbmRWZ2dRODNlTHRKIiwicHJvcGVydHlfdG9rZW4iOiJwdEpxeW91RzR4VkU2eURScjhySGt1Q3kifQ=="},
    {"titel_basis": "Baugebiet Großschirma", "ort": "Großschirma", "anzahl": 3,
     "groesse_min": 830, "groesse_max": 830, "preis_pro_qm": None,
     "link": "https://alainreinicke.landingpage.immobilien/public/exposee/10-grundstucke-in-lichtenwalde-eyJzaG9wX3Rva2VuIjoiRHFGU1ZDY0M3V29XbmRWZ2dRODNlTHRKIiwicHJvcGVydHlfdG9rZW4iOiJwdEpxeW91RzR4VkU2eURScjhySGt1Q3kifQ=="},
    {"titel_basis": "Baugebiet Königshain-Wiederau", "ort": "Königshain-Wiederau",
     "parzellen": [(700, 42000), (700, 42000), (850, 51000)],
     "link": "https://alainreinicke.landingpage.immobilien/public/exposee/3x-bauen-in-konigshein-wiederau-moglich-eyJzaG9wX3Rva2VuIjoiRHFGU1ZDY0M3V29XbmRWZ2dRODNlTHRKIiwicHJvcGVydHlfdG9rZW4iOiJrWjI2NGt6cUpzQWFqRkdwZHdzTldxQVkifQ=="},
    {"titel_basis": "Baugebiet Mittweida (Schützenplatz)", "ort": "Mittweida", "anzahl": 6,
     "groesse_min": 580, "groesse_max": 880, "preis_pro_qm": 120,
     "link": "https://alainreinicke.landingpage.immobilien/public/exposee/attraktive-baugrundstucke-am-schutzenplatz-in-mittweida-6-parzellen-fur-ihr-traumhaus-eyJzaG9wX3Rva2VuIjoiRHFGU1ZDY0M3V29XbmRWZ2dRODNlTHRKIiwicHJvcGVydHlfdG9rZW4iOiJyeHV1c1hUbnFEOXVMRzlRTUxoWjdabk4ifQ=="},
    {"titel_basis": "Baugebiet Altgeringswalde (Obere Dorfstraße)", "ort": "Altgeringswalde",
     "parzellen": [(600, 45000), (750, 56250), (820, 61500)],
     "link": "https://alainreinicke.landingpage.immobilien/public/exposee/3-traumhafte-grundstucke-in-alteringswalde-eyJzaG9wX3Rva2VuIjoiRHFGU1ZDY0M3V29XbmRWZ2dRODNlTHRKIiwicHJvcGVydHlfdG9rZW4iOiJ6RVVNR1dMYWozMVBVaktQQUFRNEpLSlUifQ=="},
    {"titel_basis": "Baugebiet Niederwiesa (Ernst-Thälmann-Straße)", "ort": "Niederwiesa",
     "parzellen": [(1400, 99500), (1400, 99500)],
     "link": "https://alainreinicke.landingpage.immobilien/public/exposee/2x-bauen-in-niederwiesa-eyJzaG9wX3Rva2VuIjoiRHFGU1ZDY0M3V29XbmRWZ2dRODNlTHRKIiwicHJvcGVydHlfdG9rZW4iOiJ1OUdjemdYb1doRXdFWWNVdGpORzFycDcifQ=="},
    {"titel_basis": "Baugebiet Penig (Chemnitzer Straße)", "ort": "Penig", "anzahl": 13,
     "groesse_min": 750, "groesse_max": 1172, "preis_pro_qm": 130,
     "link": "https://alainreinicke.landingpage.immobilien/public/exposee/baugrundstucke-in-penig-13-freie-parzellen-im-baugebiet-chemnitzer-strasse-eyJzaG9wX3Rva2VuIjoiRHFGU1ZDY0M3V29XbmRWZ2dRODNlTHRKIiwicHJvcGVydHlfdG9rZW4iOiJnSDFvbUxidmlId2ZFbVhaS1V0NGthZFYifQ=="},
]


def build_alain_entries():
    entries = []
    for item in ALAIN_REINICKE_EINZEL:
        entries.append({
            "kategorie": "alain_reinicke",
            "quelle": "Alain Reinicke Immobilien",
            "titel": item["titel"],
            "groesse": item["groesse"],
            "preis": item["preis"],
            "preis_pro_qm": compute_preis_pro_qm(item["preis"], item["groesse"]),
            "link": item["link"],
            "status": "",
            "geo_query": f"{item['ort']}, Deutschland",
        })
    for item in ALAIN_REINICKE_BAUFELDER:
        entries.extend(expand_parzellen(
            kategorie="alain_reinicke", quelle="Alain Reinicke Immobilien",
            titel_basis=item["titel_basis"], ort=item["ort"], link=item["link"],
            anzahl=item.get("anzahl"), groesse_min=item.get("groesse_min"),
            groesse_max=item.get("groesse_max"), preis_pro_qm=item.get("preis_pro_qm"),
            erschliessung=item.get("erschliessung", 0), parzellen=item.get("parzellen"),
        ))
    return entries


# Offizielle, von Kommunen ausgewiesene Neubaugebiete im PLZ-Gebiet der
# Excel-Liste (Mittelsachsen, Erzgebirgskreis), recherchiert über das
# kommunale Immobilienportal kip.net + Gemeinde-Websites (Stand: Juni 2026).
# Einzelgrundstücke / Gebiete ohne sicheren Parzellen-Einzelpreis:
BAUGEBIETE_EINZEL = [
    {"titel": "Wohngebiet »Bergsiedlung«", "ort": "Kriebethal, Kriebstein", "groesse": "k.A. (1 freies Grundstück)",
     "preis": "", "preis_text": "38 €/m²",
     "link": "https://www.kip.net/sachsen/mittelsachsen/bauen/bergsiedlung_BG11475"},
    {"titel": "Wohngebiet »Am Waldrand«", "ort": "Rochlitz", "groesse": "k.A.",
     "preis": "", "preis_text": "38,29–43,00 €/m²",
     "link": "https://www.kip.net/sachsen/mittelsachsen/bauen/am-waldrand_BG3135"},
    {"titel": "Gewerbegebiet »Goldene Höhe«", "ort": "Roßwein", "groesse": "87.553 m² verfügbar",
     "preis": "", "preis_text": "ab 45,00 €/m²",
     "link": "https://www.kip.net/sachsen/mittelsachsen/bauen/gewerbegebiet-goldene-hahe_BG3042"},
    {"titel": "Walduferviertel (B-Plan-Gebiet)", "ort": "Döbeln", "groesse": "500–1.200 m² (Einzelparzellen variabel)",
     "preis": "", "preis_text": "k.A.",
     "link": "https://www.xn--wohnen-im-grnen-bwb.de/wohnen-im-gruenen-bwb-de-baugebiete/doebeln-walduferviertel/"},
    {"titel": "Städtische Baugrundstücke »Sonnenhufe II« (Meinsberg) / Walduferviertel", "ort": "Waldheim", "groesse": "k.A.",
     "preis": "", "preis_text": "k.A.",
     "link": "https://www.stadt-waldheim.de/portal/seiten/staedtische-baugrundstuecke-900000166-26400.html"},
]

# Baugebiete mit mehreren amtlichen Parzellen – aufgesplittet:
BAUGEBIETE_BAUFELDER = [
    {"titel_basis": "Wohngebiet »Am Hübel« (kommunal, kip.net)", "ort": "Eibenstock", "anzahl": 4,
     "groesse_min": 490, "groesse_max": 490, "preis_pro_qm": None,
     "link": "https://www.kip.net/sachsen/erzgebirgskreis/bauen/am-habel_BG2977"},
    {"titel_basis": "Baugebiet »Am Hüttenbach« (kommunal)", "ort": "Wolkenstein", "anzahl": 30,
     "groesse_min": 660, "groesse_max": 1050, "preis_pro_qm": 91,
     "link": "https://www.ohne-makler.net/immobilie/wolkenstein-provisonsfreie-einfamilienhausgrundstuecke-in-wolkenstein/"},
    {"titel_basis": "B-Plan-Gebiet »Am Gräbel« (städtisch, ehem. Kleingärten)", "ort": "Zschopau", "anzahl": 12,
     "groesse_min": None, "groesse_max": None, "preis_pro_qm": None,
     "link": "https://www.zschopau.de/grundstuecksboerse/verkaufsangebot-baugrundstuecke-am-graebel"},
    {"titel_basis": "Neues Baugebiet »Amtsberg Schlößchen« / Dittersdorf (kommunal)", "ort": "Amtsberg", "anzahl": 10,
     "groesse_min": 700, "groesse_max": 800, "preis_pro_qm": 114,
     "link": "https://www.immowelt.de/suche/kaufen/grundstueck/sachsen/amtsberg-09439/ad08de9806"},
    {"titel_basis": "Baugebiet 29 Bauplätze (erschlossen, bauträgerfrei)", "ort": "Brand-Erbisdorf", "anzahl": 29,
     "groesse_min": 605, "groesse_max": 944, "preis_pro_qm": None,
     "link": "https://www.lstw-freiberg.de/grundstuecke/brand-erbisdorf/"},
    {"titel_basis": "Kommunales Baugebiet (Gemeinde, gv-bobritzsch.de)", "ort": "Bobritzsch-Hilbersdorf", "anzahl": 10,
     "groesse_min": 500, "groesse_max": 1000, "preis_pro_qm": None,
     "link": "https://www.bobritzsch-hilbersdorf.de/seite/273442/bauland.html"},
]


def build_baugebiete_entries():
    entries = []
    for item in BAUGEBIETE_EINZEL:
        entries.append({
            "kategorie": "baugebiet",
            "quelle": "Kommunales Baugebiet",
            "titel": f"{item['titel']} – {item['ort']}",
            "groesse": item["groesse"],
            "preis": item["preis_text"],
            "preis_pro_qm": None,
            "link": item["link"],
            "status": "",
            "geo_query": f"{item['ort']}, Deutschland",
        })
    for item in BAUGEBIETE_BAUFELDER:
        entries.extend(expand_parzellen(
            kategorie="baugebiet", quelle="Kommunales Baugebiet",
            titel_basis=item["titel_basis"], ort=item["ort"], link=item["link"],
            anzahl=item["anzahl"], groesse_min=item.get("groesse_min"),
            groesse_max=item.get("groesse_max"), preis_pro_qm=item.get("preis_pro_qm"),
        ))
    return entries


CATEGORY_COLORS = {
    "alain_reinicke": "#1e3a8a",   # dunkelblau
    "eigene_suche": "#ec4899",     # rosa
    "baugebiet": "#eab308",        # sattes Gelb
}
# Kurzbezeichnung für Karten-Legende/Popup
CATEGORY_LABELS = {
    "alain_reinicke": "Alain Reinicke Immobilien",
    "eigene_suche": "OAC",
    "baugebiet": "Offizielle Baugebiete (Kommune)",
}
# Ausführliche Bezeichnung für die Liste unter der Karte
CATEGORY_LABELS_LISTE = {
    "alain_reinicke": "Alain Reinicke Immobilien",
    "eigene_suche": "Online Anzeichen Check",
    "baugebiet": "Offizielle Baugebiete (Kommune)",
}


def main():
    cache = load_geocache()
    entries = load_excel_entries() + build_alain_entries() + build_baugebiete_entries()

    markers = []
    skipped = 0
    for e in entries:
        geo = geocode(e["geo_query"], cache)
        if not geo:
            skipped += 1
            continue
        markers.append({**e, "lat": geo["lat"], "lon": geo["lon"]})

    print(f"{len(markers)} Grundstücke platziert, {skipped} ohne Geocoding-Treffer übersprungen.")

    markers_json = json.dumps(markers, ensure_ascii=False)
    colors_json = json.dumps(CATEGORY_COLORS, ensure_ascii=False)
    labels_json = json.dumps(CATEGORY_LABELS, ensure_ascii=False)
    labels_liste_json = json.dumps(CATEGORY_LABELS_LISTE, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<title>Grundstücke Karte</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<style>
  html, body {{ margin: 0; padding: 0; font-family: sans-serif; }}
  #map {{ height: 70vh; width: 100%; }}
  .legend {{ position: absolute; top: 10px; right: 10px; background: white; padding: 8px 12px;
             border-radius: 6px; box-shadow: 0 1px 4px rgba(0,0,0,.3); z-index: 1000; font-size: 13px; }}
  .legend div {{ margin: 2px 0; }}
  .dot {{ display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:6px; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
  th, td {{ border: 1px solid #ddd; padding: 6px 8px; text-align: left; }}
  th {{ background: #f3f4f6; position: sticky; top: 0; cursor: pointer; }}
  tr:hover {{ background: #f9fafb; }}
  #liste-wrapper {{ height: 30vh; overflow-y: auto; display: none; }}
  #liste-wrapper.offen {{ display: block; }}
  h2 {{ margin: 10px 14px; font-size: 16px; cursor: pointer; user-select: none; }}
  h2 .toggle-icon {{ display: inline-block; transition: transform 0.2s; margin-right: 6px; }}
  h2.offen .toggle-icon {{ transform: rotate(90deg); }}
  select {{ margin: 0 14px 8px; }}
</style>
</head>
<body>
<div id="map"></div>
<div class="legend" id="legend"></div>
<h2 id="liste-toggle"><span class="toggle-icon">&#9656;</span>Alle Grundstücke (<span id="anzahl"></span>)</h2>
<select id="filter"><option value="">Alle Kategorien</option></select>
<div id="liste-wrapper">
<table id="liste">
  <thead><tr>
    <th data-key="kategorie">Kategorie</th>
    <th data-key="titel">Titel/Ort</th>
    <th data-key="groesse_zahl">Größe</th>
    <th data-key="preis_zahl">Preis gesamt</th>
    <th data-key="preis_pro_qm">Preis/m²</th>
    <th>Link</th>
  </tr></thead>
  <tbody></tbody>
</table>
</div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
  const markers = {markers_json};
  const colors = {colors_json};
  const labels = {labels_json};
  const labelsListe = {labels_liste_json};

  const legend = document.getElementById('legend');
  Object.keys(labels).forEach(k => {{
    legend.innerHTML += `<div><span class="dot" style="background:${{colors[k]}}"></span>${{labels[k]}}</div>`;
  }});

  const filterSel = document.getElementById('filter');
  filterSel.style.display = 'none';
  Object.keys(labelsListe).forEach(k => {{
    filterSel.innerHTML += `<option value="${{k}}">${{labelsListe[k]}}</option>`;
  }});

  const listeToggle = document.getElementById('liste-toggle');
  const listeWrapper = document.getElementById('liste-wrapper');
  listeToggle.addEventListener('click', () => {{
    const offen = listeWrapper.classList.toggle('offen');
    listeToggle.classList.toggle('offen', offen);
    filterSel.style.display = offen ? '' : 'none';
  }});

  const map = L.map('map').setView([50.85, 12.95], 9);
  L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
    attribution: '&copy; OpenStreetMap-Mitwirkende'
  }}).addTo(map);

  const mapMarkers = [];
  markers.forEach(m => {{
    const color = colors[m.kategorie] || '#666';
    const marker = L.circleMarker([m.lat, m.lon], {{
      radius: 7, color: color, fillColor: color, fillOpacity: 0.85, weight: 1
    }}).addTo(map);
    const linkHtml = m.link ? `<br><a href="${{m.link}}" target="_blank">Zur Anzeige &rarr;</a>` : '';
    marker.bindPopup(
      `<b>${{m.titel}}</b><br>Quelle: ${{labels[m.kategorie] || m.quelle}}` +
      (m.groesse ? `<br>Größe: ${{m.groesse}}` : '') +
      (m.preis ? `<br>Preis gesamt: ${{m.preis}}` : '') +
      (m.preis_pro_qm ? `<br>Preis/m²: ${{m.preis_pro_qm}} €` : '') +
      (m.status ? `<br>Status: ${{m.status}}` : '') +
      linkHtml
    );
    mapMarkers.push({{m, marker}});
  }});

  const bounds = markers.map(m => [m.lat, m.lon]);
  if (bounds.length) {{ map.fitBounds(bounds, {{ padding: [30, 30] }}); }}

  // --- Liste unter der Karte ---
  const tbody = document.querySelector('#liste tbody');

  function renderListe(filterKey) {{
    const data = filterKey ? markers.filter(m => m.kategorie === filterKey) : markers;
    document.getElementById('anzahl').textContent = data.length;
    tbody.innerHTML = data.map(m => `
      <tr>
        <td><span class="dot" style="background:${{colors[m.kategorie]}}"></span>${{labelsListe[m.kategorie] || m.quelle}}</td>
        <td>${{m.titel}}</td>
        <td>${{m.groesse || ''}}</td>
        <td>${{m.preis || ''}}</td>
        <td>${{m.preis_pro_qm ? m.preis_pro_qm + ' €' : ''}}</td>
        <td>${{m.link ? `<a href="${{m.link}}" target="_blank">Zur Anzeige</a>` : ''}}</td>
      </tr>
    `).join('');
  }}
  renderListe('');
  filterSel.addEventListener('change', () => {{
    renderListe(filterSel.value);
    mapMarkers.forEach(({{m, marker}}) => {{
      const visible = !filterSel.value || m.kategorie === filterSel.value;
      if (visible) {{ if (!map.hasLayer(marker)) marker.addTo(map); }}
      else {{ map.removeLayer(marker); }}
    }});
  }});

  // Klick auf Tabellenzeile zentriert/öffnet Popup auf der Karte
  tbody.addEventListener('click', (ev) => {{
    const row = ev.target.closest('tr');
    if (!row) return;
    const idx = Array.from(tbody.children).indexOf(row);
    const data = filterSel.value ? markers.filter(m => m.kategorie === filterSel.value) : markers;
    const m = data[idx];
    if (!m) return;
    map.setView([m.lat, m.lon], 14);
    const found = mapMarkers.find(x => x.m === m);
    if (found) found.marker.openPopup();
  }});
</script>
</body>
</html>
"""
    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"Karte geschrieben nach: {OUT_HTML}")


if __name__ == "__main__":
    main()
