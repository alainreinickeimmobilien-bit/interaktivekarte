"""Crawlt alle Anzeigen von alainreinickeimmobilien.de und baut daraus eine
einbettbare Leaflet/OpenStreetMap-Karte (docs/index.html für GitHub Pages).

Läuft täglich per GitHub Actions (siehe .github/workflows/update-alain-karte.yml)
und nimmt neue Anzeigen automatisch auf bzw. entfernt verschwundene.
"""
import json
import re
import time
from html import unescape
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent.parent
OUT_HTML = BASE / "docs" / "index.html"
GEOCACHE = Path(__file__).resolve().parent / "geocode_cache.json"

OVERVIEW_URL = "https://alainreinickeimmobilien.de/immobilien-angebote-chemnitz/"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; alain-reinicke-karte/1.0)"}

COLORS = {
    "Einfamilienhaus": "#2563eb",
    "Doppelhaushälfte": "#16a34a",
    "Mehrfamilienhaus": "#dc2626",
    "Eigentumswohnung": "#9333ea",
    "Mietwohnung": "#db2777",
    "Gewerbe": "#ea580c",
    "Grundstück": "#65a30d",
    "Sonstiges": "#6b7280",
}


def load_geocache():
    if GEOCACHE.exists():
        return json.loads(GEOCACHE.read_text())
    return {}


def save_geocache(cache):
    GEOCACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=2))


# Orte, die Nominatim unter der vollen "PLZ Ort"-Schreibweise nicht findet
# (Tippfehler/Abkürzungen aus dem Exposé) und die deshalb umgeschrieben werden.
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


def geocode(query, cache, plz=None, ort=None):
    if not query:
        return None
    key = query.strip().lower()
    if key in cache:
        return cache[key]
    result = None
    try:
        result = _nominatim_request(query)
        # Fallback 1: ohne PLZ, nur Ortsname (PLZ-Praefix kann die Trefferquote senken)
        if not result and ort:
            result = _nominatim_request(f"{ort}, Deutschland")
        # Fallback 2: bekannte Korrektur für abweichende Schreibweisen
        if not result and ort:
            fixed = ORT_FIXES.get(ort.strip().lower())
            if fixed:
                result = _nominatim_request(f"{fixed}, Deutschland")
    except Exception:
        result = None
    cache[key] = result
    save_geocache(cache)
    return result


