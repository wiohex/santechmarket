from datetime import timedelta

from conftest import csrf, post
from fastapi.testclient import TestClient
from test_admin import login_admin
from test_auth_account import COMPANY, register


def test_password_spaces_are_preserved(store):
    client, _ = store
    password = "  long-password-123  "
    assert register(client, password=password).status_code == 303
    post(client, "/logout")
    assert (
        post(
            client, "/login", {"email": COMPANY["email"], "password": password.strip()}
        ).status_code
        == 401
    )
    assert (
        post(client, "/login", {"email": COMPANY["email"], "password": password}).status_code == 303
    )


def test_session_rotation_expiry_and_csrf_on_logout(store):
    from app.models import WebSession, now
    from app.security import digest

    client, factory = store
    client.get("/")
    cookie = client.cookies.get("store_session")
    register(client)
    with TestClient(client.app) as attacker:
        attacker.cookies.set("store_session", cookie)
        assert attacker.get("/account/requests/1").status_code == 401
    assert client.post("/logout").status_code == 403
    with factory() as db:
        session = db.get(WebSession, digest(client.cookies.get("store_session")))
        session.expires_at = now() - timedelta(seconds=1)
        db.commit()
    assert client.get("/account", follow_redirects=False).headers["location"] == "/login"


def test_login_rate_limit(store):
    client, _ = store
    for _ in range(10):
        assert (
            post(client, "/login", {"email": "nobody@example.com", "password": "wrong"}).status_code
            == 401
        )
    assert (
        post(client, "/login", {"email": "nobody@example.com", "password": "wrong"}).status_code
        == 429
    )


def test_large_body_and_text_in_photo_field(store):
    client, factory = store
    assert client.post("/request/add", content=b"x" * (6 * 1024 * 1024 + 1)).status_code == 413
    login_admin(client, factory)
    data = {
        "csrf_token": csrf(client),
        "name": "Товар",
        "sku": "TEXT-PHOTO",
        "category_id": 1,
        "price": 100,
        "photo": "not-an-upload",
    }
    assert client.post("/admin/products/save", data=data).status_code == 422
