"""Controles compartidos de filtros de observacion."""

import tkinter as tk
from tkinter import ttk
from ..history.filters import Filters


class FilterBar(ttk.Frame):
    def __init__(self,parent,on_apply):
        """Initialize view widgets and callbacks."""
        super().__init__(parent)
        self.values={}
        for index,(field,label,width) in enumerate([
            ('country','Country',5),('criterion','Search criteria (contains)',22),
            ('advertiser_id','Advertiser ID (exact)',20),
            ('date_from','From (YYYY-MM-DD)',12),('date_to','To (YYYY-MM-DD)',12)]):
            column=index%3; row=(index//3)*2
            ttk.Label(self,text=label).grid(row=row,column=column,sticky='w',padx=4)
            value=tk.StringVar(); self.values[field]=value
            entry=ttk.Entry(self,textvariable=value,width=width)
            entry.grid(row=row+1,column=column,sticky='ew',padx=4,pady=(0,5))
            entry.bind('<Return>',lambda event:on_apply())
            self.columnconfigure(column,weight=1)
        ttk.Label(self,text='Source ad timestamps: UTC (+00:00). Display: UTC or Colombia (UTC-05:00), selected with Show dates in UTC. From / To filter observation dates in Colombia.',wraplength=950).grid(row=4,column=0,columnspan=3,sticky='w',padx=4,pady=(0,4))
        actions=ttk.Frame(self); actions.grid(row=3,column=2,sticky='e')
        ttk.Button(actions,text='Apply filters',command=on_apply).pack(side='left',padx=4)
        def reset():
            """Clear filter controls and immediately ask the parent view to refresh."""
            for value in self.values.values(): value.set('')
            on_apply()
        ttk.Button(actions,text='Clear filters',command=reset).pack(side='left')

    def get(self):
        """Read controls into validated history filters."""
        return Filters(**{field:value.get() for field,value in self.values.items()})
