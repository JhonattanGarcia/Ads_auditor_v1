"""Valores predeterminados y rutas locales del proyecto."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """Rutas relativas a un directorio de datos configurable."""

    data_dir: Path = Path("data")
    timezone: str = "America/Bogota"
    days_to_review: int = 1

    @property
    def database_path(self) -> Path:
        """Resolve the local SQLite path from application settings."""
        return self.data_dir / "database" / "monitor.sqlite3"
