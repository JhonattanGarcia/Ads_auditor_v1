"""Ventana de historicos, correcciones y reportes externos manuales."""

import json
import tkinter as tk
from datetime import datetime
from zoneinfo import ZoneInfo
from tkinter import ttk, messagebox, simpledialog, filedialog

from ..storage.database import connect, initialize
from ..review.service import case_detail, list_cases, reopen_case
from ..review.reports import record_report
from ..history.service import list_runs
from .filters import FilterBar
from .evidence import EvidenceWindow
from .information import format_information


class HistoryWindow(tk.Toplevel):
    def __init__(self,parent,database,on_change=None):
        """Initialize view widgets and callbacks."""
        super().__init__(parent)
        self.database=database
        self.on_change=on_change
        self.case_id=None
        self.title('History and case management'); self.geometry('1050x700')
        self.protocol('WM_DELETE_WINDOW',self.destroy)
        self.filters=FilterBar(self,lambda:self.guard(self.refresh))
        self.filters.pack(fill='x',padx=10,pady=(8,0))
        ttk.Label(self,text='Dates are inclusive, Colombia time: run start for Search runs; observation date for Review cases.').pack(anchor='w',padx=12)
        self.tabs=ttk.Notebook(self); self.tabs.pack(fill='both',expand=True,padx=10,pady=10)
        runs=ttk.Frame(self.tabs,padding=8); cases=ttk.Frame(self.tabs,padding=8)
        self.tabs.add(runs,text='Search runs'); self.tabs.add(cases,text='Review cases')
        self.run_table=ttk.Treeview(runs,columns=('date','client','query','status','coverage'),show='headings',height=7)
        for col,title in [('date','Started'),('client','Client'),('query','Search criteria'),('status','Status'),('coverage','Coverage')]:
            self.run_table.heading(col,text=title); self.run_table.column(col,width=170)
        self.run_table.pack(fill='x'); self.run_table.bind('<<TreeviewSelect>>',lambda event:self.guard(self.show_run))
        self.run_detail=self.text_area(runs)
        bar=ttk.Frame(cases); bar.pack(fill='x',pady=(0,8))
        ttk.Label(bar,text='Client ID (blank for all):').pack(side='left')
        self.client=tk.StringVar(); ttk.Entry(bar,textvariable=self.client,width=25).pack(side='left',padx=8)
        ttk.Button(bar,text='Refresh',command=lambda:self.guard(self.refresh)).pack(side='left')
        self.case_table=ttk.Treeview(cases,columns=('client','ad','decision','status'),show='headings',height=7)
        for col,title in [('client','Client'),('ad','Ad ID'),('decision','Decision'),('status','Status')]:
            self.case_table.heading(col,text=title); self.case_table.column(col,width=210)
        self.case_table.pack(fill='x'); self.case_table.bind('<<TreeviewSelect>>',lambda event:self.guard(self.show_case))
        self.case_detail=self.text_area(cases)
        actions=ttk.Frame(cases); actions.pack(fill='x',pady=8)
        ttk.Button(actions,text='Correct and reopen case',command=lambda:self.guard(self.correct)).pack(side='left',padx=4)
        ttk.Button(actions,text='Record a manual report',command=lambda:self.guard(self.report_dialog)).pack(side='left',padx=4)
        ttk.Button(actions,text='Local evidence',command=lambda:self.guard(self.open_evidence)).pack(side='left',padx=4)
        for format in ['json','csv']:
            ttk.Button(actions,text='Export '+format.upper(),command=lambda f=format:self.guard(lambda:self.export(f))).pack(side='left',padx=4)
        ttk.Label(cases,text='Reports are submitted outside this application. Recording a report does not confirm removal.').pack(anchor='w')
        self.guard(self.refresh)

    def text_area(self,parent):
        """Create a read-only history text area with scrolling support."""
        frame=ttk.Frame(parent); frame.pack(fill='both',expand=True,pady=8)
        text=tk.Text(frame,wrap='word',state='disabled')
        scroll=ttk.Scrollbar(frame,command=text.yview); text.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right',fill='y'); text.pack(fill='both',expand=True)
        return text

    def show_text(self,widget,value):
        """Replace history details while preserving the text widget's read-only state."""
        widget.configure(state='normal'); widget.delete('1.0','end')
        widget.insert('1.0',format_information(value)); widget.configure(state='disabled')

    def guard(self,action):
        """Run a UI callback and display any raised error in a parented dialog."""
        try: return action()
        except Exception as exc: messagebox.showerror('Unable to complete the action',str(exc),parent=self)

    def refresh(self):
        """Reload filtered saved records and refresh the view while preserving selection where possible."""
        selected=self.case_id
        filters=self.filters.get()
        with connect(self.database) as db:
            initialize(db)
            self.runs={row['run_id']:row for row in list_runs(db,client_id=self.client.get().strip() or None,filters=filters)}
            cases=list_cases(db,client_id=self.client.get().strip() or None,filters=filters)
        self.run_table.delete(*self.run_table.get_children())
        self.show_text(self.run_detail,{'message':'Select a run to inspect its history.'})
        for run_id,run in self.runs.items():
            payload=json.loads(run['payload_json'])
            self.run_table.insert('','end',iid=run_id,values=(run['started_at'],payload.get('client_name') or payload.get('client_id') or 'Not available',payload.get('query') or 'Not available',run['status'],run['coverage']))
        self.case_table.delete(*self.case_table.get_children()); self.case_id=None
        for case in cases:
            self.case_table.insert('','end',iid=case['case_id'],values=(case['client_id'] or 'Global',case['ad_id'],case['decision'] or 'Not decided',case['status']))
        if selected in self.case_table.get_children():
            self.case_table.selection_set(selected); self.show_case()
        else: self.show_text(self.case_detail,{'message':'Select a case to inspect its history.'})

    def show_run(self):
        """Display saved metadata and structured result information for the selected run."""
        selection=self.run_table.selection()
        if selection: self.show_text(self.run_detail,json.loads(self.runs[selection[0]]['payload_json']))

    def show_case(self):
        """Display the selected case, evidence, events and manual report history."""
        selection=self.case_table.selection()
        if not selection: return
        self.case_id=selection[0]
        with connect(self.database) as db:
            self.show_text(self.case_detail,case_detail(db,self.case_id))

    def correct(self):
        """Request justification and reopen a classified case without erasing earlier events or evidence."""
        if not self.case_id: raise ValueError('Select a case first')
        case_id=self.case_id
        reason=simpledialog.askstring('Correction reason','Explain why this classification should be corrected:',parent=self)
        if not reason or not reason.strip(): return
        if not messagebox.askyesno('Reopen case',f'Reopen case {case_id}? Its own list effects will be reversed; history and evidence will be retained.',parent=self): return
        with connect(self.database) as db:
            reopen_case(db,case_id,actor='local_operator',reason=reason,confirm_case_id=case_id)
        self.refresh()
        if self.on_change: self.on_change()

    def open_evidence(self):
        """Open local evidence management for the selected case, creating its case context when needed."""
        if not self.case_id: raise ValueError('Select a case first')
        window=EvidenceWindow(self,self.database,self.case_id,self.database.parent.parent/'evidence')
        window.transient(self); window.grab_set()

    def export(self,format):
        """Export the selected case to JSON or CSV without overwriting existing files."""
        if not self.case_id: raise ValueError('Select a case first')
        filename=filedialog.asksaveasfilename(parent=self,title='Export case as '+format.upper(),
            initialdir=self.database.parent.parent/'exports',initialfile=self.case_id+'.'+format,
            defaultextension='.'+format,filetypes=[(format.upper(),'*.'+format)])
        if not filename: return
        from ..exports.service import export_case
        with connect(self.database) as db:
            output=export_case(db,self.case_id,filename,format=format)
        messagebox.showinfo('Case exported',str(output),parent=self)

    def report_dialog(self):
        """Build the manual report-recording dialog; this does not submit anything to Meta."""
        if not self.case_id: raise ValueError('Select a case first')
        case_id=self.case_id
        window=tk.Toplevel(self); window.title('Record a manual report'); window.transient(self); window.grab_set()
        fields={}
        for index,(key,label,default) in enumerate([
            ('reported_at','Report date/time (ISO with time zone)',datetime.now(ZoneInfo('America/Bogota')).isoformat(timespec='seconds')),
            ('reference','External reference or HTTPS URL',''),('reason','Notes / external confirmation evidence','')]):
            ttk.Label(window,text=label).grid(row=index,column=0,sticky='w',padx=10,pady=8)
            value=tk.StringVar(value=default); fields[key]=value
            ttk.Entry(window,textvariable=value,width=58).grid(row=index,column=1,padx=10,pady=8)
        ttk.Label(window,text='External status').grid(row=3,column=0,sticky='w',padx=10)
        status=tk.StringVar(value='sent')
        ttk.Combobox(window,textvariable=status,values=['sent','awaiting_response','action_confirmed','unknown'],state='readonly').grid(row=3,column=1,sticky='w',padx=10)
        ttk.Label(window,text='This only records a report you already submitted manually.').grid(row=4,columnspan=2,padx=10,pady=10)
        def save():
            """Validate report dialog fields, record the manual event and refresh history."""
            try:
                with connect(self.database) as db:
                    record_report(db,case_id,actor='local_operator',reported_at=fields['reported_at'].get(),
                                  reference=fields['reference'].get().strip() or None,status=status.get(),reason=fields['reason'].get())
                window.destroy(); self.refresh()
            except Exception as exc: messagebox.showerror('Unable to record report',str(exc),parent=window)
        ttk.Button(window,text='Save manual report',command=save).grid(row=5,column=1,sticky='e',padx=10,pady=10)
