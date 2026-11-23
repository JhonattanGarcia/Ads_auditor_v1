"""Intercambio masivo de listas; validacion completa antes de cambios."""

import copy
import csv
import hashlib
import json
from pathlib import Path
from uuid import uuid4
from datetime import datetime,timezone

from .service import KINDS,validate_document,merge_database_lists
from .admin import scope_key
from ..config.profiles import read_json
from ..config.operator import validate_actor
from ..review.service import audit
from ..backups.service import create_backup
from ..exports.service import csv_safe

COLUMNS=['schema_version','list_type','source','advertiser_id','ad_id','scope_type','client_id',
         'reason','reviewer','created_at','active','case_id','evidence_refs','escaped_fields']
TEXT_FIELDS=['source','advertiser_id','ad_id','client_id','reason','reviewer','created_at','case_id']
MAX_FILE_BYTES=5*1024*1024
MAX_ENTRIES=10000


def empty_documents():
    """Build empty versioned whitelist, blacklist and brownlist documents for exchange."""
    return {kind:{'schema_version':'1.0','list_type':kind,'identity_fields':['source',key],'entries':[]}
            for kind,key in KINDS.items()}


def validate_bundle(documents):
    """Validate all three list documents and reject inconsistent or unsupported bundle content."""
    if set(documents)!=set(KINDS): raise ValueError('Bundle must contain all three list types')
    if sum(len(documents[k].get('entries',[])) for k in KINDS)>MAX_ENTRIES:
        raise ValueError('Import exceeds the 10000-entry limit')
    for kind in KINDS:
        validate_document(documents[kind],kind)
        if any(not e['active'] for e in documents[kind]['entries']):
            raise ValueError('Bulk import only adds active entries; use explicit deactivation for removals')
    return documents


def read_lists_file(path):
    """Parse a bounded JSON or CSV import and validate its list-exchange structure."""
    path=Path(path)
    if path.stat().st_size>MAX_FILE_BYTES: raise ValueError('List file exceeds 5 MiB')
    if path.suffix.lower()=='.json':
        data=read_json(path)
        if data.get('type')=='list_bundle' and data.get('schema_version')=='1.0': documents=data['lists']
        elif data.get('list_type') in KINDS:
            documents=empty_documents(); documents[data['list_type']]=data
        else: raise ValueError('Expected a list_bundle or single-list JSON document')
    elif path.suffix.lower()=='.csv':
        documents=empty_documents()
        with path.open(encoding='utf-8-sig',newline='') as stream:
            reader=csv.DictReader(stream)
            if reader.fieldnames!=COLUMNS: raise ValueError('CSV columns do not match the documented list exchange format')
            for index,row in enumerate(reader,1):
                if index>MAX_ENTRIES: raise ValueError('Import exceeds 10000 entries')
                if None in row or any(v is None for v in row.values()): raise ValueError('Malformed CSV row')
                if row['schema_version']!='1.0' or row['list_type'] not in KINDS: raise ValueError('Unsupported CSV version/list type')
                escaped=json.loads(row['escaped_fields'])
                if not isinstance(escaped,list) or any(f not in TEXT_FIELDS for f in escaped): raise ValueError('Invalid CSV escaped_fields')
                for field in escaped:
                    if not row[field].startswith("'"): raise ValueError('Invalid protected CSV value')
                    row[field]=row[field][1:]
                if row['active']!='true': raise ValueError('CSV entries must have active=true')
                kind=row['list_type']; key=KINDS[kind]
                if row['advertiser_id' if key=='ad_id' else 'ad_id']: raise ValueError('Do not mix ad and advertiser identities')
                scope={'type':row['scope_type']}
                if row['client_id']: scope['client_id']=row['client_id']
                entry={field:row[field] for field in ['source',key,'reason','reviewer','created_at']}
                entry.update(scope=scope,active=True)
                if kind=='blacklist': entry.update(case_id=row['case_id'],evidence_refs=json.loads(row['evidence_refs']))
                documents[kind]['entries'].append(entry)
    else: raise ValueError('Use a .json or .csv file')
    return validate_bundle(documents)


