#!/usr/bin/env python3
# ============================================================
# main.py – Grundstückssuche Hauptskript
# Aufruf: python3 main.py
# ============================================================

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from plz_liste             import lade_plz_liste
from scraper_thinkimmo     import suche_thinkimmo    # 50 Portale in einem!
from scraper_kleinanzeigen import suche_kleinanzeigen  # Backup / Direktsuche
from scraper_makler        import suche_makler        # Lokale Makler
from excel_handler         import schreibe_in_excel
from propstack_import      import importiere_in_propstack


def main():
    print("=" * 60)
    print("  GRUNDSTÜCKSSUCHE – massa haus Sophia")
    print("=" * 60)

    # PLZ-Liste laden
    print("\n📍 Lade PLZ-Liste...")
    plz_set = lade_plz_liste()
    print(f"   {len(plz_set)} PLZ geladen")

    alle_ergebnisse = []

    # ── ThinkImmo (IS24 + ImmoWelt + Kleinanzeigen + 47 weitere)
    print("\n🔍 Suche via ThinkImmo (50 Portale)...")
    try:
        ti = suche_thinkimmo(plz_set)
        alle_ergebnisse.extend(ti)
    except Exception as e:
        print(f"   Fehler ThinkImmo: {e}")
        # Fallback: direkte Scraper
        print("   → Fallback: Direktsuche Kleinanzeigen...")
        try:
            alle_ergebnisse.extend(suche_kleinanzeigen(plz_set))
        except Exception as e2:
            print(f"   Fehler Kleinanzeigen: {e2}")

    # ── Lokale Makler-Websites (nicht auf ThinkImmo)
    print("\n🔍 Suche auf lokalen Makler-Websites...")
    try:
        makler = suche_makler(plz_set)
        alle_ergebnisse.extend(makler)
    except Exception as e:
        print(f"   Fehler Makler: {e}")

    # ── Excel schreiben ────────────────────────────────────
    print(f"\n📊 Schreibe in Excel ({len(alle_ergebnisse)} Treffer gesamt)...")
    neu = schreibe_in_excel(alle_ergebnisse)

    print("\n" + "=" * 60)
    print(f"  ✅ FERTIG – {neu} neue Grundstücke in Excel eingetragen")
    print("=" * 60)

    # ── Propstack: neue Grundstücke als Entwurf anlegen ───────
    # Nur Zeilen mit Status "Import" werden übertragen.
    # Veröffentlichung erfolgt manuell durch Sophia in Propstack.
    print()
    importiere_in_propstack()


if __name__ == "__main__":
    main()
