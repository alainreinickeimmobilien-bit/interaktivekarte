"""
Adapter zwischen der Webapp-DB und der bestehenden Scraper-/Propstack-Logik
in grundstueck_system/. Die Scraper- und Propstack-Hilfsfunktionen werden
unverändert wiederverwendet — nur die Excel-I/O wird durch DB-Zugriffe ersetzt.
"""
from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from typing import Callable

from sqlalchemy.orm import Session

from app.config import GRUNDSTUECK_SYSTEM_DIR
from app.models import Property, SeenUrl, ThinkImmoSession

sys.path.insert(0, GRUNDSTUECK_SYSTEM_DIR)

from plz_liste import lade_plz_liste  # noqa: E402
from scraper_thinkimmo import suche_thinkimmo  # noqa: E402
from scraper_kleinanzeigen import suche_kleinanzeigen  # noqa: E402
from scraper_makler import suche_makler  # noqa: E402
from gs_update import check_link  # noqa: E402
from propstack_import import (  # noqa: E402
    BROKER_ID,
    IMPORT_STATI,
    _beschreibung,
    _fmt,
    _lade_bilder_fuer_haustyp,
    _lade_hauspreise,
    _parse_grundstueck_preis,
    _payload,
    _post_to_propstack,
    _titel,
    _upload_bilder,
)

LogFn = Callable[[str], None]


def _noop_log(msg: str) -> None:
    pass


def _wert(eintrag: dict, key: str) -> str:
    val = eintrag.get(key, "")
    return str(val).strip() if val else ""


def get_thinkimmo_cookies(db: Session) -> dict | None:
    session = (
        db.query(ThinkImmoSession).order_by(ThinkImmoSession.updated_at.desc()).first()
    )
    if not session:
        return None
    try:
        import json

        return json.loads(session.cookie_value)
    except (ValueError, TypeError):
        return None


def schreibe_in_db(db: Session, neue_eintraege: list, log: LogFn = _noop_log) -> int:
    """Pendant zu excel_handler.schreibe_in_excel — Dedup über DB statt Excel."""
    vorhandene_links = {row.link for row in db.query(Property.link).all()}
    gesehene_urls = {row.url for row in db.query(SeenUrl.url).all()}

    heute = date.today().strftime("%d.%m.%Y")
    neu_geschrieben = 0

    for eintrag in neue_eintraege:
        link = _wert(eintrag, "link")
        if not link or link in vorhandene_links or link in gesehene_urls:
            continue

        db.add(
            Property(
                link=link,
                datum=heute,
                plattform=_wert(eintrag, "plattform"),
                plz=_wert(eintrag, "plz"),
                ort=_wert(eintrag, "ort"),
                adresse=_wert(eintrag, "adresse"),
                groesse=_wert(eintrag, "groesse"),
                preis=_wert(eintrag, "preis"),
                bplan=_wert(eintrag, "bplan"),
                anbieter=_wert(eintrag, "anbieter"),
                status="Neu",
                propstack_id="",
                notizen=_wert(eintrag, "notizen"),
                haustyp="",
                is_expired=False,
            )
        )
        db.add(SeenUrl(url=link))
        vorhandene_links.add(link)
        gesehene_urls.add(link)
        neu_geschrieben += 1

    db.commit()
    log(f"📊 {neu_geschrieben} neue Grundstücke in DB eingetragen")
    return neu_geschrieben


