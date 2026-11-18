"""Administracion explicita de listas con exclusiones JSON y auditoria SQLite."""

import json
from datetime import datetime,timezone
from uuid import uuid4

from .service import KINDS,text,merge_database_lists
from ..config.operator import validate_actor
from ..review.service import audit


def scope_key(scope):
    if scope.get('type')=='global': return 'global'
    if scope.get('type')=='client': return 'client:'+text(scope.get('client_id'),'scope.client_id')
    raise ValueError('Use global or client scope')


def list_entries(db,snapshot):
    effective=merge_database_lists(db,snapshot)
    result=[]
    for kind,document in effective.documents.items():
        for entry in document['entries']:
            if entry['active']:
                result.append({'kind':kind,'entity_id':entry[KINDS[kind]],
                               'origin':'SQLite' if entry.get('db_entry_id') else 'JSON',**entry})
    return result


def _deactivate(db,kind,entry,actor,reason):
    key=KINDS[kind]; scope=scope_key(entry['scope'])
    now=datetime.now(timezone.utc).isoformat()
    # Suppression applies to JSON sources, not to future deliberate SQLite decisions.
    db.execute('''INSERT INTO list_exclusions VALUES (?,?,?,?,?,?,?)
        ON CONFLICT(source,list_type,entity_id,scope) DO UPDATE SET
        reason=excluded.reason,reviewer=excluded.reviewer,created_at=excluded.created_at''',
        (entry['source'],kind,entry[key],scope,reason,actor,now))
    if kind=='brownlist':
        db.execute('UPDATE brownlist SET active=0 WHERE source=? AND ad_id=? AND scope=? AND active=1',
                   (entry['source'],entry[key],scope))
    else:
        db.execute('UPDATE advertiser_lists SET active=0 WHERE source=? AND advertiser_id=? AND list_type=? AND scope=? AND active=1',
                   (entry['source'],entry[key],{'whitelist':'white','blacklist':'black'}[kind],scope))


def deactivate(db,snapshot,kind,source,entity_id,scope,*,actor,reason,confirm_id):
    actor=validate_actor(actor); text(reason,'reason')
    if kind not in KINDS or entity_id!=confirm_id: raise ValueError('Confirm the exact entity ID')
    with db:
        db.execute('BEGIN IMMEDIATE')
        effective=merge_database_lists(db,snapshot)
        entry=next((e for e in effective.documents[kind]['entries'] if e['active'] and e['source']==source
                    and e[KINDS[kind]]==entity_id and scope_key(e['scope'])==scope_key(scope)),None)
        if not entry: raise ValueError('Active list entry not found')
        _deactivate(db,kind,entry,actor,reason)
        audit(db,actor,'deactivate_list_entry',entity_id,{'kind':kind,'entry':entry},
              {'kind':kind,'scope':scope,'active':False},reason)
    return {'kind':kind,'entity_id':entity_id,'active':False}


def authorize(db,snapshot,source,advertiser_id,scope,*,actor,reason,confirm_id):
    actor=validate_actor(actor); text(source,'source'); text(advertiser_id,'advertiser_id'); text(reason,'reason')
    scope_value=scope_key(scope)
    if confirm_id!=advertiser_id: raise ValueError('Confirm the exact advertiser ID')
    with db:
        db.execute('BEGIN IMMEDIATE')
        effective=merge_database_lists(db,snapshot)
        for entry in effective.documents['blacklist']['entries']:
            if entry['active'] and entry['source']==source and entry['advertiser_id']==advertiser_id:
                other=scope_key(entry['scope'])
                if scope_value=='global' or other=='global' or scope_value==other:
                    raise ValueError('Overlapping blacklist entry: resolve it explicitly before authorizing')
        for entry in effective.documents['whitelist']['entries']:
            if entry['active'] and entry['source']==source and entry['advertiser_id']==advertiser_id and scope_key(entry['scope'])==scope_value:
                raise ValueError('An active whitelist entry already exists for this scope')
        if scope_value!='global' and not db.execute('SELECT 1 FROM clients WHERE client_id=?',(scope['client_id'],)).fetchone():
            raise ValueError('Unknown client ID')
        db.execute('INSERT OR IGNORE INTO advertisers VALUES (?,?)',(source,advertiser_id))
        entry_id=str(uuid4())
        db.execute('INSERT INTO advertiser_lists VALUES (?,?,?,?,?,?,?,?,?,?)',(entry_id,source,advertiser_id,'white',scope_value,
                   reason,actor,datetime.now(timezone.utc).isoformat(),1,None))
        after={'entry_id':entry_id,'source':source,'advertiser_id':advertiser_id,'scope':scope,'kind':'whitelist'}
        audit(db,actor,'authorize_advertiser',advertiser_id,None,after,reason)
    return after


def resolve_conflict(db,snapshot,source,advertiser_id,client_id,keep,*,actor,reason,confirm_id):
    actor=validate_actor(actor); text(reason,'reason')
    if keep not in {'whitelist','blacklist'} or confirm_id!=advertiser_id:
        raise ValueError('Choose whitelist or blacklist and confirm the advertiser ID')
    with db:
        db.execute('BEGIN IMMEDIATE')
        effective=merge_database_lists(db,snapshot)
        ad={'source':source,'advertiser_id':advertiser_id}
        white=effective.matching('whitelist',ad,client_id)
        black=effective.matching('blacklist',ad,client_id)
        if not white or not black: raise ValueError('No whitelist/blacklist conflict in this context')
        opposing='blacklist' if keep=='whitelist' else 'whitelist'
        removed=black if opposing=='blacklist' else white
        for entry in removed: _deactivate(db,opposing,entry,actor,reason)
        audit(db,actor,'resolve_list_conflict',advertiser_id,{'white':white,'black':black},
              {'keep':keep,'client_id':client_id,'deactivated':removed},reason)
    return {'advertiser_id':advertiser_id,'keep':keep,'deactivated_entries':len(removed)}
