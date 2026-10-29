from fastapi import HTTPException
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy import select
from starlette.responses import RedirectResponse

from app.config import ROOT, get_settings
from app.models import Category

templates = Jinja2Templates(directory=ROOT / "app/templates")
STATUSES = {
    "new": "Новая",
    "working": "В работе",
    "completed": "Выполнена",
    "cancelled": "Отменена",
}


def money(value):
    return f"{value / 100:,.2f}".replace(",", " ").replace(".", ",") + " ₽"


templates.env.filters["money"] = money


def render(request, template, status_code=200, **context):
    with request.app.state.session_factory() as db:
        navigation_categories = db.scalars(select(Category).order_by(Category.id).limit(12)).all()
    return templates.TemplateResponse(
        request=request,
        name=template,
        context={
            "settings": get_settings(),
            "navigation_categories": navigation_categories,
            "user": getattr(request.state, "user", None),
            "csrf_token": request.session.get("csrf", ""),
            "statuses": STATUSES,
            "cart_count": sum(request.session.get("cart", {}).values()),
            "notice": request.session.pop("notice", ""),
            **context,
        },
        status_code=status_code,
    )


def redirect(path):
    return RedirectResponse(path, status_code=303)


def validate(schema, data):
    try:
        return schema.model_validate(dict(data))
    except ValidationError as error:
        messages = [f"{e['loc'][0]}: {e['msg']}" for e in error.errors()]
        raise HTTPException(422, "Проверьте форму: " + "; ".join(messages)) from None
