"""Recoge resultados sin fechas en servidor y postfiltra la captura local."""
from datetime import datetime
from uuid import uuid4
from urllib.parse import urlencode,urlsplit,urlunsplit,parse_qsl
from importlib.metadata import version
from ..collectors.bounded import BoundedMetaCollector,CollectorTimeout
from ..collectors.base import CollectorCancelled
from ..search.query_builder import prepare
from ..search.post_filter import post_filter


def collect(profile, *, url=None, max_scan=30, collector_factory=BoundedMetaCollector, cancel_event=None, progress_callback=None, diagnostic_mode=False, max_pages=None, max_duration=None, idle_timeout=None):
    """Capture bounded source results and post-filter locally, preserving received data on handled failures."""
    if type(max_scan) is not int or max_scan<1: raise ValueError('max_scan must be a positive integer')
    from ..config.limits import validate_limits
    overrides={key:value for key,value in {'max_pages':max_pages,'max_duration':max_duration,'idle_timeout':idle_timeout}.items() if value is not None}
    validate_limits({'max_scan':max_scan,**overrides})
    original,effective,params,zone,low,high=prepare(profile,url)
    parts=urlsplit(effective)
    source_url=urlunsplit((parts.scheme,parts.netloc,parts.path,urlencode([
        (key,value) for key,value in parse_qsl(parts.query,keep_blank_values=True)
        if key not in {'start_date[min]','start_date[max]'}]),''))
    result={
        'schema_version':'1.0','run_id':str(uuid4()),'source':'meta_ad_library',
        'source_version':version('meta-ads-collector'),'filter_mode':'post',
        'diagnostic_mode':diagnostic_mode,'received_ads':[],'date_mismatches':0,
        'status':'running','started_at':datetime.now(zone).isoformat(),'finished_at':None,
        'coverage':'unknown','original_url':original,'effective_url':effective,'requested_url':effective,
        'source_search_url':source_url,'query':params['q'],'country':params['country'],
        'timezone':str(zone),'date_range':{'min':low.isoformat(),'max':high.isoformat()},
        'temporal_filter_status':'post_filtered_locally','max_scanned_ads':max_scan,
        'scanned_ads':0,'ads':[],'observations':[],'invalid_records':[],'scanned_ad_diagnostics':[],
        'excluded_by_date':0,'errors':[],
        'server_filters':{'query':params['q'],'country':params['country'],'active_status':'ACTIVE',
                          'start_date':None,'is_targeted_country':False},
        'warnings':['Date filtering is applied locally after collection; no date range is sent to Meta.',
                    'Results are bounded and coverage is partial; local sorting cannot recover ads outside the collected sample.',
                    'The effective search URL describes the requested local range; source_search_url omits date filters.']}
    collector=None
    try:
        with collector_factory(timeout=20,max_retries=1,**overrides) as collector:
            if hasattr(collector,'max_duration'):
                result['search_limits']={'max_duration_seconds':collector.max_duration,'idle_timeout_seconds':collector.idle_timeout,'max_pages':getattr(collector,'max_pages',None),'max_scanned_ads':max_scan}
            if progress_callback is not None and hasattr(collector,'progress_callback'):
                collector.progress_callback=lambda event:progress_callback({**event,'scanned_ads':result['scanned_ads'],
                    'accepted_ads':None,'excluded_by_date':None,'phase':'collecting'})
            options={'query':params['q'],'country':params['country'],'max_results':max_scan}
            if cancel_event is not None: options['cancel_event']=cancel_event
            for ad in collector.search(**options):
                content=ad.to_dict()
                content.update(source='meta_ad_library',ad_id=str(ad.id) if ad.id else None,
                    advertiser_id=str(ad.page.id) if ad.page and ad.page.id else None,
                    delivery_start_time=ad.delivery_start_time.isoformat() if ad.delivery_start_time else None)
                if ad.id: content['library_url']='https://www.facebook.com/ads/library/?'+urlencode({'id':ad.id})
                result['received_ads'].append({'content':content,'observed_at':datetime.now(zone).isoformat()})
                result['scanned_ads']+=1
            result['stop_reason']='scan_limit_reached' if result['scanned_ads']>=max_scan else 'collector_finished'
            if collector.stats.get('page_limit_reached') and result['scanned_ads']<max_scan:
                result['stop_reason']='page_limit_reached'
            if collector.stats.get('errors',0): result['warnings'].append('The collector recorded processing errors.')
        result['status']='partial'; result['coverage']='partial'
    except (KeyboardInterrupt,CollectorCancelled):
        result.update(status='cancelled',coverage='partial',stop_reason='cancelled')
    except Exception as exc:
        result.update(status='partial' if result['scanned_ads'] else 'failed',
                      coverage='partial' if result['scanned_ads'] else 'unknown',
                      stop_reason='time_limit_reached' if isinstance(exc,CollectorTimeout) else 'source_error')
        result['errors'].append({'type':type(exc).__name__,'message':str(exc)})
    if collector is not None:
        stats=getattr(collector,'stats',{})
        result['connector_stats']={key:stats[key] for key in ['requests_made','pages_fetched','errors','date_filter_requests'] if key in stats}
    result.update(post_filter(result['received_ads'],minimum=low.isoformat(),maximum=high.isoformat(),
                              timezone=str(zone),run_id=result['run_id']))
    result['finished_at']=datetime.now(zone).isoformat()
    if progress_callback is not None:
        elapsed=int((datetime.now(zone)-datetime.fromisoformat(result['started_at'])).total_seconds())
        progress_callback({'elapsed_seconds':elapsed,'received_ads':result['scanned_ads'],
                           'scanned_ads':result['scanned_ads'],'accepted_ads':result['returned_ads'],
                           'excluded_by_date':result['excluded_by_date'],'phase':'post_filtered',
                           'message':'Local post-filter complete'})
    return result
