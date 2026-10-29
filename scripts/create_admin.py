import getpass

from pydantic import EmailStr, TypeAdapter
from sqlalchemy import select

from app.config import get_settings
from app.db.session import SessionLocal
from app.models import User
from app.security import hasher


def create_admin(email, password, factory=SessionLocal):
    email = str(TypeAdapter(EmailStr).validate_python(email)).lower()
    if not 3 <= len(password) <= 128:
        raise ValueError("Пароль владельца должен содержать от 3 до 128 символов.")
    with factory() as db:
        if db.scalar(select(User.id).where(User.email == email)):
            raise ValueError("Email уже занят. Существующая учётная запись не изменена.")
        db.add(User(email=email, password_hash=hasher.hash(password), role="admin"))
        db.commit()


if __name__ == "__main__":
    settings = get_settings()
    try:
        password = settings.admin_password
        if not password:
            password = getpass.getpass("Пароль владельца (от 3 символов): ")
            if password != getpass.getpass("Повторите пароль: "):
                raise ValueError("Пароли не совпадают.")
        create_admin(settings.admin_email, password)
        print("Администратор создан. Войдите через /login.")
    except ValueError as error:
        raise SystemExit(str(error)) from None
