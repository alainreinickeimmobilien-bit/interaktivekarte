#!/usr/bin/env python3
"""
Liest den ThinkImmo-Session-Cookie aus dem Chrome-Profil des
noVNC-Browser-Containers und speichert ihn in der Webapp-DB.

Voraussetzung: Sophia hat sich einmalig über noVNC bei https://thinkimmo.com
im dort laufenden Chrome eingeloggt (siehe README.md).

Aufruf: python3 thinkimmo_cookie_export.py [chrome-profil-verzeichnis]
Env: CHROME_PROFILE_DIR (Default-Pfad, falls kein Argument übergeben wird)
"""
import json
import os
import sys

import browser_cookie3

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.db import SessionLocal, init_db
from app.models import ThinkImmoSession

DEFAULT_PROFILE_DIR = os.environ.get(
    "CHROME_PROFILE_DIR", "/chrome-profile/Default"
)


def export_cookie(profile_dir: str) -> dict:
    cookie_file = os.path.join(profile_dir, "Cookies")
    if not os.path.exists(cookie_file):
        raise FileNotFoundError(
            f"Keine Chrome-Cookies-Datei gefunden unter {cookie_file} — "
            "bitte zuerst über noVNC bei thinkimmo.com einloggen."
        )
    jar = browser_cookie3.chrome(domain_name="thinkimmo.com", cookie_file=cookie_file)
    cookies = {c.name: c.value for c in jar}
    if not cookies:
        raise RuntimeError(
            "Keine ThinkImmo-Cookies gefunden — Login über noVNC erneut prüfen."
        )
    return cookies


def save_cookie(cookies: dict):
    init_db()
    db = SessionLocal()
    db.add(ThinkImmoSession(cookie_value=json.dumps(cookies)))
    db.commit()
    db.close()


if __name__ == "__main__":
    profile_dir = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PROFILE_DIR
    cookies = export_cookie(profile_dir)
    save_cookie(cookies)
    print(f"✅ {len(cookies)} Cookies für thinkimmo.com gespeichert.")
