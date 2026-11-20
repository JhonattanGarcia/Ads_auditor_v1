"""Tarjeta visual para anuncios, separada de la informacion tecnica completa."""

import queue
import re
import webbrowser
import threading
from collections import OrderedDict
import tkinter as tk
from tkinter import ttk
from datetime import datetime
from urllib.parse import urlsplit, urlencode, parse_qs
from zoneinfo import ZoneInfo
from .theme import INK, TEAL, IVORY, PAPER, SECONDARY, BORDER, font_family


def text(value):
    if isinstance(value,str): return value
    if isinstance(value,dict): return text(value.get('text') or value.get('body') or value.get('value'))
    return ''


def web_url(value):
    if not isinstance(value,str): return ''
    try:
        parts=urlsplit(value.strip())
        if parts.scheme in {'http','https'} and parts.hostname and not parts.username and not parts.password:
            return value.strip()
    except ValueError: pass
    return ''


def external_links(payload):
    """Ad destinations and links in copy, across all creatives; exclude media assets."""
    found=[]
    records=[payload]+[c for c in payload.get('creatives',[]) if isinstance(c,dict)]
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


def card_data(payload,index=0,*,display_timezone='America/Bogota'):
    page=payload.get('page') if isinstance(payload.get('page'),dict) else {}
    creatives=[c for c in payload.get('creatives',[]) if isinstance(c,dict)]
    creative=creatives[max(0,min(index,len(creatives)-1))] if creatives else {}
    name=text(page.get('name')) or 'Advertiser name unavailable'
    title=text(creative.get('title')) or text(payload.get('title'))
    body=text(creative.get('body')) or text(payload.get('body')) or 'Ad text is not available.'
    destination=text(creative.get('link_url')) or text(payload.get('link_url'))
    try: domain=urlsplit(destination).hostname or ''
    except ValueError: domain=''
    media=[creative[k] for k in ['image_url','original_image_url','resized_image_url','video_url','video_hd_url','video_sd_url'] if isinstance(creative.get(k),str) and creative[k]]
    images=list(dict.fromkeys(creative[k] for k in ['resized_image_url','image_url','original_image_url','thumbnail_url','video_preview_image_url','watermarked_image_url'] if isinstance(creative.get(k),str) and creative[k]))
    def date_label(value):
        if not value: return 'Not available'
        try:
            stamp=datetime.fromisoformat(value)
            if stamp.tzinfo is not None: stamp=stamp.astimezone(ZoneInfo(display_timezone))
            return stamp.strftime('%d %b %Y, %H:%M')
        except (ValueError,TypeError): return str(value)
    metrics=[]
    for key,metric_title in [('impressions','Impressions'),('reach','Reach'),('spend','Spend')]:
        value=payload.get(key)
        if isinstance(value,dict):
            low,high=value.get('lower_bound'),value.get('upper_bound')
            if low is not None or high is not None:
                shown=str(low) if low==high else f'{low if low is not None else "?"} - {high if high is not None else "?"}'
                currency=value.get('currency') or (payload.get('currency') if key=='spend' else None)
                metrics.append(metric_title+': '+shown+(' '+str(currency) if currency else ''))
    publisher_url=web_url(page.get('page_url')) or web_url(page.get('page_profile_uri'))
    publisher_id=page.get('id') or payload.get('advertiser_id')
    if not publisher_url and str(publisher_id or '').isdigit(): publisher_url='https://www.facebook.com/'+str(publisher_id)
    ad_id=payload.get('ad_id') or payload.get('id')
    ad_url='https://www.facebook.com/ads/library/?'+urlencode({'id':str(ad_id)}) if ad_id else ''
    active=payload.get('is_active')
    return {'publisher_url':publisher_url,'ad_url':ad_url,'external_links':external_links(payload),'name':name,'initials':''.join(word[0] for word in name.split()[:2]).upper(),
            'status':'Active' if active is True else 'Inactive' if active is False else 'Status unavailable',
            'title':title,'body':body,'destination':destination,'domain':domain,
            'cta':text(creative.get('cta_text')) or 'View ad',
            'advertiser_images':[page['profile_picture_url']] if isinstance(page.get('profile_picture_url'),str) and page['profile_picture_url'] else [],'images':images,'media':media,'media_type':'Video' if any(creative.get(k) for k in ['video_url','video_hd_url','video_sd_url']) else 'Image' if media else 'Media unavailable',
            'start':date_label(payload.get('delivery_start_time')),
            'stop':date_label(payload.get('delivery_stop_time')),
            'ad_id':payload.get('ad_id') or payload.get('id') or 'Not available',
            'advertiser_id':payload.get('advertiser_id') or page.get('id') or 'Not available',
            'count':len(creatives),'metrics':'   |   '.join(metrics) or 'Reach, impressions and spend were not provided.'}


