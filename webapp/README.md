# Grundstücks-Webapp

Web-App für die Grundstücks-Übersicht: Tabelle ansehen & filtern, Update per
Knopfdruck, Propstack-Status einsehen. Läuft als Docker-Container auf dem
UGREEN-NAS, Daten liegen in einer SQLite-Datenbank (nicht mehr in Excel).

## Umzug / Verschieben des Projektordners

Der gesamte Code (`webapp/` + `grundstueck_system/`) kann problemlos verschoben
werden (z.B. auf das NAS) — die Pfade darin sind relativ zueinander aufgebaut.

**Aber:** drei Dateien/Ordner liegen bisher außerhalb dieses Projektordners auf
dem Mac und werden zur Laufzeit gebraucht (PLZ-Liste, Hauspreise-Datenbank,
Bilder für den Propstack-Upload). Damit das auch auf dem NAS funktioniert,
auf dem NAS einen Ordner `assets/` neben `docker-compose.yml` anlegen mit:

```
webapp/assets/PLZ-Liste_26.03.26.xlsx         ← Kopie von 2_ZUM KALKULIEREN/PLZ-Liste_26.03.26.xlsx
webapp/assets/Preisliste_massa_haus.db        ← Kopie von 2_ZUM KALKULIEREN/Preisliste_massa_haus.db
webapp/assets/bilder/FamilyStyle_Grundrisse/  ← Kopien der Bilder-Ordner
webapp/assets/bilder/UrbanStyle_Grundrisse/   ← (alle *_Grundrisse-Ordner, die es gibt)
```

`docker-compose.yml` mountet diesen `assets/`-Ordner automatisch in den
Container und setzt die passenden Umgebungsvariablen (`PLZ_FILE`, `DB_PREISE`,
`IMG_BASISORDNER`). Liegt der `assets/`-Ordner woanders, in `.env` zusätzlich
`ASSETS_DIR=/pfad/zum/assets-ordner` eintragen.

Auf dem Mac läuft alles unverändert weiter — die Umgebungsvariablen sind
optional, ohne sie greifen automatisch die bisherigen Mac-Pfade.

## Einmalige Einrichtung

1. **`.env` anlegen** (im `webapp/`-Ordner, neben `docker-compose.yml`):
   ```
   cp .env.example .env
   ```
   Dann `APP_PASSWORD` und `SECRET_KEY` in `.env` eintragen (für `SECRET_KEY`
   z.B. `openssl rand -hex 32` ausführen). **Diese Datei nicht ins Repo
   einchecken.**

2. **Bestehende Excel-Daten migrieren** (einmalig, bevor die App zum ersten
   Mal läuft):
   ```
   cd webapp
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   APP_PASSWORD=x SECRET_KEY=x python3 migrate_excel_to_db.py
   ```
   Das legt `webapp/data/grundstuecke.db` an und übernimmt alle Zeilen aus
   `Grundstuecke_Uebersicht.xlsx` (rot markierte Zeilen werden als
   "abgelaufen" übernommen, nicht gelöscht).

3. **Container bauen und starten** (auf dem NAS, im Docker/Container-Manager
   von UGREEN, oder per SSH mit `docker compose`):
   ```
   docker compose --env-file .env up -d --build
   ```
   Die App ist danach unter `http://NAS-IP:8080` erreichbar.

4. **DB-Datei auf das NAS übertragen**: Die migrierte `webapp/data/grundstuecke.db`
   einmalig in das `gs-data`-Volume des Containers kopieren (z.B. via
   `docker cp grundstuecke.db <container>:/webapp/data/grundstuecke.db`),
   bevor der Container zum ersten Mal startet — sonst beginnt die App mit
   einer leeren Datenbank.

## ThinkImmo-Login einrichten (einmalig, danach gelegentlich wiederholen)

Der ThinkImmo-Scraper braucht eine eingeloggte Session. Das übernimmt ein
zweiter Container mit einem Browser inkl. Web-Oberfläche (noVNC):

1. Im Browser öffnen: `http://NAS-IP:3001` (Passwort/Setup je nach
   `linuxserver/chromium`-Image-Version, siehe Container-Logs beim ersten
   Start).
2. Im dort angezeigten Chrome-Fenster zu `https://thinkimmo.com` navigieren
   und einloggen.
3. Cookie-Export ausführen (entweder per Cronjob im `webapp`-Container oder
   manuell):
   ```
   docker compose exec webapp python3 thinkimmo_cookie_export.py
   ```
   **Wichtig:** Der Pfad zum Chrome-Profil (`CHROME_PROFILE_DIR`, Standard
   `/chrome-profile/Default`) hängt von der genauen Ordnerstruktur des
   `linuxserver/chromium`-Images ab — beim ersten Versuch prüfen, ob dort
   tatsächlich eine `Cookies`-Datei liegt, sonst Pfad in `.env` anpassen
   (`docker compose exec thinkimmo-browser find /config -name Cookies`).
4. Die Session läuft nach einiger Zeit ab — wenn der "Update starten"-Button
   in der App einen ThinkImmo-Fehler meldet, einfach Schritt 2+3 wiederholen.

## Tägliche Nutzung

- **Tabelle ansehen/filtern**: einfach die Startseite öffnen, nach PLZ/Ort/Status
  filtern. Abgelaufene Einträge sind rot hinterlegt und standardmäßig
  ausgeblendet (Checkbox "abgelaufene anzeigen" zum Einblenden).
- **Update starten**: Button "Update starten" — läuft im Hintergrund, der
  Log erscheint live darunter.
- **Haustyp setzen / Status auf "Import" setzen**: direkt in der Tabelle pro
  Zeile editierbar. Bei Status "Import" wird beim nächsten Update-Lauf
  automatisch ein **Entwurf** in Propstack angelegt (nie automatisch
  veröffentlicht — das macht Sophia wie bisher manuell in Propstack).

## Sicherung

Die SQLite-Datei (`webapp/data/grundstuecke.db` im `gs-data`-Volume) ist die
einzige Datenquelle — regelmäßig sichern (z.B. über die NAS-eigene
Backup-Funktion für Docker-Volumes).
