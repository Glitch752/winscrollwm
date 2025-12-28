# adapters/windows/layout.py
import win32gui
import win32con
from typing import Tuple
import math

from .models import Rect
from core.models import Workspace

def layout_workspace_windows(workspace: Workspace, work_rect: Rect, gap_px: int):
    """
    Layout windows in `workspace` within `work_rect` (left,top,right,bottom).
    Each window carries .width (float) meaning relative fraction of the workspace width.
    We'll normalize widths to sum to 1. If only a single window, it gets the whole space.

    We respect `gap_px` around the edges and between windows.
    """
    if not workspace.windows:
        return

    # compute available rectangle (apply outer gap)
    avail_w = work_rect.width() - 2 * gap_px
    avail_h = work_rect.height() - 2 * gap_px
    if avail_w <= 0 or avail_h <= 0:
        return

    # place windows left-to-right with inner gaps
    x = work_rect.left() + gap_px
    y = work_rect.top() + gap_px
    for idx, win in enumerate(workspace.windows):
        w = math.floor(avail_w * win.width)
        try:
            # MoveWindow expects (hwnd, x, y, width, height, repaint)
            win32gui.MoveWindow(win.id, x, y, w, avail_h, True)
            # ensure it's not minimized / hidden by us
            win32gui.ShowWindow(win.id, win32con.SW_RESTORE)
        except Exception:
            # ignore problematic windows for now
            pass
        
        x += w + gap_px
