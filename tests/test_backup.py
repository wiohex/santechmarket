import sqlite3

import pytest

from scripts.backup import create_backup


def test_backup_includes_uncheckpointed_wal_and_photos(tmp_path):
    database = tmp_path / "live.db"
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    (uploads / "photo.jpg").write_bytes(b"sample-photo")
    destination = tmp_path / "backup"
    with sqlite3.connect(database) as live:
        live.execute("PRAGMA journal_mode=WAL")
        live.execute("CREATE TABLE products (name TEXT)")
        live.execute("INSERT INTO products VALUES ('Mixer')")
        live.commit()
        create_backup(database, uploads, destination)
    with sqlite3.connect(destination / "store.db") as copied:
        assert copied.execute("SELECT name FROM products").fetchall() == [("Mixer",)]
        assert copied.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    assert (destination / "uploads/photo.jpg").read_bytes() == b"sample-photo"
    with pytest.raises(FileExistsError):
        create_backup(database, uploads, destination)


def test_missing_database_does_not_create_empty_backup(tmp_path):
    destination = tmp_path / "backup"
    with pytest.raises(ValueError):
        create_backup(tmp_path / "missing.db", tmp_path / "uploads", destination)
    assert not destination.exists()
