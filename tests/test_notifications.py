import json
import re
from urllib.error import URLError

from conftest import post
from sqlalchemy import select


def test_telegram_payload_and_failure_keeps_request(store, monkeypatch, caplog):
    from app.config import get_settings
    from app.models import OrderRequest
    from app.services import notifications

    settings = get_settings()
    monkeypatch.setattr(settings, "telegram_bot_token", "secret-test-token")
    monkeypatch.setattr(settings, "telegram_chat_id", "1234")
    payloads = []

    def offline(request, timeout):
        payloads.append(json.loads(request.data))
        raise URLError("secret-test-token")

    monkeypatch.setattr(notifications, "urlopen", offline)
    client, factory = store
    key = re.search(
        r'name="submission_key" value="([^"]+)"', client.get("/quick-request").text
    ).group(1)
    result = post(
        client,
        "/request/quick",
        {
            "submission_key": key,
            "name": "Иван",
            "phone": "79991234567",
            "quick_text": "Нужны трубы",
        },
    )
    assert result.status_code == 303
    with factory() as db:
        assert db.scalar(select(OrderRequest)).quick_text == "Нужны трубы"
    assert payloads[0]["chat_id"] == "1234"
    assert "З-000001" in payloads[0]["text"]
    assert "Нужны трубы" in payloads[0]["text"]
    assert "secret-test-token" not in caplog.text
    assert len(payloads) == 1


def test_telegram_success_and_unconfigured(monkeypatch):
    from io import BytesIO

    from app.config import get_settings
    from app.services import notifications

    monkeypatch.setattr(get_settings(), "telegram_bot_token", "")
    assert notifications.send_notification("test") is False
    monkeypatch.setattr(get_settings(), "telegram_bot_token", "test-token")
    monkeypatch.setattr(get_settings(), "telegram_chat_id", "1234")
    monkeypatch.setattr(notifications, "urlopen", lambda request, timeout: BytesIO(b'{"ok": true}'))
    assert notifications.send_notification("test") is True
