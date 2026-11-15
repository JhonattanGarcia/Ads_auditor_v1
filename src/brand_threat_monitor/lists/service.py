"""Validacion y cruce determinista de listas JSON con alcance explicito."""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from ..config.profiles import read_json
from ..storage.repositories import timestamp

KINDS = {'whitelist':'advertiser_id', 'blacklist':'advertiser_id', 'brownlist':'ad_id'}


def text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{field}: cadena no vacia obligatoria')
    return value


def validate_document(document, kind):
    key = KINDS[kind]
    if document.get('schema_version') != '1.0' or document.get('list_type') != kind:
        raise ValueError(f'{kind}: version o tipo incorrecto')
    if document.get('identity_fields') != ['source', key]:
        raise ValueError(f'{kind}: identity_fields debe ser source y {key}')
    entries = document.get('entries')
    if not isinstance(entries, list):
        raise ValueError(f'{kind}.entries: lista obligatoria')
    active_keys = set()
    for index, entry in enumerate(entries):
        prefix=f'{kind}.entries[{index}]'
        if not isinstance(entry, dict):
            raise ValueError(f'{prefix}: objeto obligatorio')
        for field in ['source',key,'reason','reviewer','created_at']:
            text(entry.get(field), f'{prefix}.{field}')
        timestamp(entry['created_at'])
        if type(entry.get('active')) is not bool:
            raise ValueError(f'{prefix}.active: booleano obligatorio')
        scope=entry.get('scope')
        if not isinstance(scope,dict) or scope.get('type') not in {'global','client'}:
            raise ValueError(f'{prefix}.scope: usar type global o client')
        if scope['type']=='client':
            text(scope.get('client_id'),f'{prefix}.scope.client_id')
        elif 'client_id' in scope:
            raise ValueError(f'{prefix}.scope: global no admite client_id')
        if kind=='blacklist':
            text(entry.get('case_id'),f'{prefix}.case_id')
            refs=entry.get('evidence_refs')
            if not isinstance(refs,list) or not refs:
                raise ValueError(f'{prefix}.evidence_refs: evidencia obligatoria')
            for ref in refs: text(ref,f'{prefix}.evidence_refs')
        unique=(entry['source'],entry[key],scope['type'],scope.get('client_id'))
        if entry['active']:
            if unique in active_keys:
                raise ValueError(f'{prefix}: entrada activa duplicada')
            active_keys.add(unique)
    return entries


@dataclass(frozen=True)
class ListSnapshot:
    documents: dict
    fingerprint: str

    def matching(self, kind, ad, client_id):
        key=KINDS[kind]
        return [entry for entry in self.documents[kind]['entries']
                if entry['active'] and entry['source']==ad['source']
                and entry[key]==ad.get(key)
                and (entry['scope']['type']=='global' or
                     (client_id is not None and entry['scope'].get('client_id')==client_id))]


def load_lists(directory):
    directory=Path(directory)
    documents={}
    for kind in KINDS:
        document=read_json(directory/f'{kind}.json')
        validate_document(document,kind)
        documents[kind]=document
    fingerprint=hashlib.sha256(json.dumps(documents,sort_keys=True,ensure_ascii=False).encode('utf-8')).hexdigest()
    return ListSnapshot(documents,fingerprint)


def evaluate(ad, client_id, snapshot):
    text(ad.get('source'),'ad.source')
    text(ad.get('ad_id'),'ad.ad_id')
    white=snapshot.matching('whitelist',ad,client_id)
    black=snapshot.matching('blacklist',ad,client_id)
    brown=snapshot.matching('brownlist',ad,client_id)
    if white and black:
        state,priority,reason='list_conflict',None,'Conflicto blanca/negra: requiere resolucion administrativa'
    elif black:
        state,priority,reason='known_black',1,'Anunciante con antecedentes; revisar este anuncio individualmente'
    elif white:
        state,priority,reason='known_white',None,'Anunciante autorizado en este alcance; conservar observacion'
    elif brown:
        state,priority,reason='discarded_brown',None,'Anuncio individual previamente descartado'
    else:
        state,priority,reason='pending_review',3,'Sin antecedentes aplicables; requiere revision humana'
    return {'source':ad['source'],'ad_id':ad['ad_id'],'advertiser_id':ad.get('advertiser_id'),
            'state':state,'priority':priority,'reason':reason,
            'matched_lists':{'white':bool(white),'black':bool(black),'brown':bool(brown)}}


def merge_database_lists(db, snapshot):
    """Anexa decisiones SQLite sin eliminar las listas JSON de entrada."""
    import copy
    documents=copy.deepcopy(snapshot.documents)
    for table in ['advertiser_lists','brownlist']:
        for row in db.execute(f'SELECT * FROM {table} WHERE active=1'):
            scope={'type':'global'} if row['scope']=='global' else {'type':'client','client_id':row['scope'].removeprefix('client:')}
            kind='brownlist' if table=='brownlist' else {'white':'whitelist','black':'blacklist'}[row['list_type']]
            key=KINDS[kind]
            entry={'source':row['source'],key:row[key],'scope':scope,'reason':row['reason'],
                   'reviewer':row['reviewer'],'created_at':row['created_at'],'active':True}
            if kind=='blacklist':
                entry['case_id']=row['case_id']
                entry['evidence_refs']=[e['local_path'] or e['original_url'] or e['evidence_id']
                    for e in db.execute('SELECT * FROM evidence WHERE case_id=?',(row['case_id'],))]
            entries=documents[kind]['entries']
            entries[:]=[e for e in entries if not (e['source']==entry['source'] and e[key]==entry[key] and e['scope']==scope and e['active'])]
            entries.append(entry)
    for kind,document in documents.items():
        validate_document(document,kind)
    fingerprint=hashlib.sha256(json.dumps(documents,sort_keys=True,ensure_ascii=False).encode('utf-8')).hexdigest()
    return ListSnapshot(documents,fingerprint)
