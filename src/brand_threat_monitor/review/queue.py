"""Construccion de cola explicable sin clasificar fraude automaticamente."""

import json
from datetime import datetime
from ..lists.service import evaluate


def evaluate_result(result, snapshot):
    decisions=[evaluate(ad,result.get('client_id'),snapshot) for ad in result['ads']]
    queue=sorted([d for d in decisions if d['priority'] is not None],
                 key=lambda d:d['priority'])
    counts={name:sum(d['state']==state for d in decisions) for name,state in
            [('blacklisted','known_black'),('whitelisted','known_white'),
             ('brownlisted','discarded_brown'),('unknown','pending_review'),('conflicts','list_conflict')]}
    counts['pending']=len(queue)
    return {'schema_version':'1.0','run_id':result['run_id'],
            'lists_fingerprint':snapshot.fingerprint,'decisions':decisions,
            'queue':queue,'conflicts':[d for d in decisions if d['state']=='list_conflict'],
            'counts':counts}


def database_queue(db, snapshot, *, client_id=None, filters=None):
    """Evalua estado actual de listas y omite casos ya clasificados."""
    from ..lists.service import merge_database_lists
    effective=merge_database_lists(db,snapshot)
    from ..history.filters import Filters
    from ..history.service import observation_contexts,matches_context
    filters=filters or Filters()
    contexts=observation_contexts(db)
    unique={}
    for context in contexts:
        if matches_context(context,filters):
            key=(context['source'],context['ad_id'],context['client_id'])
            previous=unique.get(key)
            if previous is None or context['observed_at']>previous['observed_at']:
                unique[key]=context
    rows=list(unique.values())
    queue,conflicts=[],[]
    for row in rows:
        context=row['client_id']
        if client_id is not None and context!=client_id: continue
        cases=db.execute('SELECT * FROM review_cases WHERE source=? AND ad_id=? AND (client_id IS ? OR client_id IS NULL)',
                         (row['source'],row['ad_id'],context)).fetchall()
        if any(c['decision'] in {'spam','attack'} for c in cases): continue
        cleared=db.execute('SELECT cleared_through FROM queue_clears WHERE source=? AND ad_id=? AND client_id=?',
                           (row['source'],row['ad_id'],context or '')).fetchone()
        if cleared and datetime.fromisoformat(row['observed_at'])<=datetime.fromisoformat(cleared['cleared_through']): continue
        decision=evaluate(dict(row),context,effective)
        decision['reviewed']=any(c['decision'] is not None for c in cases)
        decision['client_id']=context
        decision['last_observed_at']=row['observed_at']
        decision['delivery_start_time']=json.loads(row['payload_json']).get('delivery_start_time')
        exact=next((c for c in cases if c['client_id']==context),cases[0] if cases else None)
        decision['case_id']=exact['case_id'] if exact else None
        if decision['state']=='list_conflict': conflicts.append(decision)
        elif decision['priority'] is not None: queue.append(decision)
    queue.sort(key=lambda d:(d['source'],d['ad_id'],d['client_id'] or ''))
    def start_order(decision):
        value=decision.get('delivery_start_time') or decision['last_observed_at']
        try: return datetime.fromisoformat(value).timestamp()
        except (ValueError,TypeError): return float('-inf')
    queue.sort(key=start_order,reverse=True)
    queue.sort(key=lambda d:d['priority'])
    return {'queue':queue,'conflicts':conflicts,'lists_fingerprint':effective.fingerprint}


def clear_unreviewed(db, rows, *, actor):
    """Hide only the supplied observations, preserving classifications and history."""
    from .service import audit
    from ..config.operator import validate_actor
    actor=validate_actor(actor)
    count=0
    with db:
        db.execute('BEGIN IMMEDIATE')
        for row in rows:
            if row.get('state')=='list_conflict': continue
            key=(row['source'],row['ad_id'],row['client_id'])
            cases=db.execute('SELECT decision FROM review_cases WHERE source=? AND ad_id=? AND (client_id IS ? OR client_id IS NULL)',key).fetchall()
            if any(c['decision'] is not None for c in cases): continue
            stored=db.execute('SELECT cleared_through FROM queue_clears WHERE source=? AND ad_id=? AND client_id=?',
                              (key[0],key[1],key[2] or '')).fetchone()
            through=row['last_observed_at']
            if stored and datetime.fromisoformat(stored['cleared_through'])>=datetime.fromisoformat(through): continue
            db.execute('INSERT INTO queue_clears VALUES (?,?,?,?) ON CONFLICT(source,ad_id,client_id) DO UPDATE SET cleared_through=excluded.cleared_through',
                       (key[0],key[1],key[2] or '',through))
            audit(db,actor,'clear_unreviewed',str(key),dict(stored) if stored else None,
                  {'cleared_through':through},'Removed from review queue without classification')
            count+=1
    return count
