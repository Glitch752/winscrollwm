from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple

WindowID = int

@dataclass
class Window:
    id: WindowID
    workspace: Optional["Workspace"] = None
    
    data: Any = None
    
    # in screen-widths
    x: float = 0.0
    # in screen-widths
    width: float = 1.0

WorkspaceID = int
workspace_id_autoinc: WorkspaceID = 0
def _get_next_workspace_id() -> WorkspaceID:
    global workspace_id_autoinc
    workspace_id_autoinc += 1
    return workspace_id_autoinc

class Workspace:
    id: WorkspaceID
    windows: List[Window]
    monitor: Optional["Monitor"] = None
    _focused_id: Optional[WindowID] = None
    scroll_offset: float = 0.0
    
    def __init__(self, windows: Optional[List[Window]] = None):
        self.id = _get_next_workspace_id()
        
        self.windows = windows if windows is not None else []
        for win in self.windows:
            win.workspace = self

    def focused_window(self):
        if not self._focused_id and len(self.windows) > 0:
            self._focused_id = self.windows[0].id
        
        if not self.windows:
            return None
        return next((w for w in self.windows if w.id == self._focused_id), self.windows[0])
    
    def layout_windows(self):
        x = 0
        for win in self.windows:
            win.x = x
            x += win.width
        
        self.scroll_to_focus()
    
    def focus_position(self, position: int):
        if not self.windows:
            self._focused_id = None
            return
        if position < 0:
            position = len(self.windows) + position
        position = max(0, min(position, len(self.windows) - 1))
        self._focused_id = self.windows[position].id
        
        self.layout_windows()
        self.scroll_to_focus()
        
        print(f"Workspace focus_position: focused_id={self._focused_id}")
    
    def move_focus(self, delta: int):
        if not self.windows:
            self._focused_id = None
            return
        if not self._focused_id:
            self._focused_id = self.windows[0].id
            return

        indices = {w.id: i for i, w in enumerate(self.windows)}
        current_index = indices.get(self._focused_id, 0)
        new_index = max(0, min(current_index + delta, len(self.windows) - 1))
        self._focused_id = self.windows[new_index].id
        
        self.layout_windows()
        self.scroll_to_focus()
        
        print(f"Workspace move_focus: {current_index} -> {new_index} / {len(self.windows)}, focused_id={self._focused_id}")
    
    def scroll_to_focus(self):
        # If the total width of windows is less than a screen, center them
        total_width = sum(win.width for win in self.windows)
        if total_width <= 1.0:
            self.scroll_offset = (total_width - 1.0) / 2.0
            return
        else:
            # If the scroll offset is out of bounds, clamp it
            max_offset = total_width - 1.0
            self.scroll_offset = max(0.0, min(self.scroll_offset, max_offset))
        
        # Make sure the focused window is visible in the scroll offset
        focused_win = self.focused_window()
        
        if not focused_win:
            return
        
        win_start = focused_win.x
        win_end = focused_win.x + focused_win.width
        if win_start < self.scroll_offset:
            self.scroll_offset = win_start
        elif win_end > self.scroll_offset + 1.0:
            self.scroll_offset = win_end - 1.0

class Rect(Tuple[int, int, int, int]):
    ZERO: "Rect" = None  # type: ignore
    
    def __new__(cls, left: int, top: int, right: int, bottom: int):
        return super(Rect, cls).__new__(cls, (left, top, right, bottom))

    def sized(self) -> Tuple[int, int, int, int]:
        return (self.left(), self.top(), self.width(), self.height())

    def left(self) -> int:
        return self[0]
    def top(self) -> int:
        return self[1]
    def right(self) -> int:
        return self[2]
    def bottom(self) -> int:
        return self[3]
    
    def width(self) -> int:
        return abs(self.right() - self.left())
    def height(self) -> int:
        return abs(self.bottom() - self.top())
    
    def contains(self, x: int, y: int) -> bool:
        return self.left() <= x < self.right() and self.top() <= y < self.bottom()
    def clamp_pos(self, x: int, y: int) -> Tuple[int, int]:
        clamped_x = max(self.left(), min(x, self.right() - 1))
        clamped_y = max(self.top(), min(y, self.bottom() - 1))
        return (clamped_x, clamped_y)
    
    def intersects(self, other: "Rect") -> bool:
        "Check if this rectangle partially overlaps with another"
        return not (self.right() <= other.left() or self.left() >= other.right() or
                    self.bottom() <= other.top() or self.top() >= other.bottom())  
    def intersection(self, other: "Rect") -> Optional["Rect"]:
        if not self.intersects(other):
            return None
        return Rect(
            max(self.left(), other.left()),
            max(self.top(), other.top()),
            min(self.right(), other.right()),
            min(self.bottom(), other.bottom())
        )
    
    def contains_rect(self, other: "Rect") -> bool:
        return (self.left() <= other.left() and self.right() >= other.right() and
                self.top() <= other.top() and self.bottom() >= other.bottom())
    def relative_to(self, other: "Rect") -> "Rect":
        return Rect(
            self.left() - other.left(),
            self.top() - other.top(),
            self.right() - other.left(),
            self.bottom() - other.top()
        )
Rect.ZERO = Rect(0, 0, 0, 0)

class Monitor:
    workspaces: List[Workspace]
    rect: Rect = Rect.ZERO
    _focused_workspace: WorkspaceID
    
    def __init__(self, workspaces: Optional[List[Workspace]] = None, rect: Optional[Rect] = None):
        self.workspaces = workspaces if workspaces is not None else []
        for ws in self.workspaces:
            ws.monitor = self
        
        if rect is not None:
            self.rect = rect
        
        self._focused_workspace = self.workspaces[0].id if self.workspaces else -1
    
    def contains_point(self, x: int, y: int) -> bool:
        return self.rect.contains(x, y)

    def current_workspace(self):
        for ws in self.workspaces:
            if ws.id == self._focused_workspace:
                return ws
        if self.workspaces:
            self._focused_workspace = self.workspaces[0].id
            return self.workspaces[0]
        
        self.workspaces.append(Workspace())
        return self.workspaces[0]
    
    def ensure_valid_workspaces(self):
        # Ensure at least one workspace
        if not self.workspaces:
            self.workspaces.append(Workspace())
        
        # Ensure focused workspace is valid
        if not any(ws.id == self._focused_workspace for ws in self.workspaces):
            self._focused_workspace = self.workspaces[0].id
        
        # Ensure there is a free workspace at the top and bottom
        if self.workspaces[0].windows:
            self.workspaces.insert(0, Workspace())
        if self.workspaces[-1].windows:
            self.workspaces.append(Workspace())