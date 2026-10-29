import os
import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("SECRET_KEY", "test-only-secret-0123456789-abcdefghijk")


@pytest.fixture(autouse=True)
def no_external_notifications(monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "telegram_bot_token", "")
    monkeypatch.setattr(get_settings(), "telegram_chat_id", "")


@pytest.fixture
def store(tmp_path):
    from app.db.base import Base
    from app.db.session import make_engine
    from app.main import create_app
    from app.models import Category, Product

    engine = make_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        db.add(Category(id=1, name="Смесители", slug="mixers"))
        db.flush()
        db.add(
            Product(
                id=1,
                category_id=1,
                name="Смеситель тестовый",
                sku="M-01",
                price=150000,
                description="Латунь",
            )
        )
        db.add(
            Product(
                id=2,
                category_id=1,
                name="Архивный",
                sku="OLD",
                price=10000,
                active=False,
            )
        )
        db.commit()
    app = create_app(factory)
    app.state.upload_dir = tmp_path / "uploads"
    app.state.upload_dir.mkdir()
    with TestClient(app) as client:
        yield client, factory
    engine.dispose()


def csrf(client, path="/"):
    page = client.get(path)
    assert page.status_code == 200
    return re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)


def post(client, path, data=None, page="/"):
    return client.post(
        path,
        data={"csrf_token": csrf(client, page), **(data or {})},
        follow_redirects=False,
    )
