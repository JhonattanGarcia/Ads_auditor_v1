"""Expedientes JSON/CSV con instantanea consistente y contenido CSV protegido."""

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from ..review.service import case_detail


def build_case_file(db, case_id):
    if db.in_transaction:
        raise ValueError('Export requires a connection without an active transaction')
    try:
        db.execute('BEGIN')
        detail=case_detail(db,case_id)
        case=detail['case']
        ad=detail['ad']
        ad['content']=json.loads(ad.pop('payload_json'))
        for event in detail['events']:
            for field in ['before_json','after_json']:
                raw=event.pop(field)
                event[field.removesuffix('_json')]=json.loads(raw) if raw else None
        params=[case['source'],case['ad_id']]
        sql='''SELECT o.run_id,o.observed_at,q.query_id,q.client_id,q.country,q.query,
            q.original_url,q.effective_url,r.started_at,r.finished_at,r.status,r.coverage,r.source_version
            FROM ad_observations o JOIN observation_queries p ON p.run_id=o.run_id AND p.source=o.source AND p.ad_id=o.ad_id
            JOIN run_queries q ON q.query_id=p.query_id JOIN runs r ON r.run_id=o.run_id
            WHERE o.source=? AND o.ad_id=?'''
        if case['client_id'] is not None:
            sql+=' AND q.client_id=?'; params.append(case['client_id'])
        observations=[dict(row) for row in db.execute(sql+' ORDER BY o.observed_at,q.query_id',params)]
        urls=[dict(row) for row in db.execute('SELECT * FROM ad_urls WHERE source=? AND ad_id=? ORDER BY kind,url_original',(case['source'],case['ad_id']))]
        result={'schema_version':'1.0','exported_at':datetime.now(timezone.utc).isoformat(),
                'case':case,'ad':ad,'observations':observations,'urls':urls,
                'evidence':detail['evidence'],'reports':detail['reports'],'events':detail['events'],
                'limitations':['Evidence files are referenced, not embedded or copied.',
                              'Only observed data is exported; missing data does not establish absence.',
                              'Report states are manually recorded and do not prove Meta action.']}
        db.commit()
        return result
    except BaseException:
        db.rollback()
        raise


def csv_safe(value):
    if value is None: return ''
    if not isinstance(value,str):
        value=json.dumps(value,ensure_ascii=False,sort_keys=True) if isinstance(value,(dict,list)) else str(value)
    # Detect formulas even when preceded by spaces or control characters.
    trimmed=value.lstrip(' \t\r\n\ufeff')
    if (trimmed and trimmed[0] in '=+-@') or value.startswith(('\t','\r','\n')):
        return "'"+value
    return value


def csv_rows(document):
    yield ['section','record','field','value']
    for field in ['schema_version','exported_at','limitations']:
        yield ['metadata','1',field,csv_safe(document[field])]
    for section in ['case','ad','observations','urls','evidence','reports','events']:
        records=document[section]
        if isinstance(records,dict): records=[records]
        for index,record in enumerate(records,1):
            for field,value in record.items():
                yield [section,str(index),field,csv_safe(value)]


def export_case(db, case_id, output, *, format):
    output=Path(output)
    if format not in {'json','csv'}: raise ValueError('Export format must be json or csv')
    if output.exists(): raise ValueError('Choose a new file: exports do not overwrite existing files')
    document=build_case_file(db,case_id)
    output.parent.mkdir(parents=True,exist_ok=True)
    created=False
    try:
        with output.open('x',encoding='utf-8-sig' if format=='csv' else 'utf-8',newline='') as stream:
            created=True
            if format=='json':
                json.dump(document,stream,ensure_ascii=False,indent=2); stream.write('\n')
            else:
                csv.writer(stream).writerows(csv_rows(document))
    except BaseException:
        if created: output.unlink(missing_ok=True)
        raise
    return output.resolve()