def get_overview_links():
    resp = requests.get(OVERVIEW_URL, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    links = set(re.findall(
        r'https://alainreinicke\.landingpage\.immobilien/public/exposee/[A-Za-z0-9\-_=]+',
        resp.text,
    ))
    return sorted(links)


FIELD_RE = re.compile(
    r'data-field-name="(?P<name>[a-z_]+)">\s*<td>[^<]*</td>\s*<td class="text-right">\s*(?P<value>[^<]*?)\s*</td>',
    re.S,
)
TYPE_MAP = {
    "Einfamilienhaus": "Einfamilienhaus",
    "Doppelhaushälfte": "Doppelhaushälfte",
    "Mehrfamilienhaus": "Mehrfamilienhaus",
    "Eigentumswohnung": "Eigentumswohnung",
    "Wohnung": "Eigentumswohnung",
    "Grundstück": "Grundstück",
    "Baugrundstück": "Grundstück",
    "Gewerbe": "Gewerbe",
    "Büro": "Gewerbe",
    "Praxis": "Gewerbe",
    "Laden": "Gewerbe",
    "Hotel": "Gewerbe",
}

# Unterkategorien (rs_category), die bei Mietobjekten auftauchen und auf eine
# einheitliche Bezeichnung ("Mietwohnung" / "Gewerbe") gemappt werden, statt
# als unbeschrifteter Rohwert ("Etagenwohnung", "Penthouse" etc.) zu erscheinen.
MIETE_WOHNUNG_SUBTYPES = {
    "Wohnung", "Etagenwohnung", "Dachgeschoss", "Penthouse", "Maisonette",
    "Erdgeschosswohnung", "Souterrain", "Loft", "Apartment",
}
MIETE_GEWERBE_SUBTYPES = {
    "Büro", "Büroetage", "Praxis", "Laden", "Halle", "Lager", "Hotel", "Gewerbe",
}


def parse_number(text):
    if not text:
        return None
    text = text.replace(".", "").replace(",", ".")
    m = re.search(r"[\d.]+", text)
    return float(m.group()) if m else None


def fetch_listing(url):
    entry = {
        "titel": None, "url": url, "typ": "Sonstiges", "kauf_oder_miete": None,
        "ort": None, "plz": None, "geo_query": None,
        "wohnflaeche_m2": None, "zimmer": None, "grundstueck_m2": None, "preis": None,
        "status": "aktiv",
    }
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
    except Exception:
        entry["status"] = "fehler"
        return entry
    if resp.status_code != 200:
        entry["status"] = f"http_{resp.status_code}"
        return entry

    html = resp.text

    m = re.search(r'<h1 class="lp-title">([^<]*)</h1>', html)
    entry["titel"] = unescape(m.group(1)).strip() if m else None

    m = re.search(r'<p class="lp-subTitle">([^<]*)</p>', html)
    if m:
        loc = unescape(m.group(1)).strip()
        zm = re.match(r"(\d{4,5})\s+(.*)", loc)
        if zm:
            entry["plz"], entry["ort"] = zm.group(1), zm.group(2)
        else:
            entry["ort"] = loc
        entry["geo_query"] = f"{loc}, Deutschland"

    fields = {fm.group("name"): unescape(fm.group("value")).strip() for fm in FIELD_RE.finditer(html)}

    category = fields.get("category", "")
    entry["kauf_oder_miete"] = "Miete" if category.lower().startswith("miete") else "Kauf"

    sub = fields.get("rs_category", "")
    if entry["kauf_oder_miete"] == "Miete" and sub in MIETE_WOHNUNG_SUBTYPES:
        entry["typ"] = "Mietwohnung"
    elif entry["kauf_oder_miete"] == "Miete" and sub in MIETE_GEWERBE_SUBTYPES:
        entry["typ"] = "Gewerbe"
    else:
        entry["typ"] = TYPE_MAP.get(sub, sub or "Sonstiges")

    entry["wohnflaeche_m2"] = parse_number(fields.get("living_space"))
    entry["zimmer"] = parse_number(fields.get("number_of_rooms"))
    entry["grundstueck_m2"] = parse_number(fields.get("plot_area"))
    entry["preis"] = parse_number(fields.get("price"))

    if "reserviert" in html.lower()[:200] or "Reserviert" in fields.get("category", ""):
        pass  # Statusfeld variiert je Anzeige; grobe Erkennung über Übersichtsseite separat

    return entry


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
  .approx {{ font-size:11px; color:#888; font-style:italic; margin-top:4px; }}
  a.expose-link {{ display:inline-block; margin-top:6px; font-size:13px; }}
  .stand {{ position:absolute; bottom:6px; left:6px; z-index:1000; background:rgba(255,255,255,0.85);
    padding:3px 8px; border-radius:6px; font-size:11px; color:#555; }}
</style>
</head>
<body>
<div id="map"></div>
<div class="legend">
  <b>Immobilienart</b>
  <div><span style="background:#2563eb"></span>Einfamilienhaus</div>
  <div><span style="background:#16a34a"></span>Doppelhaushälfte</div>
  <div><span style="background:#dc2626"></span>Mehrfamilienhaus</div>
  <div><span style="background:#9333ea"></span>Eigentumswohnung</div>
  <div><span style="background:#db2777"></span>Mietwohnung</div>
  <div><span style="background:#ea580c"></span>Gewerbe</div>
  <div><span style="background:#65a30d"></span>Grundstück</div>
</div>
<div class="stand" id="stand"></div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const colors = {colors_json};
const listings = {markers_json};

function jitter([lat, lng], i) {{
  const d = 0.003 * (i % 5) - 0.006;
  return [lat + d, lng - d];
}}

const map = L.map('map').setView([50.85, 12.95], 10);
L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
  attribution: '&copy; OpenStreetMap-Mitwirkende',
  maxZoom: 19
}}).addTo(map);

document.getElementById('stand').textContent =
  'Stand: ' + new Date().toLocaleDateString('de-DE') + ' · ' + listings.length + ' Anzeigen';

const grouped = {{}};
listings.forEach(l => {{
  const key = l.geo_query || l.ort;
  grouped[key] = grouped[key] || [];
  grouped[key].push(l);
}});

let bounds = [];
Object.keys(grouped).forEach(key => {{
  const group = grouped[key];
  group.forEach((l, i) => {{
    if (l.lat == null || l.lon == null) return;
    const base = [l.lat, l.lon];
    const pos = group.length > 1 ? jitter(base, i) : base;
    bounds.push(pos);
    const color = colors[l.typ] || "#6b7280";
    const marker = L.circleMarker(pos, {{
      radius: 9, color: "#222", weight: 1, fillColor: color, fillOpacity: 0.9
    }}).addTo(map);

    const preisText = l.preis ? (l.kauf_oder_miete === "Miete"
      ? l.preis.toLocaleString("de-DE") + " € / Monat"
      : l.preis.toLocaleString("de-DE") + " €") : "auf Anfrage";

    const html = `
      <div class="popup-title">${{l.titel || "Anzeige"}}</div>
      <table class="popup-table">
        <tr><td>Art der Immobilie:</td><td>${{l.typ}}${{l.kauf_oder_miete ? " ("+l.kauf_oder_miete+")" : ""}}</td></tr>
        <tr><td>Wohnfläche:</td><td>${{l.wohnflaeche_m2 != null ? l.wohnflaeche_m2 + " m²" : "k.A."}}</td></tr>
        <tr><td>Zimmer:</td><td>${{l.zimmer != null ? l.zimmer : "k.A."}}</td></tr>
        <tr><td>Grundstück:</td><td>${{l.grundstueck_m2 != null ? l.grundstueck_m2.toLocaleString("de-DE") + " m²" : "k.A."}}</td></tr>
        <tr><td>Preis:</td><td>${{preisText}}</td></tr>
        <tr><td>Ort:</td><td>${{l.ort || ""}}${{l.plz ? " ("+l.plz+")" : ""}}</td></tr>
      </table>
      <div class="approx">Ungefähre Lage (Ort/Stadtteil, keine genaue Adresse im Exposé)</div>
      ${{l.url ? `<a class="expose-link" href="${{l.url}}" target="_blank">Exposé öffnen →</a>` : ""}}
    `;
    marker.bindPopup(html);
  }});
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
    cache = load_geocache()
    links = get_overview_links()
    print(f"{len(links)} Exposé-Links auf der Übersichtsseite gefunden.")

    markers = []
    for url in links:
        entry = fetch_listing(url)
        if entry["status"] != "aktiv":
            print(f"  übersprungen ({entry['status']}): {url}")
            continue
        geo = geocode(entry["geo_query"], cache, plz=entry["plz"], ort=entry["ort"])
        if geo:
            entry["lat"], entry["lon"] = geo["lat"], geo["lon"]
        else:
            entry["lat"], entry["lon"] = None, None
        markers.append(entry)
        time.sleep(0.5)

    placed = sum(1 for m in markers if m["lat"] is not None)
    print(f"{placed}/{len(markers)} Anzeigen mit Koordinaten platziert.")
    build_html(markers)
    print(f"Karte geschrieben nach: {OUT_HTML}")


if __name__ == "__main__":
    main()
