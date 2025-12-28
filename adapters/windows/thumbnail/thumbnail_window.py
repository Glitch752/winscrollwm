import win32gui
import win32con
import ctypes
from ctypes.wintypes import RECT

from core.models import Rect
from log import log_error

user32 = ctypes.windll.user32
dwmapi = ctypes.windll.dwmapi

DWM_TNP_RECTDESTINATION = 0x00000001
DWM_TNP_RECTSOURCE = 0x00000002
DWM_TNP_OPACITY = 0x00000004
DWM_TNP_VISIBLE = 0x00000008
class DWM_THUMBNAIL_PROPERTIES(ctypes.Structure):
    _fields_ = [
        ("dwFlags", ctypes.c_uint),
        ("rcDestination", RECT),
        ("rcSource", RECT),
        ("opacity", ctypes.c_byte),
        ("fVisible", ctypes.c_bool),
        ("fSourceClientAreaOnly", ctypes.c_bool),
    ]
    
CLASS_NAME = "ThumbnailWindowClass"
# No border/window decorations
WINDOW_STYLE = win32con.WS_VISIBLE | win32con.WS_POPUP

class_registered = False
def register_class_if_needed():
    global class_registered
    if class_registered:
        return
    
    hinst = win32gui.GetModuleHandle(None)
    
    wc = win32gui.WNDCLASS()
    wc.hInstance = hinst # type: ignore
    wc.lpszClassName = CLASS_NAME # type: ignore
    wc.style = win32con.CS_HREDRAW | win32con.CS_VREDRAW # type: ignore
    message_map = {
        win32con.WM_DESTROY: on_destroy
    }
    wc.lpfnWndProc = message_map # type: ignore
    win32gui.RegisterClass(wc)
    
    class_registered = True

thumbnail_windows: dict[int, "ThumbnailWindow"] = {}

def on_destroy(hwnd, msg, wparam, lparam):
    if hwnd in thumbnail_windows:
        thumbnail_windows[hwnd].on_destroy()
        
        del thumbnail_windows[hwnd]
    
    return 0

class ThumbnailWindow:
    """
    A wrapper for a win32 DWM thumbnail window.
    opens a window that displays a section of another window's content.
    """
    
    hwnd_src: int
    src_rect: Rect
    self_pos: tuple[int, int]
    
    thumbnail_id: ctypes.c_void_p | None = None
    hwnd: int
    
    def __init__(self, hwnd_src: int, src_rect: Rect, self_pos: tuple[int, int]):
        self.hwnd_src = hwnd_src
        self.src_rect = src_rect
        self.self_pos = self_pos
        
        self.create_window()
        self.register_thumbnail()
        self.fixorder()
    
    def create_window(self):
        # Create a simple window to host the thumbnail
        hinst = win32gui.GetModuleHandle(None)
        
        register_class_if_needed()
        
        # We don't need to call AdjustWindowRect because we have no window decorations
        self.hwnd = win32gui.CreateWindowEx(
            win32con.WS_EX_TOOLWINDOW,
            CLASS_NAME,
            "Thumbnail Window",
            WINDOW_STYLE,
            self.self_pos[0],
            self.self_pos[1],
            self.src_rect.width(),
            self.src_rect.height(),
            0,
            0,
            hinst,
            None
        )
        
        win32gui.ShowWindow(self.hwnd, win32con.SW_SHOW)
        
        thumbnail_windows[self.hwnd] = self
    
    def register_thumbnail(self):
        self.thumbnail_id = ctypes.c_void_p()
        
        # Adjust the crop rect to be in the window space as reported by the DWM
        dwmapi.DwmRegisterThumbnail(
            ctypes.c_void_p(self.hwnd),
            ctypes.c_void_p(self.hwnd_src),
            ctypes.byref(self.thumbnail_id)
        )
        dest_rect = RECT(0, 0, self.src_rect.width(), self.src_rect.height())
        source_rect = RECT(*self.src_rect)
        
        properties = DWM_THUMBNAIL_PROPERTIES()
        properties.dwFlags = (
            DWM_TNP_RECTDESTINATION |
            DWM_TNP_RECTSOURCE |
            DWM_TNP_OPACITY |
            DWM_TNP_VISIBLE
        )
        properties.rcDestination = dest_rect
        properties.rcSource = source_rect
        properties.opacity = 255
        properties.fVisible = True
        properties.fSourceClientAreaOnly = False
        dwmapi.DwmUpdateThumbnailProperties(
            self.thumbnail_id,
            ctypes.byref(properties)
        )
    
    def update(self, new_src: Rect, new_pos: tuple[int, int]):
        self.src_rect = new_src
        
        if self.hwnd == 0:
            log_error("Thumbnail window handle is invalid.")
            return
        
        if self.thumbnail_id:
            dest_rect = RECT(0, 0, self.src_rect.width(), self.src_rect.height())
            source_rect = RECT(*self.src_rect)
            
            properties = DWM_THUMBNAIL_PROPERTIES()
            properties.dwFlags = (
                DWM_TNP_RECTDESTINATION |
                DWM_TNP_RECTSOURCE
            )
            properties.rcDestination = dest_rect
            properties.rcSource = source_rect
            dwmapi.DwmUpdateThumbnailProperties(
                self.thumbnail_id,
                ctypes.byref(properties)
            )
        
        # Adjust window size
        try:
            win32gui.SetWindowPos(
                self.hwnd,
                0,
                new_pos[0],
                new_pos[1],
                self.src_rect.width(),
                self.src_rect.height(),
                win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE | win32con.SWP_NOREDRAW | win32con.SWP_NOOWNERZORDER | win32con.SWP_NOSENDCHANGING
            )
        except Exception as e:
            log_error(f"Failed to update thumbnail window position/size: {e}")
    
    def fixorder(self):
        if self.hwnd != 0:
            # Put the thumbnail just below the source window to ensure proper rendering
            win32gui.SetWindowPos(
                self.hwnd,
                self.hwnd_src,
                0, 0, 0, 0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE | win32con.SWP_NOREDRAW
            )
            pass
    
    def hide(self):
        if self.hwnd != 0:
            win32gui.ShowWindow(self.hwnd, win32con.SW_HIDE)
    def show(self):
        if self.hwnd != 0:
            win32gui.ShowWindow(self.hwnd, win32con.SW_SHOW)
    
    def close(self):
        if self.hwnd != 0:
            try:
                win32gui.DestroyWindow(self.hwnd)
            except Exception as e:
                log_error(f"Failed to destroy thumbnail window: {e}")
            self.hwnd = 0
    
    def on_destroy(self):
        if self.thumbnail_id:
            dwmapi.DwmUnregisterThumbnail(self.thumbnail_id)
            self.thumbnail_id = None
            self.hwnd = 0