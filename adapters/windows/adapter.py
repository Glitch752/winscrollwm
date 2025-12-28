# adapters/windows/adapter.py
import threading
import logging
import win32gui
import win32con
import win32api

from adapters.base import Adapter
from core.models import Monitor, Workspace, Window
from adapters.windows.monitor_info import list_monitors
from adapters.windows.enumerate import enumerate_top_level_windows, is_manageable
from adapters.windows.layout import layout_workspace_windows
from adapters.windows.watch import WinEventWatcher

log = logging.getLogger(__name__)

DEFAULT_GAP_PX = 12

class WindowsAdapter(Adapter):
    _watcher: WinEventWatcher
    _windows: dict[int, Window]
    # I'm not sure what all we need to lock here, so we just lock everything...
    _lock: threading.RLock
    
    def __init__(self, gap_px: int = DEFAULT_GAP_PX):
        # monitor data: list of dicts {hMonitor, monitor, work}
        self._monitors_info = list_monitors()
        # Create Monitor objects (1 workspace each by default)
        self._monitors = [Monitor(workspaces=[Workspace()]) for _ in self._monitors_info]
        self._lock = threading.RLock()
        self.gap_px = gap_px

        # initial population
        self._populate_initial_windows()
        
        print(f"WindowsAdapter initialized with {len(self._monitors)} monitors:")
        # pretty print with some silly ascii art
        for i, mon in enumerate(self._monitors):
            print(f"Monitor {i}: {len(mon.workspaces)} workspaces")
            for j, ws in enumerate(mon.workspaces):
                print(f"> Workspace {j}: {len(ws.windows)} windows")
                for w in ws.windows:
                    title = ""
                    className = ""
                    try:
                        title = win32gui.GetWindowText(w.id)
                        className = win32gui.GetClassName(w.id)
                    except Exception:
                        pass
                    print(f"|  - Window {w.id} (width={w.width}) | {title} ({className})")

        # start the watcher
        self._watcher = WinEventWatcher(self)
        self._watcher.start()

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

    def resize_window(self, window):
        # Just re-run layout for the workspace which contains this window
        with self._lock:
            self.refresh()

    def refresh(self):
        """
        apply layout to the *active* workspace on each monitor.
        other workspaces' windows will be hidden.
        """
        with self._lock:
            for mi, mon in enumerate(self._monitors):
                work_rect = self._monitors_info[mi].work
                
                # ensure focused_workspace index safe
                if mon.focused_workspace >= len(mon.workspaces):
                    mon.focused_workspace = max(0, len(mon.workspaces) - 1)
                
                # hide all windows not in active workspace
                active_ws = mon.current_workspace()
                
                # first hide all windows in other workspaces
                for ws_i, ws in enumerate(mon.workspaces):
                    if ws_i != mon.focused_workspace:
                        for w in ws.windows:
                            try:
                                win32gui.ShowWindow(w.id, win32con.SW_HIDE)
                            except Exception:
                                pass
                
                # layout active workspace
                layout_workspace_windows(active_ws, work_rect, self.gap_px)

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
                
                win = Window(id=hwnd)
                ws.windows.append(win)
                self._windows[hwnd] = win
            
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
            mi = self._monitor_index_for_hwnd(hwnd)
            if mi is None:
                mi = 0
            mon = self._monitors[mi]
            ws = mon.current_workspace()
            # avoid duplicates
            if any(w.id == hwnd for w in ws.windows):
                return
            
            win = Window(id=hwnd)
            self._windows[hwnd] = win
            print(f"Adding window {hwnd} to monitor {mi} workspace {mon.focused_workspace}")
            ws.windows.append(win)
            
            log.debug("Added window %s to monitor %d workspace %d", hwnd, mi, mon.focused_workspace)
            # Only the current monitor's active workspace should be visible; refresh that monitor's layout.
            self.refresh()

    def on_window_destroyed(self, hwnd):
        "Remove window from any workspace it belongs to."
        
        with self._lock:
            if hwnd not in self._windows:
                return
            self._windows.pop(hwnd)
            
            print(f"Removing window {hwnd}")
        
            for mon in self._monitors:
                changed = False
                for ws in mon.workspaces:
                    for i, w in enumerate(list(ws.windows)):
                        if w.id == hwnd:
                            ws.windows.pop(i)
                            changed = True
                            break
                    if changed:
                        break
                if changed:
                    log.debug("Removed window %s", hwnd)
            
            # re-layout active workspaces
            self.refresh()

    def stop(self):
        try:
            self._watcher.stop()
        except Exception:
            pass
