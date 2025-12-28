# adapters/windows/adapter.py
import threading
import logging
from typing import cast
import win32gui
import win32con
import win32api

from adapters.base import Adapter
from adapters.windows.models import WinMonitor, WinWindow
from adapters.windows.print import print_ascii_layout
from adapters.windows.thumbnail.cloak import create_cloaking_thumbnail, remove_cloaking_thumbnail
from core.models import Monitor, Rect, Workspace, Window
from adapters.windows.monitor_info import list_monitors
from adapters.windows.enumerate import enumerate_top_level_windows, is_manageable
from adapters.windows.layout import layout_workspace_windows
from adapters.windows.watch import WinEventWatcher
from log import log_error

log = logging.getLogger(__name__)

DEFAULT_GAP_PX = 12

class WindowsAdapter(Adapter):
    _watcher: WinEventWatcher
    # I'm not sure what all we need to lock here, so we just lock everything...
    _lock: threading.RLock
    _monitors_info: list[WinMonitor]
    _windows: dict[int, Window]
    
    _focused_monitor: int | None = None
    
    def __init__(self, gap_px: int = DEFAULT_GAP_PX):
        # monitor data: list of dicts {hMonitor, monitor, work}
        self._monitors_info = list_monitors()
        # Create Monitor objects (1 workspace each by default)
        self._monitors = [Monitor(workspaces=[Workspace()], rect=m.monitor) for m in self._monitors_info]
        self._lock = threading.RLock()
        self.gap_px = gap_px

        # start the watcher
        self._watcher = WinEventWatcher(self)
        self._watcher.start()
        
        # initial population
        self._populate_initial_windows()
        
        print_ascii_layout(self._monitors, self._focused_monitor)
        
    async def initialize(self):
        pass
    
    # -------------------------
    # Adapter public API
    # -------------------------

    def get_monitors(self):
        with self._lock:
            return self._monitors

    def focus_window(self, window):
        hwnd = window.id
        try:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
        except Exception:
            log.exception("focus_window failed for %s", hwnd)
        
        # Temporary (?)
        for i, mon in enumerate(self._monitors):
            for ws in mon.workspaces:
                for w in ws.windows:
                    if w.id == hwnd:
                        self._focused_monitor = i
                        break
        
        self.refresh()

    def resize_window(self, window):
        # Just re-run layout for the workspace which contains this window
        with self._lock:
            self.refresh()

    def close_window(self, window):
        hwnd = window.id
        try:
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
        except Exception:
            log.exception("close_window failed for %s", hwnd)

    def refresh(self):
        """
        apply layout to the *active* workspace on each monitor.
        other workspaces' windows will be hidden.
        """
        with self._lock:
            for mi, mon in enumerate(self._monitors):
                work_rect = self._monitors_info[mi].work
                monitor_rect = self._monitors_info[mi].monitor
                
                # hide all windows not in active workspace
                active_ws = mon.current_workspace()
                
                if not active_ws:
                    continue
                
                # first minimize windows in other workspaces
                for ws in mon.workspaces:
                    if ws.id != mon._focused_workspace:
                        for w in ws.windows:
                            try:
                                win32gui.ShowWindow(w.id, win32con.SW_MINIMIZE)
                            except Exception:
                                pass
                
                # layout active workspace
                layout_workspace_windows(active_ws, work_rect, monitor_rect, self.gap_px)
            
            print_ascii_layout(self._monitors, self._focused_monitor)

    # -------------------------
    # Internal helpers
    # -------------------------

    def _populate_initial_windows(self):
        """
        Enumerate current top-level windows and assign them to the monitor's current workspace.
        """
        self._windows = {}
        
        hwnds = enumerate_top_level_windows()
        with self._lock:
            for hwnd in hwnds:
                mi = self._monitor_index_for_hwnd(hwnd)
                if mi is None:
                    mi = 0
                mon = self._monitors[mi]
                ws = mon.current_workspace()
                if not ws:
                    continue
                
                self.init_window(hwnd, mon, ws, True)
            
            # after initial population, apply layout
            self.refresh()

    def _monitor_index_for_hwnd(self, hwnd):
        try:
            hMonitor = win32api.MonitorFromWindow(hwnd, win32con.MONITOR_DEFAULTTONEAREST)
            for idx, info in enumerate(self._monitors_info):
                if info.hMonitor == hMonitor:
                    return idx
        except Exception:
            pass
        return None

    # These are called from the watcher thread
    def on_window_created(self, hwnd):
        "Add new window to the focused workspace of the monitor it belongs to."
        # Filter again for manageability
        try:
            if not is_manageable(hwnd):
                return
        except Exception:
            return
        
        with self._lock:
            # avoid duplicates
            if hwnd in self._windows:
                return
            
            mi = self._monitor_index_for_hwnd(hwnd)
            if mi is None:
                mi = 0
            mon = self._monitors[mi]
            ws = mon.current_workspace()
            if not ws:
                return
            
            self.init_window(hwnd, mon, ws)
            
            log.debug("Added window %s to monitor %d workspace %d", hwnd, mi, mon._focused_workspace)
            # Only the current monitor's active workspace should be visible; refresh that monitor's layout.
            self.refresh()

    def init_window(self, hwnd: int, mon: Monitor, ws: Workspace, initial: bool = False):
        title = ""
        try:
            title = win32gui.GetWindowText(hwnd)
        except Exception:
            pass
        
        rect = Rect(*win32gui.GetWindowRect(hwnd))
        winwin = WinWindow(id=hwnd, title=title, rect=rect)
        def cloak():
            with self._lock:
                print(f"Cloaking window {hwnd} ({title})")
                thumbnail = create_cloaking_thumbnail(hwnd, rect)
                winwin.thumbnail = thumbnail
        self._watcher.run_on_thread(cloak)
        win = Window(id=hwnd, data=winwin, workspace=ws)
        self._windows[hwnd] = win
        
        print(f"Adding window {hwnd} ({title}) to workspace {mon._focused_workspace}")
        ws.windows.append(win)
        mon.ensure_valid_workspaces()
        
        ws.layout_windows()

    def on_window_destroyed(self, hwnd):
        "Remove window from any workspace it belongs to."
        
        with self._lock:
            if hwnd not in self._windows:
                return
            win = self._windows.pop(hwnd)
            
            winwin = cast(WinWindow, win.data)
            if winwin.thumbnail:
                winwin.thumbnail.close()
            
            print(f"Removing window {hwnd}")
        
            for mon in self._monitors:
                changed = False
                for ws in mon.workspaces:
                    for i, w in enumerate(list(ws.windows)):
                        if w.id == hwnd:
                            ws.windows.pop(i)
                            ws.scroll_to_focus()
                            changed = True
                            break
                    if changed:
                        break
                if changed:
                    log.debug("Removed window %s", hwnd)
            
            # re-layout active workspaces
            self.refresh()

    def on_window_moved(self, hwnd):
        with self._lock:
            if hwnd in self._windows:
                try:
                    rect = win32gui.GetWindowRect(hwnd)
                except Exception:
                    title = ""
                    try:
                        title = win32gui.GetWindowText(hwnd)
                    except Exception:
                        pass
                    log_error(f"on_window_moved: failed to get rect for window {hwnd} ({title})")
                    return
                
                win = self._windows[hwnd]
                winwin = cast(WinWindow, win.data)
                print(f"moved {winwin.title}")
                
                # Clamp the thumbnail to the window's workspace's monitor
                if not win.workspace or not win.workspace.monitor:
                    log_error(f"on_window_moved: no workspace/monitor for window {hwnd}")
                    return
                
                win_pos = Rect(*rect)
                monitor_rect = win.workspace.monitor.rect
                mon_rect = monitor_rect
                source = mon_rect.intersection(win_pos)
                
                if not source:
                    return
                
                if winwin.thumbnail:
                    winwin.thumbnail.update(source.relative_to(win_pos), monitor_rect.clamp_pos(rect[0], rect[1]))

    def on_window_title_changed(self, hwnd):
        pass
    
    def on_window_minimized(self, hwnd):
        with self._lock:
            if hwnd in self._windows:
                win = self._windows[hwnd]
                winwin = cast(WinWindow, win.data)
                if winwin.thumbnail:
                    winwin.thumbnail.hide()
    def on_window_restored(self, hwnd):
        with self._lock:
            if hwnd in self._windows:
                win = self._windows[hwnd]
                winwin = cast(WinWindow, win.data)
                if winwin.thumbnail:
                    winwin.thumbnail.show()

    def on_foreground_changed(self, hwnd):
        print(f"Window {hwnd} reordered")
        # For now, just refresh layout
        with self._lock:
            if hwnd in self._windows:
                print(f"Fixing order for window {hwnd}")
                win = self._windows[hwnd]
                winwin = cast(WinWindow, win.data)
                if winwin.thumbnail:
                    winwin.thumbnail.fixorder()

    def stop(self):
        for window in self._windows.values():
            win = cast(WinWindow, window.data)
            if win.thumbnail:
                remove_cloaking_thumbnail(window.id, win.thumbnail)
        
        print("Cleanly stopped WindowsAdapter.")
        
        try:
            self._watcher.stop()
        except Exception:
            pass
