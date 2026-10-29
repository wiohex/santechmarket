from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.staticfiles import StaticFiles

from app.config import ROOT, get_settings
from app.db.session import SessionLocal
from app.routers import account, admin, auth, public, requests
from app.security import RateLimiter, StoreSessionMiddleware
from app.web import render


def create_app(session_factory=None):
    app = FastAPI(title="Магазин сантехники", docs_url=None, redoc_url=None)
    app.state.session_factory = session_factory or SessionLocal
    app.state.upload_dir = ROOT / "uploads"
    app.state.upload_dir.mkdir(exist_ok=True)
    app.state.limiter = RateLimiter()
    app.add_middleware(StoreSessionMiddleware)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=get_settings().allowed_hosts.split(","))
    app.mount("/static", StaticFiles(directory=ROOT / "app/static"), name="static")
    app.mount("/uploads", StaticFiles(directory=ROOT / "uploads"), name="uploads")
    app.include_router(public.router)
    app.include_router(requests.router)
    app.include_router(auth.router)
    app.include_router(admin.router)
    app.include_router(account.router)

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc):
        return render(request, "error.html", status_code=exc.status_code, message=exc.detail)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc):
        return render(
            request,
            "error.html",
            status_code=422,
            message="Некорректные параметры. Проверьте числа и обязательные поля.",
        )

    return app


app = create_app()
