from io import BytesIO

from conftest import csrf, post
from sqlalchemy import select


def login_admin(client, factory):
    from app.models import User
    from app.security import hasher

    with factory() as db:
        db.add(
            User(
                email="owner@example.com",
                password_hash=hasher.hash("correct-password"),
                role="admin",
            )
        )
        db.commit()
    return post(client, "/login", {"email": "owner@example.com", "password": "correct-password"})


def test_admin_auth_crud_status_and_photo(store):
    from app.models import OrderRequest, Product

    client, factory = store
    assert client.get("/admin").status_code == 401
    assert login_admin(client, factory).status_code == 303
    assert client.get("/admin").status_code == 200
    assert post(client, "/admin/categories", {"name": "Трубы", "slug": "pipes"}).status_code == 303
    assert (
        post(
            client,
            "/admin/products/save",
            {
                "name": "Труба PPR",
                "sku": "PIPE-01",
                "price": "123.45",
                "category_id": 2,
                "in_stock": "true",
                "active": "true",
            },
        ).status_code
        == 303
    )
    with factory() as db:
        product = db.scalar(select(Product).where(Product.sku == "PIPE-01"))
        assert product.price == 12345
        product_id = product.id
    token = csrf(client)
    bad = client.post(
        "/admin/products/save",
        data={
            "csrf_token": token,
            "id": product_id,
            "name": "Труба PPR",
            "sku": "PIPE-01",
            "price": "123.45",
            "category_id": 2,
        },
        files={"photo": ("evil.png", b"<script>bad</script>", "image/png")},
    )
    assert bad.status_code == 422
    from PIL import Image

    photo = BytesIO()
    Image.new("RGB", (20, 20), "green").save(photo, "PNG")
    good = client.post(
        "/admin/products/save",
        data={
            "csrf_token": token,
            "id": product_id,
            "name": "Труба PPR",
            "sku": "PIPE-01",
            "price": "123.45",
            "category_id": 2,
            "active": "true",
        },
        files={"photo": ("ok.png", photo.getvalue(), "image/png")},
        follow_redirects=False,
    )
    assert good.status_code == 303
    with factory() as db:
        assert db.get(Product, product_id).photo.startswith("/uploads/")
        order = OrderRequest(
            name="Иван",
            phone="79991234567",
            submission_key="test",
            receipt_token="test",
        )
        db.add(order)
        db.commit()
        order_id = order.id
    assert (
        post(
            client,
            f"/admin/requests/{order_id}",
            {"status": "completed", "owner_comment": "Можно забирать"},
        ).status_code
        == 303
    )
    with factory() as db:
        assert db.get(OrderRequest, order_id).status == "completed"
    assert post(client, f"/admin/products/{product_id}/delete").status_code == 303
    assert client.get(f"/products/{product_id}").status_code == 404
    assert post(client, "/admin/categories/1/delete").status_code == 409


def test_import_preview_atomic_commit_and_bad_rows(store):
    from app.models import Product

    client, factory = store
    login_admin(client, factory)
    csv = "sku;name;category;price;in_stock\nM-01;Новый смеситель;Смесители;2500,50;да\nP-01;Труба;Трубы;120;1\n".encode(
        "utf-8-sig"
    )
    response = client.post(
        "/admin/import/preview",
        data={"csrf_token": csrf(client)},
        files={"file": ("price.csv", csv, "text/csv")},
    )
    assert response.status_code == 200
    with factory() as db:
        assert db.get(Product, 1).price == 150000
        assert db.scalar(select(Product).where(Product.sku == "P-01")) is None
    assert post(client, "/admin/import/confirm").status_code == 303
    with factory() as db:
        assert db.get(Product, 1).price == 250050
        assert db.scalar(select(Product).where(Product.sku == "P-01")).price == 12000
    broken = b"sku,name,category,price\nX,Valid,pipes,10\nY,Invalid,pipes,-1\n"
    assert (
        client.post(
            "/admin/import/preview",
            data={"csrf_token": csrf(client)},
            files={"file": ("bad.csv", broken, "text/csv")},
        ).status_code
        == 422
    )
    with factory() as db:
        assert db.scalar(select(Product).where(Product.sku == "X")) is None


def test_xlsx_import_rejects_formulas(store):
    from openpyxl import Workbook

    client, factory = store
    login_admin(client, factory)
    book = Workbook()
    book.active.append(["sku", "name", "category", "price"])
    book.active.append(["XLS-1", "Переходник", "Фитинги", 120.50])
    buffer = BytesIO()
    book.save(buffer)
    response = client.post(
        "/admin/import/preview",
        data={"csrf_token": csrf(client)},
        files={
            "file": (
                "price.xlsx",
                buffer.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert response.status_code == 200
    book.active["D2"] = "=1+1"
    buffer = BytesIO()
    book.save(buffer)
    assert (
        client.post(
            "/admin/import/preview",
            data={"csrf_token": csrf(client)},
            files={
                "file": (
                    "price.xlsx",
                    buffer.getvalue(),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        ).status_code
        == 422
    )
