"""Holt alle aktiv vermarkteten Immobilien von Alain Reinicke Immobilien über
die Propstack-API und baut daraus eine einbettbare Leaflet/OpenStreetMap-Karte
(docs/index.html für GitHub Pages).

Läuft täglich per GitHub Actions (siehe .github/workflows/update-alain-karte.yml)
und nimmt neue Anzeigen automatisch auf bzw. entfernt verschwundene – Propstacks
eigenes "status"-Feld (Vermarktung/Reserviert/Abgeschlossen/...) übernimmt die
Sichtbarkeitsentscheidung, kein Rätselraten über HTML-Marker mehr nötig.

Benötigt den Umgebungsvariable PROPSTACK_API_KEY (Read-Only-Key aus Propstack).
"""
import json
import os
import re
import sys
import time
from html import unescape
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent.parent
OUT_HTML = BASE / "docs" / "index.html"
GEOCACHE = Path(__file__).resolve().parent / "geocode_cache.json"

PROPSTACK_API_KEY = os.environ.get("PROPSTACK_API_KEY")
PROPSTACK_BASE = "https://api.propstack.de/v1"
OVERVIEW_URL = "https://alainreinickeimmobilien.de/immobilien-angebote-chemnitz/"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; alain-reinicke-karte/1.0)"}

ACTIVE_STATUS = "Vermarktung"

# Anzeigen, die laut Propstack-Status zwar (noch) aktiv sind, aber manuell
# als nicht mehr relevant markiert wurden.
EXCLUDED_TITLES = set()

COLORS = {
    # Tableau10-Palette: bewusst maximal unterscheidbare Kategoriefarben
    # (statt verwandter Töne, die auf der Karte schwer zu trennen sind).
    "Einfamilienhaus": "#1f77b4",   # Blau
    "Doppelhaushälfte": "#2ca02c", # Grün
    "Mehrfamilienhaus": "#d62728", # Rot
    "Eigentumswohnung": "#9467bd", # Violett
    "Mietwohnung": "#8c564b",      # Braun
    "Gewerbe": "#ff7f0e",          # Orange
    "Grundstück": "#17becf",       # Türkis/Cyan
    "Sonstiges": "#7f7f7f",        # Grau
}


def load_geocache():
    if GEOCACHE.exists():
        return json.loads(GEOCACHE.read_text())
    return {}


def save_geocache(cache):
    GEOCACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=2))


# Ortsnamen, die Nominatim nicht direkt findet (Tippfehler/Abkürzungen) und
# die deshalb auf eine geocodierbare Form umgeschrieben werden.
ORT_FIXES = {
    "gornau/erzgeb.": "Gornau, Erzgebirgskreis",
    "schönerstädt": "Schönerstadt, Oederan",
}


def _nominatim_request(query):
    resp = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params={"q": query, "format": "json", "limit": 1, "countrycodes": "de"},
        headers={"User-Agent": "alain-reinicke-karte/1.0 (sophia)"},
        timeout=10,
    )
    data = resp.json()
    time.sleep(1)  # Nominatim Nutzungsrichtlinie: max. 1 req/sec
    return {"lat": float(data[0]["lat"]), "lon": float(data[0]["lon"])} if data else None


def geocode(query, cache, ort=None):
    if not query:
        return None
    key = query.strip().lower()
    if key in cache:
        return cache[key]
    result = None
    try:
        result = _nominatim_request(query)
        if not result and ort:
            result = _nominatim_request(f"{ort}, Deutschland")
        if not result and ort:
            fixed = ORT_FIXES.get(ort.strip().lower())
            if fixed:
                result = _nominatim_request(f"{fixed}, Deutschland")
    except Exception:
        result = None
    cache[key] = result
    save_geocache(cache)
    return result


