"""Recoleccion compartida por CLI e interfaz de escritorio."""
from datetime import datetime
from uuid import uuid4
from urllib.parse import urlencode
from importlib.metadata import version
from ..collectors.bounded import BoundedMetaCollector
from ..collectors.base import CollectorCancelled
from ..search.query_builder import prepare
from ..collectors.date_filter import ServerDateFilterMismatch

def collect(profile, *, url=None, max_scan=30, collector_factory=BoundedMetaCollector, cancel_event=None, progress_callback=None):
    original, effective, params, zone, low, high = prepare(profile, url)
    result = {
        "schema_version": "1.0", "run_id": str(uuid4()), "source": "meta_ad_library",
        "source_version": version("meta-ads-collector"), "status": "running",
        "started_at": datetime.now(zone).isoformat(), "finished_at": None,
        "coverage": "unknown", "original_url": original, "effective_url": effective,
        "query": params["q"], "country": params["country"], "timezone": str(zone),
        "date_range": {"min": low.isoformat(), "max": high.isoformat()},
        "temporal_filter_status": "local_delivery_start_date",
        "max_scanned_ads": max_scan, "scanned_ads": 0, "excluded_by_date": 0,
        "ads": [], "observations": [], "invalid_records": [],
        "scanned_ad_diagnostics": [],
        "requested_url": effective,
        "server_filters": {"query": params["q"], "country": params["country"],
                           "active_status": "ACTIVE", "start_date": None,
                           "is_targeted_country": False},
        "warnings": ["Fechas filtradas localmente por inicio del anuncio; Meta no recibe el rango.",
                     "Consulta limitada: no garantiza todos los resultados del intervalo ni cobertura total.",
                     "La URL mostrada representa el rango solicitado; no es una URL ejecutada literalmente por el recolector."],
        "errors": []
    }
    collector = None
    seen = set()
    try:
        with collector_factory(timeout=20, max_retries=1) as collector:
            if hasattr(collector,'max_duration'):
                result['search_limits']={'max_duration_seconds':collector.max_duration,
                                         'idle_timeout_seconds':collector.idle_timeout}
            if progress_callback is not None and hasattr(collector,'progress_callback'):
                collector.progress_callback=lambda event: progress_callback({**event,
                    'scanned_ads':result['scanned_ads'], 'accepted_ads':len(result['ads']),
                    'excluded_by_date':result['excluded_by_date']})
            options = {"query":params["q"], "country":params["country"], "max_results":max_scan}
            capabilities=getattr(collector,'capabilities',None)
            if capabilities is not None and capabilities.server_date_filter:
                options.update(start_date=low.isoformat(),end_date=high.isoformat())
                result['server_filters']['start_date']={'min':low.isoformat(),'max':high.isoformat()}
                result['temporal_filter_status']='server_requested_with_local_guard'
                result['warnings'][0]='Start-date range requested from Meta on every page; local validation remains enabled.'
            if cancel_event is not None:
                options["cancel_event"] = cancel_event
            for ad in collector.search(**options):
                result["scanned_ads"] += 1
                diagnostic = {
                    "ad_id": str(ad.id) if ad.id else None,
                    "delivery_start_time": ad.delivery_start_time.isoformat() if ad.delivery_start_time else None,
                    "local_start_date": None, "source_start_date": None,
                    "decision": "invalid_identity_or_date"
                }
                result["scanned_ad_diagnostics"].append(diagnostic)
                if not ad.id or ad.delivery_start_time is None:
                    result["invalid_records"].append({"ad_id": ad.id or None,
                        "reason": "Falta ID o fecha de inicio verificable"})
                    continue
                stamp = ad.delivery_start_time
                if stamp.tzinfo is None:
                    result["invalid_records"].append({"ad_id": ad.id,
                        "reason": "Fecha de inicio sin zona horaria"})
                    continue
                diagnostic["local_start_date"] = stamp.astimezone(zone).date().isoformat()
                diagnostic["source_start_date"] = stamp.date().isoformat()
                if not low <= stamp.astimezone(zone).date() <= high:
                    diagnostic["decision"] = "excluded_by_local_date"
                    result["excluded_by_date"] += 1
                    if result['temporal_filter_status']=='server_requested_with_local_guard' and not low<=stamp.date()<=high:
                        result['temporal_filter_status']='server_filter_not_respected'
                        raise ServerDateFilterMismatch(
                            f'Meta returned ad {ad.id} with start date {stamp.date()} outside requested {low} to {high}. '
                            'Pagination stopped: this endpoint did not honor the requested date range. '
                            'This is not an empty-search result; use the manual Library to verify coverage.')
                    continue
                if ad.id in seen:
                    diagnostic["decision"] = "duplicate"
                    continue
                diagnostic["decision"] = "included"
                seen.add(ad.id)
                payload = ad.to_dict()
                payload["source"] = "meta_ad_library"
                payload["ad_id"] = str(ad.id)
                payload["advertiser_id"] = str(ad.page.id) if ad.page and ad.page.id else None
                payload["library_url"] = "https://www.facebook.com/ads/library/?" + urlencode({"id": ad.id})
                result["ads"].append(payload)
                result["observations"].append({"run_id": result["run_id"],
                    "ad_id": str(ad.id), "source": "meta_ad_library",
                    "observed_at": datetime.now(zone).isoformat()})
            if collector.stats.get("errors", 0):
                result["warnings"].append("El recolector registro errores de procesamiento.")
        result["status"] = "partial"
        result["coverage"] = "partial"
    except (KeyboardInterrupt, CollectorCancelled):
        result["status"] = "cancelled"
        result["coverage"] = "partial"
    except Exception as exc:
        result["status"] = "partial" if result["scanned_ads"] else "failed"
        result["coverage"] = "partial" if result["scanned_ads"] else "unknown"
        result["errors"].append({"type": type(exc).__name__, "message": str(exc)})
    if collector is not None:
        stats=getattr(collector,'stats',{})
        result['connector_stats']={key:stats[key] for key in
            ['requests_made','pages_fetched','errors','date_filter_requests'] if key in stats}
        if result.get('temporal_filter_status')=='server_requested_with_local_guard' and result['excluded_by_date']:
            result['warnings'].append('Meta returned records outside the local date range; server/local date equivalence is not guaranteed.')
    result["finished_at"] = datetime.now(zone).isoformat()
    result["returned_ads"] = len(result["ads"])
    return result
