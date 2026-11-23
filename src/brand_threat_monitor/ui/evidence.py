"""Previsualizacion local bajo accion explicita; sin red ni reproductor externo."""

import tkinter as tk
from pathlib import Path
from tkinter import ttk,filedialog,messagebox,simpledialog
from PIL import ImageTk

from ..storage.database import connect
from ..evidence.service import load_preview,attach_image


class EvidenceWindow(tk.Toplevel):
    def __init__(self,parent,database,case_id,evidence_directory):
        """Initialize view widgets and callbacks."""
        super().__init__(parent)
        self.database=database; self.case_id=case_id; self.evidence_directory=Path(evidence_directory)
        self.photo=None; self.records={}
        self.title('Local evidence images'); self.geometry('820x740')
        ttk.Label(self,text='Local files only. No URLs are fetched. Videos and documents are not rendered.',wraplength=780).pack(anchor='w',padx=12,pady=8)
        self.table=ttk.Treeview(self,columns=('type','file'),show='headings',height=5)
        self.table.heading('type',text='Type'); self.table.heading('file',text='Local file')
        self.table.column('type',width=100); self.table.column('file',width=650)
        self.table.pack(fill='x',padx=12)
        self.table.bind('<<TreeviewSelect>>',lambda event:self.clear())
        actions=ttk.Frame(self); actions.pack(fill='x',padx=12,pady=8)
        ttk.Button(actions,text='Preview selected image',command=lambda:self.guard(self.preview)).pack(side='left')
        ttk.Button(actions,text='Attach local image',command=lambda:self.guard(self.attach)).pack(side='left',padx=8)
        self.metadata=tk.StringVar(value='Select an image and click Preview.')
        ttk.Label(self,textvariable=self.metadata,wraplength=780).pack(anchor='w',padx=12)
        self.image_label=ttk.Label(self,anchor='center'); self.image_label.pack(fill='both',expand=True,padx=12,pady=12)
        self.refresh()

    def guard(self,action):
        """Run a UI callback and display any raised error in a parented dialog."""
        try: action()
        except Exception as exc:
            self.clear(); self.metadata.set(str(exc))
            messagebox.showerror('Unable to preview or attach image',str(exc),parent=self)

    def clear(self):
        """Detach image references and reset the evidence selection before releasing preview ownership."""
        self.image_label.configure(image=''); self.photo=None
        self.metadata.set('Select an image and click Preview.')

    def refresh(self):
        """Reload filtered saved records and refresh the view while preserving selection where possible."""
        self.clear()
        with connect(self.database) as db:
            self.records={row['evidence_id']:dict(row) for row in db.execute('SELECT * FROM evidence WHERE case_id=? ORDER BY evidence_id',(self.case_id,))}
        self.table.delete(*self.table.get_children())
        for evidence_id,row in self.records.items():
            self.table.insert('','end',iid=evidence_id,values=(row['type'],row['local_path'] or 'No local file'))

    def preview(self):
        """Validate a local evidence image and its stored hash before displaying its retained Tk preview."""
        selection=self.table.selection()
        if not selection: raise ValueError('Select an evidence file first')
        row=self.records[selection[0]]
        if not row['local_path']: raise ValueError('This evidence has no local file')
        preview=load_preview(row['local_path'],expected_hash=row['hash'])
        self.photo=ImageTk.PhotoImage(preview.image,master=self)
        self.image_label.configure(image=self.photo)
        frame='; first frame only' if preview.animated else ''
        self.metadata.set(f'{preview.format} | {preview.width} x {preview.height} | {len(preview.content)} bytes{frame}\nSHA-256: {preview.sha256}')

    def attach(self):
        """Select a local image and note, then attach a verified managed copy with audit."""
        source=filedialog.askopenfilename(parent=self,title='Select a local image',filetypes=[('Images','*.png *.jpg *.jpeg *.webp *.gif'),('All files','*.*')])
        if not source: return
        reason=simpledialog.askstring('Evidence note','Describe what this image documents:',parent=self)
        if not reason or not reason.strip(): return
        with connect(self.database) as db:
            evidence_id=attach_image(db,self.case_id,source,self.evidence_directory,actor='local_operator',reason=reason)
        self.refresh(); self.table.selection_set(evidence_id)
        self.metadata.set('Image attached. Click Preview to inspect the stored copy.')
