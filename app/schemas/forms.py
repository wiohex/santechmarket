import re
from decimal import Decimal
from typing import Annotated

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    field_validator,
)


def empty_none(value):
    return None if value == "" else value


class FormModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")


class CatalogFilters(FormModel):
    category: Annotated[int | None, BeforeValidator(empty_none)] = Field(None, gt=0)
    min_price: Annotated[Decimal | None, BeforeValidator(empty_none)] = Field(
        None, ge=0, le=100000000
    )
    max_price: Annotated[Decimal | None, BeforeValidator(empty_none)] = Field(
        None, ge=0, le=100000000
    )


class CartItemForm(FormModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(ge=1, le=9999)


class ContactForm(FormModel):
    name: str = Field(min_length=2, max_length=100)
    phone: str = Field(min_length=10, max_length=24)

    @field_validator("phone")
    @classmethod
    def phone_number(cls, value):
        if (
            not re.fullmatch(r"[+\d\s()\-]+", value)
            or not 10 <= len(re.sub(r"\D", "", value)) <= 15
        ):
            raise ValueError("укажите корректный телефон: от 10 до 15 цифр")
        return value


class RequestForm(ContactForm):
    comment: str = Field("", max_length=2000)
    quick_text: str = Field("", max_length=4000)
    submission_key: str = Field(pattern=r"^[A-Za-z0-9_-]{32,64}$")


class LoginForm(FormModel):
    email: str = Field(min_length=1, max_length=254)
    password: Annotated[str, StringConstraints(strip_whitespace=False)] = Field(
        min_length=1, max_length=128
    )

    @field_validator("email", mode="after")
    @classmethod
    def lower_email(cls, value):
        return value.lower()


class CompanyForm(FormModel):
    name: str = Field(min_length=2, max_length=200)
    inn: str = Field(pattern=r"^(?:\d{10}|\d{12})$")
    contact: str = Field(min_length=2, max_length=100)
    phone: str = Field(min_length=10, max_length=24)
    _phone = field_validator("phone")(ContactForm.phone_number.__func__)

    @field_validator("inn")
    @classmethod
    def inn_checksum(cls, value):
        def digit(weights, text):
            return str(sum(int(x) * w for x, w in zip(text, weights)) % 11 % 10)

        if len(value) == 10:
            valid = digit([2, 4, 10, 3, 5, 9, 4, 6, 8], value) == value[-1]
        else:
            valid = (
                digit([7, 2, 4, 10, 3, 5, 9, 4, 6, 8], value) == value[-2]
                and digit([3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8], value) == value[-1]
            )
        if not valid or len(set(value)) == 1:
            raise ValueError("проверьте контрольные цифры ИНН")
        return value


class RegistrationForm(CompanyForm, LoginForm):
    email: EmailStr
    password: Annotated[str, StringConstraints(strip_whitespace=False)] = Field(
        min_length=10, max_length=128
    )


class CategoryForm(FormModel):
    name: str = Field(min_length=2, max_length=100)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=100)


class ProductForm(FormModel):
    name: str = Field(min_length=2, max_length=200)
    sku: str = Field(min_length=1, max_length=80)
    category_id: int = Field(gt=0)
    price: Decimal = Field(ge=0, le=100000000, max_digits=11, decimal_places=2)
    description: str = Field("", max_length=10000)
    in_stock: bool = False
    active: bool = False


class StatusForm(FormModel):
    status: str = Field(pattern=r"^(new|working|completed|cancelled)$")
    owner_comment: str = Field("", max_length=4000)
