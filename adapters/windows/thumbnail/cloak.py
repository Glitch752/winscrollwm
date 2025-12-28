import win32gui
import win32con

from adapters.windows.models import WinWindow
from adapters.windows.thumbnail.thumbnail_window import ThumbnailWindow
from core.models import Rect
from log import log_error

def create_cloaking_thumbnail(hwnd: int, rect: Rect) -> ThumbnailWindow:
    # Create thumbnail
    src_rect = Rect(0, 0, rect[2] - rect[0], rect[3] - rect[1])
    thumbnail = ThumbnailWindow(hwnd, src_rect, (rect[0], rect[1]))
    
    try:
        # Hide the original but maintain mouse interactivity by settings its opacity to 0 and making it layered
        exstyle = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, exstyle | win32con.WS_EX_LAYERED)
        alpha = 1
        win32gui.SetLayeredWindowAttributes(hwnd, 0, alpha, win32con.LWA_ALPHA)
    except Exception as e:
        thumbnail.close()
        log_error(f"Failed to cloak window {hwnd}: {e}")
    
    return thumbnail

def remove_cloaking_thumbnail(hwnd: int, thumbnail: ThumbnailWindow):
    # Restore original window opacity and remove thumbnail
    alpha = 255
    try:
        win32gui.SetLayeredWindowAttributes(hwnd, 0, alpha, win32con.LWA_ALPHA)
    except Exception as e:
        log_error(f"Failed to restore window {hwnd} opacity: {e}")
    
    exstyle = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
    win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, exstyle & ~win32con.WS_EX_LAYERED)
    
    thumbnail.close()