"""Respaldo completo de datos locales y restauracion a un directorio nuevo."""

import hashlib
import json
import os
import shutil
import sqlite3
from contextlib import closing
from datetime import datetime,timezone
from pathlib import Path,PurePosixPath
from tempfile import TemporaryDirectory
from uuid import uuid4

from .service import create_backup,digest,open_readonly,verify_database
from ..config.operator import validate_actor

DATABASE='data/database/monitor.sqlite3'


def reject_links(path):
    path=Path(path).absolute()
    for part in [path,*path.parents]:
        if part.is_symlink() or (hasattr(part,'is_junction') and part.is_junction()):
            raise ValueError(f'Linked paths are not supported in backups: {part}')


def copy_checked(source,target,expected_hash=None):
    source,target=Path(source),Path(target)
    reject_links(source)
    if not source.is_file(): raise ValueError(f'Required file is missing: {source}')
    before=digest(source)
    if expected_hash and before!=expected_hash: raise ValueError(f'Evidence hash mismatch: {source}')
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(source,target)
    if digest(target)!=before or digest(source)!=before:
        raise ValueError(f'File changed while creating the backup: {source}')


def directory_files(root,json_only=False):
    root=Path(root)
    if not root.exists(): return []
    reject_links(root)
    result=[]
    for directory,dirs,files in os.walk(root,followlinks=False):
        for name in dirs: reject_links(Path(directory)/name)
        for name in files:
            path=Path(directory)/name; reject_links(path)
            if not json_only or path.suffix.lower()=='.json': result.append(path)
    return sorted(result)


