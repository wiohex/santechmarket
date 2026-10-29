from alembic import context

import app.models  # noqa
from app.db.base import Base
from app.db.session import engine

with engine.connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()
