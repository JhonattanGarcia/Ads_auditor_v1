"""Finaliza cada consulta: JSON recuperable, SQLite y resumen explicito."""

import json
from pathlib import Path
from tempfile import NamedTemporaryFile

from ..storage.database import connect, initialize
from ..storage.repositories import import_result


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def persist_result(result, output, database, *, actor):
    """Guarda JSON antes de SQLite para permitir recuperacion con import-results."""
    output, database = Path(output), Path(database)
    if output.resolve() == database.resolve():
        raise ValueError("La salida JSON y la base deben ser distintas")
    summary_path = output.with_name("run_summary.json" if output.name == "results.json" else output.stem + "_summary.json")
    if summary_path.resolve() == database.resolve():
        raise ValueError("El resumen y la base deben ser distintos")
    # El JSON importado es inmutable; los errores de almacenamiento van en el resumen.
    write_json(output, result)
    summary = {
        "schema_version":"1.0", "run_id":result["run_id"], "actor":actor,
        "client_id":result.get("client_id"), "query":result["query"],
        "diagnostic_mode":result.get("diagnostic_mode",False),
        "received_for_diagnostics":len(result.get("received_ads",[])),
        "date_mismatches":result.get("date_mismatches",0),
        "filter_mode":result.get("filter_mode"),
        "post_filter":result.get("post_filter"),
        "stop_reason":result.get("stop_reason"),
        "search_limits":result.get("search_limits"),
        "connector_stats":result.get("connector_stats",{}),
        "status":result["status"], "coverage":result["coverage"],
        "started_at":result["started_at"], "finished_at":result.get("finished_at"),
        "timezone":result.get("timezone"), "date_range":result.get("date_range"),
        "counts":{"scanned":result.get("scanned_ads"),"accepted":len(result["ads"]),
                  "excluded_by_date":result.get("excluded_by_date"),
                  "incomplete":len(result.get("invalid_records",[])),
                  "new_ads":None, "blacklisted":None,"whitelisted":None,
                  "brownlisted":None,"pending":None,"reported":None},
        "persistence":{"status":"pending", "database":str(database.resolve())},
        "results_file":str(output.resolve()),
        "warnings":list(result.get("warnings",[])), "errors":list(result.get("errors",[]))
    }
    evaluation = result.get("list_evaluation")
    if evaluation is not None:
        summary["counts"].update(evaluation["counts"])
        summary["lists_fingerprint"] = evaluation["lists_fingerprint"]
        summary["review_queue"] = evaluation["queue"]
        summary["list_conflicts"] = evaluation["conflicts"]
        if evaluation["conflicts"]:
            summary["warnings"].append("Conflictos de listas pendientes de resolucion administrativa")
    write_json(summary_path, summary)
    try:
        with connect(database) as db:
            initialize(db)
            imported = import_result(db,result,actor=actor)
        summary["persistence"].update(status="saved",imported=imported["imported"])
        summary["counts"]["new_ads"] = imported["new_ads"] if imported["imported"] else None
    except Exception as exc:
        summary["persistence"]["status"] = "failed"
        summary["errors"].append({"stage":"persistence","type":type(exc).__name__,"message":str(exc)})
    write_json(summary_path,summary)
    return summary, summary_path
