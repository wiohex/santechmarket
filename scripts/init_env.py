"""Create .env without printing a secret and without replacing existing settings."""

import secrets
from pathlib import Path

from app import __file__ as package_file

if __name__ == "__main__":
    root = Path(package_file).resolve().parent.parent
    target = root / ".env"
    if target.exists():
        print(".env уже существует, изменения не внесены.")
    else:
        content = (
            (root / ".env.example")
            .read_text(encoding="utf-8")
            .replace(
                "replace-with-a-random-secret-at-least-32-characters",
                secrets.token_urlsafe(48),
            )
        )
        with target.open("x", encoding="utf-8") as file:
            file.write(content)
        print(".env создан со случайным SECRET_KEY.")
