"""Interfaz de escritorio local con Tkinter y consultas en segundo plano."""

import json
from datetime import datetime
from zoneinfo import ZoneInfo
import queue
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import ttk, filedialog, messagebox
from urllib.parse import urlencode

from ..config.limits import DEFAULT_LIMITS, BOUNDS, validate_limits
from ..config.profiles import load_manifest, SearchPlan, validate_profile, read_json
from .search_rows import SearchRows
from ..ingestion.service import write_json
from ..ingestion.collector import collect
from ..ingestion.service import persist_result
from ..lists.service import load_lists, merge_database_lists
from ..review.queue import database_queue, evaluate_result, clear_unreviewed
from ..review.service import open_case, decide
from ..storage.database import connect, initialize
from .audit import format_ad
from .history import HistoryWindow
from .filters import FilterBar
from .evidence import EvidenceWindow
from .lists import ListsWindow
from .ad_card import AdCard
from .information import format_information, InformationWindow
from ..review.service import case_detail


REASONS = {
    'known_black': 'Advertiser with prior findings; review this ad individually',
    'known_white': 'Authorized advertiser in this scope',
    'discarded_brown': 'This ad was previously discarded',
    'pending_review': 'No applicable history; human review required',
    'list_conflict': 'Whitelist/blacklist conflict; administrative review required',
}


def ad_start(row,display_timezone='America/Bogota'):
    try:
        value=datetime.fromisoformat(row.get('delivery_start_time') or '')
        if value.tzinfo is None: return None
        return value.astimezone(ZoneInfo(display_timezone))
    except (TypeError,ValueError): return None


