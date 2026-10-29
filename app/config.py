from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )
    secret_key: str = Field(min_length=32)
    database_url: str = "sqlite:///./store.db"
    admin_email: str = "owner@example.com"
    admin_login: str = Field("", max_length=64)
    admin_password: str = ""
    cookie_secure: bool = False
    allowed_hosts: str = "localhost,127.0.0.1,testserver"
    store_name: str = "СантехМаркет"
    store_phone: str = ""
    store_address: str = ""
    store_hours: str = "Пн–Сб 09:00–19:00"
    store_map_url: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    @field_validator("store_map_url")
    @classmethod
    def safe_map_url(cls, value):
        if value and not value.startswith("https://"):
            raise ValueError("STORE_MAP_URL должен начинаться с https://")
        return value


@lru_cache
def get_settings():
    return Settings()
