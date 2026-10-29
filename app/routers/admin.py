import zipfile
from xml.etree.ElementTree import ParseError

from defusedxml.common import DefusedXmlException
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.db.session import get_db
from app.models import Category, OrderRequest, Product
from app.schemas.forms import CategoryForm, ProductForm, StatusForm
from app.security import checked_form, require_admin
from app.services.imports import apply_import, parse_price_file
from app.services.uploads import save_photo
from app.web import STATUSES, redirect, render, validate

router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)])


def commit_unique(db):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            409, "Такой артикул, название категории или slug уже существует."
        ) from None


@router.get("")
def dashboard(request: Request, status: str = "", page: int = Query(1, ge=1), db=Depends(get_db)):
    query = select(OrderRequest)
    if status:
        if status not in STATUSES:
            raise HTTPException(422, "Неизвестный статус.")
        query = query.where(OrderRequest.status == status)
    count = db.scalar(select(func.count()).select_from(query.subquery()))
    orders = db.scalars(
        query.order_by(OrderRequest.id.desc()).offset((page - 1) * 30).limit(30)
    ).all()
    return render(
        request,
        "admin/requests.html",
        orders=orders,
        status=status,
        page=page,
        count=count,
    )


@router.get("/requests/{order_id}")
def order_detail(request: Request, order_id: int, db=Depends(get_db)):
    order = db.get(OrderRequest, order_id)
    if order is None:
        raise HTTPException(404, "Заявка не найдена.")
    return render(request, "admin/request_detail.html", order=order)


@router.post("/requests/{order_id}")
async def order_update(request: Request, order_id: int, db=Depends(get_db)):
    data = validate(StatusForm, await checked_form(request))
    order = db.get(OrderRequest, order_id)
    if order is None:
        raise HTTPException(404, "Заявка не найдена.")
    order.status, order.owner_comment = data.status, data.owner_comment
    db.commit()
    request.session["notice"] = "Заявка обновлена."
    return redirect(f"/admin/requests/{order_id}")


@router.get("/products")
def products_page(request: Request, page: int = Query(1, ge=1), db=Depends(get_db)):
    products = db.scalars(
        select(Product).order_by(Product.id.desc()).offset((page - 1) * 50).limit(50)
    ).all()
    count = db.scalar(select(func.count(Product.id)))
    return render(request, "admin/products.html", products=products, page=page, count=count)


@router.get("/products/edit")
def product_edit(request: Request, id: int | None = Query(None, gt=0), db=Depends(get_db)):
    product = db.get(Product, id) if id else None
    if id and product is None:
        raise HTTPException(404, "Товар не найден.")
    return render(
        request,
        "admin/product_form.html",
        product=product,
        categories=db.scalars(select(Category).order_by(Category.name)).all(),
    )


@router.post("/products/save")
async def product_save(request: Request, db=Depends(get_db)):
    form = await checked_form(request)
    data = validate(ProductForm, form)
    if db.get(Category, data.category_id) is None:
        raise HTTPException(422, "Выберите существующую категорию.")
    try:
        product_id = int(form.get("id", "") or 0)
    except ValueError:
        raise HTTPException(422, "Некорректный ID товара.") from None
    product = db.get(Product, product_id) if product_id else Product()
    if product is None:
        raise HTTPException(404, "Товар не найден.")
    if db.scalar(select(Product).where(Product.sku == data.sku, Product.id != product_id)):
        raise HTTPException(409, "Товар с таким артикулом уже существует.")
    photo = await save_photo(form.get("photo"), request.app.state.upload_dir)
    for key in ("name", "sku", "category_id", "description", "in_stock", "active"):
        setattr(product, key, getattr(data, key))
    product.price = int(data.price * 100)
    if photo:
        product.photo = photo
    elif form.get("remove_photo") == "true":
        product.photo = ""
    db.add(product)
    commit_unique(db)
    request.session["notice"] = "Товар сохранён."
    return redirect("/admin/products")


@router.post("/products/{product_id}/delete")
async def product_delete(request: Request, product_id: int, db=Depends(get_db)):
    await checked_form(request)
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(404, "Товар не найден.")
    product.active = False
    db.commit()
    request.session["notice"] = "Товар скрыт из каталога. Его можно восстановить в редакторе."
    return redirect("/admin/products")


@router.get("/categories")
def categories_page(request: Request, db=Depends(get_db)):
    return render(
        request,
        "admin/categories.html",
        categories=db.scalars(select(Category).order_by(Category.id)).all(),
    )


@router.post("/categories")
async def category_create(request: Request, db=Depends(get_db)):
    data = validate(CategoryForm, await checked_form(request))
    db.add(Category(**data.model_dump()))
    commit_unique(db)
    return redirect("/admin/categories")


@router.post("/categories/{category_id}/edit")
async def category_edit(request: Request, category_id: int, db=Depends(get_db)):
    data = validate(CategoryForm, await checked_form(request))
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(404, "Категория не найдена.")
    category.name, category.slug = data.name, data.slug
    commit_unique(db)
    return redirect("/admin/categories")


@router.post("/categories/{category_id}/delete")
async def category_delete(request: Request, category_id: int, db=Depends(get_db)):
    await checked_form(request)
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(404, "Категория не найдена.")
    if db.scalar(select(Product.id).where(Product.category_id == category_id).limit(1)):
        raise HTTPException(
            409, "Сначала перенесите товары этой категории в другую, включая архивные."
        )
    db.delete(category)
    commit_unique(db)
    return redirect("/admin/categories")


@router.get("/import")
def import_page(request: Request):
    return render(request, "admin/import.html", rows=None)


@router.post("/import/preview")
async def import_preview(request: Request):
    form = await checked_form(request)
    request.session.pop("import_rows", None)
    upload = form.get("file")
    if not upload or not getattr(upload, "filename", ""):
        raise HTTPException(422, "Выберите CSV или XLSX.")
    content = await upload.read(2 * 1024 * 1024 + 1)
    try:
        rows = parse_price_file(upload.filename, content)
    except (
        ValueError,
        IndexError,
        UnicodeError,
        zipfile.BadZipFile,
        KeyError,
        OSError,
        ParseError,
        DefusedXmlException,
    ):
        # Return known validation messages; malformed container internals stay private.
        import sys

        error = sys.exception()
        message = (
            str(error)
            if isinstance(error, ValueError)
            else "Файл повреждён или не соответствует формату."
        )
        raise HTTPException(422, message) from None
    request.session["import_rows"] = rows
    return render(request, "admin/import.html", rows=rows)


@router.post("/import/confirm")
async def import_confirm(request: Request, db=Depends(get_db)):
    await checked_form(request)
    rows = request.session.get("import_rows")
    if not rows:
        raise HTTPException(422, "Сначала загрузите файл для проверки.")
    try:
        apply_import(db, rows)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Каталог изменился. Повторно загрузите прайс.") from None
    request.session.pop("import_rows", None)
    request.session["notice"] = f"Импортировано товаров: {len(rows)}."
    return redirect("/admin/products")