def propstack_get(path, **params):
    resp = requests.get(
        f"{PROPSTACK_BASE}/{path}",
        params=params,
        headers={"X-API-KEY": PROPSTACK_API_KEY},
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_active_units():
    """Alle Units mit Status 'Vermarktung' (= aktiv beworben).
    Die Propstack-Pagination liefert vereinzelt dieselbe Unit auf zwei
    Seiten zurück, daher zusätzlich nach id deduplizieren."""
    units, page, seen = [], 1, set()
    while True:
        batch = propstack_get("units.json", page=page)
        if not batch:
            break
        for u in batch:
            if u["id"] not in seen:
                seen.add(u["id"])
                units.append(u)
        page += 1
    return [u for u in units if (u.get("status") or {}).get("name") == ACTIVE_STATUS]


def parse_number(text):
    if not text:
        return None
    text = str(text).replace(".", "").replace(",", ".")
    m = re.search(r"[\d.]+", text)
    return float(m.group()) if m else None


def fields_lookup(required_fields, *names):
    for f in required_fields or []:
        if f.get("name") in names:
            return f.get("value")
    return None


def categorize(rs_type, marketing_type, title, number_of_rooms):
    t = (title or "").lower()
    if rs_type == "TRADE_SITE":
        return "Grundstück"
    if rs_type in ("STORE", "OFFICE"):
        return "Gewerbe"
    if rs_type == "APARTMENT":
        return "Mietwohnung" if marketing_type == "RENT" else "Eigentumswohnung"
    if rs_type == "HOUSE":
        if "mfh" in t or "mehrfamilienhaus" in t or "wohnungen" in t:
            return "Mehrfamilienhaus"
        if "doppelhaushälfte" in t or "dhh" in t:
            return "Doppelhaushälfte"
        if number_of_rooms and number_of_rooms >= 10:
            return "Mehrfamilienhaus"
        return "Einfamilienhaus"
    return "Sonstiges"


def build_geo_query(detail):
    street = (detail.get("street") or "").strip()
    house_number = (detail.get("house_number") or "").strip()
    zip_code = (detail.get("zip_code") or "").strip()
    city = (detail.get("city") or "").strip()
    district = (detail.get("district") or "").strip()
    if street:
        addr = f"{street} {house_number}".strip()
        return f"{addr}, {zip_code} {city}, Deutschland".strip()
    ort = district or city
    return f"{zip_code} {ort}, Deutschland".strip()


def fetch_website_links():
    """Leichte, fehlertolerante Zuordnung Titel -> öffentlicher Exposé-Link.
    Nur für den 'Exposé öffnen'-Button; alle Objektdaten kommen aus Propstack."""
    try:
        resp = requests.get(OVERVIEW_URL, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except Exception:
        return {}
    links = set(re.findall(
        r'https://alainreinicke\.landingpage\.immobilien/public/exposee/[A-Za-z0-9\-_=]+',
        resp.text,
    ))
    title_to_url = {}
    for url in links:
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code != 200:
                continue
            m = re.search(r'<h1 class="lp-title">([^<]*)</h1>', r.text)
            if m:
                title_to_url[unescape(m.group(1)).strip()] = url
        except Exception:
            continue
    return title_to_url


def build_markers(units, geocache, title_to_url):
    markers = []
    for u in units:
        try:
            detail = propstack_get(f"units/{u['id']}.json")
        except Exception:
            continue

        title = detail.get("title") or detail.get("name") or "Anzeige"
        if title in EXCLUDED_TITLES:
            continue

        marketing_type = detail.get("marketing_type")
        kauf_oder_miete = "Miete" if marketing_type == "RENT" else "Kauf"
        rs_type = detail.get("rs_type")
        number_of_rooms = detail.get("number_of_rooms")
        typ = categorize(rs_type, marketing_type, title, number_of_rooms)

        rf = detail.get("required_fields") or []
        preis = parse_number(fields_lookup(rf, "Preis", "Kaltmiete"))
        wohnflaeche = parse_number(fields_lookup(
            rf, "Wohnfläche ca.", "Vermietbare Fläche ca.", "Büro-/ Praxisfläche ca."
        ))
        grundstueck = parse_number(fields_lookup(rf, "Grundstücksfläche ca."))
        zimmer = parse_number(fields_lookup(rf, "Zimmer")) or number_of_rooms

        geo_query = build_geo_query(detail)
        ort = detail.get("district") or detail.get("city")
        geo = geocode(geo_query, geocache, ort=ort)
        if not geo:
            print(f"  kein Geocoding-Treffer: {title} ({geo_query})")
            continue

        markers.append({
            "titel": title,
            "url": title_to_url.get(title),
            "typ": typ,
            "kauf_oder_miete": kauf_oder_miete,
            "ort": detail.get("city"),
            "plz": detail.get("zip_code"),
            "wohnflaeche_m2": wohnflaeche,
            "zimmer": zimmer,
            "grundstueck_m2": grundstueck,
            "preis": preis,
            "lat": geo["lat"],
            "lon": geo["lon"],
        })
    return markers


def build_html(markers):
    markers_json = json.dumps(markers, ensure_ascii=False)
    colors_json = json.dumps(COLORS, ensure_ascii=False)
    html = f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<title>Alain Reinicke Immobilien – Anzeigenkarte</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<style>
  html, body {{ margin:0; padding:0; height:100%; font-family: Arial, Helvetica, sans-serif; }}
  #map {{ height:100vh; width:100%; }}
  .legend {{ position:absolute; top:10px; right:10px; z-index:1000; background:white;
    padding:10px 14px; border-radius:8px; box-shadow:0 2px 6px rgba(0,0,0,0.3); font-size:13px; max-width:230px; }}
  .legend b {{ display:block; margin-bottom:6px; }}
  .legend span {{ display:inline-block; width:12px; height:12px; border-radius:50%; margin-right:6px; vertical-align:middle; }}
  .popup-title {{ font-weight:bold; margin-bottom:4px; }}
  .popup-table td {{ padding:1px 6px; font-size:13px; }}
  .popup-table td:first-child {{ color:#555; }}
  a.expose-link {{ display:inline-block; margin-top:6px; font-size:13px; }}
  .stand {{ position:absolute; bottom:6px; left:6px; z-index:1000; background:rgba(255,255,255,0.85);
    padding:3px 8px; border-radius:6px; font-size:11px; color:#555; }}
  .cluster-marker {{ width:26px; height:26px; border-radius:50%; background:#222; color:#fff;
    font-size:13px; font-weight:bold; display:flex; align-items:center; justify-content:center;
    box-shadow:0 1px 4px rgba(0,0,0,0.5); border:2px solid #fff; }}
  .popup-group {{ font-weight:bold; margin-bottom:8px; font-size:13px; color:#333; }}
  .popup-divider {{ border:none; border-top:1px solid #ddd; margin:10px 0; }}
  .dot {{ display:inline-block; width:9px; height:9px; border-radius:50%; margin-right:6px; vertical-align:middle; }}
  .leaflet-popup-content {{ max-height:320px; overflow-y:auto; }}
</style>
</head>
<body>
<div id="map"></div>
<div class="legend">
  <b>Immobilienart</b>
  <div><span style="background:#1f77b4"></span>Einfamilienhaus</div>
  <div><span style="background:#2ca02c"></span>Doppelhaushälfte</div>
  <div><span style="background:#d62728"></span>Mehrfamilienhaus</div>
  <div><span style="background:#9467bd"></span>Eigentumswohnung</div>
  <div><span style="background:#8c564b"></span>Mietwohnung</div>
  <div><span style="background:#ff7f0e"></span>Gewerbe</div>
  <div><span style="background:#17becf"></span>Grundstück</div>
</div>
<div class="stand" id="stand"></div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const colors = {colors_json};
const listings = {markers_json};

const map = L.map('map').setView([50.85, 12.95], 10);
L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
  attribution: '&copy; OpenStreetMap-Mitwirkende',
  maxZoom: 19
}}).addTo(map);

document.getElementById('stand').textContent =
  'Stand: ' + new Date().toLocaleDateString('de-DE') + ' · ' + listings.length + ' Anzeigen';

const grouped = {{}};
listings.forEach(l => {{
  const key = l.lat + ',' + l.lon;
  grouped[key] = grouped[key] || [];
  grouped[key].push(l);
}});

function preisText(l) {{
  return l.preis ? (l.kauf_oder_miete === "Miete"
    ? l.preis.toLocaleString("de-DE") + " € / Monat"
    : l.preis.toLocaleString("de-DE") + " €") : "auf Anfrage";
}}

function listingBlock(l, withDot) {{
  const color = colors[l.typ] || "#7f7f7f";
  return `
    <div class="popup-title">${{withDot ? `<span class="dot" style="background:${{color}}"></span>` : ""}}${{l.titel || "Anzeige"}}</div>
    <table class="popup-table">
      <tr><td>Art der Immobilie:</td><td>${{l.typ}}${{l.kauf_oder_miete ? " ("+l.kauf_oder_miete+")" : ""}}</td></tr>
      <tr><td>Wohnfläche:</td><td>${{l.wohnflaeche_m2 != null ? l.wohnflaeche_m2 + " m²" : "k.A."}}</td></tr>
      <tr><td>Zimmer:</td><td>${{l.zimmer != null ? l.zimmer : "k.A."}}</td></tr>
      <tr><td>Grundstück:</td><td>${{l.grundstueck_m2 != null ? l.grundstueck_m2.toLocaleString("de-DE") + " m²" : "k.A."}}</td></tr>
      <tr><td>Preis:</td><td>${{preisText(l)}}</td></tr>
      <tr><td>Ort:</td><td>${{l.ort || ""}}${{l.plz ? " ("+l.plz+")" : ""}}</td></tr>
    </table>
    ${{l.url ? `<a class="expose-link" href="${{l.url}}" target="_blank">Exposé öffnen →</a>` : ""}}
  `;
}}

let bounds = [];
Object.keys(grouped).forEach(key => {{
  const group = grouped[key];
  const pos = [group[0].lat, group[0].lon];
  bounds.push(pos);

  if (group.length === 1) {{
    const l = group[0];
    const color = colors[l.typ] || "#7f7f7f";
    const marker = L.circleMarker(pos, {{
      radius: 9, color: "#222", weight: 1, fillColor: color, fillOpacity: 0.9
    }}).addTo(map);
    marker.bindPopup(listingBlock(l, false));
    return;
  }}

  // Mehrere Anzeigen am selben Standort (z.B. mehrere Einheiten im selben
  // Haus oder mehrere Grundstücke am selben Ort): ein Marker mit
  // Zähler-Badge, alle Anzeigen im Popup untereinander gestapelt.
  const icon = L.divIcon({{
    className: '',
    html: `<div class="cluster-marker">${{group.length}}</div>`,
    iconSize: [26, 26],
    iconAnchor: [13, 13]
  }});
  const marker = L.marker(pos, {{ icon }}).addTo(map);
  const blocks = group
    .map(l => listingBlock(l, true))
    .join('<hr class="popup-divider">');
  marker.bindPopup(`<div class="popup-group">${{group.length}} Anzeigen an diesem Standort</div>${{blocks}}`);
}});

if (bounds.length) {{
  map.fitBounds(bounds, {{ padding: [40,40] }});
}}
</script>
</body>
</html>
"""
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(html, encoding="utf-8")


def main():
    if not PROPSTACK_API_KEY:
        print("Fehler: Umgebungsvariable PROPSTACK_API_KEY ist nicht gesetzt.", file=sys.stderr)
        sys.exit(1)

    geocache = load_geocache()

    units = fetch_active_units()
    print(f"{len(units)} aktiv vermarktete Einheiten in Propstack gefunden.")

    title_to_url = fetch_website_links()
    print(f"{len(title_to_url)} Exposé-Links von der Homepage zugeordnet.")

    markers = build_markers(units, geocache, title_to_url)
    print(f"{len(markers)}/{len(units)} Anzeigen mit Koordinaten platziert.")

    build_html(markers)
    print(f"Karte geschrieben nach: {OUT_HTML}")


if __name__ == "__main__":
    main()
