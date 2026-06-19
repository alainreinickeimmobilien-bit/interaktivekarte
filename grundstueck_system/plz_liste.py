# ============================================================
# plz_liste.py – PLZ-Liste aus Excel laden
# ============================================================

import pandas as pd
from config import PLZ_FILE


def lade_plz_liste() -> set:
    """Gibt ein Set aller PLZ aus der PLZ-Gebietsliste zurück."""
    df = pd.read_excel(PLZ_FILE, header=1)
    plz_set = set()
    for val in df["PLZ"].dropna():
        plz_str = str(int(val)).zfill(5)
        plz_set.add(plz_str)
    return plz_set


def plz_in_gebiet(plz: str, plz_set: set) -> bool:
    return str(plz).zfill(5) in plz_set


if __name__ == "__main__":
    plz = lade_plz_liste()
    print(f"PLZ geladen: {len(plz)}")
    print("Beispiele:", sorted(plz)[:10])
