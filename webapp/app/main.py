import threading
from datetime import datetime

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import (
    AuthMiddleware,
    SESSION_COOKIE,
    check_password,
    make_session_cookie,
)
from app.config import WEBAPP_DIR
from app.db import SessionLocal, get_db, init_db
from app.models import Property, UpdateRun
from app.scraper_bridge import run_update

app = FastAPI(title="Grundstücks-Übersicht")
app.add_middleware(AuthMiddleware)
templates = Jinja2Templates(directory=f"{WEBAPP_DIR}/app/templates")

init_db()

_update_lock = threading.Lock()


@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/login")
def login(request: Request, password: str = Form(...)):
    if not check_password(password):
        return templates.TemplateResponse(
            "login.html", {"request": request, "error": "Falsches Passwort"}
        )
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        SESSION_COOKIE, make_session_cookie(), httponly=True, samesite="lax", max_age=2592000
    )
    return response


@app.get("/logout")
def logout():
    response = RedirectResponse(url="/login")
    response.delete_cookie(SESSION_COOKIE)
    return response


@app.get("/", response_class=HTMLResponse)
def index(
    request: Request,
    plz: str = "",
    ort: str = "",
    status: str = "",
    show_expired: str = "",
    db: Session = Depends(get_db),
):
    query = db.query(Property)
    if plz:
        query = query.filter(Property.plz.contains(plz))
    if ort:
        query = query.filter(Property.ort.contains(ort))
    if status:
        query = query.filter(Property.status == status)
    if not show_expired:
        query = query.filter(Property.is_expired.is_(False))

    properties = query.order_by(Property.created_at.desc()).all()
    statuses = sorted({p.status for p in db.query(Property.status).all() if p.status})
    last_run = db.query(UpdateRun).order_by(UpdateRun.id.desc()).first()

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "properties": properties,
            "statuses": statuses,
            "filters": {"plz": plz, "ort": ort, "status": status, "show_expired": show_expired},
            "last_run": last_run,
        },
    )


def _background_update(run_id: int):
    db = SessionLocal()
    run = db.get(UpdateRun, run_id)
    log_lines = []

    def log(msg: str):
        log_lines.append(msg)
        run.log_text = "\n".join(log_lines)
        db.commit()

    try:
        run_update(db, log)
        run.status = "success"
    except Exception as e:
        log(f"❌ Fehler: {e}")
        run.status = "error"
    finally:
        run.finished_at = datetime.utcnow()
        db.commit()
        db.close()


@app.post("/update/start")
def start_update(db: Session = Depends(get_db)):
    if _update_lock.locked():
        return RedirectResponse(url="/update/status", status_code=303)

    run = UpdateRun(status="running", log_text="")
    db.add(run)
    db.commit()
    run_id = run.id

    def worker():
        with _update_lock:
            _background_update(run_id)

    threading.Thread(target=worker, daemon=True).start()
    return RedirectResponse(url="/update/status", status_code=303)


@app.get("/update/status", response_class=HTMLResponse)
def update_status(request: Request, db: Session = Depends(get_db)):
    run = db.query(UpdateRun).order_by(UpdateRun.id.desc()).first()
    return templates.TemplateResponse(
        "_update_status.html", {"request": request, "run": run, "is_locked": _update_lock.locked()}
    )


@app.post("/property/{property_id}/status")
def set_status(property_id: int, status: str = Form(...), db: Session = Depends(get_db)):
    prop = db.get(Property, property_id)
    if prop:
        prop.status = status
        db.commit()
    return RedirectResponse(url="/", status_code=303)


@app.post("/property/{property_id}/haustyp")
def set_haustyp(property_id: int, haustyp: str = Form(...), db: Session = Depends(get_db)):
    prop = db.get(Property, property_id)
    if prop:
        prop.haustyp = haustyp
        db.commit()
    return RedirectResponse(url="/", status_code=303)
