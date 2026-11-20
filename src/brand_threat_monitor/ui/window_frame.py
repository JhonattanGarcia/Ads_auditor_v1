"""Native Windows title-bar styling; preserve system window behavior."""
import sys


def colorref(hex_color):
    value=hex_color.lstrip('#')
    red,green,blue=(int(value[index:index+2],16) for index in (0,2,4))
    return red | green<<8 | blue<<16


def style_native_frame(window):
    if sys.platform!='win32': return False
    import ctypes
    from ctypes import wintypes
    from .theme import PETROLEUM,IVORY
    try:
        user32=ctypes.WinDLL('user32',use_last_error=True)
        dwm=ctypes.WinDLL('dwmapi',use_last_error=True)
        user32.GetAncestor.argtypes=[wintypes.HWND,wintypes.UINT]
        user32.GetAncestor.restype=wintypes.HWND
        dwm.DwmSetWindowAttribute.argtypes=[wintypes.HWND,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD]
        dwm.DwmSetWindowAttribute.restype=ctypes.c_long
        handle=user32.GetAncestor(window.winfo_id(),2)
        if not handle: return False
        def set_attribute(attribute,value):
            data=wintypes.DWORD(value)
            return dwm.DwmSetWindowAttribute(handle,attribute,ctypes.byref(data),ctypes.sizeof(data))==0
        dark=set_attribute(20,1)
        caption=set_attribute(35,colorref(PETROLEUM))
        set_attribute(36,colorref(IVORY))
        set_attribute(34,colorref(PETROLEUM))
        return dark or caption
    except (AttributeError,OSError):
        return False


def install_native_frame(window):
    def apply(event):
        if event.widget is window: style_native_frame(window)
    window.bind('<Map>',apply,add='+')
