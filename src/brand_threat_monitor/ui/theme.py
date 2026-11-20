"""Native Tkinter interpretation of the Editorial Tech design tokens."""
from tkinter import ttk, font

INK='#202A30'
PETROLEUM='#14252D'
TEAL='#29444A'
IVORY='#F6F3ED'
PAPER='#EEEAE2'
CHAMPAGNE='#E8D8C2'
CAMEL='#C49A67'
SECONDARY='#59696D'
BORDER='#D7D3CB'
MUTED='#67777C'
BORDER_DARK='#485158'
BORDER_SUBTLE='#E4E0D8'
ON_DARK_SECONDARY='#D2D9D7'
ON_DARK_MUTED='#A7B8BA'
ACCENT_HOVER='#D6AD7A'
ACCENT_PRESSED='#B58C5B'
SUCCESS='#A8C5AC'
WARNING='#D8AC72'
ERROR='#C77B73'


def font_family(widget,role='body'):
    available=set(font.families(widget))
    choices={'body':['Inter','Segoe UI','Arial'],
             'display':['Manrope','Segoe UI','Arial'],
             'mono':['IBM Plex Mono','Consolas','Courier New']}[role]
    return next((name for name in choices if name in available),choices[-1])


def apply_theme(root):
    body=font_family(root)
    display=font_family(root,'display')
    mono=font_family(root,'mono')
    root.configure(background=PETROLEUM)
    for name in ('TkDefaultFont','TkTextFont','TkMenuFont','TkHeadingFont'):
        font.nametofont(name,root=root).configure(family=body,size=10)
    root.option_add('*Text.background',IVORY)
    root.option_add('*Text.foreground',INK)
    root.option_add('*Text.selectBackground',CHAMPAGNE)
    root.option_add('*Text.selectForeground',INK)
    root.option_add('*Text.insertBackground',INK)
    root.option_add('*Label.background',IVORY)
    root.option_add('*Label.foreground',INK)
    root.option_add('*Canvas.background',IVORY)
    root.option_add('*Toplevel.background',IVORY)
    root.option_add('*Frame.background',IVORY)
    root.option_add('*Text.highlightBackground',BORDER)
    root.option_add('*Text.highlightColor',PETROLEUM)
    root.option_add('*Text.relief','flat')
    root.option_add('*Menu.background',IVORY)
    root.option_add('*Menu.foreground',INK)
    root.option_add('*Menu.activeBackground',CHAMPAGNE)
    root.option_add('*Menu.activeForeground',INK)
    style=ttk.Style(root)
    style.theme_use('clam')
    style.configure('.',background=IVORY,foreground=INK,font=(body,10),bordercolor=BORDER,focuscolor=PETROLEUM)
    style.configure('TFrame',background=TEAL)
    style.configure('Shell.TFrame',background=PETROLEUM)
    style.configure('Shell.Title.TLabel',background=PETROLEUM,foreground=IVORY,font=(display,22,'bold'))
    style.configure('Shell.Subtitle.TLabel',background=PETROLEUM,foreground=ON_DARK_SECONDARY,font=(body,10))
    style.configure('TLabel',background=TEAL,foreground=IVORY)
    style.configure('Title.TLabel',font=(display,22,'bold'),foreground=PETROLEUM)
    style.configure('Subtitle.TLabel',foreground=SECONDARY,font=(body,10))
    style.configure('Tech.TLabel',foreground=SECONDARY,font=(mono,9))
    style.configure('Media.TLabel',background=PAPER,foreground=SECONDARY,font=(mono,9))
    style.configure('TButton',padding=(9,6),background=INK,foreground=IVORY,borderwidth=1,relief='flat')
    style.map('TButton',background=[('disabled',INK),('pressed',PETROLEUM),('active',TEAL)],foreground=[('disabled',ON_DARK_MUTED),('!disabled',IVORY)])
    style.configure('Primary.TButton',background=INK,foreground=IVORY,font=(body,10,'bold'))
    style.map('Primary.TButton',background=[('disabled',BORDER),('pressed',PETROLEUM),('active',TEAL)],foreground=[('disabled',SECONDARY),('!disabled',IVORY)])
    style.configure('Accent.TButton',background=CAMEL,foreground=INK)
    style.map('Accent.TButton',background=[('disabled',PAPER),('pressed',ACCENT_PRESSED),('active',ACCENT_HOVER)])
    for name,color in [('Flag',ERROR),('Spam',CAMEL),('Pending',WARNING),('Success',SUCCESS)]:
        style.configure(name+'.TButton',background=color,foreground=INK)
        style.map(name+'.TButton',background=[('disabled',PAPER),('pressed',CHAMPAGNE),('active',CHAMPAGNE)],foreground=[('disabled',MUTED),('!disabled',INK)])
    style.configure('TEntry',fieldbackground=IVORY,padding=5,insertcolor=INK)
    style.configure('TSpinbox',fieldbackground=IVORY,padding=4,arrowsize=13)
    style.map('TEntry',bordercolor=[('invalid',ERROR),('focus',TEAL)])
    style.map('TSpinbox',bordercolor=[('focus',TEAL)])
    style.configure('TCheckbutton',background=TEAL,foreground=IVORY,padding=3)
    style.map('TCheckbutton',background=[('active',INK)],foreground=[('disabled',ON_DARK_MUTED),('!disabled',IVORY)])
    style.configure('TNotebook',background=PETROLEUM,borderwidth=0,relief='flat',bordercolor=TEAL,lightcolor=TEAL,darkcolor=TEAL,tabmargins=(0,5,0,0))
    style.configure('TNotebook.Tab',padding=(12,5),background=TEAL,foreground=ON_DARK_SECONDARY,font=(body,10),expand=(0,0,0,0),borderwidth=0,relief='flat',bordercolor=TEAL,lightcolor=TEAL,darkcolor=TEAL)
    style.map('TNotebook.Tab',background=[('selected',INK),('active',TEAL)],foreground=[('selected',IVORY),('!selected',ON_DARK_SECONDARY)],bordercolor=[('selected',INK),('!selected',TEAL)],lightcolor=[('selected',INK),('!selected',TEAL)],darkcolor=[('selected',INK),('!selected',TEAL)],padding=[('selected',(20,10)),('!selected',(12,5))],font=[('selected',(body,11,'bold')),('!selected',(body,10))],expand=[('selected',(2,4,2,0)),('!selected',(0,0,0,0))])
    style.configure('TLabelframe',background=TEAL,bordercolor=TEAL,relief='flat',borderwidth=0)
    style.configure('TLabelframe.Label',background=TEAL,foreground=CHAMPAGNE,font=(body,10,'bold'))
    style.configure('Treeview',background=IVORY,fieldbackground=IVORY,foreground=INK,rowheight=28,borderwidth=1)
    style.configure('Treeview.Heading',background=PAPER,foreground=TEAL,font=(body,10,'bold'),padding=(6,6),relief='flat')
    style.map('Treeview',background=[('selected',TEAL)],foreground=[('selected',IVORY)])
    style.map('Treeview.Heading',background=[('active',CHAMPAGNE)])
    style.configure('TCombobox',fieldbackground=IVORY,background=PAPER,foreground=INK,arrowcolor=TEAL,padding=4)
    style.map('TCombobox',fieldbackground=[('readonly',IVORY)],foreground=[('readonly',INK)],bordercolor=[('focus',TEAL)])
    root.option_add('*TCombobox*Listbox.background',IVORY)
    root.option_add('*TCombobox*Listbox.foreground',INK)
    root.option_add('*TCombobox*Listbox.selectBackground',TEAL)
    root.option_add('*TCombobox*Listbox.selectForeground',IVORY)
    style.configure('TSeparator',background=BORDER)
    style.configure('TProgressbar',background=CAMEL,troughcolor=PAPER,borderwidth=0)
    # Flat, narrow scrollbars without legacy arrow buttons.
    for orientation in ('Vertical','Horizontal'):
        prefix=orientation+'.Scrollbar'
        style.layout(orientation+'.TScrollbar',[(prefix+'.trough',{'sticky':'nswe','children':[(prefix+'.thumb',{'sticky':'nswe','expand':True})]})])
        style.configure(orientation+'.TScrollbar',background=SECONDARY,troughcolor=TEAL,borderwidth=0,relief='flat',width=9,arrowsize=9,gripcount=0,lightcolor=SECONDARY,darkcolor=SECONDARY,bordercolor=TEAL)
        style.map(orientation+'.TScrollbar',background=[('pressed',CAMEL),('active',CAMEL)],lightcolor=[('active',CAMEL)],darkcolor=[('active',CAMEL)])
    return style
