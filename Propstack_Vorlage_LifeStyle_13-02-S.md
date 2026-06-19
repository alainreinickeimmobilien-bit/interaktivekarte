# Propstack-Vorlage: LifeStyle 13.02 S
Stand: Mai 2026 | Referenzobjekt: ID 5468828 (Hauptstrasse 11, Niederwiesa)

---

## STAMMDATEN

| Feld (API-Key) | Wert |
|---|---|
| `rs_type` | `HOUSE` |
| `object_type` | `LIVING` ← immer LIVING lassen, sonst weiße Detailseite! |
| `marketing_type` | `BUY` |
| `construction_phase` | `PROJECTED` → "Haus in Planung (projektiert)" |
| `living_space` | `134` (m², laut massa-haus.de, nur EG+DG zählen, kein KG) |
| `number_of_rooms` | `5` (Wohnzimmer + 4 Schlafzimmer) |
| `number_of_bed_rooms` | `4` |
| `number_of_bath_rooms` | `2` (DU/WC EG + Bad/Du/WC DG – Gäste-WC zählt NICHT) |
| `plot_area` | je nach Grundstück (Niederwiesa: 520 m²) |
| `hide_address` | `true` ← immer! (Blindadresse) |

---

## PREISFORMEL (mit Technikpaket)

```
Ausbauhaus (massa Preisliste)
+ Technikpaket (LW-WP + Bodenplatte + Heizung)
+ Grundstückspreis (inkl. 3,57 % Provision)
+ 8.500 € Pauschale
= Gesamtpreis
```

**Beispiel Niederwiesa:**
133.999 € + 125.980 € + 38.000 € + 8.500 € = **306.479 €**

> Grundstückspreis immer MIT Provision einkalkulieren, wenn GS enthalten.
> Provision 3,57 % inkl. MwSt. → in Objektbeschreibung erwähnen, wenn GS im Angebot.

---

## UNTERKATEGORIE (rs_type)

| Haustyp | `rs_type` Wert |
|---|---|
| Einfamilienhaus | `SINGLE_FAMILY_HOUSE` → "Haus" bleibt, Unterkategorie "Einfamilienhaus" |
| Doppelhaushälfte | `SEMI_DETACHED_HOUSE` |
| Reihenhaus | `ROW_HOUSE` |
| Bungalow | `BUNGALOW` |
| Zweifamilienhaus | `TWO_FAMILY_HOUSE` |
| Mehrfamilienhaus | `MULTI_FAMILY_HOUSE` |
| Trend 11 & 12 | `SINGLE_FAMILY_HOUSE` |
| Trend 16 | `TWO_FAMILY_HOUSE` |

> `object_type` bleibt IMMER `LIVING` – nur `rs_type` ändern!

---

## AUSSTATTUNG (Schieberegler / API-Felder)

Diese Felder werden als **flat properties** gepatcht (nicht unter `furnishings`):

| Feld | LifeStyle 13.02 S | Bemerkung |
|---|---|---|
| `terrace` | `true` | aus Grundriss EG |
| `garden` | `true` | Grundstück vorhanden |
| `guest_toilet` | `true` | EG: Gäste-WC separat |
| `cellar` | nach Grundriss | – |
| `balcony` | nach Grundriss | – |

### Bad (Feld: `bathroom`, Multiselect-Array)
Werte: `SHOWER`, `TUB`, `WINDOW`

| Wert | Deutsch | Wann setzen |
|---|---|---|
| `SHOWER` | Dusche | wenn "Du" im Grundriss |
| `TUB` | Wanne | wenn Wannensymbol im Grundriss sichtbar |
| `WINDOW` | Fenster | wenn Bad an Außenwand mit Fenster |

**LifeStyle 13.02 S:** `['SHOWER', 'WINDOW']` (kein TUB – Grundriss zeigt nur "Du")

> ⚠️ Achtung: Das Feld kann nach UI-Interaktion auf `['SHOWER', 'TUB', 'WINDOW']` zurückspringen. Immer per API nach UI-Bearbeitung prüfen!

