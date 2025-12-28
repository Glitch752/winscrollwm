# adapters/windows/layout.py
import ctypes
from ctypes.wintypes import RECT
from typing import cast
import win32gui
import win32con
import math

from log import log_error

from .models import Rect
from core.models import Workspace

def layout_workspace_windows(workspace: Workspace, work_rect: Rect, monitor_rect: Rect, gap_px: int):
    """
    Layout windows in `workspace` within `work_rect` (left,top,right,bottom).
    Each window carries .width (float) meaning relative fraction of the workspace width.
    We'll normalize widths to sum to 1. If only a single window, it gets the whole space.

    We respect `gap_px` around the edges and between windows.
    """
    if not workspace.windows:
        return
    
    workspace.layout_windows()

    # compute available rectangle (apply outer gap)
    avail_w = work_rect.width() - 2 * gap_px
    avail_h = work_rect.height() - 2 * gap_px
    if avail_w <= 0 or avail_h <= 0:
        return

    # place windows left-to-right with inner gaps
    screen_x = work_rect.left() + gap_px - int(avail_w * workspace.scroll_offset)
    screen_y = work_rect.top() + gap_px
    for idx, win in enumerate(workspace.windows):
        w = math.floor(avail_w * win.width)
        x = int(avail_w * win.x)
        
        rect = Rect(screen_x + x, screen_y, screen_x + x + w, screen_y + avail_h)
        
        # If the rectangle is totally outside of the monitor, hide the window
        if not monitor_rect.intersects(rect):
            
            print(monitor_rect, rect)
            try:
                win32gui.ShowWindow(win.id, win32con.SW_MINIMIZE)
            except Exception:
                pass
            continue
        
        try:
            # MoveWindow expects (hwnd, x, y, width, height, repaint)
            # win32gui.MoveWindow(win.id, *rect.sized(), True)
            # ensure it's not minimized / hidden by us
            win32gui.ShowWindow(win.id, win32con.SW_RESTORE)
        except Exception as e:
            # ignore problematic windows for now
            log_error(f"Failed to layout window {win.id}: {e}")
