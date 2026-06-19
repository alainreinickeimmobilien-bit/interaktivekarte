#!/bin/bash
# ============================================================
# starte_suche.sh – Grundstückssuche manuell starten
# Doppelklick oder Terminal: bash starte_suche.sh
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================"
echo "  massa haus – Automatische Grundstückssuche"
echo "  $(date '+%d.%m.%Y %H:%M')"
echo "============================================"

python3 main.py

echo ""
echo "Fertig! Excel-Datei öffnen:"
open "../Grundstuecke_Uebersicht.xlsx"
