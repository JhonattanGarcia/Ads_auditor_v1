"""Postfiltrado puro de una captura acotada, sin nuevas peticiones de red."""

from datetime import date,datetime
from zoneinfo import ZoneInfo


def post_filter(received, *, minimum, maximum, timezone, run_id):
    low,high=date.fromisoformat(minimum),date.fromisoformat(maximum)
    if low>high: raise ValueError('Invalid post-filter date range')
    zone=ZoneInfo(timezone)
    accepted=[]; observations=[]; invalid=[]; diagnostics=[]; seen=set()
    excluded=duplicates=0
    for record in received:
        content=record['content']
        ad_id=content.get('ad_id'); source=content.get('source')
        raw=content.get('delivery_start_time')
        diagnostic={'ad_id':ad_id,'delivery_start_time':raw,'local_start_date':None,
                    'source_start_date':None,'decision':'invalid_identity_or_date'}
        record['date_evaluation']=diagnostic
        diagnostics.append(diagnostic)
        try:
            if not isinstance(ad_id,str) or not ad_id.strip() or not isinstance(source,str) or not source.strip():
                raise ValueError('Missing or invalid ad identity')
            if not raw: raise ValueError('Missing ad delivery start date')
            stamp=datetime.fromisoformat(raw)
            if stamp.tzinfo is None or stamp.utcoffset() is None: raise ValueError('Start date has no time zone')
        except (TypeError,ValueError) as exc:
            invalid.append({'ad_id':ad_id,'reason':str(exc)}); continue
        local=stamp.astimezone(zone).date()
        diagnostic.update(local_start_date=local.isoformat(),source_start_date=stamp.date().isoformat())
        if not low<=local<=high:
            diagnostic['decision']='excluded_by_local_date'; excluded+=1; continue
        key=(source,ad_id)
        if key in seen:
            diagnostic['decision']='duplicate'; duplicates+=1; continue
        seen.add(key); diagnostic['decision']='included'
        accepted.append(dict(content))
        observations.append({'run_id':run_id,'source':source,'ad_id':ad_id,'observed_at':record['observed_at']})
    accepted.sort(key=lambda ad:(ad['source'],ad['ad_id']))
    accepted.sort(key=lambda ad:datetime.fromisoformat(ad['delivery_start_time']).timestamp(),reverse=True)
    positions={(ad['source'],ad['ad_id']):index for index,ad in enumerate(accepted)}
    observations.sort(key=lambda o:positions[(o['source'],o['ad_id'])])
    return {'ads':accepted,'observations':observations,'invalid_records':invalid,
            'scanned_ad_diagnostics':diagnostics,'excluded_by_date':excluded,
            'duplicates_skipped':duplicates,'returned_ads':len(accepted),
            'post_filter':{'version':'1.0','field':'delivery_start_time','timezone':timezone,
                           'min':minimum,'max':maximum,'inclusive':True,
                           'order':'delivery_start_time_desc','received':len(received),
                           'accepted':len(accepted),'excluded_by_date':excluded,
                           'invalid':len(invalid),'duplicates':duplicates}}
