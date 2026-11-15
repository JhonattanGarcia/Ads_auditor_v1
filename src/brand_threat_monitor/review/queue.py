"""Construccion de cola explicable sin clasificar fraude automaticamente."""

from ..lists.service import evaluate


def evaluate_result(result, snapshot):
    decisions=[evaluate(ad,result.get('client_id'),snapshot) for ad in result['ads']]
    queue=sorted([d for d in decisions if d['priority'] is not None],
                 key=lambda d:(d['priority'],d['source'],d['ad_id']))
    counts={name:sum(d['state']==state for d in decisions) for name,state in
            [('blacklisted','known_black'),('whitelisted','known_white'),
             ('brownlisted','discarded_brown'),('unknown','pending_review'),('conflicts','list_conflict')]}
    counts['pending']=len(queue)
    return {'schema_version':'1.0','run_id':result['run_id'],
            'lists_fingerprint':snapshot.fingerprint,'decisions':decisions,
            'queue':queue,'conflicts':[d for d in decisions if d['state']=='list_conflict'],
            'counts':counts}


def database_queue(db, snapshot, *, client_id=None):
    """Evalua estado actual de listas y omite casos ya clasificados."""
    from ..lists.service import merge_database_lists
    effective=merge_database_lists(db,snapshot)
    rows=db.execute('''SELECT DISTINCT a.source,a.ad_id,a.advertiser_id,q.client_id
        FROM ads a JOIN observation_queries o ON a.source=o.source AND a.ad_id=o.ad_id
        JOIN run_queries q ON q.query_id=o.query_id''').fetchall()
    queue,conflicts=[],[]
    for row in rows:
        context=row['client_id']
        if client_id is not None and context!=client_id: continue
        cases=db.execute('SELECT * FROM review_cases WHERE source=? AND ad_id=? AND (client_id IS ? OR client_id IS NULL)',
                         (row['source'],row['ad_id'],context)).fetchall()
        if any(c['decision'] in {'spam','attack'} for c in cases): continue
        decision=evaluate(dict(row),context,effective)
        decision['client_id']=context
        exact=next((c for c in cases if c['client_id']==context),cases[0] if cases else None)
        decision['case_id']=exact['case_id'] if exact else None
        if decision['state']=='list_conflict': conflicts.append(decision)
        elif decision['priority'] is not None: queue.append(decision)
    queue.sort(key=lambda d:(d['priority'],d['source'],d['ad_id'],d['client_id'] or ''))
    return {'queue':queue,'conflicts':conflicts,'lists_fingerprint':effective.fingerprint}
