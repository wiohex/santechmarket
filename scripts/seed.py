"""Idempotent demo catalog. Run after alembic upgrade head."""

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import Category, Product

CATEGORIES = [
    ("Трубы", "pipes"),
    ("Смесители", "mixers"),
    ("Ванны", "baths"),
    ("Унитазы", "toilets"),
    ("Фитинги", "fittings"),
    ("Раковины", "sinks"),
]
PRODUCTS = [
    (
        "DEMO-001",
        "Смеситель для кухни, хром",
        "mixers",
        249000,
        True,
        "Демонстрационный товар. Однорычажный смеситель с высоким изливом. Характеристики и цену замените реальными данными.",
    ),
    (
        "DEMO-002",
        "Труба полипропиленовая 20 мм",
        "pipes",
        9550,
        True,
        "Демонстрационный товар. Цена за метр. Для внутреннего водоснабжения.",
    ),
    (
        "DEMO-003",
        "Ванна акриловая 170 × 70 см",
        "baths",
        1899000,
        True,
        "Демонстрационный товар. Прямоугольная ванна. Комплектацию уточняет владелец.",
    ),
    (
        "DEMO-004",
        "Унитаз-компакт напольный",
        "toilets",
        899000,
        True,
        "Демонстрационный товар. Белая керамика, бачок в комплекте.",
    ),
    (
        "DEMO-005",
        "Смеситель для ванной с душем",
        "mixers",
        469000,
        True,
        "Демонстрационный товар. Настенное крепление, хромированная поверхность.",
    ),
    (
        "DEMO-006",
        "Труба канализационная 50 мм",
        "pipes",
        18900,
        True,
        "Демонстрационный товар. Длина 1 метр, для внутренней канализации.",
    ),
    (
        "DEMO-007",
        "Ванна стальная 150 × 70 см",
        "baths",
        1249000,
        False,
        "Демонстрационный товар. Эмалированная поверхность. Под заказ.",
    ),
    (
        "DEMO-008",
        "Унитаз подвесной",
        "toilets",
        1149000,
        False,
        "Демонстрационный товар. Инсталляция приобретается отдельно.",
    ),
    (
        "DEMO-009",
        "Уголок полипропиленовый 20 мм",
        "fittings",
        3500,
        True,
        "Демонстрационный товар. Угол соединения 90°, цена за штуку.",
    ),
    (
        "DEMO-010",
        "Тройник полипропиленовый 25 мм",
        "fittings",
        5900,
        True,
        "Демонстрационный товар. Равнопроходный тройник, цена за штуку.",
    ),
    (
        "DEMO-011",
        "Раковина керамическая 55 см",
        "sinks",
        379000,
        True,
        "Демонстрационный товар. Белая керамика, отверстие под смеситель.",
    ),
    (
        "DEMO-012",
        "Раковина накладная 40 см",
        "sinks",
        549000,
        True,
        "Демонстрационный товар. Для установки на столешницу.",
    ),
]


def seed(factory=SessionLocal):
    added = 0
    with factory() as db:
        categories = {}
        for name, slug in CATEGORIES:
            category = db.scalar(select(Category).where(Category.slug == slug))
            if category is None:
                category = db.scalar(select(Category).where(Category.name == name))
            if category is None:
                category = Category(name=name, slug=slug)
                db.add(category)
                db.flush()
            categories[slug] = category.id
        for sku, name, slug, price, stock, description in PRODUCTS:
            if db.scalar(select(Product.id).where(Product.sku == sku)):
                continue
            db.add(
                Product(
                    sku=sku,
                    name=name,
                    category_id=categories[slug],
                    price=price,
                    in_stock=stock,
                    description=description,
                )
            )
            added += 1
        db.commit()
    return added


if __name__ == "__main__":
    print(f"Демо-товаров добавлено: {seed()}. Существующие товары не изменены.")
