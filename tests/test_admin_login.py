from conftest import post
from sqlalchemy import select


def test_owner_can_use_requested_login_and_short_password(store, monkeypatch):
    from app.config import get_settings
    from app.models import User
    from app.security import hasher

    client, factory = store
    monkeypatch.setenv("ADMIN_LOGIN", "тест")
    monkeypatch.setenv("ADMIN_EMAIL", "owner@example.com")
    get_settings.cache_clear()
    try:
        with factory() as db:
            db.add(User(email="owner@example.com", role="admin", password_hash=hasher.hash("t7Q")))
            db.commit()
        result = post(client, "/login", {"email": "тест", "password": "t7Q"})
        assert result.status_code == 303
        assert result.headers["location"] == "/admin"
        assert client.get("/admin").status_code == 200
        assert post(client, "/login", {"email": "тест", "password": "wrong"}).status_code == 401
        with factory() as db:
            assert db.scalar(select(User)).password_hash != "t7Q"
    finally:
        get_settings.cache_clear()


def test_admin_creation_accepts_requested_password(store):
    from scripts.create_admin import create_admin

    _, factory = store
    create_admin("owner@example.com", "t7Q", factory)
