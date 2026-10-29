from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select

from app.db.session import get_db
from app.models import Category, Product
from app.schemas.forms import CatalogFilters
from app.web import render, validate

router = APIRouter()


@router.get("/")
def home(request: Request, db=Depends(get_db)):
    return render(
        request,
        "home.html",
        categories=db.scalars(select(Category).order_by(Category.id)).all(),
        products=db.scalars(select(Product).where(Product.active).limit(4)).all(),
    )


@router.get("/catalog")
def catalog(
    request: Request,
    q: str = Query("", max_length=100),
    category: str = "",
    min_price: str = "",
    max_price: str = "",
    stock: bool = False,
    page: int = Query(1, ge=1, le=10000),
    db=Depends(get_db),
):
    filters = validate(
        CatalogFilters,
        {"category": category, "min_price": min_price, "max_price": max_price},
    )
    category, min_price, max_price = (
        filters.category,
        filters.min_price,
        filters.max_price,
    )
    statement = select(Product).where(Product.active)
    if q:
        # Python casefold handles Cyrillic consistently on SQLite/PostgreSQL.
        matches = [
            p.id
            for p in db.scalars(select(Product).where(Product.active))
            if q.casefold() in (p.name + " " + p.sku).casefold()
        ]
        statement = statement.where(Product.id.in_(matches))
    if category:
        statement = statement.where(Product.category_id == category)
    if min_price is not None:
        statement = statement.where(Product.price >= int(min_price * 100))
    if max_price is not None:
        statement = statement.where(Product.price <= int(max_price * 100))
    if stock:
        statement = statement.where(Product.in_stock)
    count = db.scalar(select(func.count()).select_from(statement.subquery()))
    products = db.scalars(statement.order_by(Product.id).offset((page - 1) * 12).limit(12)).all()
    return render(
        request,
        "catalog.html",
        products=products,
        categories=db.scalars(select(Category).order_by(Category.name)).all(),
        q=q,
        category=category,
        min_price=min_price,
        max_price=max_price,
        stock=stock,
        page=page,
        count=count,
        pages=(count + 11) // 12,
    )


@router.get("/products/{product_id}")
def product_detail(request: Request, product_id: int, db=Depends(get_db)):
    product = db.get(Product, product_id)
    if product is None or not product.active:
        raise HTTPException(404, "Товар не найден.")
    return render(request, "product.html", product=product)
