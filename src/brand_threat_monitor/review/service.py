"""Casos y decisiones humanas con listas y auditoria atomicas."""

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from ..backups.service import digest
from ..config.operator import validate_actor


def audit(db, actor, operation, entity, before, after, reason):
    db.execute('INSERT INTO audit_log VALUES (?,?,?,?,?,?,?,?)',
               (str(uuid4()),actor,datetime.now(timezone.utc).isoformat(),operation,entity,
                json.dumps(before,ensure_ascii=False),json.dumps(after,ensure_ascii=False),reason))


def open_case(db, source, ad_id, *, actor, client_id=None):
    actor=validate_actor(actor)
    with db:
        db.execute('BEGIN IMMEDIATE')
        ad=db.execute('SELECT * FROM ads WHERE source=? AND ad_id=?',(source,ad_id)).fetchone()
        if ad is None:
            raise ValueError('El anuncio no existe en SQLite')
        if client_id is not None and not db.execute('SELECT 1 FROM clients WHERE client_id=?',(client_id,)).fetchone():
            raise ValueError('Cliente desconocido')
        existing=db.execute('SELECT * FROM review_cases WHERE source=? AND ad_id=? AND client_id IS ?',
                            (source,ad_id,client_id)).fetchone()
        if existing:
            return dict(existing)
        case_id=str(uuid4())
        db.execute('INSERT INTO review_cases(case_id,source,ad_id,reviewer,decision,status,client_id) VALUES (?,?,?,?,?,?,?)',
                   (case_id,source,ad_id,actor,None,'pending_review',client_id))
        result=dict(db.execute('SELECT * FROM review_cases WHERE case_id=?',(case_id,)).fetchone())
        audit(db,actor,'open_case',case_id,None,result,'Apertura deliberada de caso')
    return result


def decide(db, case_id, decision, *, actor, reason, confirm_id=None, evidence_file=None, lists=None):
    actor=validate_actor(actor)
    if decision not in {'spam','attack','pending'}:
        raise ValueError('Decision admitida: spam, attack o pending')
    if not isinstance(reason,str) or not reason.strip():
        raise ValueError('Motivo obligatorio')
    evidence=None
    if decision=='attack':
        if evidence_file is None or not Path(evidence_file).is_file():
            raise ValueError('Ataque requiere un archivo local de evidencia existente')
        path=Path(evidence_file).resolve()
        if path.stat().st_size > 20*1024*1024:
            raise ValueError('Evidencia supera el limite inicial de 20 MiB')
        evidence={'path':str(path),'hash':digest(path)}
    with db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT * FROM review_cases WHERE case_id=?',(case_id,)).fetchone()
        if row is None:
            raise ValueError('Caso desconocido')
        before=dict(row)
        if row['decision'] in {'spam','attack'}:
            raise ValueError('Caso ya clasificado; usar correct-case antes de una nueva decision')
        ad=db.execute('SELECT * FROM ads WHERE source=? AND ad_id=?',(row['source'],row['ad_id'])).fetchone()
        scope='global' if row['client_id'] is None else 'client:'+row['client_id']
        now=datetime.now(timezone.utc).isoformat()
        effects=[]
        if decision=='spam':
            if confirm_id != row['ad_id']:
                raise ValueError('Spam requiere confirmar el ID exacto del anuncio')
            existing=db.execute('SELECT entry_id FROM brownlist WHERE source=? AND ad_id=? AND scope=? AND active=1',
                                (row['source'],row['ad_id'],scope)).fetchone()
            if not existing:
                entry_id=str(uuid4())
                db.execute('INSERT INTO brownlist VALUES (?,?,?,?,?,?,?,?)',
                           (entry_id,row['source'],row['ad_id'],scope,reason,actor,now,1))
                effects.append({'list':'brown','entry_id':entry_id,'ad_id':row['ad_id'],'scope':scope})
        elif decision=='attack':
            advertiser=ad['advertiser_id']
            if not advertiser or confirm_id != advertiser:
                raise ValueError('Ataque requiere confirmar el ID exacto del anunciante conocido')
            # Cualquier whitelist activa se trata conservadoramente como conflicto.
            if db.execute("SELECT 1 FROM advertiser_lists WHERE source=? AND advertiser_id=? AND list_type='white' AND active=1",
                          (row['source'],advertiser)).fetchone():
                raise ValueError('Conflicto con whitelist: resolver administrativamente antes de Ataque')
            if lists is not None and any(e['active'] and e['source']==row['source'] and e['advertiser_id']==advertiser
                                         for e in lists.documents['whitelist']['entries']):
                raise ValueError('Conflicto con whitelist JSON: resolver antes de Ataque')
            evidence_id=str(uuid4())
            db.execute('INSERT INTO evidence(evidence_id,case_id,type,hash,local_path) VALUES (?,?,?,?,?)',
                       (evidence_id,case_id,'local_file',evidence['hash'],evidence['path']))
            existing=db.execute("SELECT entry_id FROM advertiser_lists WHERE source=? AND advertiser_id=? AND scope='global' AND active=1",
                                (row['source'],advertiser)).fetchone()
            if not existing:
                entry_id=str(uuid4())
                db.execute('INSERT INTO advertiser_lists VALUES (?,?,?,?,?,?,?,?,?,?)',
                           (entry_id,row['source'],advertiser,'black','global',reason,actor,now,1,case_id))
                effects.append({'list':'black','entry_id':entry_id,'advertiser_id':advertiser,'scope':'global'})
            effects.append({'evidence_id':evidence_id,**evidence})
        status={'spam':'classified_spam','attack':'classified_attack','pending':'pending_evidence'}[decision]
        db.execute('UPDATE review_cases SET decision=?,status=?,reviewer=? WHERE case_id=?',(decision,status,actor,case_id))
        after=dict(db.execute('SELECT * FROM review_cases WHERE case_id=?',(case_id,)).fetchone())
        audit(db,actor,'review_'+decision,case_id,before,{'case':after,'effects':effects},reason)
    return after


