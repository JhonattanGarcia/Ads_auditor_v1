"""Comandos locales de administracion de Brand Threat Monitor."""

import argparse
import json
from pathlib import Path

from . import __version__
from .storage.database import connect, initialize
from .storage.repositories import import_result


def main() -> int:
    parser = argparse.ArgumentParser(description="Brand Threat Monitor")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command")
    for name in ("init-db", "import-results"):
        command = commands.add_parser(name)
        command.add_argument("--database", type=Path, default=Path("data/database/monitor.sqlite3"))
        if name == "import-results":
            command.add_argument("file", type=Path)
            command.add_argument("--actor")
    validation = commands.add_parser("validate-profiles")
    validation.add_argument("manifest", type=Path)
    operator = commands.add_parser("set-operator")
    operator.add_argument("actor")
    operator.add_argument("--operator-file", type=Path, default=Path("data/operator.json"))
    who = commands.add_parser("whoami")
    who.add_argument("--operator-file", type=Path, default=Path("data/operator.json"))
    backup = commands.add_parser("backup-db")
    backup.add_argument("--database", type=Path, default=Path("data/database/monitor.sqlite3"))
    backup.add_argument("--directory", type=Path, default=Path("data/backups"))
    backup.add_argument("--actor")
    restore = commands.add_parser("restore-db")
    restore.add_argument("backup", type=Path)
    restore.add_argument("--target", type=Path, required=True)
    restore.add_argument("--actor")
    case = commands.add_parser("open-case")
    case.add_argument("source")
    case.add_argument("ad_id")
    case.add_argument("--client-id")
    case.add_argument("--actor")
    case.add_argument("--database", type=Path, default=Path("data/database/monitor.sqlite3"))
    review = commands.add_parser("review-case")
    review.add_argument("case_id")
    review.add_argument("decision", choices=["spam", "attack", "pending"])
    review.add_argument("--reason", required=True)
    review.add_argument("--confirm-id")
    review.add_argument("--evidence-file", type=Path)
    review.add_argument("--actor")
    review.add_argument("--lists-dir", type=Path, default=Path("lists"))
    review.add_argument("--database", type=Path, default=Path("data/database/monitor.sqlite3"))
    cases = commands.add_parser("list-cases")
    cases.add_argument("--client-id")
    cases.add_argument("--status")
    detail = commands.add_parser("show-case")
    detail.add_argument("case_id")
    queue = commands.add_parser("review-queue")
    queue.add_argument("--client-id")
    queue.add_argument("--lists-dir", type=Path, default=Path("lists"))
    correction = commands.add_parser("correct-case")
    correction.add_argument("case_id")
    correction.add_argument("--confirm-case-id", required=True)
    correction.add_argument("--reason", required=True)
    correction.add_argument("--actor")
    report = commands.add_parser("record-report")
    report.add_argument("case_id")
    report.add_argument("--reported-at", required=True)
    report.add_argument("--status", choices=["sent","awaiting_response","action_confirmed","unknown"], default="sent")
    report.add_argument("--reference")
    report.add_argument("--reason", required=True)
    report.add_argument("--actor")
    for command in [cases, detail, queue, correction, report]:
        command.add_argument("--database", type=Path, default=Path("data/database/monitor.sqlite3"))
    export = commands.add_parser("export-case")
    export.add_argument("case_id")
    export.add_argument("--format", choices=["json","csv"], required=True)
    export.add_argument("--output", type=Path, required=True)
    export.add_argument("--database", type=Path, default=Path("data/database/monitor.sqlite3"))
    runs = commands.add_parser("list-runs")
    runs.add_argument("--client-id")
    runs.add_argument("--database", type=Path, default=Path("data/database/monitor.sqlite3"))
    for command in [cases,queue,runs]:
        command.add_argument("--country")
        command.add_argument("--criterion", help="Case-insensitive substring")
        command.add_argument("--advertiser-id", help="Exact advertiser ID")
        command.add_argument("--date-from", help="Inclusive local date YYYY-MM-DD")
        command.add_argument("--date-to", help="Inclusive local date YYYY-MM-DD")
    workspace_backup = commands.add_parser("backup-workspace")
    workspace_backup.add_argument("--workspace",type=Path,default=Path.cwd())
    workspace_backup.add_argument("--directory",type=Path,default=Path("data/backups"))
    workspace_backup.add_argument("--actor",default="local_operator")
    workspace_restore = commands.add_parser("restore-workspace")
    workspace_restore.add_argument("backup",type=Path)
    workspace_restore.add_argument("--target",type=Path,required=True)
    workspace_restore.add_argument("--actor",default="local_operator")
    admin_list = commands.add_parser("list-entries")
    authorize_cmd = commands.add_parser("authorize-advertiser")
    deactivate_cmd = commands.add_parser("deactivate-entry")
    conflict_cmd = commands.add_parser("resolve-list-conflict")
    for command in [admin_list,authorize_cmd,deactivate_cmd,conflict_cmd]:
        command.add_argument("--database",type=Path,default=Path("data/database/monitor.sqlite3"))
        command.add_argument("--lists-dir",type=Path,default=Path("lists"))
    for command in [authorize_cmd,deactivate_cmd,conflict_cmd]:
        command.add_argument("source")
        command.add_argument("entity_id")
        command.add_argument("--client-id")
        command.add_argument("--reason",required=True)
        command.add_argument("--confirm-id",required=True)
        command.add_argument("--actor",default="local_operator")
    deactivate_cmd.add_argument("--list",choices=["whitelist","blacklist","brownlist"],required=True)
    conflict_cmd.add_argument("--keep",choices=["whitelist","blacklist"],required=True)
    bulk_import=commands.add_parser("import-lists")
    bulk_import.add_argument("file",type=Path)
    bulk_import.add_argument("--apply",action="store_true",help="Apply after preview; otherwise validate only")
    bulk_import.add_argument("--confirm-sha")
    bulk_import.add_argument("--reason")
    bulk_import.add_argument("--actor",default="local_operator")
    bulk_import.add_argument("--backup-directory",type=Path,default=Path("data/backups"))
    bulk_export=commands.add_parser("export-lists")
    bulk_export.add_argument("--output",type=Path,required=True)
    for command in [bulk_import,bulk_export]:
        command.add_argument("--database",type=Path,default=Path("data/database/monitor.sqlite3"))
        command.add_argument("--lists-dir",type=Path,default=Path("lists"))
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 0
    try:
        from .config.operator import resolve_actor, set_operator
        if args.command in {"backup-workspace","restore-workspace"}:
            from .backups.workspace import create_workspace_backup,restore_workspace_backup
            if args.command=="backup-workspace":
                print(create_workspace_backup(args.workspace,args.directory,actor=args.actor))
            else:
                print(restore_workspace_backup(args.backup,args.target,actor=args.actor))
            return 0
        if args.command == "set-operator":
            print(set_operator(args.actor, args.operator_file))
            return 0
        if args.command == "whoami":
            print(resolve_actor(path=args.operator_file))
            return 0
        if args.command in {"backup-db", "restore-db"}:
            from .backups.service import create_backup, restore_backup
            actor = resolve_actor(args.actor)
            if args.command == "backup-db":
                print(create_backup(args.database, args.directory, actor=actor))
            else:
                print(restore_backup(args.backup, args.target, actor=actor))
            return 0
        if args.command == "validate-profiles":
            from .config.profiles import load_manifest
            plan = load_manifest(args.manifest)
            print(json.dumps({"valid": True, "profiles": len(plan.profiles),
                              "queries": len(list(plan.queries())),
                              "output_directory": str(plan.output_directory)}, ensure_ascii=False))
            return 0
        actor = resolve_actor(args.actor) if args.command in {"import-results", "open-case", "review-case", "correct-case", "record-report"} else None
        filters=None
        if args.command in {"list-cases","review-queue","list-runs"}:
            from .history.filters import Filters
            filters=Filters(country=args.country,criterion=args.criterion,advertiser_id=args.advertiser_id,
                            date_from=args.date_from,date_to=args.date_to)
        with connect(args.database) as db:
            initialize(db)
            if args.command in {"import-lists","export-lists"}:
                from .lists.service import load_lists
                from .lists.exchange import read_lists_file,plan_import,import_lists,export_lists,document_hash
                snapshot=load_lists(args.lists_dir)
                if args.command=="export-lists":
                    print(export_lists(db,snapshot,args.output))
                else:
                    documents=read_lists_file(args.file)
                    if not args.apply:
                        plan=plan_import(db,snapshot,documents)
                        print(json.dumps({k:plan[k] for k in ['add_count','skipped','document_sha256']}))
                    else:
                        if args.confirm_sha!=document_hash(documents): raise ValueError('Preview first and pass the matching --confirm-sha')
                        print(json.dumps(import_lists(db,snapshot,documents,args.file,args.backup_directory,actor=args.actor,reason=args.reason)))
            elif args.command in {"list-entries","authorize-advertiser","deactivate-entry","resolve-list-conflict"}:
                from .lists.service import load_lists
                from .lists.admin import list_entries,authorize,deactivate,resolve_conflict
                snapshot=load_lists(args.lists_dir)
                if args.command=="list-entries":
                    result=list_entries(db,snapshot)
                else:
                    scope={"type":"client","client_id":args.client_id} if args.client_id else {"type":"global"}
                    options={"actor":args.actor,"reason":args.reason,"confirm_id":args.confirm_id}
                    if args.command=="authorize-advertiser":
                        result=authorize(db,snapshot,args.source,args.entity_id,scope,**options)
                    elif args.command=="deactivate-entry":
                        result=deactivate(db,snapshot,args.list,args.source,args.entity_id,scope,**options)
                    else:
                        result=resolve_conflict(db,snapshot,args.source,args.entity_id,args.client_id,args.keep,**options)
                print(json.dumps(result,ensure_ascii=False))
            elif args.command == "list-runs":
                from .history.service import list_runs
                print(json.dumps(list_runs(db,client_id=args.client_id,filters=filters),ensure_ascii=False))
            elif args.command == "export-case":
                from .exports.service import export_case
                print(export_case(db,args.case_id,args.output,format=args.format))
            elif args.command == "list-cases":
                from .review.service import list_cases
                print(json.dumps(list_cases(db,client_id=args.client_id,status=args.status,filters=filters),ensure_ascii=False))
            elif args.command == "show-case":
                from .review.service import case_detail
                print(json.dumps(case_detail(db,args.case_id),ensure_ascii=False))
            elif args.command == "review-queue":
                from .lists.service import load_lists
                from .review.queue import database_queue
                print(json.dumps(database_queue(db,load_lists(args.lists_dir),client_id=args.client_id,filters=filters),ensure_ascii=False))
            elif args.command == "correct-case":
                from .review.service import reopen_case
                print(json.dumps(reopen_case(db,args.case_id,actor=actor,reason=args.reason,confirm_case_id=args.confirm_case_id)))
            elif args.command == "record-report":
                from .review.reports import record_report
                print(json.dumps(record_report(db,args.case_id,actor=actor,reported_at=args.reported_at,status=args.status,reference=args.reference,reason=args.reason)))
            elif args.command == "open-case":
                from .review.service import open_case
                print(json.dumps(open_case(db,args.source,args.ad_id,actor=actor,client_id=args.client_id)))
            elif args.command == "review-case":
                from .review.service import decide
                from .lists.service import load_lists,merge_database_lists
                print(json.dumps(decide(db,args.case_id,args.decision,actor=actor,reason=args.reason,
                                        confirm_id=args.confirm_id,evidence_file=args.evidence_file,
                                        lists=merge_database_lists(db,load_lists(args.lists_dir)))))
            elif args.command == "import-results":
                result = json.loads(args.file.read_text(encoding="utf-8-sig"))
                print(json.dumps(import_result(db, result, actor=actor),ensure_ascii=False))
            else:
                print(f"Base inicializada: {args.database.resolve()}")
    except Exception as exc:
        parser.exit(1, f"Error: {exc}\n")
    return 0