---

## TITEL

| Variante | Titel |
|---|---|
| Mit Technikpaket | Fast ein Haus. Fehlst nur noch du. |
| Ohne Technikpaket | Außen fertig, innen dein Ding – [X] m² in [Ort] |

---

## OBJEKTBESCHREIBUNG (`description_note`)

### MIT Technikpaket
```
Jetzt anrufen: Sophia Kröhner – massa haus – 0176 637 214 38

Anzeige beinhaltet Grundstück und technisch fertiges Haus

Das LifeStyle 13.02 S bietet auf ca. 134 m² Wohnfläche eine durchdachte Raumaufteilung für Familien: offener Wohn-/Essbereich mit Küche, flexibles Zimmer (Büro/Gast), Duschbad und HWR im EG – Elternschlafzimmer mit Ankleide, zwei Kinderzimmer und Bad im DG. Zwei vollwertige Geschosse, kein Dachschrägen-Verlust.

── AUSBAUHAUS ENTHÄLT ──
• Architektenleistung & Bauantrag
• Klima-Plus-Wände mit Außenputz
• Fenster & Haustür (3-fach-Verglasung)
• Alu-Rollläden, Dachstuhl & Eindeckung
• Freiraum-Upgrade (2,75 m Deckenhöhe)
• Vierfach-Versicherungsschutz & Bauleitung

── GRUNDSTÜCK ──
Ca. 520 m² | vollerschlossen | Bauvoranfrage positiv
Provision: 3,57 % inkl. MwSt.
```

### OHNE Technikpaket
```
Jetzt anrufen: Sophia Kröhner – massa haus – 0176 637 214 38

Anzeige beinhaltet Grundstück und Ausbauhaus

[Hausbeschreibung analog, ohne Technikpaket-Block]

── AUSBAUHAUS ENTHÄLT ──
• Architektenleistung & Bauantrag
• Klima-Plus-Wände mit Außenputz
• Fenster & Haustür (3-fach-Verglasung)
• Alu-Rollläden, Dachstuhl & Eindeckung
• Freiraum-Upgrade (2,75 m Deckenhöhe)
• Vierfach-Versicherungsschutz & Bauleitung

── GRUNDSTÜCK ──
Ca. [X] m² | vollerschlossen
Provision: 3,57 % inkl. MwSt.
```

---

## AUSSTATTUNGSBESCHREIBUNG (`furnishing_note`)

### MIT Technikpaket
```
Technikpaket (Luft-Wasser-Wärmepumpe Kompaktanlage):
• LW-Wärmepumpe inkl. Montage
• Standard-Bodenplatte
• Fußbodenheizung EG/OG
• Sanitärrohinstallation
• Elektroinstallation inkl. Netzwerkdosen
• Holztreppe EG/OG – Colorline
• Dämmungs- & Beplankungspaket (Materiallieferung)
• Be- und Entlüftungsanlage (bis zu 90 % Wärmerückgewinnung)
```

### OHNE Technikpaket
```
[Leer oder individuelle Sonderausstattung eintragen]
```

---

## LAGEBESCHREIBUNG (`location_note`)

Vorlage Niederwiesa – je nach Ort anpassen:

```
[Ort] liegt im Landkreis [Landkreis], eingebettet in [Landschaft] – eine gewachsene Gemeinde, die für unterschiedliche Lebensphasen das Richtige bietet.

── VERSORGUNG & EINKAUFEN ──
[Supermärkte, Discounter, Bäcker, Apotheke]

── GESUNDHEIT ──
[Hausärzte, Zahnärzte, Fachärzte via nächste Stadt]

── FÜR FAMILIEN ──
[Kita, Grundschule, Oberschule, ruhige Lage]

── FÜR JUNGE MENSCHEN ──
[Nächste Stadt mit Hochschulen/Arbeit, Pendelzeit, erschwingliche Preise]

── FÜR ÄLTERE MENSCHEN ──
[Naturnahes Wohnen, kurze Wege, ruhige Gemeinschaft]
```

