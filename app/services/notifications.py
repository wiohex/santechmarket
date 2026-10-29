"""Best-effort Telegram delivery after a successful database commit."""

import json
import logging
from urllib.error import URLError
from urllib.request import Request, urlopen

from app.config import get_settings
from app.web import money

logger = logging.getLogger(__name__)


def notification_text(order):
    lines = [
        f"Новая заявка {order.number}",
        f"Клиент: {order.name}",
        f"Телефон: {order.phone}",
    ]
    if order.user and order.user.company:
        lines.append(f"Компания: {order.user.company.name}, ИНН {order.user.company.inn}")
    lines += [f"{item.sku} · {item.name} × {item.quantity}" for item in order.items]
    if order.quick_text:
        lines.append(order.quick_text)
    if order.comment:
        lines.append("Комментарий: " + order.comment)
    lines.append("Товары, предварительно (без доставки): " + money(order.total))
    lines.append("Стоимость и условия доставки согласовать с клиентом по телефону.")
    lines.append("Все детали — в админке магазина.")
    return "\n".join(lines)[:3900]


def send_notification(text: str) -> bool:
    settings = get_settings()
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        return False
    payload = json.dumps(
        {"chat_id": settings.telegram_chat_id, "text": text}, ensure_ascii=False
    ).encode("utf-8")
    request = Request(
        f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=5) as response:
            if not json.loads(response.read(65536)).get("ok"):
                logger.warning("Telegram отклонил уведомление; заявка сохранена в админке.")
                return False
        return True
    except (URLError, OSError, ValueError, TimeoutError):
        # Never log exception/URL: Telegram credentials are part of its URL.
        logger.warning("Не удалось отправить уведомление Telegram; заявка сохранена в админке.")
        return False
