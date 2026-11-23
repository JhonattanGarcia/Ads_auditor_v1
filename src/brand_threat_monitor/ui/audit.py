"""Presentacion pasiva del contenido; nunca carga enlaces del anuncio."""


def format_ad(payload):
    """Format obtained ad content and metadata as readable evidence-review text."""
    lines=[]
    page=payload.get('page') or {}
    if isinstance(page,dict):
        lines.append('Advertiser name: '+str(page.get('name') or 'Not available'))
    creatives=payload.get('creatives') or []
    if not isinstance(creatives,list): creatives=[]
    bodies=[str(payload[k]) for k in ['title','body'] if payload.get(k)]
    urls=[]
    media=[]
    for creative in creatives:
        if not isinstance(creative,dict): continue
        for key in ['title','body','caption','description']:
            if creative.get(key): bodies.append(str(creative[key]))
        for key in ['link_url','link','website_url','cta_url']:
            if creative.get(key): urls.append(str(creative[key]))
        for key in ['image_url','video_hd_url','video_sd_url','video_url']:
            if creative.get(key): media.append(str(creative[key]))
    for item in payload.get('urls') or []:
        if isinstance(item,str): urls.append(item)
        elif isinstance(item,dict):
            url=item.get('url_original') or item.get('original') or item.get('url')
            if url: urls.append(str(url))
    lines+=['','Ad content:', '\n\n'.join(dict.fromkeys(bodies)) or 'Not available',
            '', 'Associated URLs:', '\n'.join(dict.fromkeys(urls)) or 'Not available',
            '', 'Media references:', '\n'.join(dict.fromkeys(media)) or 'Not available',
            '', 'Media are not downloaded or opened automatically.']
    return '\n'.join(lines)
