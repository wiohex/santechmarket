from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.db.session import get_db
from app.models import CompanyProfile, User, WebSession, now
from app.schemas.forms import LoginForm, RegistrationForm
from app.security import DUMMY_HASH, checked_form, hasher, sign_in, verify_password
from app.web import redirect, render, validate

router = APIRouter()


@router.get("/register")
def register_page(request: Request):
    return render(request, "register.html")


@router.post("/register")
async def register(request: Request, db=Depends(get_db)):
    data = validate(RegistrationForm, await checked_form(request))
    request.app.state.limiter.check(("register", request.client.host), limit=5)
    if db.scalar(select(User.id).where(User.email == data.email)):
        raise HTTPException(409, "Этот email уже зарегистрирован. Войдите в кабинет.")
    user = User(email=data.email, password_hash=hasher.hash(data.password), role="company")
    user.company = CompanyProfile(
        name=data.name, inn=data.inn, contact=data.contact, phone=data.phone
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Этот email уже зарегистрирован.") from None
    sign_in(request, user.id)
    return redirect("/account")


@router.get("/login")
def login_page(request: Request):
    return render(request, "login.html")


@router.post("/login")
async def login(request: Request, db=Depends(get_db)):
    data = validate(LoginForm, await checked_form(request))
    request.app.state.limiter.check(("auth", request.client.host))
    settings = get_settings()
    if settings.admin_login and data.email.casefold() == settings.admin_login.strip().casefold():
        user = db.scalar(
            select(User).where(User.email == settings.admin_email.lower(), User.role == "admin")
        )
    else:
        user = db.scalar(select(User).where(User.email == data.email))
    valid = verify_password(user.password_hash if user else DUMMY_HASH, data.password)
    if user is None or not user.active or not valid:
        raise HTTPException(401, "Неверный email, логин или пароль.")
    db.execute(delete(WebSession).where(WebSession.expires_at < now()))
    db.commit()
    sign_in(request, user.id)
    return redirect("/admin" if user.role == "admin" else "/account")


@router.post("/logout")
async def logout(request: Request):
    await checked_form(request)
    request.state.session_record.user_id = None
    request.session.clear()
    import secrets

    request.session["csrf"] = secrets.token_urlsafe(32)
    request.state.rotate_session = True
    return redirect("/")
