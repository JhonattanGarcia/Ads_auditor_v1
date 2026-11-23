"""Read-only diagnosis of the data path from saved runs to the review queue."""
import json
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path

from ..history.filters import Filters
from ..history.service import observation_contexts,matches_context
from ..lists.service import load_lists,merge_database_lists,evaluate
from .queue import database_queue


def diagnose_review(database,lists_dir,*,filters=None):
    """Inspect persisted data and exclusion causes without migration or state changes."""
    path=Path(database).resolve();filters=filters or Filters()
    report={'schema_version':'1.0','database':str(path),'lists_directory':str(Path(lists_dir).resolve()),
            'read_only':True,'database_exists':path.is_file(),'filters':dict(vars(filters)),
            'counts':{},'exclusions':{},'examples':{},'errors':[],'findings':[]}
    if not path.is_file():
        report['findings'].append('Database not found. Check the application workspace or import results.json.')
        return report
    db=None;stage='open_database'
    try:
        db=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=10)
        db.row_factory=sqlite3.Row
        db.execute('PRAGMA query_only=ON');db.execute('BEGIN')
        stage='integrity'
        report['integrity']=[row[0] for row in db.execute('PRAGMA quick_check')]
        report['foreign_key_violations']=[list(row) for row in db.execute('PRAGMA foreign_key_check').fetchmany(20)]
        if report['integrity']!=['ok'] or report['foreign_key_violations']:
            report['findings'].append('SQLite integrity or relationship errors detected; preserve the database for investigation.')
        stage='schema'
        names={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        required={'runs','ads','ad_observations','observation_queries','run_queries','review_cases','queue_clears','advertiser_lists','brownlist','list_exclusions'}
        report['missing_tables']=sorted(required-names)
        if report['missing_tables']:
            report['findings'].append('Database schema is incomplete or outdated. Update the application and back up before applying migrations.')
            return report
        if 'schema_migrations' in names:
            report['migrations']=[r[0] for r in db.execute('SELECT version FROM schema_migrations ORDER BY version')]
        stage='saved_data'
        for table in ('runs','ads','ad_observations','run_queries','observation_queries','review_cases','queue_clears'):
            report['counts'][table]=db.execute('SELECT count(*) FROM '+table).fetchone()[0]
        run_totals=Counter();bad_payloads=0
        for row in db.execute('SELECT payload_json FROM runs'):
            try:
                payload=json.loads(row[0]);ads=payload.get('ads',[]);received=payload.get('received_ads',[])
                if not isinstance(ads,list) or not isinstance(received,list):raise ValueError('Invalid run arrays')
                run_totals['accepted_entries']+=len(ads);run_totals['received_entries']+=len(received)
                run_totals['runs_without_accepted_ads']+=not bool(ads)
                run_totals['runs_with_errors']+=bool(payload.get('errors'))
                excluded=payload.get('excluded_by_date',0)
                if type(excluded) is int:run_totals['excluded_by_date']+=excluded
            except (ValueError,TypeError,AttributeError):bad_payloads+=1
        report['run_totals']=dict(run_totals);report['run_totals']['invalid_payloads']=bad_payloads
        contexts=observation_contexts(db)
        report['counts']['joined_observation_contexts']=len(contexts)
        linked={(r['source'],r['ad_id']) for r in contexts}
        all_ads={(r['source'],r['ad_id']) for r in db.execute('SELECT source,ad_id FROM ads')}
        orphaned=all_ads-linked
        report['counts']['ads_without_query_context']=len(orphaned)
        report['examples']['ads_without_query_context']=[{'source':s,'ad_id':a} for s,a in sorted(orphaned)[:20]]
        stage='lists'
        snapshot=load_lists(lists_dir);effective=merge_database_lists(db,snapshot)
        stage='queue'
        unfiltered=database_queue(db,snapshot)
        filtered=database_queue(db,snapshot,filters=filters)
        report['counts'].update(queue_without_filters=len(unfiltered['queue']),conflicts_without_filters=len(unfiltered['conflicts']),
                                queue_with_filters=len(filtered['queue']),conflicts_with_filters=len(filtered['conflicts']))
        unique={}
        for row in contexts:
            key=(row['source'],row['ad_id'],row['client_id'])
            previous=unique.get(key)
            if previous is None or row['observed_at']>previous['observed_at']:unique[key]=row
        reasons=Counter()
        for key,row in unique.items():
            cases=db.execute('SELECT decision FROM review_cases WHERE source=? AND ad_id=? AND (client_id IS ? OR client_id IS NULL)',key).fetchall()
            if any(c['decision'] in {'spam','attack'} for c in cases):reason='already_classified'
            else:
                clear=db.execute('SELECT cleared_through FROM queue_clears WHERE source=? AND ad_id=? AND client_id=?',(key[0],key[1],key[2] or '')).fetchone()
                if clear and datetime.fromisoformat(row['observed_at'])<=datetime.fromisoformat(clear[0]):reason='cleared_unreviewed'
                else:
                    decision=evaluate(row,row['client_id'],effective)
                    reason={'known_white':'whitelisted','discarded_brown':'brownlisted','list_conflict':'conflict_visible'}.get(decision['state'],'eligible')
            reasons[reason]+=1
            samples=report['examples'].setdefault(reason,[])
            if len(samples)<20:samples.append({'source':key[0],'ad_id':key[1],'client_id':key[2]})
        report['exclusions']=dict(reasons)
        if report['counts']['runs'] and not report['counts']['ads']:
            report['findings'].append('History contains runs but no persisted accepted ads. Inspect run_totals and local date exclusions.')
        if orphaned:
            report['findings'].append('Some ads have no joined observation/query context and cannot enter the review queue.')
        if reasons['already_classified'] or reasons['cleared_unreviewed'] or reasons['whitelisted'] or reasons['brownlisted']:
            report['findings'].append('Saved decisions, queue clears or lists exclude ads. See exclusions; history is intentionally preserved.')
        visible=len(filtered['queue'])+len(filtered['conflicts'])
        all_visible=len(unfiltered['queue'])+len(unfiltered['conflicts'])
        if filters.active and visible<all_visible:
            report['findings'].append('Active UI filters hide eligible entries. Clear filters and refresh the queue.')
        if visible:
            report['findings'].append('Eligible entries exist. If the UI is empty, compare this database path/workspace with the running application and inspect UI loading errors.')
        if not report['findings']:
            report['findings'].append('No reviewable data found. Import a collector results.json with nonempty accepted ads.')
    except (sqlite3.Error,ValueError,KeyError,TypeError,OSError) as exc:
        report['errors'].append({'stage':stage,'type':type(exc).__name__,'message':str(exc)})
        report['findings'].append('Diagnosis stopped at '+stage+'. This can block automatic review loading; see errors.')
    finally:
        if db is not None:db.close()
    return report
