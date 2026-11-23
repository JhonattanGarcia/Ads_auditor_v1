"""Snapshot SQLite consistente, hash e integridad; restauracion a destino nuevo."""

from contextlib import closing
import hashlib
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from ..config.operator import validate_actor


def digest(path):
    """Compute the file SHA-256 used to verify backup and evidence integrity."""
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def open_readonly(path):
    """Open an existing SQLite database for inspection without allowing writes."""
    return sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)


def verify_database(path):
    """Check SQLite integrity and foreign keys before accepting a backup or restoration."""
    with closing(open_readonly(path)) as db:
        if db.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise ValueError("Respaldo SQLite corrupto")
        if db.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("Respaldo con claves foraneas invalidas")
        if not db.execute("SELECT version FROM schema_migrations").fetchall():
            raise ValueError("Base sin migraciones de la aplicacion")


def create_backup(database, directory, *, actor):
    """Create and verify a SQLite snapshot, recording its integrity manifest."""
    actor = validate_actor(actor)
    database, directory = Path(database).resolve(), Path(directory).resolve()
    if not database.is_file():
        raise ValueError("La base de origen no existe")
    verify_database(database)
    directory.mkdir(parents=True, exist_ok=True)
    backup_id = str(uuid4())
    final = directory / backup_id
    with TemporaryDirectory(dir=directory, prefix=".building-") as temporary:
        staging = Path(temporary)
        snapshot = staging / "database.sqlite3"
        source = open_readonly(database)
        destination = sqlite3.connect(snapshot)
        try:
            source.backup(destination)
            destination.execute("PRAGMA journal_mode=DELETE")
        finally:
            destination.close()
            source.close()
        verify_database(snapshot)
        manifest = {"schema_version":"1.0", "backup_id":backup_id,
                    "created_at":datetime.now(timezone.utc).isoformat(), "actor":actor,
                    "scope":"sqlite_only", "database_sha256":digest(snapshot),
                    "excluded":["profiles", "evidence", "operator", "results"]}
        (staging / "manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
        # El directorio UUID evita sobrescribir otros respaldos.
        final.mkdir()
        try:
            shutil.copy2(snapshot, final / "database.sqlite3")
            shutil.copy2(staging / "manifest.json", final / "manifest.json")
        except BaseException:
            for path in final.iterdir():
                path.unlink()
            final.rmdir()
            raise
    return final


def restore_backup(backup, target, *, actor):
    """Verify the snapshot and restore it to a new database path without overwriting data."""
    actor = validate_actor(actor)
    backup, target = Path(backup).resolve(), Path(target).resolve()
    if target.exists() or Path(str(target)+"-wal").exists() or Path(str(target)+"-shm").exists():
        raise ValueError("Restaurar requiere un destino nuevo, sin archivos WAL/SHM")
    manifest = json.loads((backup / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "1.0" or manifest.get("scope") != "sqlite_only":
        raise ValueError("Formato de respaldo no soportado")
    snapshot = backup / "database.sqlite3"
    if digest(snapshot) != manifest["database_sha256"]:
        raise ValueError("El hash del respaldo no coincide")
    verify_database(snapshot)
    target.parent.mkdir(parents=True, exist_ok=True)
    # Copia exclusiva: nunca sobrescribe una base existente.
    try:
        with snapshot.open("rb") as source, target.open("xb") as destination:
            shutil.copyfileobj(source, destination)
    except FileExistsError:
        raise ValueError("El destino ya existe")
    try:
        verify_database(target)
        with closing(sqlite3.connect(target)) as db:
            db.execute("INSERT INTO audit_log VALUES (?,?,?,?,?,?,?,?)", (
                str(uuid4()),actor,datetime.now(timezone.utc).isoformat(),"restore_backup",
                manifest["backup_id"],None,json.dumps({"database_sha256":manifest["database_sha256"]}),
                "Restauracion verificada en una base nueva"))
            db.commit()
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    return target