class AdCard(ttk.Frame):
    def __init__(self,parent,on_open=None):
        super().__init__(parent)
        self.display_timezone='America/Bogota'
        self.on_open=on_open; self.payload={}; self.index=0; self.photo=None; self.evidence=[]
        self.fit_job=None
        self.image_generation=0; self.image_results=queue.Queue(); self.image_cache=OrderedDict()
        self.image_poll=self.after(100,self.poll_images)
        self.columnconfigure(0,weight=1,uniform='card')
        self.columnconfigure(1,weight=1,uniform='card')
        self.columnconfigure(2,weight=2,uniform='card')
        self.rowconfigure(0,weight=1)
        self.advertiser_panel=tk.Frame(self,bg=PAPER,width=1,height=1,highlightthickness=1,highlightbackground=BORDER)
        self.media_panel=tk.Frame(self,bg=PAPER,width=1,height=1,highlightthickness=1,highlightbackground=BORDER)
        self.text_panel=ttk.Frame(self,width=1,height=1)
        for column,panel in enumerate((self.advertiser_panel,self.media_panel,self.text_panel)):
            panel.grid(row=0,column=column,sticky='nsew',padx=(0,6) if column<2 else 0)
            panel.grid_propagate(False)
        self.advertiser_photo=None
        self.source_images={}
        self.advertiser_panel.rowconfigure(1,weight=1)
        self.advertiser_panel.columnconfigure(0,weight=1)
        ttk.Label(self.advertiser_panel,text='PUBLISHER',style='Media.TLabel').grid(row=0,column=0,pady=6)
        self.advertiser_media=tk.Label(self.advertiser_panel,bg=PAPER,fg=SECONDARY,text='No advertiser image',wraplength=150)
        self.advertiser_media.bind('<Button-1>',lambda event:self.open_publisher())
        self.advertiser_media.grid(row=1,column=0,sticky='nsew')
        self.media_panel.columnconfigure(0,weight=1); self.media_panel.rowconfigure(1,weight=1)
        ttk.Label(self.media_panel,text='AD PREVIEW',style='Media.TLabel').grid(row=0,column=0,pady=6)
        self.media=tk.Label(self.media_panel,bg=PAPER,fg=SECONDARY,text='No ad image',wraplength=150)
        self.media.bind('<Button-1>',lambda event:self.open_ad())
        self.media.grid(row=1,column=0,sticky='nsew')
        self.preview_button=ttk.Button(self.media_panel,text='Preview local image',command=self.preview)
        self.preview_button.grid(row=2,column=0,pady=3)
        self.retry_button=ttk.Button(self.media_panel,text='Retry web images',command=self.retry_image)
        self.retry_button.grid(row=3,column=0,pady=3)
        self.text_panel.columnconfigure(0,weight=1); self.text_panel.rowconfigure(0,weight=1)
        self.canvas=tk.Canvas(self.text_panel,highlightthickness=0,background=IVORY,width=1,height=1)
        scroll=ttk.Scrollbar(self.text_panel,command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scroll.set)
        self.canvas.grid(row=0,column=0,sticky='nsew'); scroll.grid(row=0,column=1,sticky='ns')
        self.surface=tk.Frame(self.canvas,bg=IVORY,padx=10,pady=10)
        self.item=self.canvas.create_window((0,0),window=self.surface,anchor='nw')
        self.surface.bind('<Configure>',lambda e:self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>',self.resize)
        def label(size=10,color=SECONDARY):
            widget=tk.Label(self.surface,text='',font=(font_family(self,'display' if size>=14 else 'body'),size,'bold' if size>=14 else 'normal'),bg=IVORY,fg=color,justify='left',anchor='w')
            widget.pack(fill='x',pady=4)
            return widget
        self.name=label(14,INK); self.status=label(); self.priority=label()
        self.title=label(16,INK)
        self.body=tk.Text(self.surface,height=7,width=1,wrap='word',state='disabled',relief='flat',bg=IVORY,fg=INK,font=(font_family(self),11),spacing1=3,spacing3=5)
        self.body.pack(fill='x',pady=5)
        self.destination=label(10,TEAL)
        self.external_section=ttk.LabelFrame(self.surface,text='External links in this ad',padding=8)
        self.external_section.pack(fill='x',pady=8)
        self.copy_button=ttk.Button(self.surface,text='Copy destination URL',command=self.copy_url); self.copy_button.pack(anchor='w',pady=3)
        self.library_button=ttk.Button(self.surface,text='Open in Meta Ad Library',command=lambda:self.on_open() if self.on_open else None); self.library_button.pack(anchor='w',pady=3)
        self.dates=label(); self.metrics=label(); self.identifiers=label(); self.variant_label=label()
        ttk.Button(self.surface,text='Previous creative',command=lambda:self.change(-1)).pack(anchor='w',pady=3)
        ttk.Button(self.surface,text='Next creative',command=lambda:self.change(1)).pack(anchor='w',pady=3)
        self.bind('<Configure>',self.resize_images)
        self.show_message('Select an ad to see its presentation card.')

    def resize(self,event):
        width=max(80,event.width)
        self.canvas.itemconfigure(self.item,width=width)
        for widget in [self.name,self.title,self.destination,self.dates,self.identifiers,self.metrics,self.status,self.priority,self.variant_label]:
            widget.configure(wraplength=max(40,width-24))
        self.schedule_fit()

    def schedule_fit(self):
        if self.fit_job is not None: self.after_cancel(self.fit_job)
        self.fit_job=self.after_idle(self.fit_body)

    def fit_body(self):
        self.fit_job=None
        if not self.winfo_exists(): return
        count=self.body.count('1.0','end','displaylines')
        self.body.configure(height=max(3,(count[0] if count else 1)+1))

    def resize_images(self,event=None):
        for target,image in self.source_images.items(): self.display_image(image,target,remember=False)
        self.advertiser_media.configure(wraplength=max(60,self.advertiser_panel.winfo_width()-12))
        self.media.configure(wraplength=max(60,self.media_panel.winfo_width()-12))

    def set_body(self,value):
        self.body.configure(state='normal'); self.body.delete('1.0','end'); self.body.insert('1.0',value); self.body.configure(state='disabled')
        self.schedule_fit()

    def clear_images(self):
        # Detach Tcl image names before releasing their Python PhotoImage owners.
        self.media.configure(image='')
        self.advertiser_media.configure(image='')
        self.source_images.clear()
        self.photo=None
        self.advertiser_photo=None

    def show_message(self,message):
        self.image_generation+=1
        self.clear_images()
        self.payload={}; self.evidence=[]
        self.advertiser_media.configure(cursor=''); self.media.configure(cursor='')
        for child in self.external_section.winfo_children(): child.destroy()
        self.name.configure(text='Ad review'); self.title.configure(text='No ad selected')
        self.source_images.clear(); self.advertiser_photo=None
        self.advertiser_media.configure(image='',text='No advertiser image')
        self.status.configure(text='Saved search information is available in All information')
        self.priority.configure(text=''); self.set_body(message)
        self.media.configure(image='',text='No ad media selected',width=24,height=6)
        self.destination.configure(text=''); self.dates.configure(text=''); self.metrics.configure(text=''); self.identifiers.configure(text=''); self.variant_label.configure(text='')
        for button in [self.preview_button,self.copy_button,self.library_button,self.retry_button]: button.configure(state='disabled')

    def show(self,payload,*,priority=None,evidence=None):
        self.payload=payload; self.index=0; self.evidence=evidence or []
        self.render(priority)
        self.canvas.yview_moveto(0)

    def render(self,priority=None):
        self.clear_images()
        data=card_data(self.payload,self.index,display_timezone=self.display_timezone)
        self.name.configure(text=data['name'])
        self.advertiser_media.configure(cursor='hand2' if data['publisher_url'] else '')
        self.media.configure(cursor='hand2' if data['ad_url'] else '')
        self.render_external_links(data['external_links'])
        self.image_generation+=1
        self.source_images.clear()
        self.advertiser_media.configure(image='',text='No advertiser image provided')
        self.status.configure(text='Sponsored content | '+data['status'])
        if priority is not None: self.priority.configure(text='Priority '+str(priority))
        self.title.configure(text=data['title'] or 'Advertisement')
        self.set_body(data['body'])
        self.media.configure(image='',text=data['media_type']+'\n\n'+('Source media reference available' if data['media'] else 'No media was provided'),width=24,height=6)
        self.destination.configure(text=(data['domain'] or 'Destination not available')+'   |   '+data['cta'])
        self.metrics.configure(text=data['metrics'])
        self.dates.configure(text='Started: '+data['start']+'   |   Ended: '+data['stop']+'   |   '+('UTC (+00:00)' if self.display_timezone=='UTC' else 'Colombia (UTC-05:00)'))
        self.identifiers.configure(text=f"Ad ID: {data['ad_id']}   |   Advertiser ID: {data['advertiser_id']}")
        self.variant_label.configure(text=f"Creative {self.index+1} of {max(1,data['count'])}")
        self.copy_button.configure(state='normal' if data['destination'] else 'disabled')
        self.library_button.configure(state='normal')
        self.preview_button.configure(state='normal' if self.evidence else 'disabled')
        self.load_web_image(data['images'])
        self.load_web_image(data['advertiser_images'],'advertiser')

    def open_publisher(self):
        url=card_data(self.payload)['publisher_url']
        if url: webbrowser.open(url)

    def open_ad(self):
        url=card_data(self.payload)['ad_url']
        if url: webbrowser.open(url)

    def render_external_links(self,links):
        for child in self.external_section.winfo_children(): child.destroy()
        ttk.Label(self.external_section,text=f'{len(links)} external link(s) detected' if links else 'No external links detected in the available ad data.',wraplength=250).pack(anchor='w')
        for url in links:
            label=tk.Label(self.external_section,text=url,bg=TEAL,fg=IVORY,cursor='hand2',wraplength=250,justify='left',anchor='w')
            label.pack(fill='x',pady=4)
            label.bind('<Button-1>',lambda event,target=url:webbrowser.open(target))

    def load_web_image(self,urls,target='media'):
        generation=self.image_generation
        if target=='media': self.retry_button.configure(state='normal' if urls or card_data(self.payload)['advertiser_images'] else 'disabled')
        if not urls: return
        widget=self.media if target=='media' else self.advertiser_media
        widget.configure(image='',text='Loading web image...',width=1,height=1)
        key=tuple(urls)
        if key in self.image_cache:
            self.image_cache.move_to_end(key)
            self.display_image(self.image_cache[key],target)
            return
        def worker():
            from .remote_image import load_remote_image
            error='Image unavailable'
            for url in urls:
                try:
                    image=load_remote_image(url)
                    self.image_results.put((generation,key,image,None,target))
                    return
                except Exception as exc: error=type(exc).__name__
            self.image_results.put((generation,key,None,error,target))
        threading.Thread(target=worker,daemon=True).start()

    def poll_images(self):
        try:
            while True:
                generation,key,image,error,target=self.image_results.get_nowait()
                if generation!=self.image_generation: continue
                if image is not None:
                    self.image_cache[key]=image
                    while len(self.image_cache)>20: self.image_cache.popitem(last=False)
                    self.display_image(image,target)
                else:
                    widget=self.media if target=='media' else self.advertiser_media
                    widget.configure(image='',text='Web image unavailable ('+error+').\nThe URL may have expired. Retry or open the ad in Meta.',width=24,height=6)
        except queue.Empty: pass
        self.image_poll=self.after(100,self.poll_images)

    def display_image(self,image,target='media',*,remember=True):
        from PIL import ImageTk
        if remember: self.source_images[target]=image
        panel=self.media_panel if target=='media' else self.advertiser_panel
        shown=image.copy()
        shown.thumbnail((max(20,panel.winfo_width()-12),max(20,panel.winfo_height()-110)))
        photo=ImageTk.PhotoImage(shown,master=self)
        widget=self.media if target=='media' else self.advertiser_media
        widget.configure(image=photo,text='',width=0,height=0)
        if target=='media': self.photo=photo
        else: self.advertiser_photo=photo

    def retry_image(self):
        data=card_data(self.payload,self.index)
        self.image_generation+=1
        self.image_cache.pop(tuple(data['images']),None)
        self.image_cache.pop(tuple(data['advertiser_images']),None)
        self.load_web_image(data['images'])
        self.load_web_image(data['advertiser_images'],'advertiser')

    def destroy(self):
        self.image_generation+=1
        self.after_cancel(self.image_poll)
        if self.fit_job is not None: self.after_cancel(self.fit_job)
        super().destroy()

    def change(self,direction):
        count=card_data(self.payload)['count']
        if not count: return
        self.index=max(0,min(count-1,self.index+direction)); self.render()

    def copy_url(self):
        url=card_data(self.payload,self.index)['destination']
        if url: self.clipboard_clear(); self.clipboard_append(url)

    def preview(self):
        from PIL import ImageTk
        from ..evidence.service import load_preview
        from tkinter import messagebox
        try:
            if not self.evidence: return
            self.image_generation+=1
            record=self.evidence[0]
            preview=load_preview(record['local_path'],expected_hash=record['hash'])
            image=preview.image.copy(); image.thumbnail((260,180))
            self.display_image(image)
        except Exception as exc: messagebox.showerror('Unable to preview local evidence',str(exc),parent=self)