def document_hash(documents):
    """Hash canonical document content to recognize idempotent list reimports."""
    return hashlib.sha256(json.dumps(documents,sort_keys=True,ensure_ascii=False).encode('utf-8')).hexdigest()


def plan_import(db,snapshot,documents):
    """Preview additions, duplicates and conflicts without changing database state."""
    validate_bundle(documents)
    effective=merge_database_lists(db,snapshot)
    additions=[]; skipped=0
    for kind,document in documents.items():
        key=KINDS[kind]
        for entry in document['entries']:
            scope=scope_key(entry['scope'])
            if any(e['active'] and e['source']==entry['source'] and e[key]==entry[key] and scope_key(e['scope'])==scope
                   for e in effective.documents[kind]['entries']):
                skipped+=1; continue
            if scope!='global' and not db.execute('SELECT 1 FROM clients WHERE client_id=?',(entry['scope']['client_id'],)).fetchone():
                raise ValueError(f'Unknown client: {entry["scope"]["client_id"]}')
            if kind in {'whitelist','blacklist'}:
                opposite='blacklist' if kind=='whitelist' else 'whitelist'
                for other in effective.documents[opposite]['entries']+documents[opposite]['entries']:
                    other_scope=scope_key(other['scope'])
                    if other['active'] and other['source']==entry['source'] and other['advertiser_id']==entry['advertiser_id'] and (scope=='global' or other_scope=='global' or scope==other_scope):
                        raise ValueError(f'Whitelist/blacklist conflict for {entry["advertiser_id"]}; resolve explicitly before importing')
            if kind=='brownlist':
                if not db.execute('SELECT 1 FROM ads WHERE source=? AND ad_id=?',(entry['source'],entry['ad_id'])).fetchone():
                    raise ValueError(f'Unknown ad ID: {entry["ad_id"]}')
            if kind=='blacklist':
                case=db.execute('''SELECT c.case_id FROM review_cases c JOIN ads a ON a.source=c.source AND a.ad_id=c.ad_id
                    WHERE c.case_id=? AND c.source=? AND a.advertiser_id=? AND c.decision='attack' ''',
                    (entry['case_id'],entry['source'],entry['advertiser_id'])).fetchone()
                evidence=db.execute('SELECT evidence_id,local_path,original_url FROM evidence WHERE case_id=?',(entry['case_id'],)).fetchall()
                known={v for row in evidence for v in row if v}
                if not case or not evidence or not set(entry['evidence_refs']).issubset(known):
                    raise ValueError(f'Blacklist requires an existing Attack case and matching evidence references: {entry["advertiser_id"]}')
            additions.append((kind,copy.deepcopy(entry)))
    return {'additions':additions,'add_count':len(additions),'skipped':skipped,'document_sha256':document_hash(documents)}


