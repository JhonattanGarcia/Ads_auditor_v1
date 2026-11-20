"""Consultas historicas filtradas sin modificar los datos originales."""

import json
from .filters import Filters


def observation_contexts(db):
    return [dict(row) for row in db.execute('''SELECT a.source,a.ad_id,a.advertiser_id,q.client_id,
        q.country,q.query,o.observed_at,o.run_id,a.payload_json FROM ads a
        JOIN ad_observations o ON o.source=a.source AND o.ad_id=a.ad_id
        JOIN observation_queries p ON p.run_id=o.run_id AND p.source=o.source AND p.ad_id=o.ad_id
        JOIN run_queries q ON q.query_id=p.query_id''')]


def matches_context(row,filters):
    return filters.matches(country=row['country'],criterion=row['query'],
                           advertiser_id=row['advertiser_id'],observed_at=row['observed_at'])


def filter_cases(db,cases,filters):
    if filters is None or not filters.active: return cases
    contexts=observation_contexts(db)
    result=[]
    for case in cases:
        matching=[r for r in contexts if r['source']==case['source'] and r['ad_id']==case['ad_id']
                  and (case['client_id'] is None or r['client_id']==case['client_id'])]
        if any(matches_context(r,filters) for r in matching): result.append(case)
    return result


def list_runs(db, *, client_id=None,filters=None):
    filters=filters or Filters()
    contexts=observation_contexts(db) if filters.advertiser_id else []
    result=[]
    for row in db.execute('SELECT * FROM runs ORDER BY started_at DESC,run_id'):
        run=dict(row)
        queries=[dict(q) for q in db.execute('SELECT * FROM run_queries WHERE run_id=?',(row['run_id'],))]
        if not queries:
            payload=json.loads(row['payload_json'])
            queries=[{'client_id':payload.get('client_id'),'country':payload.get('country'),'query':payload.get('query')}]
        for query in queries:
            if client_id and query['client_id']!=client_id: continue
            # Fechas de corrida: inicio local; ID anunciante: al menos un anuncio observado en esa consulta.
            advertisers=[None]
            if filters.advertiser_id:
                advertisers=[c['advertiser_id'] for c in contexts if c['run_id']==row['run_id']
                             and c['client_id']==query['client_id'] and c['country']==query['country'] and c['query']==query['query']]
            if any(filters.matches(country=query['country'],criterion=query['query'],
                    advertiser_id=advertiser,observed_at=row['started_at']) for advertiser in advertisers):
                result.append(run); break
    return result