def importiere_in_propstack_db(db: Session, log: LogFn = _noop_log) -> int:
    """Pendant zu propstack_import.importiere_in_propstack — DB statt Excel."""
    to_import = (
        db.query(Property)
        .filter(Property.status.isnot(None))
        .all()
    )
    to_import = [p for p in to_import if p.status.strip().lower() in IMPORT_STATI]

    if not to_import:
        log("ℹ️  Keine Grundstücke mit Status 'Import' gefunden.")
        return 0

    log(f"📋 {len(to_import)} Grundstück(e) zum Import")
    erfolge = 0

    for prop in to_import:
        plz, ort, groesse, haustyp, anbieter = (
            prop.plz or "",
            prop.ort or "",
            prop.groesse or "",
            prop.haustyp or "",
            prop.anbieter or "",
        )
        gs_preis = _parse_grundstueck_preis(prop.preis)

        log(f"📍 {ort} ({plz}) | {groesse} | {gs_preis:,.0f} € | {haustyp}")

        if not haustyp:
            log("⚠️  Kein Haustyp eingetragen — übersprungen.")
            prop.status = "Import fehlt Haustyp"
            db.commit()
            continue

        hauspreise = _lade_hauspreise(haustyp)
        if not hauspreise:
            prop.status = "Import fehlt Haustyp"
            db.commit()
            continue

        gesamt = gs_preis + hauspreise["ausbauhaus"] + hauspreise["technikpaket"]
        titel = _titel(ort, haustyp)
        beschr_main, beschr_lage = _beschreibung(
            gs_preis, hauspreise, groesse, plz, ort, haustyp, anbieter
        )
        payload = _payload(titel, beschr_main, beschr_lage, plz, ort, gesamt)
        payload["property"]["broker_id"] = BROKER_ID

        bilder = _lade_bilder_fuer_haustyp(haustyp)
        log(f"🖼  {len(bilder)} Bilder gefunden für {haustyp}")

        ok, result = _post_to_propstack(payload)
        if ok:
            log(f"✅ Angelegt: {titel[:55]}... | Gesamtpreis: {_fmt(gesamt)} | ID: {result}")
            if bilder:
                _upload_bilder(result, bilder)
                log(f"🖼  {len(bilder)} Bilder hochgeladen")
            prop.status = "In Propstack"
            prop.propstack_id = result
            erfolge += 1
        else:
            log(f"❌ Fehler: {result}")
        db.commit()

    log(f"✅ {erfolge} von {len(to_import)} Entwürfe angelegt (nur Entwurf, kein Publish)")
    return erfolge


def markiere_abgelaufen_db(db: Session, log: LogFn = _noop_log) -> int:
    """Pendant zu gs_update.markiere_abgelaufen — DB statt PatternFill."""
    properties = db.query(Property).filter(Property.link.isnot(None)).all()
    to_check = [(p.id, p.link, p.ort, p.plz) for p in properties if p.link]

    log(f"🔗 Prüfe {len(to_check)} Links auf Gültigkeit ...")
    with ThreadPoolExecutor(max_workers=15) as exe:
        results = list(exe.map(check_link, to_check))

    expired_ids = [r[0] for r in results if r[5]]
    by_id = {p.id: p for p in properties}

    for prop_id in expired_ids:
        prop = by_id[prop_id]
        if not prop.is_expired:
            log(f"🔴 Abgelaufen: {prop.ort} ({prop.plz})")
        prop.is_expired = True
    db.commit()

    log(f"✅ {len(expired_ids)} abgelaufene Einträge markiert.")
    return len(expired_ids)


def run_update(db: Session, log: LogFn = _noop_log) -> None:
    log("📍 Lade PLZ-Liste...")
    plz_set = lade_plz_liste()
    log(f"   {len(plz_set)} PLZ geladen")

    alle_ergebnisse = []

    log("🔍 Suche via ThinkImmo (50 Portale)...")
    try:
        cookies = get_thinkimmo_cookies(db)
        if not cookies:
            raise RuntimeError(
                "Kein ThinkImmo-Cookie in der DB hinterlegt — bitte über noVNC einloggen "
                "und Cookie-Export ausführen."
            )
        ti = suche_thinkimmo(plz_set, cookies=cookies)
        alle_ergebnisse.extend(ti)
    except Exception as e:
        log(f"⚠️  Fehler ThinkImmo: {e}")
        log("   → Fallback: Direktsuche Kleinanzeigen...")
        try:
            alle_ergebnisse.extend(suche_kleinanzeigen(plz_set))
        except Exception as e2:
            log(f"⚠️  Fehler Kleinanzeigen: {e2}")

    log("🔍 Suche auf lokalen Makler-Websites...")
    try:
        alle_ergebnisse.extend(suche_makler(plz_set))
    except Exception as e:
        log(f"⚠️  Fehler Makler: {e}")

    log(f"📊 {len(alle_ergebnisse)} Treffer gesamt — schreibe in DB...")
    schreibe_in_db(db, alle_ergebnisse, log)

    importiere_in_propstack_db(db, log)
    markiere_abgelaufen_db(db, log)
