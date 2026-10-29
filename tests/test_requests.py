import re

from conftest import csrf, post
from sqlalchemy import func, select


def test_request_snapshot_and_double_submit(store):
    from app.models import OrderRequest, Product

    client, factory = store
    assert post(client, "/request/add", {"product_id": 1, "quantity": 3}).status_code == 303
    page = client.get("/request")
    key = re.search(r'name="submission_key" value="([^"]+)"', page.text).group(1)
    data = {
        "csrf_token": csrf(client),
        "submission_key": key,
        "name": "Иван",
        "phone": "+7 (999) 123-45-67",
        "comment": "<script>alert(1)</script>",
        "price": 1,
    }
    response = client.post("/request/submit", data=data, follow_redirects=False)
    assert response.status_code == 303
    receipt = response.headers["location"]
    assert "З-000001" in client.get(receipt).text
    assert (
        client.post("/request/submit", data=data, follow_redirects=False).headers["location"]
        == receipt
    )
    with factory() as db:
        order = db.scalar(select(OrderRequest))
        assert db.scalar(select(func.count(OrderRequest.id))) == 1
        assert order.items[0].quantity == 3
        assert order.items[0].price == 150000
        db.get(Product, 1).price = 200000
        db.commit()
    assert "4 500,00" in client.get(receipt).text
    assert "<script>alert(1)</script>" not in client.get(receipt).text
    assert client.get("/request/receipt/1/bad-token").status_code == 404


def test_request_validation_csrf_and_empty_cart(store):
    client, _ = store
    assert client.post("/request/add", data={"product_id": 1, "quantity": 1}).status_code == 403
    assert post(client, "/request/add", {"product_id": 1, "quantity": -1}).status_code == 422
    assert post(client, "/request/add", {"product_id": 2, "quantity": 1}).status_code == 404
    page = client.get("/request")
    key = re.search(r'name="submission_key" value="([^"]+)"', page.text).group(1)
    assert (
        post(
            client,
            "/request/submit",
            {"submission_key": key, "name": "Иван", "phone": "123"},
        ).status_code
        == 422
    )
    assert (
        post(
            client,
            "/request/submit",
            {"submission_key": key, "name": "Иван", "phone": "79991234567"},
        ).status_code
        == 422
    )


def test_quick_request_without_products(store):
    from app.models import OrderRequest

    client, factory = store
    page = client.get("/quick-request")
    key = re.search(r'name="submission_key" value="([^"]+)"', page.text).group(1)
    response = post(
        client,
        "/request/quick",
        {
            "submission_key": key,
            "name": "Пётр",
            "phone": "89991234567",
            "quick_text": "Нужен переходник на трубу 32 мм",
        },
    )
    assert response.status_code == 303
    with factory() as db:
        order = db.scalar(select(OrderRequest))
        assert not order.items
        assert order.quick_text == "Нужен переходник на трубу 32 мм"


def test_catalog_empty_filter_fields(store):
    client, _ = store
    assert client.get("/catalog?q=&category=&min_price=&max_price=").status_code == 200
