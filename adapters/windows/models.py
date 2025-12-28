from dataclasses import dataclass
from typing import Tuple

class Rect(Tuple[int, int, int, int]):
    def __new__(cls, left: int, top: int, right: int, bottom: int):
        return super(Rect, cls).__new__(cls, (left, top, right, bottom))

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

@dataclass
class WinMonitor:
    hMonitor: int
    # (monitor_left, monitor_top, monitor_right, monitor_bottom)
    monitor: Rect
    # (work_left, work_top, work_right, work_bottom)
    work: Rect
    device: str
