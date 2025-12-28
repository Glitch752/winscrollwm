# adapters/windows/enumerator.py
import ctypes
from typing import Tuple
import win32gui
import win32process
import win32api
import win32con

# This is all very hacky, but the best I could come up with for now
BLACKLISTED_WINDOWS: list[Tuple[str, str]] = [
    ("Windows.UI.Core.CoreWindow", "Cortana"),
    ("ApplicationFrameWindow", "Cortana"),
    ("Windows.UI.Core.CoreWindow", "Media Player"),
    ("ApplicationFrameWindow", "Media Player"),
    ("Windows.UI.Core.CoreWindow", "Microsoft Text Input Application"),
    ("Windows.UI.Core.CoreWindow", "News and interests"),
    ("Windows.UI.Core.CoreWindow", "Widgets"),
    ("Windows.UI.Core.CoreWindow", "Windows Shell Experience Host"),
    
    ("Progman", "Program Manager"),
    ("Shell_TrayWnd", "Taskbar"),
    ("Button", "Start"),
    ("DV2ControlHost", "SearchBox"),
    
]

current_pid = win32api.GetCurrentProcessId()

def is_manageable(hwnd: int) -> bool:
    # Basic checks for top-level visible windows with titles
    try:
        if not win32gui.IsWindow(hwnd):
            return False
        
        # Ignore hidden windows
        if not win32gui.IsWindowVisible(hwnd):
            return False
        
        if win32gui.GetWindow(hwnd, win32con.GW_OWNER) != 0:
            return False
        
        style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
        ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)

        # Only standard top-level windows
        if not (style & win32con.WS_OVERLAPPEDWINDOW):
            return False
        # Exclude non-app windows
        if ex_style & win32con.WS_EX_TOOLWINDOW:
            return False

        # Ignore this process' windows
        _, window_pid = win32process.GetWindowThreadProcessId(hwnd)
        if window_pid == current_pid:
            return False
        
        # Ignore child windows
        if win32gui.GetParent(hwnd):
            return False
        
        # Ignore cloaked windows
        try:
            cloaked = ctypes.c_int()
            dwm_attr_size = ctypes.sizeof(cloaked)
            DWMWA_CLOAKED = 14
            res = ctypes.windll.dwmapi.DwmGetWindowAttribute(
                ctypes.c_void_p(hwnd),
                ctypes.c_uint(DWMWA_CLOAKED),
                ctypes.byref(cloaked),
                ctypes.c_uint(dwm_attr_size)
            )
            if res == 0 and cloaked.value != 0:
                return False
        except Exception:
            print("Failed to get DWM attribute")
            pass
        
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
