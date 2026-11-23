"""Extract associated ad URLs without opening their destinations."""
import re
from urllib.parse import urlsplit,parse_qs,urlencode

def text(value):
    """Extract readable text from source strings or supported nested text/body/value objects."""
    if isinstance(value,str): return value
    if isinstance(value,dict): return text(value.get('text') or value.get('body') or value.get('value'))
    return ''


def web_url(value):
    """Accept only HTTP or HTTPS URLs with a host and without embedded credentials."""
    if not isinstance(value,str): return ''
    if any(character.isspace() or ord(character)<32 for character in value.strip()):return ''
    try:
        parts=urlsplit(value.strip())
        if parts.scheme in {'http','https'} and parts.hostname and not parts.username and not parts.password:
            return value.strip()
    except ValueError: pass
    return ''


def external_links(payload):
    """Ad destinations and links in copy, across all creatives; exclude media assets."""
    found=[]
    records=[payload]+[c for c in (payload.get('creatives') or []) if isinstance(c,dict)]
    for record in records:
        candidates=[text(record.get(k)) for k in ('link_url','destination_url','website_url')]
        for field in ('body','title','caption','description'):
            candidates.extend(re.findall(r"https?://[^\s<>\"']+|www\.[^\s<>\"']+",text(record.get(field))))
        for candidate in candidates:
            candidate=candidate.rstrip('.,;!?)')
            if candidate.startswith('www.'): candidate='https://'+candidate
            url=web_url(candidate)
            if not url: continue
            parts=urlsplit(url)
            host=parts.hostname.lower()
            if host in {'l.facebook.com','lm.facebook.com'}:
                url=web_url(parse_qs(parts.query).get('u',[''])[0])
                if not url: continue
                host=urlsplit(url).hostname.lower()
            if any(host==domain or host.endswith('.'+domain) for domain in ('facebook.com','fb.com','instagram.com','messenger.com')): continue
            if url not in found: found.append(url)
    return found



def associated_links(payload):
    """Return deduplicated URLs with external destinations first, then profile/library/media references."""
    destinations=set(external_links(payload));found={}
    def add(url,kind):
        """Keep the most informative classification of each valid URL."""
        url=web_url(url)
        if not url:return
        priority={'External destination':0,'Publisher profile':1,'Meta ad':2,'Associated link':3,'Media':4}
        previous=found.get(url)
        if previous is None or priority[kind]<priority[previous]:found[url]=kind
    for url in destinations:add(url,'External destination')
    def walk(value,path=''):
        """Inspect nested source strings without requesting URLs or changing payload content."""
        if isinstance(value,dict):
            for key,item in value.items():walk(item,path+'.'+str(key))
        elif isinstance(value,list):
            for index,item in enumerate(value):walk(item,path+'.'+str(index))
        elif isinstance(value,str):
            for candidate in re.findall(r"https?://[^\s<>\"']+|www\.[^\s<>\"']+",value):
                candidate=candidate.rstrip('.,;!?)')
                if candidate.startswith('www.'):candidate='https://'+candidate
                url=web_url(candidate)
                if not url:continue
                lower=path.lower();host=urlsplit(url).hostname.lower()
                media=any(word in lower for word in ('image','video','thumbnail','picture','photo','logo'))
                platform=any(host==domain or host.endswith('.'+domain) for domain in ('facebook.com','fb.com','instagram.com','messenger.com'))
                if media:kind='Media'
                elif not platform:kind='External destination'
                elif 'page_url' in lower or 'profile_uri' in lower:kind='Publisher profile'
                elif '/ads/library/' in url:kind='Meta ad'
                else:kind='Associated link'
                if host in {'l.facebook.com','lm.facebook.com'}:
                    target=web_url(parse_qs(urlsplit(url).query).get('u',[''])[0])
                    if target:
                        target_host=urlsplit(target).hostname.lower()
                        if not any(target_host==d or target_host.endswith('.'+d) for d in ('facebook.com','fb.com','instagram.com','messenger.com')):add(target,'External destination')
                    continue
                add(url,kind)
    walk(payload)
    page=payload.get('page') if isinstance(payload.get('page'),dict) else {}
    publisher=page.get('id') or payload.get('advertiser_id')
    if not web_url(page.get('page_url')) and str(publisher or '').isdigit():add('https://www.facebook.com/'+str(publisher),'Publisher profile')
    ad=payload.get('ad_id') or payload.get('id')
    if ad:add('https://www.facebook.com/ads/library/?'+urlencode({'id':str(ad)}),'Meta ad')
    order={'External destination':0,'Publisher profile':1,'Meta ad':2,'Associated link':3,'Media':4}
    return [{'kind':kind,'url':url} for url,kind in sorted(found.items(),key=lambda item:(order[item[1]],item[0]))]
