import secrets

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import OrderRequest, Product, RequestItem


def get_cart(request, db):
    cart = request.session.get("cart", {})
    products = (
        db.scalars(
            select(Product).where(Product.id.in_([int(i) for i in cart]), Product.active)
        ).all()
        if cart
        else []
    )
    available = {str(product.id): product for product in products}
    clean = {key: quantity for key, quantity in cart.items() if key in available}
    if clean != cart:
        request.session["notice"] = "Недоступные товары убраны из заявки. Проверьте список."
        request.session["cart"] = clean
    return [(available[key], quantity) for key, quantity in clean.items()]


def form_key(request):
    key = request.session.setdefault("form_key", secrets.token_urlsafe(32))
    keys = request.session.get("submission_keys", [])
    if key not in keys:
        request.session["submission_keys"] = (keys + [key])[-10:]
    return key


def create_request(request, db, data, quick=False):
    if data.submission_key not in request.session.get("submission_keys", []):
        raise HTTPException(403, "Обновите страницу заявки и попробуйте снова.")
    existing = db.scalar(
        select(OrderRequest).where(OrderRequest.submission_key == data.submission_key)
    )
    if existing:
        return existing, False
    items = [] if quick else get_cart(request, db)
    if quick and len(data.quick_text) < 3:
        raise HTTPException(422, "Опишите, что вам нужно: минимум 3 символа.")
    if not quick and not items:
        raise HTTPException(422, "Добавьте товары или воспользуйтесь текстовой заявкой.")
    request.app.state.limiter.check(("request", request.client.host), limit=10)
    order = OrderRequest(
        user_id=request.state.user.id if request.state.user else None,
        submission_key=data.submission_key,
        receipt_token=secrets.token_urlsafe(32),
        name=data.name,
        phone=data.phone,
        comment=data.comment,
        quick_text=data.quick_text if quick else "",
    )
    order.items = [
        RequestItem(product_id=p.id, name=p.name, sku=p.sku, price=p.price, quantity=q)
        for p, q in items
    ]
    db.add(order)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(OrderRequest).where(OrderRequest.submission_key == data.submission_key)
        )
        if existing:
            return existing, False
        raise
    if not quick:
        request.session["cart"] = {}
    request.session.pop("form_key", None)
    return order, True
