import hashlib
import secrets
from collections import defaultdict, deque
from datetime import timedelta
from time import monotonic

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import HTTPException, Request
from sqlalchemy.orm.attributes import flag_modified
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import PlainTextResponse

from app.config import get_settings
from app.models import User, WebSession, now

hasher = PasswordHasher()
DUMMY_HASH = hasher.hash(secrets.token_urlsafe(24))


def verify_password(encoded, password):
    try:
        return hasher.verify(encoded, password)
    except (VerificationError, InvalidHashError):
        return False


def digest(token):
    # HMAC protects session token hashes with the environment secret.
    import hmac

    return hmac.new(get_settings().secret_key.encode(), token.encode(), hashlib.sha256).hexdigest()


class StoreSessionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.url.path.startswith(("/static/", "/uploads/")):
            return await call_next(request)
        if request.method == "POST":
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > 6 * 1024 * 1024:
                    return PlainTextResponse(
                        "Файл или форма слишком большие. Максимум 6 МБ.",
                        status_code=413,
                    )
            request._body = bytes(body)
        with request.app.state.session_factory() as db:
            raw_token = request.cookies.get("store_session", "")
            session = db.get(WebSession, digest(raw_token)) if raw_token else None
            if session and session.expires_at < now():
                db.delete(session)
                db.commit()
                session = None
            if session is None:
                raw_token = secrets.token_urlsafe(32)
                session = WebSession(
                    token_hash=digest(raw_token),
                    data={"csrf": secrets.token_urlsafe(32)},
                    expires_at=now() + timedelta(days=7),
                )
                db.add(session)
                db.commit()
            request.scope["session"] = dict(session.data)
            request.state.session_record = session
            request.state.user = db.get(User, session.user_id) if session.user_id else None
            if request.state.user and not request.state.user.active:
                request.state.user = None
                session.user_id = None
            # End read transaction before route writes through its own DB session.
            if request.state.user and request.state.user.company:
                _ = request.state.user.company.name
            db.commit()
            response = await call_next(request)
            if getattr(request.state, "rotate_session", False):
                raw_token = secrets.token_urlsafe(32)
                session.token_hash = digest(raw_token)
            session.data = dict(request.session)
            flag_modified(session, "data")
            db.commit()
            response.set_cookie(
                "store_session",
                raw_token,
                httponly=True,
                secure=get_settings().cookie_secure,
                samesite="lax",
                max_age=7 * 86400,
                path="/",
            )
            response.headers["Cache-Control"] = "no-store"
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Referrer-Policy"] = "same-origin"
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; frame-src https://yandex.ru https://yandex.com; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
            )
            return response


async def checked_form(request: Request):
    form = await request.form(max_files=1, max_fields=100, max_part_size=1024 * 1024)
    token = form.get("csrf_token", "")
    if not isinstance(token, str) or not secrets.compare_digest(
        token, request.session.get("csrf", "missing")
    ):
        raise HTTPException(403, "Форма устарела. Обновите страницу и попробуйте ещё раз.")
    return form


def require_user(request: Request):
    user = request.state.user
    if user is None:
        raise HTTPException(401, "Войдите в кабинет для продолжения.")
    return user


def require_admin(request: Request):
    user = require_user(request)
    if user.role != "admin":
        raise HTTPException(403, "Этот раздел доступен только владельцу.")
    return user


def sign_in(request, user_id):
    request.state.session_record.user_id = user_id
    request.state.rotate_session = True
    request.session["csrf"] = secrets.token_urlsafe(32)


class RateLimiter:
    def __init__(self):
        self.attempts = defaultdict(deque)

    def check(self, key, limit=10, window=900):
        current = monotonic()
        # Also expire idle keys so arbitrary requests cannot grow this forever.
        for old in list(self.attempts):
            if not self.attempts[old] or self.attempts[old][-1] < current - window:
                del self.attempts[old]
        attempts = self.attempts[key]
        while attempts and attempts[0] < current - window:
            attempts.popleft()
        if len(attempts) >= limit:
            raise HTTPException(429, "Слишком много попыток. Попробуйте через 15 минут.")
        attempts.append(current)
