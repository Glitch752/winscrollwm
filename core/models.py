from dataclasses import dataclass, field
from typing import List

@dataclass
class Window:
    id: int
    width: float = 1.0

@dataclass
class Workspace:
    windows: List[Window] = field(default_factory=list)
    focused_index: int = 0

    def focused_window(self):
        if not self.windows:
            return None
        return self.windows[self.focused_index]

@dataclass
class Monitor:
    workspaces: List[Workspace] = field(default_factory=lambda: [Workspace()])
    focused_workspace: int = 0

    def current_workspace(self):
        return self.workspaces[self.focused_workspace]
