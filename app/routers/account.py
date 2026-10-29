from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select

from app.db.session import get_db
from app.models import OrderRequest, Product, User
from app.schemas.forms import CompanyForm
from app.security import checked_form, require_user
from app.web import redirect, render, validate

router = APIRouter(prefix="/account")


@router.get("")
def dashboard(request: Request, page: int = Query(1, ge=1), db=Depends(get_db)):
    if request.state.user is None:
        return redirect("/login")
    user = request.state.user
    if user.role == "admin":
        return redirect("/admin")
    orders = db.scalars(
        select(OrderRequest)
        .where(OrderRequest.user_id == user.id)
        .order_by(OrderRequest.id.desc())
        .offset((page - 1) * 20)
        .limit(20)
    ).all()
    count = db.scalar(select(func.count(OrderRequest.id)).where(OrderRequest.user_id == user.id))
    return render(request, "account/dashboard.html", orders=orders, page=page, count=count)


@router.post("/profile")
async def update_profile(request: Request, user=Depends(require_user), db=Depends(get_db)):
    data = validate(CompanyForm, await checked_form(request))
    company = db.get(User, user.id).company
    if company is None:
        raise HTTPException(403, "Профиль компании не найден.")
    for key, value in data.model_dump().items():
        setattr(company, key, value)
    db.commit()
    request.session["notice"] = "Профиль компании обновлён."
    return redirect("/account")


def owned_order(db, order_id, user_id):
    order = db.scalar(
        select(OrderRequest).where(OrderRequest.id == order_id, OrderRequest.user_id == user_id)
    )
    if order is None:
        raise HTTPException(404, "Заявка не найдена.")
    return order


@router.get("/requests/{order_id}")
def detail(request: Request, order_id: int, user=Depends(require_user), db=Depends(get_db)):
    return render(request, "account/request_detail.html", order=owned_order(db, order_id, user.id))


@router.post("/requests/{order_id}/repeat")
async def repeat(request: Request, order_id: int, user=Depends(require_user), db=Depends(get_db)):
    await checked_form(request)
    order = owned_order(db, order_id, user.id)
    if not order.items and order.quick_text:
        request.session["repeat_text"] = order.quick_text
        request.session["notice"] = (
            "Текст прошлой заявки скопирован. Проверьте его и отправьте новую заявку."
        )
        return redirect("/quick-request")
    cart = {}
    skipped = 0
    for item in order.items:
        product = db.get(Product, item.product_id) if item.product_id else None
        if product and product.active:
            key = str(product.id)
            cart[key] = min(9999, cart.get(key, 0) + item.quantity)
        else:
            skipped += 1
    request.session["cart"] = cart
    request.session.pop("form_key", None)
    request.session["notice"] = (
        f"Список заменён товарами из заявки {order.number}. Цены и наличие актуальны на сегодня; проверьте их перед отправкой. Недоступных позиций пропущено: {skipped}."
    )
    return redirect("/request")
