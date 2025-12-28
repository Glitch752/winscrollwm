import asyncio
from time import time
import win32api
import win32gui
from adapters.base import Adapter
from core.models import Monitor
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

    def move_workspace_focus(self, delta):
        m = self.current_monitor()
        m.focused_workspace = max(
            0, min(m.focused_workspace + delta, len(m.workspaces) - 1)
        )
        self.adapter.refresh()

    def move_workspace_to_monitor(self, delta: int):
        src = self.current_monitor()
        dst_index = self.focused_monitor + delta
        if not (0 <= dst_index < len(self.monitors)):
            return

        ws = src.workspaces.pop(src.focused_workspace)
        dst = self.monitors[dst_index]
        dst.workspaces.append(ws)
        ws.monitor = dst
        
        self.focused_monitor = dst_index
        self.adapter.refresh()

    def resize_window(self, delta):
        ws = self.current_monitor().current_workspace()
        win = ws.focused_window()
        if not win:
            return
        win.width = max(0.1, win.width + delta)
        ws.layout_windows()
        self.adapter.resize_window(win)

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

    def exit(self):
        self.running = False
