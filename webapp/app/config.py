import os

WEBAPP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRUNDSTUECK_SYSTEM_DIR = os.path.join(
    os.path.dirname(WEBAPP_DIR), "grundstueck_system"
)

DB_PATH = os.environ.get("DB_PATH", os.path.join(WEBAPP_DIR, "data", "grundstuecke.db"))

APP_PASSWORD = os.environ.get("APP_PASSWORD", "")
SECRET_KEY = os.environ.get("SECRET_KEY", "")

if not APP_PASSWORD:
    raise RuntimeError("APP_PASSWORD muss als Umgebungsvariable gesetzt sein.")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY muss als Umgebungsvariable gesetzt sein.")
