import asyncio
from time import time
import win32api
import win32gui
from adapters.base import Adapter
from core.models import Monitor, Workspace
import signal

class WindowManager:
    adapter: Adapter
    monitors: list[Monitor]
    focused_monitor: int
    running: bool
    
    def __init__(self, adapter: Adapter):
        self.adapter = adapter
        self.monitors = adapter.get_monitors()
        self.focused_monitor = 0
        self.running = True
        
        self.update_workspaces()
        
        # Focus the first window on startup
        first_mon = self.current_monitor()
        first_ws = first_mon.current_workspace()
        first_win = first_ws.focused_window()
        if first_win:
            self.adapter.focus_window(first_win)
    
    async def run(self):
        await self.adapter.initialize()
        
        # Intercept termination signals and stop running cleanly
        signal.signal(signal.SIGINT, lambda s, f: self.exit())
        signal.signal(signal.SIGTERM, lambda s, f: self.exit())
        
        while self.running:
            self.check_mouse_move()

            await asyncio.sleep(0.05)
        
        self.adapter.stop()

    def current_monitor(self) -> Monitor:
        return self.monitors[self.focused_monitor]

    ####################################
    ### Focus changes
    ####################################

    def move_focus_horizontal(self, delta):
        ws = self.current_monitor().current_workspace()
        if not ws.windows:
            return
        prev_focus = ws._focused_id
        
        ws.move_focus(delta)
        
        if ws._focused_id != prev_focus:
            focused = ws.focused_window()
            if focused:
                self.adapter.focus_window(focused)

    def focus_position(self, position: int):
        ws = self.current_monitor().current_workspace()
        if not ws.windows:
            return

        prev_focus = ws._focused_id
        
        ws.focus_position(position)
        
        if ws._focused_id != prev_focus:
            focused = ws.focused_window()
            if focused:
                self.adapter.focus_window(focused)        
    
    def move_workspace_focus(self, delta):
        m = self.current_monitor()
        prev_focus = m._focused_workspace
        ws = m.current_workspace()
        target_index = m.workspaces.index(ws) + delta
        if target_index < 0 or target_index >= len(m.workspaces):
            return
        m._focused_workspace = m.workspaces[target_index].id
        if m._focused_workspace != prev_focus:
            focused_ws = m.current_workspace()
            if not focused_ws:
                return
            focused_win = focused_ws.focused_window()
            if focused_win:
                self.adapter.focus_window(focused_win)
        
            self.adapter.refresh()

    def move_monitor_focus(self, delta):
        target_index = self.focused_monitor + delta
        if target_index < 0 or target_index >= len(self.monitors):
            return
        self.focused_monitor = target_index
        
        focused_ws = self.current_monitor().current_workspace()
        focused_win = focused_ws.focused_window()
        if focused_win:
            self.adapter.focus_window(focused_win)

    ####################################
    ### Window/workspace manipulation
    ####################################

    def resize_window(self, delta):
        ws = self.current_monitor().current_workspace()
        win = ws.focused_window()
        if not win:
            return
        win.width = max(0.1, win.width + delta)
        ws.layout_windows()
        self.adapter.resize_window(win)

    def toggle_maximize_focused_window(self):
        ws = self.current_monitor().current_workspace()
        win = ws.focused_window()
        if not win:
            return
        if win.width < 0.99:
            win.width = 1.0
        else:
            win.width = 0.5
        ws.layout_windows()
        self.adapter.resize_window(win)
    
    def toggle_preset_width_focused_window(self):
        preset_widths = [0.4, 0.5, 0.6, 1.0]
        ws = self.current_monitor().current_workspace()
        win = ws.focused_window()
        if not win:
            return
        try:
            current_index = preset_widths.index(round(win.width, 2))
            new_index = (current_index + 1) % len(preset_widths)
        except ValueError:
            new_index = 0
        win.width = preset_widths[new_index]
        ws.layout_windows()
        self.adapter.resize_window(win)
        
        self.update_workspaces()
    
    def move_window_horizontal(self, delta):
        ws = self.current_monitor().current_workspace()
        win = ws.focused_window()
        if not win:
            return
        indices = {w.id: i for i, w in enumerate(ws.windows)}
        current_index = indices.get(win.id, 0)
        new_index = max(0, min(current_index + delta, len(ws.windows) - 1))
        if new_index == current_index:
            return
        ws.windows.pop(current_index)
        ws.windows.insert(new_index, win)
        ws.layout_windows()
        self.adapter.refresh()
    
    def move_window_vertical(self, delta):
        "Move the window between workspaces on the current monitor"
        current_mon = self.current_monitor()
        ws = current_mon.current_workspace()
        win = ws.focused_window()
        if not win:
            return
        target_ws_index = current_mon.workspaces.index(ws) + delta
        if target_ws_index < 0 or target_ws_index >= len(current_mon.workspaces):
            return
        target_ws = current_mon.workspaces[target_ws_index]
        # Remove from current workspace
        ws.windows.remove(win)
        ws.layout_windows()
        # Add to target workspace
        target_ws.windows.append(win)
        win.workspace = target_ws
        target_ws.layout_windows()
        # Focus the moved window
        target_ws._focused_id = win.id
        # Focus the target workspace
        current_mon._focused_workspace = target_ws.id
        
        self.adapter.focus_window(win)
        
        self.update_workspaces()

    def move_window_to_position(self, position: int):
        ws = self.current_monitor().current_workspace()
        win = ws.focused_window()
        if not win:
            return
        indices = {w.id: i for i, w in enumerate(ws.windows)}
        current_index = indices.get(win.id, 0)
        if position < 0:
            position = len(ws.windows) + position
        position = max(0, min(position, len(ws.windows) - 1))
        if position == current_index:
            return
        ws.windows.pop(current_index)
        ws.windows.insert(position, win)
        ws.layout_windows()
        self.adapter.refresh()
    
    def move_window_to_monitor(self, delta: int):
        current_mon = self.current_monitor()
        ws = current_mon.current_workspace()
        win = ws.focused_window()
        if not win:
            return
        
        target_mon_index = self.focused_monitor + delta
        if target_mon_index < 0 or target_mon_index >= len(self.monitors):
            return
        target_mon = self.monitors[target_mon_index]
        target_ws = target_mon.current_workspace()
        
        # Remove from current workspace
        ws.windows.remove(win)
        ws.layout_windows()
        
        # Add to target workspace
        target_ws.windows.append(win)
        win.workspace = target_ws
        target_ws.layout_windows()
        
        # Update focused monitor
        self.focused_monitor = target_mon_index
        
        # Focus the moved window
        target_ws._focused_id = win.id
        self.adapter.focus_window(win)
        
        self.update_workspaces()
    
    def update_workspaces(self):
        "Makes sure that every monitor has at least one workspace and there are free workspaces on the top and bottom of each monitor with windows."
        for mon in self.monitors:
            mon.ensure_valid_workspaces()
    
    ####################################
    ### Other interactions
    ####################################

    def close_focused_window(self):
        ws = self.current_monitor().current_workspace()
        if not ws:
            return
        
        win = ws.focused_window()
        if not win:
            return
        self.adapter.close_window(win)

    def mouse_move(self, pos: list[float]):
        for i, mon in enumerate(self.monitors):
            if mon.contains_point(int(pos[0]), int(pos[1])):
                if i == self.focused_monitor:
                    break
                self.focused_monitor = i
                
                win = mon.current_workspace().focused_window()
                if win:
                    self.adapter.focus_window(win)
    
    last_mouse_pos: tuple[int, int] | None = None
    def check_mouse_move(self):
        x, y = win32api.GetCursorPos()
        if self.last_mouse_pos != (x, y):
            self.last_mouse_pos = (x, y)
            self.mouse_move([x, y])

    def exit(self, restart: bool = False):
        self.running = False
        
        if restart:
            # Open a new process after a short delay
            import subprocess
            import sys
            subprocess.Popen(["powershell", "-Command", "Start-Sleep -Seconds 1; python " + " ".join(sys.argv)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
                creationflags=subprocess.DETACHED_PROCESS)