def reopen_case(db, case_id, *, actor, reason, confirm_case_id):
    """Revierte efectos propios y reabre; una nueva clasificacion es otra accion."""
    actor=validate_actor(actor)
    if confirm_case_id != case_id or not isinstance(reason,str) or not reason.strip():
        raise ValueError('Confirmar ID de caso y justificar la correccion')
    with db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT * FROM review_cases WHERE case_id=?',(case_id,)).fetchone()
        if row is None or row['decision'] not in {'spam','attack'}:
            raise ValueError('Solo se corrigen casos clasificados Spam o Ataque')
        before=dict(row)
        event=db.execute("SELECT after_json FROM audit_log WHERE entity=? AND operation IN ('review_spam','review_attack') ORDER BY rowid DESC LIMIT 1",(case_id,)).fetchone()
        if event is None:
            raise ValueError('Caso sin evento de origen verificable')
        changes=[]
        for effect in json.loads(event[0]).get('effects',[]):
            if effect.get('list')=='brown':
                db.execute('UPDATE brownlist SET active=0 WHERE entry_id=?',(effect['entry_id'],))
                changes.append({'deactivated_brown':effect['entry_id']})
        # Puede ser propietario original o haber recibido el antecedente de otro caso corregido.
        for entry in db.execute("SELECT * FROM advertiser_lists WHERE case_id=? AND list_type='black' AND active=1",(case_id,)).fetchall():
            other=db.execute("""SELECT c.case_id FROM review_cases c JOIN ads a ON a.source=c.source AND a.ad_id=c.ad_id
                WHERE c.source=? AND a.advertiser_id=? AND c.decision='attack' AND c.case_id!=?
                ORDER BY c.case_id LIMIT 1""",(entry['source'],entry['advertiser_id'],case_id)).fetchone()
            if other:
                db.execute('UPDATE advertiser_lists SET case_id=? WHERE entry_id=?',(other['case_id'],entry['entry_id']))
                changes.append({'retained_black':entry['entry_id'],'antecedent_case_id':other['case_id']})
            else:
                db.execute('UPDATE advertiser_lists SET active=0 WHERE entry_id=?',(entry['entry_id'],))
                changes.append({'deactivated_black':entry['entry_id']})
        db.execute("UPDATE review_cases SET decision=NULL,status='pending_review',reviewer=? WHERE case_id=?",(actor,case_id))
        after=dict(db.execute('SELECT * FROM review_cases WHERE case_id=?',(case_id,)).fetchone())
        audit(db,actor,'correct_case',case_id,before,{'case':after,'effects':changes},reason)
    return after


def list_cases(db, *, client_id=None, status=None, filters=None):
    clauses, values=[],[]
    if client_id is not None:
        clauses.append('client_id=?'); values.append(client_id)
    if status is not None:
        clauses.append('status=?'); values.append(status)
    query='SELECT * FROM review_cases'
    if clauses: query+=' WHERE '+' AND '.join(clauses)
    from ..history.service import filter_cases
    return filter_cases(db,[dict(row) for row in db.execute(query+' ORDER BY case_id',values)],filters)


def case_detail(db, case_id):
    row=db.execute('SELECT * FROM review_cases WHERE case_id=?',(case_id,)).fetchone()
    if row is None: raise ValueError('Caso desconocido')
    return {'case':dict(row),
            'ad':dict(db.execute('SELECT * FROM ads WHERE source=? AND ad_id=?',(row['source'],row['ad_id'])).fetchone()),
            'events':[dict(e) for e in db.execute('SELECT * FROM audit_log WHERE entity=? ORDER BY rowid',(case_id,))],
            'evidence':[dict(e) for e in db.execute('SELECT * FROM evidence WHERE case_id=?',(case_id,))],
            'reports':[dict(e) for e in db.execute('SELECT * FROM report_events WHERE case_id=? ORDER BY reported_at',(case_id,))]}
