def test_database_tables():
    from sqlalchemy import create_engine, inspect

    import app.models  # noqa
    from app.db.base import Base

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    assert set(inspect(engine).get_table_names()) == {
        "users",
        "company_profiles",
        "categories",
        "products",
        "requests",
        "request_items",
        "sessions",
    }
