from __future__ import annotations

import hmac

from itsdangerous import BadSignature, URLSafeTimedSerializer
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse

from app.config import APP_PASSWORD, SECRET_KEY

SESSION_COOKIE = "gs_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 30  # 30 Tage

_serializer = URLSafeTimedSerializer(SECRET_KEY, salt="gs-auth")

PUBLIC_PATHS = {"/login"}


def check_password(password: str) -> bool:
    return hmac.compare_digest(password, APP_PASSWORD)


def make_session_cookie() -> str:
    return _serializer.dumps({"authed": True})


def session_is_valid(token: str | None) -> bool:
    if not token:
        return False
    try:
        data = _serializer.loads(token, max_age=SESSION_MAX_AGE)
    except BadSignature:
        return False
    return bool(data.get("authed"))


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path in PUBLIC_PATHS or path.startswith("/static"):
            return await call_next(request)

        token = request.cookies.get(SESSION_COOKIE)
        if not session_is_valid(token):
            return RedirectResponse(url="/login")

        return await call_next(request)
