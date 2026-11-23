"""Administracion local de listas sin modificar los JSON de origen."""

import tkinter as tk
from tkinter import ttk,messagebox,simpledialog,filedialog
from ..storage.database import connect,initialize
from ..lists.service import load_lists
from ..lists.admin import list_entries,authorize,deactivate,resolve_conflict


class ListsWindow(tk.Toplevel):
    def __init__(self,parent,database,lists_dir,on_change=None):
        """Initialize view widgets and callbacks."""
        super().__init__(parent)
        self.database=database; self.lists_dir=lists_dir; self.on_change=on_change; self.rows=[]
        self.title('List administration'); self.geometry('1080x650')
        ttk.Label(self,text='Active JSON and SQLite entries. Deactivation preserves history and does not edit source JSON files.',wraplength=1030).pack(anchor='w',padx=12,pady=10)
        self.table=ttk.Treeview(self,columns=('kind','source','id','scope','origin','reason'),show='headings',height=13)
        for col,title,width in [('kind','List',110),('source','Source',120),('id','Entity ID',180),('scope','Scope',180),('origin','Origin',70),('reason','Reason',330)]:
            self.table.heading(col,text=title); self.table.column(col,width=width)
        self.table.pack(fill='both',expand=True,padx=12)
        self.table.bind('<<TreeviewSelect>>',lambda event:self.select())
        fields=ttk.Frame(self); fields.pack(fill='x',padx=12,pady=10)
        self.source=tk.StringVar(value='meta_ad_library'); self.entity=tk.StringVar(); self.client=tk.StringVar()
        for col,(label,value) in enumerate([('Source',self.source),('Advertiser ID',self.entity),('Client ID (blank = global)',self.client)]):
            ttk.Label(fields,text=label).grid(row=0,column=col,sticky='w',padx=4)
            ttk.Entry(fields,textvariable=value,width=28).grid(row=1,column=col,padx=4,sticky='ew')
            fields.columnconfigure(col,weight=1)
        actions=ttk.Frame(self); actions.pack(fill='x',padx=12,pady=8)
        for label,action in [('Refresh',self.refresh),('Authorize advertiser',self.authorize),('Deactivate selected',self.deactivate),('Resolve conflict',self.resolve)]:
            ttk.Button(actions,text=label,command=lambda fn=action:self.guard(fn)).pack(side='left',padx=4)
        exchange=ttk.Frame(self); exchange.pack(fill='x',padx=12,pady=4)
        ttk.Button(exchange,text='Import JSON / CSV',command=lambda:self.guard(self.import_file)).pack(side='left',padx=4)
        ttk.Button(exchange,text='Export JSON',command=lambda:self.guard(lambda:self.export_file('json'))).pack(side='left',padx=4)
        ttk.Button(exchange,text='Export CSV',command=lambda:self.guard(lambda:self.export_file('csv'))).pack(side='left',padx=4)
        ttk.Label(self,text='Blacklist requires a reviewed case and evidence: use Flag advertiser in Ad review. Global changes affect other clients too.',wraplength=1030).pack(anchor='w',padx=12,pady=10)
        self.guard(self.refresh)

    def guard(self,action):
        """Run a UI callback and display any raised error in a parented dialog."""
        try: action()
        except Exception as exc: messagebox.showerror('Unable to update lists',str(exc),parent=self)

    def refresh(self):
        """Reload filtered saved records and refresh the view while preserving selection where possible."""
        with connect(self.database) as db:
            initialize(db); self.rows=list_entries(db,load_lists(self.lists_dir))
        self.table.delete(*self.table.get_children())
        for index,row in enumerate(self.rows):
            scope=row['scope']['type'] if row['scope']['type']=='global' else 'client:'+row['scope']['client_id']
            self.table.insert('','end',iid=str(index),values=(row['kind'],row['source'],row['entity_id'],scope,row['origin'],row['reason']))

    def select(self):
        """Populate full details from the currently selected row or nested information field."""
        selection=self.table.selection()
        if not selection: return
        row=self.rows[int(selection[0])]
        self.source.set(row['source']); self.entity.set(row['entity_id'])
        self.client.set(row['scope'].get('client_id',''))

    def reason(self):
        """Ask for a nonempty administrative justification before modifying effective lists."""
        return simpledialog.askstring('Reason','Provide a reason for this list change:',parent=self)

    def changed(self):
        """Refresh list administration and notify its parent after a successful modification."""
        self.refresh()
        if self.on_change: self.on_change()

    def authorize(self):
        """Collect publisher, scope and reason inputs and add an audited whitelist authorization."""
        reason=self.reason()
        if not reason or not reason.strip(): return
        entity=self.entity.get().strip(); client=self.client.get().strip()
        scope={'type':'client','client_id':client} if client else {'type':'global'}
        if not messagebox.askyesno('Authorize advertiser',f'Whitelist advertiser {entity} for {client or "ALL clients"}?',parent=self): return
        with connect(self.database) as db:
            authorize(db,load_lists(self.lists_dir),self.source.get().strip(),entity,scope,
                      actor='local_operator',reason=reason,confirm_id=entity)
        self.changed()

    def deactivate(self):
        """Confirm and deactivate the selected effective entry with an administrative audit reason."""
        selected=self.table.selection()
        if not selected: raise ValueError('Select a list entry first')
        row=self.rows[int(selected[0])]; reason=self.reason()
        if not reason or not reason.strip(): return
        if not messagebox.askyesno('Deactivate entry',f'Deactivate {row["kind"]} entry {row["entity_id"]} in scope {row["scope"]}? Global entries affect all clients.',parent=self): return
        with connect(self.database) as db:
            deactivate(db,load_lists(self.lists_dir),row['kind'],row['source'],row['entity_id'],row['scope'],
                       actor='local_operator',reason=reason,confirm_id=row['entity_id'])
        self.changed()

    def resolve(self):
        """Explicitly select which side of a whitelist/blacklist conflict to keep."""
        entity=self.entity.get().strip(); client=self.client.get().strip() or None
        choice=messagebox.askyesnocancel('Resolve list conflict',f'Advertiser {entity}; client context {client or "global"}.\nYes: keep whitelist. No: keep blacklist. Cancel: no change.\nAll opposing entries applying here will be deactivated, including global entries affecting other clients.',parent=self)
        if choice is None: return
        reason=self.reason()
        if not reason or not reason.strip(): return
        with connect(self.database) as db:
            resolve_conflict(db,load_lists(self.lists_dir),self.source.get().strip(),entity,client,
                             'whitelist' if choice else 'blacklist',actor='local_operator',reason=reason,confirm_id=entity)
        self.changed()


    def import_file(self):
        """Preview and validate a selected list file before the backed-up audited import."""
        from ..lists.exchange import read_lists_file,plan_import,import_lists
        path=filedialog.askopenfilename(parent=self,title='Import list entries',filetypes=[('JSON or CSV','*.json *.csv')])
        if not path: return
        documents=read_lists_file(path)
        with connect(self.database) as db:
            plan=plan_import(db,load_lists(self.lists_dir),documents)
        if not messagebox.askyesno('Preview list import',f'Add {plan["add_count"]} entries; skip {plan["skipped"]} existing entries.\nAll three list types are validated. A SQLite backup is required before changes.\nApply this import?',parent=self): return
        reason=self.reason()
        if not reason or not reason.strip(): return
        with connect(self.database) as db:
            result=import_lists(db,load_lists(self.lists_dir),documents,path,self.database.parent.parent/'backups',actor='local_operator',reason=reason)
        messagebox.showinfo('Import complete',str(result),parent=self)
        self.changed()

    def export_file(self,format):
        """Export effective lists to a chosen JSON or CSV destination without overwriting existing files."""
        from ..lists.exchange import export_lists
        path=filedialog.asksaveasfilename(parent=self,title='Export effective lists',initialdir=self.database.parent.parent/'exports',defaultextension='.'+format,filetypes=[(format.upper(),'*.'+format)])
        if not path: return
        with connect(self.database) as db:
            output=export_lists(db,load_lists(self.lists_dir),path)
        messagebox.showinfo('Lists exported',str(output),parent=self)
