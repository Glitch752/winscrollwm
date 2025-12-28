# adapters/windows/enumerator.py
from typing import Tuple
import win32gui
import win32con

# This is all very hacky, but the best I could come up with for now
BLACKLISTED_WINDOWS: list[Tuple[str, str]] = [
    ("Windows.UI.Core.CoreWindow", "Cortana"),
    ("ApplicationFrameWindow", "Cortana"),
    ("Windows.UI.Core.CoreWindow", "Media Player"),
    ("ApplicationFrameWindow", "Media Player"),
    ("Windows.UI.Core.CoreWindow", "Microsoft Text Input Application"),
    
    ("Progman", "Program Manager"),
    ("Shell_TrayWnd", "Taskbar"),
    ("Button", "Start"),
    ("DV2ControlHost", "SearchBox"),
    
]

def is_manageable(hwnd: int) -> bool:
    # Basic checks for top-level visible windows with titles
    try:
        if not win32gui.IsWindow(hwnd):
            return False
        
        # Ignore hidden windows
        if not win32gui.IsWindowVisible(hwnd):
            return False
        
        if win32gui.GetParent(hwnd):
            return False
        
        style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
        if style & win32con.WS_CHILD:
            return False
        
        # Ignore always-on-top windows
        ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        if ex_style & win32con.WS_EX_TOPMOST:
            return False
        
        title = win32gui.GetWindowText(hwnd) or ""
        class_name = win32gui.GetClassName(hwnd) or ""
        
        if (class_name, title) in BLACKLISTED_WINDOWS:
            return False
        
        # ignore empty/titleless utility windows
        return bool(title.strip())
    except Exception:
        return False

def enumerate_top_level_windows() -> list[int]:
    "Return a list of HWNDs for manageable windows"
    result = []
    def _cb(hwnd, lparam):
        if is_manageable(hwnd):
            result.append(hwnd)
        return True
    win32gui.EnumWindows(_cb, None)
    return result
