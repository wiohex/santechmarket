from app.config import get_settings


def test_configured_phone_has_dialable_link(store, monkeypatch):
    client, _ = store
    monkeypatch.setattr(get_settings(), "store_phone", "+7 (495) 123-45-67")
    response = client.get("/")
    assert response.status_code == 200
    assert 'href="tel:+74951234567"' in response.text
    assert "+7 (495) 123-45-67" in response.text
    assert "Позвонить" in response.text


def test_demo_phone_does_not_dial_an_invented_number(store, monkeypatch):
    client, _ = store
    monkeypatch.setattr(get_settings(), "store_phone", "")
    response = client.get("/")
    assert "Демо-номер" in response.text
    assert 'aria-disabled="true"' in response.text
    assert 'href="tel:' not in response.text
