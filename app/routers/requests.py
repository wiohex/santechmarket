from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request

from app.db.session import get_db
from app.models import OrderRequest, Product
from app.schemas.forms import CartItemForm, RequestForm
from app.security import checked_form
from app.services.notifications import notification_text, send_notification
from app.services.requests import create_request, form_key, get_cart
from app.web import redirect, render, validate

router = APIRouter()


@router.get("/request")
def cart(request: Request, db=Depends(get_db)):
    items = get_cart(request, db)
    return render(
        request,
        "request.html",
        items=items,
        total=sum(p.price * q for p, q in items),
        submission_key=form_key(request),
    )


@router.post("/request/add")
async def add(request: Request, db=Depends(get_db)):
    data = validate(CartItemForm, await checked_form(request))
    product = db.get(Product, data.product_id)
    if product is None or not product.active:
        raise HTTPException(404, "Товар больше недоступен.")
    cart = dict(request.session.get("cart", {}))
    key = str(product.id)
    if len(cart) >= 100 and key not in cart:
        raise HTTPException(422, "В одной заявке можно указать до 100 разных товаров.")
    if cart.get(key, 0) + data.quantity > 9999:
        raise HTTPException(422, "Максимум 9999 единиц одной позиции.")
    cart[key] = cart.get(key, 0) + data.quantity
    request.session["cart"] = cart
    request.session["notice"] = "Товар добавлен. Вы можете продолжить подбор или отправить заявку."
    return redirect("/request")


@router.post("/request/update")
async def update(request: Request):
    form = await checked_form(request)
    data = validate(CartItemForm, form)
    cart = dict(request.session.get("cart", {}))
    key = str(data.product_id)
    if key in cart:
        if form.get("action") == "remove":
            del cart[key]
        else:
            cart[key] = data.quantity
    request.session["cart"] = cart
    return redirect("/request")


@router.get("/quick-request")
def quick_page(request: Request):
    return render(
        request,
        "quick_request.html",
        submission_key=form_key(request),
        quick_text=request.session.pop("repeat_text", ""),
    )


@router.post("/request/submit")
async def submit(request: Request, background_tasks: BackgroundTasks, db=Depends(get_db)):
    data = validate(RequestForm, await checked_form(request))
    order, created = create_request(request, db, data)
    if created:
        background_tasks.add_task(send_notification, notification_text(order))
    return redirect(f"/request/receipt/{order.id}/{order.receipt_token}")


@router.post("/request/quick")
async def quick_submit(request: Request, background_tasks: BackgroundTasks, db=Depends(get_db)):
    data = validate(RequestForm, await checked_form(request))
    order, created = create_request(request, db, data, quick=True)
    if created:
        background_tasks.add_task(send_notification, notification_text(order))
    return redirect(f"/request/receipt/{order.id}/{order.receipt_token}")


@router.get("/request/receipt/{order_id}/{token}")
def receipt(request: Request, order_id: int, token: str, db=Depends(get_db)):
    import secrets

    order = db.get(OrderRequest, order_id)
    if order is None or not secrets.compare_digest(order.receipt_token, token):
        raise HTTPException(404, "Заявка не найдена.")
    return render(request, "receipt.html", order=order)
