"""Ejecuta una busqueda de Biblioteca y escribe resultados JSON locales."""

import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4
from zoneinfo import ZoneInfo

from brand_threat_monitor.collectors.meta import MetaCollector
from brand_threat_monitor.collectors.base import CollectorCancelled
from importlib.metadata import version


from brand_threat_monitor.search.query_builder import prepare


from brand_threat_monitor.ingestion.collector import collect


def main():
    from brand_threat_monitor.config.profiles import load_manifest, load_profile, SearchPlan
    from tempfile import NamedTemporaryFile

    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument("--profile", type=Path)
    inputs.add_argument("--manifest", type=Path)
    parser.add_argument("--url", help="Plantilla alternativa; el perfil determina pais, criterio y fechas")
    parser.add_argument("--max-scan", type=int, default=30)
    parser.add_argument('--max-pages',type=int,default=20)
    parser.add_argument('--max-duration',type=int,default=120,help='Total seconds per search')
    parser.add_argument('--idle-timeout',type=int,default=45,help='Seconds without receiving an ad')
    parser.add_argument("--output", type=Path, help="Archivo de salida, solo para una consulta")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--diagnostic", action="store_true", help="Compatibility option; all runs now retain received content and post-filter locally")
    parser.add_argument("--database", type=Path, default=Path(__file__).resolve().parent / "data/database/monitor.sqlite3")
    parser.add_argument("--lists-dir", type=Path, default=Path(__file__).resolve().parent / "lists")
    parser.add_argument("--actor", help="Analista; si se omite usa set-operator")
    args = parser.parse_args()
    from brand_threat_monitor.config.limits import validate_limits
    try:
        limits=validate_limits({'max_scan':args.max_scan,'max_pages':args.max_pages,'max_duration':args.max_duration,'idle_timeout':args.idle_timeout})
    except ValueError as exc: parser.error(str(exc))
    try:
        root = Path(__file__).resolve().parent
        plan = load_manifest(args.manifest) if args.manifest else SearchPlan(
            [load_profile(args.profile or root / "profiles/example.json")], root / "data/results")
        queries = list(plan.queries())
        if not queries:
            raise ValueError("No hay perfiles/criterios habilitados")
        if args.output and len(queries) != 1:
            raise ValueError("--output requiere exactamente una consulta")
        # Prevalidar todo antes de escribir o consultar Meta.
        prepared = [prepare(profile, args.url) for profile in queries]
        from brand_threat_monitor.lists.service import load_lists
        from brand_threat_monitor.review.queue import evaluate_result
        lists = load_lists(args.lists_dir)
        if args.dry_run:
            for profile, query in zip(queries, prepared):
                print(f"{profile['client_id']}: {query[1]}")
            print("Collection limits: "+json.dumps(limits,sort_keys=True))
            print(f"Directorio de resultados: {plan.output_directory}")
            return 0
        from brand_threat_monitor.config.operator import resolve_actor
        from brand_threat_monitor.ingestion.service import persist_result
        from brand_threat_monitor.storage.database import connect, initialize
        actor = resolve_actor(args.actor)
        if args.output and args.output.resolve() == args.database.resolve():
            raise ValueError("La salida JSON no puede ser la base SQLite")
        # Comprobar base antes de acceder a la fuente.
        with connect(args.database) as db:
            initialize(db)
            from brand_threat_monitor.lists.service import merge_database_lists
            lists = merge_database_lists(db, lists)
        output_directory = args.output.resolve().parent if args.output else plan.output_directory
        output_directory.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(dir=output_directory, prefix=".write-check-"):
            pass
        failed = False
        for profile in queries:
            result = collect(profile, url=args.url, **limits, diagnostic_mode=args.diagnostic)
            result["client_id"] = profile["client_id"]
            result["client_name"] = profile["client_name"]
            result["list_evaluation"] = evaluate_result(result, lists)
            output = args.output or plan.output_directory / result["run_id"] / "results.json"
            summary, summary_path = persist_result(result, output, args.database, actor=actor)
            print(f"{profile['client_id']}: {result['status']}; resultados: {result['returned_ads']}")
            print(f"JSON: {output.resolve()}")
            if args.diagnostic: print(f"Received for diagnostics: {len(result['received_ads'])}; outside local range: {result['excluded_by_date']}")
            print(f"Resumen: {summary_path.resolve()}; SQLite: {summary['persistence']['status']}")
            failed |= bool(summary["errors"]) or result["status"] == "cancelled"
            if result["status"] == "cancelled":
                break
        return int(failed)
    except (ValueError, KeyError, OSError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
