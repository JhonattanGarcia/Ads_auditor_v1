"""Explicit URL exports; destinations are never fetched by this module."""
import csv
import io
import json
from pathlib import Path
from ..search.links import associated_links
from .service import csv_safe


def external_link_rows(db,rows):
    """Collect external URLs for supplied source/ad/client rows without changing review state."""
    found=[];seen=set()
    for row in rows:
        ad=db.execute('SELECT advertiser_id,payload_json FROM ads WHERE source=? AND ad_id=?',(row['source'],row['ad_id'])).fetchone()
        if ad is None:continue
        for link in associated_links(json.loads(ad['payload_json'])):
            if link['kind']!='External destination':continue
            key=(row['source'],row['ad_id'],row.get('client_id'),link['url'])
            if key in seen:continue
            seen.add(key)
            found.append({'source':row['source'],'ad_id':row['ad_id'],'advertiser_id':ad['advertiser_id'] or '',
                          'client_id':row.get('client_id') or '', 'url':link['url']})
    return found


def export_external_links(db,rows,target):
    """Save external URLs as CSV with ad context, or unique plain-text URLs; never overwrite a file."""
    target=Path(target)
    if target.suffix.lower() not in {'.csv','.txt'}:raise ValueError('Choose a .csv or .txt file')
    records=external_link_rows(db,rows)
    if not records:raise ValueError('No external links found for this selection')
    if target.suffix.lower()=='.txt':
        content='\n'.join(dict.fromkeys(row['url'] for row in records))+'\n'
    else:
        buffer=io.StringIO(newline='');writer=csv.writer(buffer)
        fields=['source','ad_id','advertiser_id','client_id','url'];writer.writerow(fields)
        for row in records:writer.writerow([csv_safe(row[field]) for field in fields])
        content='\ufeff'+buffer.getvalue()
    with target.open('x',encoding='utf-8',newline='') as stream:stream.write(content)
    return {'rows':len(records),'unique_urls':len({row['url'] for row in records}),'path':str(target.resolve())}
