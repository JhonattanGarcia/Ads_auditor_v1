"""Registro de acciones manuales externas; no realiza envios a Meta."""

from datetime import datetime, timezone
from uuid import uuid4
from urllib.parse import urlsplit

from ..config.operator import validate_actor
from ..storage.repositories import timestamp
from .service import audit


def record_report(db, case_id, *, actor, reported_at, status, reference=None, reason):
    actor=validate_actor(actor)
    if status not in {'sent','awaiting_response','action_confirmed','unknown'}:
        raise ValueError('Estado externo no valido')
    stamp=timestamp(reported_at)
    if datetime.fromisoformat(stamp)>datetime.now(timezone.utc):
        raise ValueError('La fecha de reporte no puede ser futura')
    if not isinstance(reason,str) or not reason.strip():
        raise ValueError('Notas/motivo obligatorio; para accion confirmada indicar evidencia externa')
    if reference is not None:
        if not isinstance(reference,str) or not reference.strip():
            raise ValueError('Referencia vacia')
        if reference.startswith(('http:','https:')):
            url=urlsplit(reference)
            if url.scheme!='https' or not url.hostname or url.username or url.password:
                raise ValueError('Referencia URL debe ser HTTPS sin credenciales')
    if status=='action_confirmed' and not reference:
        raise ValueError('Accion confirmada requiere referencia de confirmacion externa')
    with db:
        db.execute('BEGIN IMMEDIATE')
        case=db.execute('SELECT * FROM review_cases WHERE case_id=?',(case_id,)).fetchone()
        if case is None: raise ValueError('Caso desconocido')
        report={'report_id':str(uuid4()),'case_id':case_id,'reported_at':stamp,
                'reviewer':actor,'reference':reference,'status':status}
        db.execute('INSERT INTO report_events VALUES (?,?,?,?,?,?)',tuple(report.values()))
        audit(db,actor,'manual_report',case_id,None,report,reason)
    return report
