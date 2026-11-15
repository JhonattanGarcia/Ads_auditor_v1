"""Interfaz de escritorio local con Tkinter y consultas en segundo plano."""

import json
import queue
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import ttk, filedialog, messagebox, simpledialog
from urllib.parse import urlencode

from ..config.profiles import load_manifest, SearchPlan, validate_profile, read_json
from .search_rows import SearchRows
from ..ingestion.service import write_json
from ..ingestion.collector import collect
from ..ingestion.service import persist_result
from ..lists.service import load_lists, merge_database_lists
from ..review.queue import database_queue, evaluate_result
from ..review.service import open_case, decide
from ..storage.database import connect, initialize


REASONS = {
    'known_black': 'Advertiser with prior findings; review this ad individually',
    'known_white': 'Authorized advertiser in this scope',
    'discarded_brown': 'This ad was previously discarded',
    'pending_review': 'No applicable history; human review required',
    'list_conflict': 'Whitelist/blacklist conflict; administrative review required',
}


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
        ttk.Label(self,textvariable=self.status,wraplength=1050).pack(fill='x',pady=(8,0))
        self.timer=self.after(150,self.poll)
        if self.search_list_file.exists():
            self.guard(lambda:self.load_path(self.search_list_file))
        self.days.trace_add('write',lambda *args:self.save_days_change())

    def build_home(self):
        bar=ttk.Frame(self.home); bar.pack(fill='x')
        self.load_button=ttk.Button(bar,text='Load search list',command=self.load)
        self.load_button.pack(side='left')
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
        self.progress=ttk.Progressbar(self.home,mode='indeterminate'); self.progress.pack(fill='x',pady=12)
        ttk.Label(self.home,text='The range includes today and the preceding days; 1 = today in Colombia. Dates are requested from Meta and checked locally.\nCoverage is partial and ads may be missed. Stop interrupts the search. Searches stop after 120s or 45s without receiving ads.',wraplength=1000).pack(anchor='w')
        self.log=tk.Text(self.home,height=12,wrap='word',state='disabled')
        self.log.pack(fill='both',expand=True,pady=10)

    def build_audit(self):
        bar=ttk.Frame(self.audit); bar.pack(fill='x')
        ttk.Button(bar,text='Refresh queue',command=lambda:self.guard(self.refresh)).pack(side='left')
        ttk.Label(bar,text='  Client ID (leave blank for all):').pack(side='left')
        self.client_filter=tk.StringVar()
        ttk.Entry(bar,textvariable=self.client_filter,width=24).pack(side='left',padx=8)
        self.queue_table=ttk.Treeview(self.audit,columns=('priority','client','ad','advertiser','reason'),show='headings',height=7)
        for col,label,width in [('priority','Priority',70),('client','Client',150),('ad','Ad',160),('advertiser','Advertiser',160),('reason','Reason',400)]:
            self.queue_table.heading(col,text=label); self.queue_table.column(col,width=width)
        self.queue_table.pack(fill='x',pady=10)
        self.queue_table.bind('<<TreeviewSelect>>',lambda event:self.guard(self.show_selected))
        self.detail=tk.Text(self.audit,height=12,wrap='word',state='disabled')
        self.detail.pack(fill='both',expand=True)
        self.decision_buttons=[]
        actions=ttk.Frame(self.audit); actions.pack(fill='x',pady=10)
        for label,decision in [('Spam (this ad)','spam'),('Flag advertiser','attack'),('Keep pending','pending')]:
            button=ttk.Button(actions,text=label,command=lambda d=decision:self.guard(lambda:self.classify(d)))
            button.pack(side='left',padx=4); self.decision_buttons.append(button)
        ttk.Button(actions,text='Open in Meta Ad Library',command=self.open_library).pack(side='left',padx=10)
        ttk.Label(self.audit,text='Conflicts require administrative review. Reports to Meta are submitted manually.',wraplength=1000).pack(anchor='w')

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
        else:
            plan=load_manifest(filename)
        self.search_rows.from_profiles(plan.profiles)
        self.plan=plan
        if document.get('type')=='editable_search_list':
            self.days.set(str(loaded_days))
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
                'output_directory':str(self.plan.output_directory),'profiles':profiles}

    def autosave_searches(self):
        write_json(self.search_list_file,self.search_list_document())

    def save_days_change(self):
        # Spinbox editing may temporarily leave an empty value; save once valid.
        try:
            days=int(self.days.get())
        except ValueError: return
        if 1<=days<=90: self.guard(self.autosave_searches)

    def save_search_list(self):
        if self.busy: raise ValueError('Wait for the current search to finish')
        filename=filedialog.asksaveasfilename(parent=self,title='Export search list',initialdir=self.root_dir/'data',defaultextension='.json',filetypes=[('JSON','*.json')])
        if filename:
            write_json(filename,self.search_list_document())
            self.status.set(f'Search list exported: {filename}')

    def start(self):
        if self.busy: return
        def setup():
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
            threading.Thread(target=self.worker,args=(queries,output,actor,snapshot),daemon=True).start()
        self.guard(setup)

    def worker(self,queries,output,actor,snapshot):
        try:
            for index,profile in enumerate(queries,1):
                if self.cancel.is_set(): break
                self.events.put(('log',f'{index}/{len(queries)} · {profile["client_name"]}: {profile["criteria"][0]["query"]}'))
                result=collect(profile,max_scan=100,cancel_event=self.cancel,
                    progress_callback=lambda progress:self.events.put(('progress',progress)))
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
                    self.status.set(f'{value["elapsed_seconds"]}s | Received: {value["received_ads"]} | In date range: {value["accepted_ads"]} | Outside date range: {value["excluded_by_date"]} | {value["message"]}')
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
        with connect(self.database) as db:
            initialize(db)
            result=database_queue(db,load_lists(self.lists_dir),client_id=self.client_filter.get().strip() or None)
        self.rows=result['queue']+result['conflicts']; self.selected=None
        for row in self.rows:
            row['reason']=REASONS.get(row['state'],row['reason'])
        self.queue_table.delete(*self.queue_table.get_children())
        for index,row in enumerate(self.rows):
            self.queue_table.insert('','end',iid=str(index),values=(row['priority'] or 'Conflict',row['client_id'] or 'Global',row['ad_id'],row['advertiser_id'] or 'Not available',row['reason']))
        self.set_detail('Select an ad to review its evidence.\n'+f'{len(result["queue"])} to review; {len(result["conflicts"])} conflicts.')

    def set_detail(self,text):
        self.detail.configure(state='normal'); self.detail.delete('1.0','end'); self.detail.insert('1.0',text); self.detail.configure(state='disabled')

    def show_selected(self):
        selected=self.queue_table.selection()
        if not selected: return
        row=self.rows[int(selected[0])]; self.selected=row
        with connect(self.database) as db:
            ad=db.execute('SELECT * FROM ads WHERE source=? AND ad_id=?',(row['source'],row['ad_id'])).fetchone()
            payload=json.loads(ad['payload_json'])
            cases=[dict(c) for c in db.execute('SELECT * FROM review_cases WHERE source=? AND ad_id=?',(row['source'],row['ad_id']))]
        self.set_detail(f'Ad: {row["ad_id"]}\nAdvertiser: {row["advertiser_id"] or "Not available"}\nReason: {row["reason"]}\nFirst observed: {ad["first_observed_at"]}\nLast observed: {ad["last_observed_at"]}\n\nCollected content (missing fields = unavailable):\n'+json.dumps(payload,ensure_ascii=False,indent=2)+'\n\nPrevious cases:\n'+json.dumps(cases,ensure_ascii=False,indent=2))

    def classify(self,decision):
        if self.busy: raise ValueError('Wait for the search to finish')
        row=self.selected
        if row is None: raise ValueError('Select an ad')
        if row['state']=='list_conflict': raise ValueError('Resolve the list conflict before classifying')
        actor='local_operator'
        reason=simpledialog.askstring('Reason','Enter the reason for this decision:',parent=self)
        if not reason or not reason.strip(): return
        evidence=None; confirmation=None
        if decision=='attack':
            confirmation=row['advertiser_id']
            if not confirmation: raise ValueError('No verifiable advertiser ID is available')
            if not messagebox.askyesno('Confirm advertiser flag',f'Flag advertiser {confirmation}: future ads will be prioritized. Confirm?',parent=self): return
            evidence=filedialog.askopenfilename(parent=self,title='Select an evidence file')
            if not evidence: return
        elif decision=='spam':
            confirmation=row['ad_id']
            if not messagebox.askyesno('Confirm spam',f'Discard only ad {confirmation}. Confirm?',parent=self): return
        with connect(self.database) as db:
            initialize(db)
            case_id=row.get('case_id') or open_case(db,row['source'],row['ad_id'],actor=actor,client_id=row['client_id'])['case_id']
            decide(db,case_id,decision,actor=actor,reason=reason,confirm_id=confirmation,evidence_file=evidence,lists=load_lists(self.lists_dir))
        self.refresh(); self.status.set(f'Decision saved: {decision}')

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