class Application(ttk.Frame):
    def __init__(self, master, root_dir):
        super().__init__(master, padding=12)
        self.root_dir=Path(root_dir).resolve()
        self.database=self.root_dir/'data/database/monitor.sqlite3'
        self.lists_dir=self.root_dir/'lists'
        self.events=queue.Queue()
        self.cancel=threading.Event()
        self.busy=False
        self.plan=SearchPlan([],self.root_dir/"data/results")
        self.search_rows=SearchRows()
        self.search_list_file=self.root_dir/'data/search_list.json'
        self.rows=[]
        self.selected=None
        self.analysis_information={}
        self.pack(fill='both',expand=True)
        master.title('Brand Threat Monitor')
        master.geometry('1150x780')
        master.minsize(850,600)
        master.protocol('WM_DELETE_WINDOW',self.close)
        ttk.Label(self,text='Brand Threat Monitor',font=('Segoe UI',20,'bold')).pack(anchor='w')
        ttk.Label(self,text='Local monitoring and human review of Meta ads').pack(anchor='w',pady=(0,10))
        self.tabs=ttk.Notebook(self); self.tabs.pack(fill='both',expand=True)
        self.home=ttk.Frame(self.tabs,padding=12); self.audit=ttk.Frame(self.tabs,padding=12)
        self.tabs.add(self.home,text='Search setup'); self.tabs.add(self.audit,text='Ad review')
        self.build_home(); self.build_audit()
        self.status=tk.StringVar(value='Ready. Add searches manually or load a JSON list.')
        self.status_label=tk.Label(self,textvariable=self.status,wraplength=1050,height=2,anchor='w',justify='left')
        self.status_label.pack(side='bottom',fill='x',pady=(6,0),before=self.tabs)
        self.bind('<Configure>',lambda event:self.status_label.configure(wraplength=max(200,event.width-24)))
        self.timer=self.after(150,self.poll)
        if self.search_list_file.exists():
            self.guard(lambda:self.load_path(self.search_list_file))
        self.days.trace_add('write',lambda *args:self.save_days_change())
        self.tabs.bind('<<NotebookTabChanged>>',self.review_tab_changed)
        self.auto_refresh()

    def build_home(self):
        bar=ttk.Frame(self.home); bar.pack(fill='x')
        self.load_button=ttk.Button(bar,text='Load search list',command=self.load)
        self.load_button.pack(side='left')
        ttk.Button(bar,text='Manage lists',command=lambda:self.guard(self.open_lists)).pack(side='right',padx=5)
        ttk.Button(bar,text='History',command=lambda:self.guard(self.open_history)).pack(side='right')
        ttk.Button(bar,text='Export search list',command=lambda:self.guard(self.save_search_list)).pack(side='left',padx=8)
        editor=ttk.Frame(self.home); editor.pack(fill='x',pady=(10,0))
        self.row_enabled=tk.BooleanVar(value=True)
        self.enabled_button=ttk.Checkbutton(editor,text='Enabled',variable=self.row_enabled,command=lambda:self.guard(self.enabled_changed))
        self.enabled_button.pack(side='left')
        ttk.Label(editor,text='Country:').pack(side='left',padx=(8,3))
        self.row_country=tk.StringVar(value='CO')
        self.country_entry=ttk.Entry(editor,textvariable=self.row_country,width=6)
        self.country_entry.pack(side='left')
        ttk.Label(editor,text='Search criteria:').pack(side='left',padx=(8,3))
        self.row_criterion=tk.StringVar()
        self.criterion_entry=ttk.Entry(editor,textvariable=self.row_criterion,width=32)
        self.criterion_entry.pack(side='left',fill='x',expand=True)
        self.add_button=ttk.Button(editor,text='Add',command=lambda:self.guard(self.add_search))
        self.add_button.pack(side='left',padx=5)
        self.update_button=ttk.Button(editor,text='Update selected search',command=lambda:self.guard(self.update_search))
        self.update_button.pack(side='left')
        self.profile_table=ttk.Treeview(self.home,columns=('enabled','country','criterion','delete'),show='headings',height=8,selectmode='browse')
        for col,label,width in [('enabled','Enabled',80),('country','Country',80),('criterion','Search criteria',500),('delete','Delete',80)]:
            self.profile_table.heading(col,text=label)
            self.profile_table.column(col,width=width,stretch=col=='criterion')
        self.profile_table.pack(fill='x',pady=12)
        self.profile_table.bind('<ButtonRelease-1>',self.search_click)
        self.profile_table.bind('<<TreeviewSelect>>',lambda event:self.select_search())
        self.profile_table.bind('<space>',lambda event:self.guard(self.toggle_search))
        self.profile_table.bind('<Delete>',lambda event:self.guard(self.delete_search))
        self.profile_table.bind('<Double-1>',lambda event:self.criterion_entry.focus_set())
        actions=ttk.Frame(self.home); actions.pack(fill='x')
        ttk.Label(actions,text='Days to review:').pack(side='left')
        self.days=tk.StringVar(value='1')
        ttk.Spinbox(actions,from_=1,to=90,textvariable=self.days,width=6).pack(side='left',padx=8)
        self.run_button=ttk.Button(actions,text='Run searches',command=self.start)
        self.run_button.pack(side='left',padx=5)
        self.stop_button=ttk.Button(actions,text='Stop',command=self.cancel.set,state='disabled')
        self.stop_button.pack(side='left')
        limits_bar=ttk.LabelFrame(self.home,text='Collection limits (per search)',padding=5)
        limits_bar.pack(fill='x',pady=(5,0))
        self.limit_values={}
        for column,(key,label) in enumerate([('max_scan','Max ads'),('max_pages','Max pages'),('max_duration','Total seconds'),('idle_timeout','Idle seconds')]):
            ttk.Label(limits_bar,text=label).grid(row=0,column=column*2,padx=3)
            value=tk.StringVar(value=str(DEFAULT_LIMITS[key])); self.limit_values[key]=value
            ttk.Spinbox(limits_bar,from_=BOUNDS[key][0],to=BOUNDS[key][1],textvariable=value,width=7).grid(row=0,column=column*2+1,padx=3)
            value.trace_add('write',lambda *args:self.save_limits_change())
        self.progress=ttk.Progressbar(self.home,mode='indeterminate'); self.progress.pack(fill='x',pady=12)
        ttk.Label(self.home,text='The range includes today and the preceding days; 1 = today in Colombia (UTC-05:00). Source ad timestamps are UTC (+00:00), converted to Colombia time for filtering. Dates are applied locally after collection; accepted ads are sorted newest first.\nCoverage is partial and ads may be missed. Stop interrupts the search. Collection stops at the configured ad, page or time limit. Limits apply separately to each enabled search.',wraplength=1000).pack(anchor='w')
        self.log=tk.Text(self.home,height=12,wrap='word',state='disabled')
        self.log.pack(fill='both',expand=True,pady=10)

    def build_audit(self):
        self.show_utc=tk.BooleanVar(value=False)
        self.date_sort=None
        self.audit.columnconfigure(0,weight=1)
        self.audit.rowconfigure(3,weight=1,minsize=45)
        self.audit.rowconfigure(5,weight=5,minsize=100)
        bar=ttk.Frame(self.audit); bar.grid(row=0,column=0,sticky='ew')
        ttk.Button(bar,text='Refresh queue',command=lambda:self.guard(self.refresh)).pack(side='left')
        ttk.Button(bar,text='Clear unreviewed',command=lambda:self.guard(self.clear_queue)).pack(side='left',padx=6)
        ttk.Label(bar,text='  Client ID (leave blank for all):').pack(side='left')
        self.client_filter=tk.StringVar()
        ttk.Entry(bar,textvariable=self.client_filter,width=24).pack(side='left',padx=8)
        self.queue_filters=FilterBar(self.audit,lambda:self.guard(self.refresh))
        self.queue_filters.grid(row=1,column=0,sticky='ew',pady=(5,0))
        self.queue_filters.grid_remove()
        ttk.Button(bar,text='Show / hide filters',command=self.toggle_review_filters).pack(side='right')
        self.review_summary=tk.StringVar(value='Saved results load automatically. Dates refer to observations in Colombia.')
        self.review_summary_label=ttk.Label(self.audit,textvariable=self.review_summary,wraplength=1000)
        self.review_summary_label.grid(row=2,column=0,sticky='ew',pady=(2,4))
        table_frame=ttk.Frame(self.audit); table_frame.grid(row=3,column=0,sticky='nsew')
        table_frame.columnconfigure(0,weight=1); table_frame.rowconfigure(0,weight=1)
        self.queue_table=ttk.Treeview(table_frame,columns=('priority','start','client','ad','advertiser','reason'),show='headings',height=4)
        for col,label,width in [('priority','Priority',65),('start','Ad start date',155),('client','Client',130),('ad','Ad',150),('advertiser','Advertiser',150),('reason','Reason',400)]:
            self.queue_table.heading(col,text=label); self.queue_table.column(col,width=width,minwidth=55)
        self.queue_table.heading('start',command=lambda:self.guard(self.sort_by_date))
        self.queue_table.grid(row=0,column=0,sticky='nsew')
        queue_y=ttk.Scrollbar(table_frame,orient='vertical',command=self.queue_table.yview)
        queue_y.grid(row=0,column=1,sticky='ns')
        queue_x=ttk.Scrollbar(table_frame,orient='horizontal',command=self.queue_table.xview)
        queue_x.grid(row=1,column=0,sticky='ew')
        self.queue_table.configure(yscrollcommand=queue_y.set,xscrollcommand=queue_x.set)
        self.queue_table.bind('<<TreeviewSelect>>',lambda event:self.guard(self.show_selected))
        navigation=ttk.Frame(self.audit); navigation.grid(row=4,column=0,sticky='ew',pady=5)
        ttk.Button(navigation,text='Previous',command=lambda:self.guard(lambda:self.navigate(-1))).pack(side='left')
        ttk.Button(navigation,text='Next',command=lambda:self.guard(lambda:self.navigate(1))).pack(side='left',padx=6)
        ttk.Checkbutton(navigation,text='Show dates in UTC',variable=self.show_utc,command=lambda:self.guard(self.change_display_timezone)).pack(side='left',padx=6)
        self.position=tk.StringVar(value='No ads selected')
        ttk.Label(navigation,textvariable=self.position).pack(side='left',padx=10)
        ttk.Button(navigation,text='All information',command=self.open_all_information).pack(side='left',padx=5)
        ttk.Button(navigation,text='History / corrections / reports',command=lambda:self.guard(self.open_history)).pack(side='right')
        self.card=AdCard(self.audit,on_open=self.open_library)
        self.card.grid(row=5,column=0,sticky='nsew')
        self.detail=self.card.body
        self.decision_buttons=[]
        self.review_actions=ttk.Frame(self.audit); self.review_actions.grid(row=6,column=0,sticky='ew',pady=(6,3))
        for column,(label,decision) in enumerate([('Spam (this ad)','spam'),('Flag advertiser','attack'),('Keep pending','pending')]):
            button=ttk.Button(self.review_actions,text=label,command=lambda d=decision:self.guard(lambda:self.classify(d)))
            button.grid(row=0,column=column,sticky='ew',padx=3,pady=2)
            self.review_actions.columnconfigure(column,weight=1)
            self.decision_buttons.append(button)
        ttk.Button(self.review_actions,text='Local evidence',command=lambda:self.guard(self.open_evidence)).grid(row=1,column=0,sticky='ew',padx=3,pady=2)
        ttk.Button(self.review_actions,text='Open in Meta Ad Library',command=self.open_library).grid(row=1,column=1,columnspan=2,sticky='ew',padx=3,pady=2)
        self.review_notice=ttk.Label(self.audit,text='Conflicts require administrative review. Reports to Meta are submitted manually.',wraplength=1000)
        self.review_notice.grid(row=7,column=0,sticky='ew',pady=(2,0))
        self.audit.bind('<Configure>',lambda event:self.resize_review(event.width))

    def toggle_review_filters(self):
        if self.queue_filters.winfo_manager(): self.queue_filters.grid_remove()
        else: self.queue_filters.grid()

    def resize_review(self,width):
        self.review_notice.configure(wraplength=max(200,width-24))
        self.review_summary_label.configure(wraplength=max(200,width-24))

    def auto_refresh(self):
        if self.busy: return
        if not self.database.exists():
            self.review_summary.set('No saved results yet. Run a search from Search setup.')
            self.set_detail('No saved results yet. Run a search to populate Ad review.')
            return
        try:
            self.refresh()
        except Exception as exc:
            self.review_summary.set('Unable to load saved results. Use Refresh queue to retry.')
            self.set_detail(str(exc))

    def review_tab_changed(self,event=None):
        if self.tabs.select()==str(self.audit): self.auto_refresh()

    def guard(self, action):
        try: return action()
        except Exception as exc: messagebox.showerror('Unable to complete the action',str(exc),parent=self)

    def load(self):
        filename=filedialog.askopenfilename(parent=self,title='Select a search list or manifest',initialdir=self.root_dir/'profiles',filetypes=[('JSON','*.json')])
        if filename: self.guard(lambda:self.load_path(filename))

    def load_path(self, filename):
        if self.busy: raise ValueError('Wait for the current search to finish')
        document=read_json(filename)
        if document.get('type')=='editable_search_list':
            profiles=[validate_profile(p) for p in document['profiles']]
            plan=SearchPlan(profiles,Path(document.get('output_directory',self.root_dir/'data/results')))
            days=document.get('days_to_review',1)
            if type(days) is not int or not 1<=days<=90: raise ValueError('Days to review must be between 1 and 90')
            loaded_days=days
            loaded_limits=validate_limits(document.get('collection_limits',{}))
        else:
            plan=load_manifest(filename)
        self.search_rows.from_profiles(plan.profiles)
        self.plan=plan
        if document.get('type')=='editable_search_list':
            self.loading_limits=True
            try:
                self.days.set(str(loaded_days))
                for key,value in loaded_limits.items(): self.limit_values[key].set(str(value))
            finally: self.loading_limits=False
        self.render_searches()
        self.status.set(f'{len(self.search_rows.rows)} searches loaded. Output folder: {plan.output_directory}')

    def render_searches(self):
        self.profile_table.delete(*self.profile_table.get_children())
        for row in self.search_rows.rows:
            self.profile_table.insert('','end',iid=row['id'],values=('[X]' if row['enabled'] else '[ ]',row['country'],row['criterion'],'Delete'))
        self.autosave_searches()

    def select_search(self):
        selected=self.profile_table.selection()
        if not selected: return
        row=self.search_rows.get(selected[0])
        self.row_country.set(row['country']); self.row_criterion.set(row['criterion']); self.row_enabled.set(row['enabled'])

    def add_search(self):
        if self.busy: raise ValueError('Wait for the current search to finish')
        self.search_rows.add(self.row_country.get(),self.row_criterion.get(),self.row_enabled.get())
        self.render_searches(); self.row_criterion.set('')

    def update_search(self):
        if self.busy: raise ValueError('Wait for the current search to finish')
        selected=self.profile_table.selection()
        if not selected: raise ValueError('Select a search to edit')
        row_id=selected[0]
        self.search_rows.update(row_id,self.row_country.get(),self.row_criterion.get(),self.row_enabled.get())
        self.render_searches(); self.profile_table.selection_set(row_id)

    def toggle_search(self):
        if self.busy: return
        selected=self.profile_table.selection()
        if selected:
            row=self.search_rows.get(selected[0]); row['enabled']=not row['enabled']
            self.render_searches(); self.profile_table.selection_set(row['id']); self.select_search()

    def delete_search(self):
        if self.busy: return
        selected=self.profile_table.selection()
        if selected and messagebox.askyesno('Delete search','Delete the selected search?',parent=self):
            self.search_rows.remove(selected[0]); self.render_searches()

    def search_click(self,event):
        row=self.profile_table.identify_row(event.y)
        column=self.profile_table.identify_column(event.x)
        if not row: return
        self.profile_table.selection_set(row)
        if column=='#1': self.guard(self.toggle_search)
        elif column=='#4': self.guard(self.delete_search)

    def enabled_changed(self):
        if self.busy:
            self.select_search()
            return
        selected=self.profile_table.selection()
        if selected:
            row=self.search_rows.get(selected[0])
            row['enabled']=self.row_enabled.get()
            self.profile_table.item(row['id'],values=('[X]' if row['enabled'] else '[ ]',row['country'],row['criterion'],'Delete'))
            self.autosave_searches()
        # Without a selected row, the checkbox sets the enabled state of the next Add.

    def search_list_document(self):
        import copy
        profiles=[]
        for row in self.search_rows.rows:
            profile=copy.deepcopy(row['profile'])
            profile.update(country=row['country'].lower(),enabled=row['enabled'])
            profile['criteria']=[{'query':row['criterion'],'enabled':True}]
            profile['days_to_review']=int(self.days.get())
            profile['search']['date_range']={'mode':'rolling_days'}
            profiles.append(validate_profile(profile))
        days=int(self.days.get())
        if not 1<=days<=90: raise ValueError('Days to review must be between 1 and 90')
        return {'schema_version':'1.0','type':'editable_search_list','days_to_review':days,
                'output_directory':str(self.plan.output_directory),'profiles':profiles,'collection_limits':self.collection_limits()}

    def collection_limits(self):
        values={}
        for key,variable in self.limit_values.items():
            try: values[key]=int(variable.get())
            except ValueError: raise ValueError(f'{key}: enter a whole number') from None
        return validate_limits(values)

    def save_limits_change(self):
        try: self.collection_limits()
        except ValueError: return
        if not getattr(self,'loading_limits',False): self.guard(self.autosave_searches)

    def autosave_searches(self):
        if not getattr(self,'loading_limits',False):
            write_json(self.search_list_file,self.search_list_document())

    def save_days_change(self):
        # Spinbox editing may temporarily leave an empty value; save once valid.
        try:
            days=int(self.days.get())
        except ValueError: return
        if 1<=days<=90: self.save_limits_change()

    def save_search_list(self):
        if self.busy: raise ValueError('Wait for the current search to finish')
        filename=filedialog.asksaveasfilename(parent=self,title='Export search list',initialdir=self.root_dir/'data',defaultextension='.json',filetypes=[('JSON','*.json')])
        if filename:
            write_json(filename,self.search_list_document())
            self.status.set(f'Search list exported: {filename}')

    def start(self):
        if self.busy: return
        def setup():
            limits=self.collection_limits()
            self.autosave_searches()
            actor='local_operator'
            days=int(self.days.get())
            if not 1<=days<=90: raise ValueError('Days to review must be between 1 and 90')
            queries=self.search_rows.queries(days)
            if not queries: raise ValueError('Enable at least one search')
            snapshot=load_lists(self.lists_dir)
            with connect(self.database) as db:
                initialize(db); snapshot=merge_database_lists(db,snapshot)
            output=self.plan.output_directory
            from tempfile import NamedTemporaryFile
            output.mkdir(parents=True,exist_ok=True)
            with NamedTemporaryFile(dir=output,prefix='.write-check-'):
                pass
            self.busy=True; self.cancel.clear(); self.set_busy(True)
            threading.Thread(target=self.worker,args=(queries,output,actor,snapshot,limits),daemon=True).start()
        self.guard(setup)

    def worker(self,queries,output,actor,snapshot,limits=None):
        try:
            for index,profile in enumerate(queries,1):
                if self.cancel.is_set(): break
                self.events.put(('log',f'{index}/{len(queries)} · {profile["client_name"]}: {profile["criteria"][0]["query"]}'))
                result=collect(profile,**(limits or DEFAULT_LIMITS),cancel_event=self.cancel,
                    progress_callback=lambda progress:self.events.put(('progress',progress)))
                self.events.put(('log',f"Stopped: {result.get('stop_reason','unknown')}; pages: {result.get('connector_stats',{}).get('pages_fetched','not available')}"))
                self.events.put(('log',f"Post-filtered: {result['scanned_ads']} received; {result['returned_ads']} accepted; {result['excluded_by_date']} outside range. Newest ad starts first."))
                result.update(client_id=profile['client_id'],client_name=profile['client_name'])
                result['list_evaluation']=evaluate_result(result,snapshot)
                path=output/result['run_id']/'results.json'
                summary,summary_path=persist_result(result,path,self.database,actor=actor)
                self.events.put(('log',f'{result["status"]}: {len(result["ads"])} ads; SQLite {summary["persistence"]["status"]}\n{summary_path}'))
                if summary['errors']: self.events.put(('log',json.dumps(summary['errors'],ensure_ascii=False)))
                if result['status']=='cancelled': break
        except Exception as exc: self.events.put(('error',str(exc)))
        finally: self.events.put(('done',None))

    def poll(self):
        try:
            while True:
                kind,value=self.events.get_nowait()
                if kind=='log':
                    self.log.configure(state='normal'); self.log.insert('end',value+'\n'); self.log.see('end'); self.log.configure(state='disabled'); self.status.set(value)
                elif kind=='progress':
                    self.status.set(f'{value["elapsed_seconds"]}s | Received: {value["received_ads"]} | In date range: {value["accepted_ads"] if value["accepted_ads"] is not None else "pending"} | Outside date range: {value["excluded_by_date"] if value["excluded_by_date"] is not None else "pending"} | {value["message"]}')
                elif kind=='error': messagebox.showerror('Search error',value,parent=self)
                elif kind=='done':
                    self.busy=False; self.set_busy(False); self.status.set('Searches finished. See the log and run summaries.'); self.guard(self.refresh)
        except queue.Empty: pass
        self.timer=self.after(150,self.poll)

    def set_busy(self,busy):
        self.run_button.configure(state='disabled' if busy else 'normal')
        self.load_button.configure(state='disabled' if busy else 'normal')
        self.stop_button.configure(state='normal' if busy else 'disabled')
        for button in [self.add_button,self.update_button,self.enabled_button]: button.configure(state='disabled' if busy else 'normal')
        for button in self.decision_buttons: button.configure(state='disabled' if busy else 'normal')
        if busy: self.progress.start()
        else: self.progress.stop()

    def refresh(self):
        old=self.selected
        old_index=next((i for i,row in enumerate(self.rows) if row is old),0)
        with connect(self.database) as db:
            initialize(db)
            result=database_queue(db,load_lists(self.lists_dir),client_id=self.client_filter.get().strip() or None,filters=self.queue_filters.get())
            last_run=db.execute('SELECT started_at,payload_json FROM runs ORDER BY started_at DESC,run_id DESC LIMIT 1').fetchone()
        self.rows=result['queue']+result['conflicts']; self.selected=None
        for row in self.rows:
            row['reason']=REASONS.get(row['state'],row['reason'])
        if self.date_sort:
            dated=[r for r in self.rows if ad_start(r) is not None]
            missing=[r for r in self.rows if ad_start(r) is None]
            self.rows=sorted(dated,key=lambda r:ad_start(r).timestamp(),reverse=self.date_sort=='desc')+missing
        self.queue_table.heading('start',text=('Ad start (UTC)' if self.show_utc.get() else 'Ad start (UTC-05)')+(' (newest)' if self.date_sort=='desc' else ' (oldest)' if self.date_sort else ''))
        self.queue_table.delete(*self.queue_table.get_children())
        for index,row in enumerate(self.rows):
            self.queue_table.insert('','end',iid=str(index),values=(row['priority'] or 'Conflict',ad_start(row,'UTC' if self.show_utc.get() else 'America/Bogota').strftime('%Y-%m-%d %H:%M') if ad_start(row) else 'Not available',row['client_id'] or 'Global',row['ad_id'],row['advertiser_id'] or 'Not available',row['reason']))
        self.review_summary.set(f'{len(result["queue"])} pending; {len(result["conflicts"])} conflicts. Click Ad start date to sort. Source timestamps: UTC. Use Show dates in UTC to switch the display; date filters use observation dates in Colombia.')
        if not self.rows and last_run is not None:
            payload=json.loads(last_run['payload_json'])
            errors=payload.get('errors',[])
            explanation=' No accepted ads in the last run.' if not payload.get('ads') else ' Cases may already be reviewed, excluded by lists or hidden by filters.'
            if errors: explanation+=' Source error: '+str(errors[0].get('type','Unknown source error'))
            self.review_summary.set(f'No pending ads match the current filters. Last saved run: {last_run["started_at"]}.'+explanation)
        self.set_detail('Select an ad to review its evidence.\n'+f'{len(result["queue"])} to review; {len(result["conflicts"])} conflicts.')
        if not self.rows and last_run is not None:
            self.set_information({'Last saved search execution':payload,'Review queue note':'Only accepted, unreviewed ads appear here. Records excluded by date remain diagnostics, not review cases.'})
        self.position.set('No ads selected')
        if self.rows:
            preserved=next((i for i,row in enumerate(self.rows) if old and
                (row['source'],row['ad_id'],row['client_id'])==(old['source'],old['ad_id'],old['client_id'])),
                min(old_index,len(self.rows)-1))
            self.queue_table.selection_set(str(preserved)); self.queue_table.see(str(preserved))
            self.show_selected()

    def change_display_timezone(self):
        self.card.display_timezone='UTC' if self.show_utc.get() else 'America/Bogota'
        if self.database.exists(): self.refresh()
        else:
            self.queue_table.heading('start',text='Ad start (UTC)' if self.show_utc.get() else 'Ad start (UTC-05)')

    def sort_by_date(self):
        self.date_sort='asc' if self.date_sort=='desc' else 'desc'
        self.refresh()

    def clear_queue(self):
        if self.busy: raise ValueError('Wait for the search to finish')
        rows=[dict(r) for r in self.rows if not r.get('reviewed') and r['state']!='list_conflict']
        if not rows:
            messagebox.showinfo('Clear unreviewed','No unreviewed ads in the current queue.',parent=self)
            return
        if not messagebox.askyesno('Clear unreviewed',f'Remove {len(rows)} unreviewed ads matching the current filters from the queue? No category will be assigned. History is preserved. A later observation can return an ad to the queue.',parent=self): return
        with connect(self.database) as db:
            count=clear_unreviewed(db,rows,actor='local_operator')
        self.refresh()
        self.status.set(f'{count} unreviewed ads cleared without classification')

    def set_detail(self,text):
        self.analysis_information={}
        self.card.show_message(text)

    def set_information(self,data):
        self.set_detail('Select an ad to see its presentation card. Open All information for search results and diagnostics.')
        self.analysis_information=data

    def open_all_information(self):
        if not self.analysis_information: return
        window=InformationWindow(self,self.analysis_information)
        window.transient(self.master)

    def show_selected(self):
        selected=self.queue_table.selection()
        if not selected: return
        row=self.rows[int(selected[0])]; self.selected=row
        self.position.set(f'Ad {int(selected[0])+1} of {len(self.rows)}')
        with connect(self.database) as db:
            ad=db.execute('SELECT * FROM ads WHERE source=? AND ad_id=?',(row['source'],row['ad_id'])).fetchone()
            payload=json.loads(ad['payload_json'])
            cases=[case_detail(db,c['case_id']) for c in db.execute('SELECT case_id FROM review_cases WHERE source=? AND ad_id=?',(row['source'],row['ad_id'])).fetchall()]
            run_rows=db.execute('''SELECT DISTINCT r.run_id,r.started_at,r.payload_json FROM runs r
                JOIN ad_observations o ON o.run_id=r.run_id WHERE o.source=? AND o.ad_id=?
                ORDER BY r.started_at DESC,r.run_id DESC''',(row['source'],row['ad_id'])).fetchall()
            runs=[json.loads(run['payload_json']) for run in run_rows]
        ad_metadata=dict(ad); ad_metadata.pop('payload_json',None)
        self.set_information({'Ad identification and observations':ad_metadata,
                              'Ad content and all source fields':payload,
                              'Current queue evaluation':row,
                              'Review cases, evidence and history':cases,
                              'Related search results':runs})
        local_images=[e for case in cases for e in case['evidence'] if e.get('local_path') and e.get('type')=='local_image']
        self.card.show(payload,priority=row['priority'] or 'Conflict',evidence=local_images)


    def navigate(self,direction):
        if not self.rows: return
        selection=self.queue_table.selection()
        current=int(selection[0]) if selection else 0
        index=max(0,min(len(self.rows)-1,current+direction))
        self.queue_table.selection_set(str(index)); self.queue_table.see(str(index)); self.show_selected()

    def open_lists(self):
        if self.busy: raise ValueError('Wait for the search to finish before changing lists')
        window=ListsWindow(self,self.database,self.lists_dir,on_change=lambda:self.guard(self.refresh))
        window.transient(self.master); window.grab_set()

    def open_history(self):
        if self.busy: raise ValueError('Wait for the search to finish before editing case history')
        window=HistoryWindow(self,self.database,on_change=lambda:self.guard(self.refresh))
        window.transient(self.master); window.grab_set()


    def classify(self,decision):
        if self.busy: raise ValueError('Wait for the search to finish')
        row=self.selected
        if row is None: raise ValueError('Select an ad')
        if row['state']=='list_conflict': raise ValueError('Resolve the list conflict before classifying')
        actor='local_operator'
        reason={'spam':'Ad marked as spam by the reviewer',
                'attack':'Advertiser flagged by the reviewer',
                'pending':'Ad kept pending by the reviewer'}[decision]
        evidence=None; confirmation=None
        if decision=='attack':
            confirmation=row['advertiser_id']
            if not confirmation: raise ValueError('No verifiable advertiser ID is available')
            evidence=filedialog.askopenfilename(parent=self,title='Select an evidence file')
            if not evidence: return
        elif decision=='spam':
            confirmation=row['ad_id']
        with connect(self.database) as db:
            initialize(db)
            case_id=row.get('case_id') or open_case(db,row['source'],row['ad_id'],actor=actor,client_id=row['client_id'])['case_id']
            decide(db,case_id,decision,actor=actor,reason=reason,confirm_id=confirmation,evidence_file=evidence,lists=merge_database_lists(db,load_lists(self.lists_dir)))
        self.refresh(); self.status.set(f'Decision saved: {decision}')

    def open_evidence(self):
        if self.busy: raise ValueError('Wait for the search to finish')
        row=self.selected
        if row is None: raise ValueError('Select an ad first')
        if row['state']=='list_conflict': raise ValueError('Resolve the list conflict before creating a review case')
        with connect(self.database) as db:
            case_id=row.get('case_id') or open_case(db,row['source'],row['ad_id'],actor='local_operator',client_id=row['client_id'])['case_id']
        window=EvidenceWindow(self,self.database,case_id,self.root_dir/'data/evidence')
        window.transient(self.master); window.grab_set()

    def open_library(self):
        if self.selected:
            webbrowser.open('https://www.facebook.com/ads/library/?'+urlencode({'id':self.selected['ad_id']}))

    def close(self):
        if self.busy:
            self.cancel.set()
            messagebox.showinfo('Stopping','Stopping the search. Wait for received results to be saved before closing.',parent=self)
            return
        self.after_cancel(self.timer); self.master.destroy()


def main():
    import argparse
    parser=argparse.ArgumentParser(description='Brand Threat Monitor desktop application')
    parser.add_argument('--workspace',type=Path,default=Path.cwd())
    parser.add_argument('--check',action='store_true',help='Build and close the window without running searches')
    args=parser.parse_args()
    root=tk.Tk()
    if args.check: root.withdraw()
    app=Application(root,args.workspace)
    if args.check:
        root.update_idletasks(); app.close()
    else: root.mainloop()


if __name__=='__main__': main()