def safe_member(name):
    if not isinstance(name,str) or not name or '\\' in name or ':' in name:
        raise ValueError('Invalid backup member path')
    path=PurePosixPath(name)
    if path.is_absolute() or any(p in {'..','.'} or p.endswith((' ','.')) for p in path.parts):
        raise ValueError('Unsafe backup member path')
    reserved={'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(1,10)),*(f'LPT{i}' for i in range(1,10))}
    if any(part.split('.')[0].upper() in reserved for part in path.parts):
        raise ValueError('Reserved device name in backup path')
    if str(path)!=name: raise ValueError('Non-canonical backup path')
    if not (name==DATABASE or name=='data/search_list.json' or name.startswith(('profiles/','lists/','data/evidence/'))):
        raise ValueError('Backup member outside supported data directories')
    return Path(*path.parts)


def create_workspace_backup(workspace,directory,*,actor):
    actor=validate_actor(actor)
    reject_links(workspace); reject_links(directory)
    workspace,directory=Path(workspace).resolve(),Path(directory).resolve()
    for source_dir in [workspace/'profiles',workspace/'lists',workspace/'data/evidence']:
        if directory.is_relative_to(source_dir): raise ValueError('Backup destination cannot be inside source data')
    directory.mkdir(parents=True,exist_ok=True)
    backup_id=str(uuid4()); final=directory/backup_id
    with TemporaryDirectory(dir=directory,prefix='.bundle-') as temporary:
        stage=Path(temporary)/'payload'; stage.mkdir()
        sqlite_backup=create_backup(workspace/DATABASE,Path(temporary)/'sqlite',actor=actor)
        copy_checked(sqlite_backup/'database.sqlite3',stage/DATABASE)
        for root,json_only in [(workspace/'profiles',True),(workspace/'lists',True),(workspace/'data/evidence',False)]:
            for source in directory_files(root,json_only):
                copy_checked(source,stage/source.relative_to(workspace))
        if (workspace/'data/search_list.json').exists():
            copy_checked(workspace/'data/search_list.json',stage/'data/search_list.json')
        evidence_map={}
        with closing(open_readonly(stage/DATABASE)) as db:
            evidence=db.execute('SELECT evidence_id,local_path,hash FROM evidence WHERE local_path IS NOT NULL').fetchall()
        for evidence_id,local_path,expected in evidence:
            source=Path(local_path)
            if not source.is_absolute(): source=workspace/source
            reject_links(source); source=source.resolve()
            if source.is_relative_to(workspace/'data/evidence'):
                member=source.relative_to(workspace).as_posix()
            else:
                key=hashlib.sha256(evidence_id.encode('utf-8')).hexdigest()
                member='data/evidence/linked/'+key+'.bin'
            copy_checked(source,stage/safe_member(member),expected)
            evidence_map[evidence_id]=member
        members=[]
        for file in directory_files(stage):
            members.append({'path':file.relative_to(stage).as_posix(),'sha256':digest(file),'size':file.stat().st_size})
        manifest={'schema_version':'2.0','scope':'workspace_data','backup_id':backup_id,
                  'created_at':datetime.now(timezone.utc).isoformat(),'actor':actor,
                  'members':members,'evidence_map':evidence_map,
                  'excluded':['application_code','virtual_environment','results_json','exports','logs','operator_identity'],
                  'consistency':'SQLite snapshot plus individually verified files; pause other writers during backup.'}
        (stage/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
        verify_workspace_backup(stage)
        stage.rename(final)
    return final


def verify_workspace_backup(backup):
    backup=Path(backup).absolute(); reject_links(backup)
    reject_links(backup/'manifest.json')
    manifest=json.loads((backup/'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('schema_version')!='2.0' or manifest.get('scope')!='workspace_data':
        raise ValueError('Unsupported workspace backup format')
    seen=set()
    for entry in manifest['members']:
        relative=safe_member(entry['path'])
        normalized=relative.as_posix().casefold()
        if normalized in seen: raise ValueError('Duplicate backup member')
        seen.add(normalized)
        file=backup/relative; reject_links(file)
        if not file.is_file() or file.stat().st_size!=entry['size'] or digest(file)!=entry['sha256']:
            raise ValueError(f'Backup integrity check failed: {relative}')
    if DATABASE not in seen: raise ValueError('Database missing from backup')
    for evidence_id,name in manifest['evidence_map'].items():
        safe_member(name)
        if name.casefold() not in seen or not name.startswith('data/evidence/'):
            raise ValueError('Invalid evidence mapping')
    verify_database(backup/DATABASE)
    with closing(open_readonly(backup/DATABASE)) as db:
        evidence=db.execute('SELECT evidence_id,hash FROM evidence WHERE local_path IS NOT NULL').fetchall()
    if set(manifest['evidence_map'])!={row[0] for row in evidence}:
        raise ValueError('Evidence mappings do not match database records')
    for evidence_id,expected in evidence:
        if expected and digest(backup/safe_member(manifest['evidence_map'][evidence_id]))!=expected:
            raise ValueError('Evidence content does not match its database hash')
    return manifest


def restore_workspace_backup(backup,target,*,actor):
    actor=validate_actor(actor)
    reject_links(target)
    target=Path(target).absolute()
    if target.exists(): raise ValueError('Restore requires a new destination directory')
    reject_links(backup)
    backup=Path(backup).resolve()
    manifest=verify_workspace_backup(backup)
    target.parent.mkdir(parents=True,exist_ok=True)
    with TemporaryDirectory(dir=target.parent,prefix='.restore-') as temporary:
        stage=Path(temporary)/'restored'; stage.mkdir()
        for entry in manifest['members']:
            relative=safe_member(entry['path'])
            copy_checked(backup/relative,stage/relative,entry['sha256'])
        verify_database(stage/DATABASE)
        with closing(sqlite3.connect(stage/DATABASE)) as db:
            with db:
                rows=db.execute('SELECT evidence_id FROM evidence WHERE local_path IS NOT NULL').fetchall()
                if set(manifest['evidence_map'])!={row[0] for row in rows}:
                    raise ValueError('Evidence mappings do not match the database')
                for evidence_id,name in manifest['evidence_map'].items():
                    db.execute('UPDATE evidence SET local_path=? WHERE evidence_id=?',(str(target/safe_member(name)),evidence_id))
                db.execute('INSERT INTO audit_log VALUES (?,?,?,?,?,?,?,?)',(str(uuid4()),actor,
                    datetime.now(timezone.utc).isoformat(),'restore_workspace',manifest['backup_id'],None,
                    json.dumps({'evidence_paths_rebased':len(rows),'target':str(target)}),
                    'Verified restoration into a new workspace; historical evidence references retained in audit events'))
        search_list=stage/'data/search_list.json'
        if search_list.exists():
            data=json.loads(search_list.read_text(encoding='utf-8-sig'))
            data['output_directory']=str(target/'data/results')
            search_list.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
        verify_database(stage/DATABASE)
        if target.exists(): raise ValueError('Restore target already exists')
        stage.rename(target)
    return target.resolve()
