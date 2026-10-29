"""Create a consistent SQLite backup and copy uploaded product photos."""

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from sqlalchemy.engine import make_url

from app.config import ROOT, get_settings


def create_backup(database: Path, uploads: Path, destination: Path):
    if not database.is_file():
        raise ValueError("Database file does not exist.")
    destination.mkdir(parents=True, exist_ok=False)
    with sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True) as source:
        with sqlite3.connect(destination / "store.db") as target:
            source.backup(target)
    if uploads.is_dir():
        shutil.copytree(uploads, destination / "uploads")
    return destination


if __name__ == "__main__":
    url = make_url(get_settings().database_url)
    if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:":
        raise SystemExit("This backup command supports file-based SQLite only.")
    database = Path(url.database)
    if not database.is_absolute():
        database = ROOT / database
    destination = ROOT / "backups" / datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
    create_backup(database, ROOT / "uploads", destination)
    print(f"Backup saved: {destination}")
