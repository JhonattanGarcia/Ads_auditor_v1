"""Identidad local declarada; no sustituye autenticacion de usuarios."""

import json
from pathlib import Path
from tempfile import NamedTemporaryFile

DEFAULT_OPERATOR_FILE = Path("data/operator.json")


def validate_actor(actor):
    """Validate and normalize the nonempty audit actor required for attributed changes."""
    if not isinstance(actor, str) or not actor.strip() or len(actor.strip()) > 100:
        raise ValueError("Analista: indicar identificador de 1 a 100 caracteres")
    if any(ord(c) < 32 for c in actor):
        raise ValueError("Analista: no se admiten caracteres de control")
    return actor.strip()


def set_operator(actor, path=DEFAULT_OPERATOR_FILE):
    """Persist the validated local operator used by CLI commands without an explicit actor."""
    actor = validate_actor(actor)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump({"schema_version":"1.0", "actor":actor}, stream, ensure_ascii=False, indent=2)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return actor


def resolve_actor(explicit=None, path=DEFAULT_OPERATOR_FILE):
    """Resolve an explicit actor or the saved operator; reject missing audit attribution."""
    if explicit is not None:
        return validate_actor(explicit)
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if data.get("schema_version") != "1.0":
            raise ValueError("Version de identidad no soportada")
        return validate_actor(data.get("actor"))
    except FileNotFoundError as exc:
        raise ValueError("Configurar analista con set-operator o indicar --actor") from exc