def import_lists(db,snapshot,documents,source_file,backup_directory,*,actor,reason):
    """Validate and back up before atomically importing list entries with provenance and audit."""
    actor=validate_actor(actor)
    if not reason or not reason.strip(): raise ValueError('Import reason is required')
    fingerprint=document_hash(documents)
    existing=db.execute('SELECT import_id FROM list_imports WHERE document_sha256=?',(fingerprint,)).fetchone()
    if existing: return {'already_imported':True,'import_id':existing['import_id'],'added':0}
    preview=plan_import(db,snapshot,documents)
    if preview['add_count']==0: return {'already_imported':False,'added':0,'skipped':preview['skipped'],'backup_path':None}
    database=next(row[2] for row in db.execute('PRAGMA database_list') if row[1]=='main')
    backup=create_backup(database,backup_directory,actor=actor)
    with db:
        db.execute('BEGIN IMMEDIATE')
        existing=db.execute('SELECT import_id FROM list_imports WHERE document_sha256=?',(fingerprint,)).fetchone()
        if existing: return {'already_imported':True,'import_id':existing['import_id'],'added':0}
        plan=plan_import(db,snapshot,documents)
        for kind,entry in plan['additions']:
            scope=scope_key(entry['scope']); entry_id=str(uuid4())
            if kind=='brownlist':
                db.execute('INSERT INTO brownlist VALUES (?,?,?,?,?,?,?,?)',(entry_id,entry['source'],entry['ad_id'],scope,entry['reason'],entry['reviewer'],entry['created_at'],1))
            else:
                db.execute('INSERT OR IGNORE INTO advertisers VALUES (?,?)',(entry['source'],entry['advertiser_id']))
                db.execute('INSERT INTO advertiser_lists VALUES (?,?,?,?,?,?,?,?,?,?)',(entry_id,entry['source'],entry['advertiser_id'],
                           'white' if kind=='whitelist' else 'black',scope,entry['reason'],entry['reviewer'],entry['created_at'],1,entry.get('case_id') if kind=='blacklist' else None))
        import_id=str(uuid4()); counts={'added':plan['add_count'],'skipped':plan['skipped']}
        db.execute('INSERT INTO list_imports VALUES (?,?,?,?,?,?,?,?,?)',(import_id,fingerprint,str(Path(source_file).resolve()),Path(source_file).suffix.lower(),
                   datetime.now(timezone.utc).isoformat(),actor,reason,str(backup),json.dumps(counts)))
        audit(db,actor,'import_lists',import_id,None,{'document_sha256':fingerprint,'backup_path':str(backup),'counts':counts,'entries':plan['additions']},reason)
    return {'import_id':import_id,**counts,'backup_path':str(backup),'already_imported':False}


def export_lists(db,snapshot,path):
    """Export effective lists as JSON or CSV without overwriting an existing destination."""
    path=Path(path)
    if path.suffix.lower() not in {'.json','.csv'}: raise ValueError('Use .json or .csv')
    if path.exists(): raise ValueError('Choose a new export file')
    effective=merge_database_lists(db,snapshot)
    documents=empty_documents()
    for kind,document in effective.documents.items():
        for item in document['entries']:
            if not item['active']: continue
            fields=['source',KINDS[kind],'scope','reason','reviewer','created_at','active']
            if kind=='blacklist': fields+=['case_id','evidence_refs']
            documents[kind]['entries'].append({k:item[k] for k in fields})
    path.parent.mkdir(parents=True,exist_ok=True)
    created=False
    try:
        with path.open('x',encoding='utf-8-sig' if path.suffix.lower()=='.csv' else 'utf-8',newline='') as stream:
            created=True
            if path.suffix.lower()=='.json':
                json.dump({'schema_version':'1.0','type':'list_bundle','lists':documents},stream,ensure_ascii=False,indent=2)
            else:
                writer=csv.DictWriter(stream,fieldnames=COLUMNS); writer.writeheader()
                for kind,document in documents.items():
                    for entry in document['entries']:
                        row={c:'' for c in COLUMNS}
                        row.update(schema_version='1.0',list_type=kind,source=entry['source'],scope_type=entry['scope']['type'],
                                   client_id=entry['scope'].get('client_id',''),active='true',evidence_refs=json.dumps(entry.get('evidence_refs',[]),ensure_ascii=False))
                        for field in ['advertiser_id','ad_id','reason','reviewer','created_at','case_id']: row[field]=entry.get(field,'')
                        escaped=[]
                        for field in TEXT_FIELDS:
                            safe=csv_safe(row[field])
                            if safe!=row[field]: escaped.append(field)
                            row[field]=safe
                        row['escaped_fields']=json.dumps(escaped)
                        writer.writerow(row)
    except BaseException:
        if created: path.unlink(missing_ok=True)
        raise
    return path.resolve()
