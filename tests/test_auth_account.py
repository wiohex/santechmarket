import re

from conftest import post
from fastapi.testclient import TestClient
from sqlalchemy import select

COMPANY = {
    "name": "ООО Монтаж",
    "inn": "7707083893",
    "contact": "Иван",
    "phone": "+79991234567",
    "email": "company@example.com",
    "password": "long-password-123",
}


def register(client, **changes):
    return post(client, "/register", {**COMPANY, **changes})


def test_register_login_logout_profile_and_role(store):
    from app.models import User

    client, factory = store
    post(client, "/request/add", {"product_id": 1, "quantity": 2})
    old_cookie = client.cookies.get("store_session")
    assert register(client).status_code == 303
    assert client.cookies.get("store_session") != old_cookie
    assert "Смеситель тестовый" in client.get("/request").text
    assert client.get("/account").status_code == 200
    assert client.get("/admin").status_code == 403
    assert post(client, "/admin/categories", {"name": "Обход", "slug": "bypass"}).status_code == 403
    with factory() as db:
        user = db.scalar(select(User))
        assert user.password_hash.startswith("$argon2id$")
        assert user.password_hash != COMPANY["password"]
    assert post(client, "/account/profile", {**COMPANY, "contact": "Пётр"}).status_code == 303
    assert "Пётр" in client.get("/account").text
    assert post(client, "/logout").status_code == 303
    assert (
        post(client, "/login", {"email": COMPANY["email"], "password": "incorrect"}).status_code
        == 401
    )
    assert (
        post(
            client,
            "/login",
            {"email": COMPANY["email"], "password": COMPANY["password"]},
        ).status_code
        == 303
    )
    assert register(client).status_code == 409


def test_registration_bad_inn_and_weak_password(store):
    client, factory = store
    assert register(client, inn="7707083894").status_code == 422
    assert register(client, password="123").status_code == 422


def test_company_history_repeat_and_ownership(store):
    from app.models import Product

    client, factory = store
    register(client)
    post(client, "/request/add", {"product_id": 1, "quantity": 4})
    key = re.search(r'name="submission_key" value="([^"]+)"', client.get("/request").text).group(1)
    assert (
        post(
            client,
            "/request/submit",
            {"submission_key": key, "name": "Иван", "phone": "79991234567"},
        ).status_code
        == 303
    )
    assert "З-000001" in client.get("/account").text
    assert client.get("/account/requests/1").status_code == 200
    with factory() as db:
        db.get(Product, 1).price = 199000
        db.commit()
    assert post(client, "/account/requests/1/repeat").status_code == 303
    page = client.get("/request")
    assert "7 960,00" in page.text
    with TestClient(client.app) as other:
        assert register(other, email="other@example.com").status_code == 303
        assert other.get("/account/requests/1").status_code == 404
        assert post(other, "/account/requests/1/repeat").status_code == 404
    with factory() as db:
        db.get(Product, 1).active = False
        db.commit()
    assert post(client, "/account/requests/1/repeat").status_code == 303
    assert "пропущено" in client.get("/request").text
