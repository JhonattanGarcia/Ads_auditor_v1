"""Conexion y migraciones transaccionales de SQLite."""

import sqlite3
from contextlib import contextmanager
from importlib.resources import files
from pathlib import Path


@contextmanager
def connect(path: Path):
    """Open configured SQLite storage with foreign keys and WAL, closing the connection on exit."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA busy_timeout=10000")
        yield db
    finally:
        db.close()


def initialize(db):
    """Aplica migraciones en orden, revalidando version bajo bloqueo."""
    directory = files("brand_threat_monitor.storage").joinpath("migrations")
    migrations = sorted(p for p in directory.iterdir() if p.name.endswith(".sql"))
    for migration in migrations:
        try:
            db.execute("BEGIN IMMEDIATE")
            db.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
            if db.execute("SELECT 1 FROM schema_migrations WHERE version=?", (migration.name,)).fetchone():
                db.commit()
                continue
            statement = ""
            for line in migration.read_text(encoding="utf-8").splitlines(keepends=True):
                statement += line
                if sqlite3.complete_statement(statement):
                    db.execute(statement)
                    statement = ""
            if statement.strip():
                raise ValueError(f"SQL incompleto: {migration.name}")
            db.execute("INSERT INTO schema_migrations(version) VALUES (?)", (migration.name,))
            db.commit()
        except BaseException:
            db.rollback()
            raise
