"""Importacion atomica e idempotente de la salida del ejecutor inicial."""

import json
from datetime import datetime, timezone
from uuid import uuid4


def timestamp(value):
    stamp = datetime.fromisoformat(value)
    if stamp.tzinfo is None:
        raise ValueError("Las observaciones requieren zona horaria")
    return stamp.astimezone(timezone.utc).isoformat()


def identity(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} debe ser una cadena no vacia")
    return value


def import_result(db, result, *, actor):
    """Importa una corrida monobusqueda; repetir el mismo documento no genera eventos."""
    identity(actor, "actor")
    if result.get("schema_version") != "1.0":
        raise ValueError("Version de resultados no soportada")
    run_id = identity(result["run_id"], "run_id")
    source = identity(result["source"], "source")
    started = timestamp(result["started_at"])
    payload = json.dumps(result, ensure_ascii=False, sort_keys=True)
    with db:
        db.execute("BEGIN IMMEDIATE")
        existing = db.execute("SELECT payload_json FROM runs WHERE run_id=?", (run_id,)).fetchone()
        if existing:
            if existing[0] != payload:
                raise ValueError("RUN_ID ya importado con contenido diferente")
            return {"run_id": run_id, "imported": False, "ads": 0, "new_ads": 0}
        db.execute("INSERT INTO runs VALUES (?,?,?,?,?,?,?,?)", (run_id, started,
            timestamp(result["finished_at"]) if result.get("finished_at") else None,
            result["status"],source,result.get("source_version"),result["coverage"],payload))
        client_id = result.get("client_id")
        if client_id is not None:
            identity(client_id, "client_id")
            name = identity(result.get("client_name"), "client_name")
            db.execute("INSERT INTO clients VALUES (?,?,?) ON CONFLICT(client_id) DO UPDATE SET name=excluded.name,country=excluded.country",
                       (client_id,name,result["country"]))
        query_id = str(uuid4())
        db.execute("INSERT INTO run_queries VALUES (?,?,?,?,?,?,?)", (query_id,run_id,client_id,
            result["country"],result["query"],result.get("original_url"),result.get("effective_url")))
        observations = {}
        for observation in result["observations"]:
            if observation["run_id"] != run_id or observation["source"] != source:
                raise ValueError("Observacion de otra corrida o fuente")
            key = identity(observation["ad_id"], "ad_id")
            if key in observations:
                raise ValueError("Observacion duplicada")
            observations[key] = timestamp(observation["observed_at"])
        seen = set()
        new_ads = 0
        for ad in result["ads"]:
            ad_id = identity(ad["ad_id"], "ad_id")
            if ad_id in seen or ad.get("source",source) != source:
                raise ValueError("Anuncio duplicado o fuente inconsistente")
            seen.add(ad_id)
            if not db.execute("SELECT 1 FROM ads WHERE source=? AND ad_id=?", (source,ad_id)).fetchone():
                new_ads += 1
            observed = observations[ad_id]
            advertiser = ad.get("advertiser_id")
            if advertiser is not None:
                identity(advertiser, "advertiser_id")
                db.execute("INSERT OR IGNORE INTO advertisers VALUES (?,?)", (source,advertiser))
            db.execute("""INSERT INTO ads VALUES (?,?,?,?,?,?,?)
                ON CONFLICT(source,ad_id) DO UPDATE SET
                first_observed_at=min(ads.first_observed_at,excluded.first_observed_at),
                last_observed_at=max(ads.last_observed_at,excluded.last_observed_at),
                advertiser_id=CASE WHEN excluded.payload_observed_at>=ads.payload_observed_at THEN excluded.advertiser_id ELSE ads.advertiser_id END,
                payload_json=CASE WHEN excluded.payload_observed_at>=ads.payload_observed_at THEN excluded.payload_json ELSE ads.payload_json END,
                payload_observed_at=max(ads.payload_observed_at,excluded.payload_observed_at)""",
                (source,ad_id,advertiser,observed,observed,observed,json.dumps(ad,ensure_ascii=False)))
            db.execute("INSERT INTO ad_observations VALUES (?,?,?,?)", (run_id,source,ad_id,observed))
            db.execute("INSERT INTO observation_queries VALUES (?,?,?,?)", (run_id,source,ad_id,query_id))
            if ad.get("library_url"):
                db.execute("INSERT OR IGNORE INTO ad_urls VALUES (?,?,?,?,?)", (source,ad_id,
                    ad["library_url"],ad["library_url"],"library"))
        if seen != set(observations):
            raise ValueError("Observaciones sin anuncio correspondiente")
        db.execute("INSERT INTO audit_log VALUES (?,?,?,?,?,?,?,?)", (str(uuid4()),actor,
            datetime.now(timezone.utc).isoformat(),"import_result",run_id,None,
            json.dumps({"ads":len(seen)}),"Importacion de JSON de resultados"))
    return {"run_id":run_id,"imported":True,"ads":len(seen),"new_ads":new_ads}
