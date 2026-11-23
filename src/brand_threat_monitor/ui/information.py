"""Presentacion completa de datos como campos legibles, sin sintaxis JSON."""

import json
import re
import tkinter as tk
from tkinter import ttk

LABELS={'ad_id':'Ad ID','advertiser_id':'Advertiser ID','run_id':'Run ID','case_id':'Case ID',
        'payload_json':'Stored content','api_fields':'Additional source fields',
        'delivery_start_time':'Ad delivery start','delivery_stop_time':'Ad delivery stop',
        'creatives':'Ad creatives','body':'Ad text','page':'Advertiser page',
        'is_active':'Currently active','q':'Search query','before_json':'Before change',
        'after_json':'After change','hash':'File hash','url_original':'Original URL',
        'url_normalized':'Normalized URL','original_url':'Original search URL',
        'effective_url':'Effective search URL','impressions':'Impressions',
        'lower_bound':'Lower bound','upper_bound':'Upper bound'}


def label(key):
    """Convert source field names into readable labels while preserving known identifiers."""
    key=str(key)
    if key in LABELS: return LABELS[key]
    spaced=re.sub(r'(?<=[a-z0-9])(?=[A-Z])',' ',key).replace('_',' ')
    words=spaced.split()
    return ' '.join(w.upper() if w.lower() in {'id','ids','url','urls','api','csv','json','eu','uk','hd','sd'}
                    else w.capitalize() if index==0 else w.lower() for index,w in enumerate(words))


def decode_field(key,value):
    """Decode supported embedded JSON fields, keeping original values when decoding is not possible."""
    if key in {'payload_json','before_json','after_json','counts_json'} and isinstance(value,str):
        try: return json.loads(value)
        except (ValueError,TypeError): pass
    return value


def scalar(value):
    """Format primitive values without confusing absent values, empty strings, booleans and zero."""
    if value is None: return 'Not available'
    if value is True: return 'Yes'
    if value is False: return 'No'
    if value=='': return '(empty text)'
    return str(value)


def format_information(data):
    """Render nested source data as labeled readable fields instead of raw JSON blocks."""
    lines=[]
    def walk(value,name,depth):
        """Recursively traverse nested values while retaining their section and field hierarchy."""
        value=decode_field(name,value)
        heading=label(name)
        indent='  '*depth
        if isinstance(value,dict):
            lines.append(f'{indent}{heading}')
            if not value: lines.append(indent+'  No fields recorded')
            for key,item in value.items(): walk(item,key,depth+1)
        elif isinstance(value,list):
            lines.append(f'{indent}{heading} ({len(value)} entries)')
            if not value: lines.append(indent+'  None recorded')
            for index,item in enumerate(value,1): walk(item,f'Entry {index}',depth+1)
        else:
            text=scalar(value).replace('\n','\n'+indent+'  ')
            lines.append(f'{indent}{heading}: {text}')
    if isinstance(data,dict):
        for key,value in data.items():
            if lines: lines.append('')
            walk(value,key,0)
    else: walk(data,'Information',0)
    return '\n'.join(lines)


class InformationWindow(tk.Toplevel):
    def __init__(self,parent,data,title='All analysis information'):
        """Initialize view widgets and callbacks."""
        super().__init__(parent)
        self.title(title); self.geometry('1000x720')
        ttk.Label(self,text='Expand a section and select a field to read its full value. No links are opened automatically.').pack(anchor='w',padx=12,pady=10)
        panel=ttk.Frame(self); panel.pack(fill='both',expand=True,padx=12)
        panel.columnconfigure(0,weight=1); panel.rowconfigure(0,weight=1)
        self.tree=ttk.Treeview(panel,columns=('value',),show='tree headings')
        self.tree.heading('#0',text='Section / field'); self.tree.heading('value',text='Value')
        self.tree.column('#0',width=350); self.tree.column('value',width=600)
        self.tree.grid(row=0,column=0,sticky='nsew')
        vertical=ttk.Scrollbar(panel,command=self.tree.yview); vertical.grid(row=0,column=1,sticky='ns')
        horizontal=ttk.Scrollbar(panel,orient='horizontal',command=self.tree.xview); horizontal.grid(row=1,column=0,sticky='ew')
        self.tree.configure(yscrollcommand=vertical.set,xscrollcommand=horizontal.set)
        self.value=tk.Text(self,height=8,wrap='word',state='disabled'); self.value.pack(fill='x',padx=12,pady=10)
        self.values={}
        def add(parent,key,value,depth):
            """Recursively insert nested information fields into the details tree."""
            value=decode_field(key,value)
            if isinstance(value,dict): text=f'{len(value)} fields'
            elif isinstance(value,list): text=f'{len(value)} entries'
            else: text=scalar(value).replace('\n',' ')
            item=self.tree.insert(parent,'end',text=label(key),values=(text[:200],),open=depth<1)
            self.values[item]=(key,value)
            if isinstance(value,dict):
                for name,child in value.items(): add(item,name,child,depth+1)
            elif isinstance(value,list):
                for index,child in enumerate(value,1): add(item,f'Entry {index}',child,depth+1)
        for key,value in data.items(): add('',key,value,0)
        self.tree.bind('<<TreeviewSelect>>',lambda event:self.select())
        ttk.Button(self,text='Copy selected value',command=self.copy).pack(anchor='e',padx=12,pady=(0,10))

    def select(self):
        """Populate full details from the currently selected row or nested information field."""
        selection=self.tree.selection()
        if not selection: return
        key,value=self.values[selection[0]]
        text=format_information({key:value}) if isinstance(value,(dict,list)) else scalar(value)
        self.value.configure(state='normal'); self.value.delete('1.0','end'); self.value.insert('1.0',text); self.value.configure(state='disabled')

    def copy(self):
        """Copy the complete selected field value to the clipboard."""
        text=self.value.get('1.0','end-1c')
        self.clipboard_clear(); self.clipboard_append(text)
