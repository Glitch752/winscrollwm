# adapters/windows/adapter.py
import threading
import logging
from typing import cast
import win32gui
import win32con
import win32api

from adapters.base import Adapter
from adapters.windows.models import WinMonitor, WinWindow
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
        
        print(f"WindowsAdapter initialized with {len(self._monitors)} monitors:")
        # pretty print with some silly ascii art
        for i, mon in enumerate(self._monitors):
            print(f"Monitor {i}: {len(mon.workspaces)} workspaces | {self._monitors_info[i].device}")
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
        self.print_ascii_layout()
        
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
            # win32gui.SetForegroundWindow(hwnd)
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

    def refresh(self):
        """
        apply layout to the *active* workspace on each monitor.
        other workspaces' windows will be hidden.
        """
        with self._lock:
            for mi, mon in enumerate(self._monitors):
                work_rect = self._monitors_info[mi].work
                monitor_rect = self._monitors_info[mi].monitor
                
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
                layout_workspace_windows(active_ws, work_rect, monitor_rect, self.gap_px)
            
            self.print_ascii_layout()

    def print_ascii_layout(self):
        outer_buf = []
        def add_rect(text: str, title: str | None, buf: list[str], style: str, ansi_col: str | None = None):
            chars = {
                'ascii': [
                    '/-\\',
                    '| |',
                    '\\-/'
                ],
                'single': [
                    '┌─┐',
                    '│ │',
                    '└─┘'
                ],
                'double': [
                    '╔═╗',
                    '║ ║',
                    '╚═╝'
                ],
            }[style]
            
            title = f" {title} " if title else None
            
            def len_without_ansi(s: str) -> int:
                import re
                ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')
                return len(ansi_escape.sub('', s))
            def ansi_ljust(s: str, width: int) -> str:
                import re
                ansi_escape = re.compile(r'(\x1B\[[0-?]*[ -/]*[@-~])')
                parts = ansi_escape.split(s)
                visible_length = sum(len(part) for i, part in enumerate(parts) if i % 2 == 0)
                padding = width - visible_length
                if padding > 0:
                    return s + ' ' * padding
                return s
            
            lines = text.splitlines()
            max_line_length = max(len_without_ansi(line) for line in lines) if lines else 0
            
            height = len(lines) + 2
            length = max(max_line_length + 4, len(title) + 4 if title else 0)
            
            if not buf:
                buf.append("")
            while len(buf) < height:
                buf.append(" " * len(buf[0]))
            
            if len(buf[0]) > 0:
                for i in range(len(buf)):
                    buf[i] += " "
            
            ansi_set = ansi_col or ""
            ansi_reset = "\033[0m" if ansi_col else ""
            
            # Header
            if title:
                buf[0] += f"{ansi_set}{chars[0][0]}{chars[0][1]}{title.center(length - 4, chars[0][1])}{chars[0][1]}{chars[0][2]}{ansi_reset}"
            else:
                buf[0] += f"{ansi_set}{chars[0][0]}{chars[0][1] * (length - 2)}{chars[0][2]}{ansi_reset}"
            
            # Content
            for i in range(1, height - 1):
                buf[i] += f"{ansi_set}{chars[1][0]}{ansi_reset} {ansi_ljust(lines[i - 1], length - 4)} {ansi_set}{chars[1][2]}{ansi_reset}"
            
            # Footer
            buf[height - 1] += f"{ansi_set}{chars[2][0]}{chars[2][1] * (length - 2)}{chars[2][2]}{ansi_reset}"
            
            # Pad buf to height
            if len(buf) > height:
                for i in range(height, len(buf)):
                    buf[i] += " " * length
        
        for mi, mon in enumerate(self._monitors):
            monitor_buf = []
            
            for wsi, ws in enumerate(mon.workspaces):
                ws_buf = []
                for wi, win in enumerate(ws.windows):
                    name = ""
                    win_class = ""
                    try:
                        name = win32gui.GetWindowText(win.id)
                        win_class = win32gui.GetClassName(win.id) or ""
                    except Exception:
                        pass
                    if len(name) > 50:
                        name = name[:47] + "..."
                    if len(win_class) > 50:
                        win_class = win_class[:47] + "..."
                    add_rect(f"{name}\n{win_class}", f"Win {win.id}", ws_buf, 'double' if win == ws.focused_window() else 'single', '\033[92m' if win.id == ws._focused_id else None)
                
                add_rect("\n".join(ws_buf), f"Workspace {wsi}", monitor_buf, 'single', '\033[94m' if wsi == mon.focused_workspace else None)
            
            add_rect("\n".join(monitor_buf), f"Monitor {mi} (ws {mon.focused_workspace})", outer_buf, 'double', '\033[96m' if mi == self._focused_monitor else None)
        
        # Clear screen
        # print("\033[2J\033[H")
        print("\n" * 2)
        print("\n".join(outer_buf))

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
            
            self.init_window(hwnd, mon, ws)
            
            log.debug("Added window %s to monitor %d workspace %d", hwnd, mi, mon.focused_workspace)
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
        
        print(f"Adding window {hwnd} ({title}) to workspace {mon.focused_workspace}")
        ws.windows.append(win)

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