---

## SOCIAL MEDIA

### Facebook (`facebook_post_description`)
```
[Titel mit Emoji] 🏡

[Wohnfläche] m² Wohnfläche, [Grundstück] m² Grundstück, [Zimmer] Zimmer – und ein Technikpaket, das dir jahrelang Arbeit abnimmt: [Kurzliste].

Das Haus steht noch nicht – aber dein Platz dafür schon. In [Ort], [Lage kurz].

Du planst, wir bauen. massa haus macht's möglich.

📞 Meld dich einfach bei mir:
Sophia Kröhner – massa haus – 0176 637 214 38
```

### Instagram (`instagram_post_description`)
```
[Titel] 🏡

[Wohnfläche] m² · [Zimmer] Zimmer · [Grundstück] m² Grundstück
[Ort] | [Landkreis/Region]

Außen fertig – innen gestaltest du. Mit dabei: [Technik-Highlights]. Die Technik läuft, der Rest gehört dir. 🔑

Interesse? Einfach melden 👇
Sophia Kröhner · massa haus · 0176 637 214 38

#massahaus #neubau #eigenheim
```

> Hashtags: max. 3–5, Algorithmus wichtiger als Tags (Stand 2026).

---

## API-REFERENZ (Propstack CRM)

```
Base URL:    https://crm.propstack.de
Endpunkt:    PATCH /api/v1/units/{id}
Auth:        Session-Cookie + X-CSRF-Token (meta[name=csrf-token])
Wrapper:     { "property": { ...felder... } }
```

### Wichtige Feldnamen
| Anzeige | API-Key |
|---|---|
| Titel | `title` |
| Preis | `price` |
| Wohnfläche | `living_space` |
| Grundstücksfläche | `plot_area` |
| Zimmer | `number_of_rooms` |
| Schlafzimmer | `number_of_bed_rooms` |
| Badezimmer | `number_of_bath_rooms` |
| Bauphase | `construction_phase` |
| Unterkategorie | `rs_type` |
| Typ (immer LIVING) | `object_type` |
| Adresse verstecken | `hide_address` |
| Objektbeschreibung | `description_note` |
| Lagebeschreibung | `location_note` |
| Ausstattungsbeschreibung | `furnishing_note` |
| Bad (Multiselect) | `bathroom` → Array: `['SHOWER','TUB','WINDOW']` |
| Terrasse | `terrace` |
| Garten | `garden` |
| Gäste-WC | `guest_toilet` |
| Facebook-Text | `facebook_post_description` |
| Instagram-Text | `instagram_post_description` |

---

## CHECKLISTE – Neues Objekt anlegen

- [ ] Haustyp aus Preisliste → Ausbauhaus + TP-Preis notieren
- [ ] Grundstückspreis (inkl. Provision) klären
- [ ] Gesamtpreis berechnen (+ 8.500 €)
- [ ] Grundrisse lesen: Wohnfläche (nur EG+DG/OG), Zimmeranzahl, Bad-Ausstattung
- [ ] Titel je Variante (mit/ohne TP)
- [ ] `rs_type` (Unterkategorie) korrekt setzen, `object_type` = LIVING lassen
- [ ] Objektbeschreibung (mit oder ohne TP-Block)
- [ ] Lagebeschreibung (nur Ort nennen, NIEMALS Straße!)
- [ ] Ausstattungsbeschreibung (TP-Liste oder leer)
- [ ] Ausstattung-Schieberegler: Terrasse, Garten, Gäste-WC, Bad (Dusche/Wanne/Fenster)
- [ ] Badezimmer-Anzahl per Grundriss (Gäste-WC zählt nicht)
- [ ] Social Media Texte (Facebook + Instagram)
- [ ] Adresse auf hide_address = true prüfen
- [ ] Details-Seite aufrufen → weiße Seite = object_type ist falsch!
- [ ] Entwurf an Sophia zur Prüfung – NICHT selbst veröffentlichen
