from adapters.base import Adapter
from core.models import Monitor

class WindowManager:
    def __init__(self, adapter: Adapter):
        self.adapter = adapter
        self.monitors = adapter.get_monitors()
        self.focused_monitor = 0
        self.running = True

    def current_monitor(self) -> Monitor:
        return self.monitors[self.focused_monitor]

    def move_focus_horizontal(self, delta):
        ws = self.current_monitor().current_workspace()
        if not ws.windows:
            return
        ws.focused_index = max(
            0, min(ws.focused_index + delta, len(ws.windows) - 1)
        )
        self.adapter.focus_window(ws.focused_window())

    def move_workspace_vertical(self, delta):
        m = self.current_monitor()
        m.focused_workspace = max(
            0, min(m.focused_workspace + delta, len(m.workspaces) - 1)
        )
        self.adapter.refresh()

    def move_workspace_to_monitor(self, delta):
        src = self.current_monitor()
        dst_index = self.focused_monitor + delta
        if not (0 <= dst_index < len(self.monitors)):
            return

        ws = src.workspaces.pop(src.focused_workspace)
        dst = self.monitors[dst_index]
        dst.workspaces.append(ws)
        self.focused_monitor = dst_index
        self.adapter.refresh()

    def resize_window(self, delta):
        ws = self.current_monitor().current_workspace()
        win = ws.focused_window()
        if not win:
            return
        win.width = max(0.1, win.width + delta)
        self.adapter.resize_window(win)

    def exit(self):
        self.running = False
